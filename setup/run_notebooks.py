#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     # Notebook execution
#     "nbconvert>=7.16",
#     "nbformat>=5.10",
#     "ipykernel>=6.29",
#     # What the labs need beyond the shared package. boto3, neo4j,
#     # neo4j-graphrag, and python-dotenv are deliberately absent: `workshop`
#     # declares all four, and restating them here is how the runner's pins
#     # drift out of step with the package's.
#     "strands-agents>=1.27.0,<2.0.0",
#     "numpy>=1.24.0",
#     "pyyaml>=6.0",
#     "bedrock-agentcore-starter-toolkit",
#     # Lab 6 (Neo4j graph memory; the notebook self-skips when unconfigured)
#     "neo4j-agent-memory[bedrock]==0.5.0",
#     # The modules more than one lab shares. Every notebook imports from it, so
#     # the runner's environment needs it the same way a lab's .venv does.
#     "workshop",
# ]
#
# [tool.uv.sources]
# workshop = { path = "../workshop", editable = true }
# ///
"""Execute the workshop notebooks without modifying their source files.

The default run covers labs 1 through 4 and lab 6. Lab 5 deploys and tears
down real AWS resources, so both of its gates are opt-in. Lab 0 is a
credential checklist in a README and has no notebook.

Usage:
    uv run setup/run_notebooks.py
    uv run setup/run_notebooks.py --labs 1
    uv run setup/run_notebooks.py --labs 1-4
    uv run setup/run_notebooks.py --labs 6
    uv run setup/run_notebooks.py --labs 5 --include-deploy
    uv run setup/run_notebooks.py --labs 5 --include-cleanup
    uv run setup/run_notebooks.py --allow-writes
    uv run setup/run_notebooks.py --keep-output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "setup" / "notebook-output"
KERNEL_NAME = "hallucinations-workshop"
RUNNER_MARKER = "WORKSHOP_RUNNER"

_INSTALL_MAGIC = re.compile(r"^(\s*)[%!]\s*(pip|pip3|conda|uv)\b")


@dataclass(frozen=True)
class Notebook:
    """A notebook included in the workshop test run."""

    lab: str
    path: Path
    deploys_resources: bool = False
    deletes_resources: bool = False


@dataclass(frozen=True)
class Result:
    """The outcome of one notebook execution."""

    notebook: Notebook
    status: str
    reason: str = ""
    detail: str = ""


#: Every lab is registered here up front, including notebooks that are still
#: being authored. A registered path that does not exist yet is reported as a
#: skip with a clear reason and does not affect the exit code, so each lab can
#: fill in its own entry without every author editing this tuple.
#:
#: Lab 0 is a credential checklist in a README rather than a notebook, so it
#: has no entry.
NOTEBOOKS = (
    Notebook(
        "1",
        REPO_ROOT / "01-graph-build" / "1.1_build_graph.ipynb",
    ),
    Notebook(
        "2",
        REPO_ROOT / "02-retrieval" / "2.1_vector_retrievers.ipynb",
    ),
    Notebook(
        "2",
        REPO_ROOT / "02-retrieval" / "2.2_fulltext_retrievers.ipynb",
    ),
    Notebook(
        "2",
        REPO_ROOT / "02-retrieval" / "2.3_text2cypher.ipynb",
    ),
    Notebook(
        "3",
        REPO_ROOT / "03-agents-and-tools" / "3.1_strands_primer.ipynb",
    ),
    Notebook(
        "4",
        REPO_ROOT / "04-grounded-write" / "4.1_reservation_write.ipynb",
    ),
    Notebook(
        "5",
        REPO_ROOT / "05-agentcore-deploy" / "5.1_agentcore_deploy.ipynb",
        deploys_resources=True,
    ),
    # 5.3 is registered ahead of 5.2 on purpose. Registry order is run order,
    # and 5.2 deletes the Runtime that 5.3 invokes, so the documented
    # `--include-deploy --include-cleanup` pair would otherwise tear the
    # Runtime down and then walk through a deleted ARN. Anything that deletes
    # resources belongs last within its lab.
    Notebook(
        "5",
        REPO_ROOT / "05-agentcore-deploy" / "5.3_agentcore_walkthrough.ipynb",
        deploys_resources=True,
    ),
    Notebook(
        "5",
        REPO_ROOT / "05-agentcore-deploy" / "5.2_teardown.ipynb",
        deletes_resources=True,
    ),
    Notebook(
        "6",
        REPO_ROOT / "06-memory" / "6.1_neo4j_agent_memory.ipynb",
    ),
)

KNOWN_LABS = tuple(notebook.lab for notebook in NOTEBOOKS)


def parse_labs(spec: str | None) -> set[str]:
    """Parse one lab, a comma-separated list, or a numeric range."""
    if spec is None:
        return set(KNOWN_LABS)

    selected: set[str] = set()
    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            continue

        if re.fullmatch(r"\d+-\d+", token):
            start, end = (int(value) for value in token.split("-"))
            if start > end:
                raise ValueError(f"invalid range '{token}': start exceeds end")
            selected.update(str(value) for value in range(start, end + 1))
        elif token.isdigit():
            selected.add(str(int(token)))
        else:
            raise ValueError(f"invalid lab '{token}'")

    unknown = selected.difference(KNOWN_LABS)
    if unknown:
        values = ", ".join(sorted(unknown, key=int))
        raise ValueError(f"unknown lab(s): {values}")
    if not selected:
        raise ValueError("no labs selected")
    return selected


def neutralize_install_magics(notebook: Any) -> int:
    """Disable package installation magics in an in-memory notebook copy."""
    count = 0
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue

        lines = []
        for line in cell.source.splitlines(keepends=True):
            match = _INSTALL_MAGIC.match(line)
            if match is None:
                lines.append(line)
                continue

            newline = "\n" if line.endswith("\n") else ""
            lines.append(
                f"{match.group(1)}# [run_notebooks] disabled: "
                f"{line.strip()}{newline}"
            )
            count += 1
        cell.source = "".join(lines)
    return count


@contextmanager
def temporary_kernel(work_dir: Path) -> Iterator[None]:
    """Expose the runner's Python environment as a temporary Jupyter kernel."""
    kernel_dir = work_dir / "kernels" / KERNEL_NAME
    kernel_dir.mkdir(parents=True)
    kernel = {
        "argv": [
            sys.executable,
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
        ],
        "display_name": "Hallucinations Workshop Runner",
        "language": "python",
    }
    (kernel_dir / "kernel.json").write_text(
        json.dumps(kernel),
        encoding="utf-8",
    )

    previous_path = os.environ.get("JUPYTER_PATH")
    paths = [str(work_dir)]
    if previous_path:
        paths.append(previous_path)
    os.environ["JUPYTER_PATH"] = os.pathsep.join(paths)

    try:
        yield
    finally:
        if previous_path is None:
            os.environ.pop("JUPYTER_PATH", None)
        else:
            os.environ["JUPYTER_PATH"] = previous_path


@contextmanager
def runner_environment(allow_writes: bool) -> Iterator[None]:
    """Mark runner kernels as write-safe unless writes were explicitly allowed."""
    previous_marker = os.environ.get(RUNNER_MARKER)
    if allow_writes:
        os.environ.pop(RUNNER_MARKER, None)
    else:
        os.environ[RUNNER_MARKER] = "1"

    try:
        yield
    finally:
        if previous_marker is None:
            os.environ.pop(RUNNER_MARKER, None)
        else:
            os.environ[RUNNER_MARKER] = previous_marker


def output_path(output_dir: Path, notebook: Notebook) -> Path:
    """Return an output path that preserves the source lab directory."""
    lab_dir = output_dir / notebook.path.parent.name
    lab_dir.mkdir(parents=True, exist_ok=True)
    return lab_dir / f"{notebook.path.stem}-executed.ipynb"


def cell_preview(cell: Any, limit: int = 100) -> str:
    """Return a compact description of a notebook cell."""
    first_line = next(
        (line.strip() for line in cell.source.splitlines() if line.strip()),
        "<empty cell>",
    )
    if len(first_line) <= limit:
        return first_line
    return f"{first_line[: limit - 3]}..."


def print_cell_outputs(cell: Any) -> None:
    """Print text captured by a completed notebook cell."""
    for output in cell.get("outputs", []):
        output_type = output.get("output_type")
        if output_type == "stream":
            text = output.get("text", "")
        elif output_type in {"display_data", "execute_result"}:
            text = output.get("data", {}).get("text/plain", "")
        elif output_type == "error":
            text = "\n".join(output.get("traceback", []))
        else:
            continue

        for line in str(text).rstrip().splitlines():
            print(f"    {line}", flush=True)


def run_notebook(
    notebook: Notebook,
    output_dir: Path,
    timeout: int,
) -> Result:
    """Execute one notebook and save its output away from the source file."""
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    relative_path = notebook.path.relative_to(REPO_ROOT)
    print(f"\nRunning {relative_path}", flush=True)

    document = None
    try:
        document = nbformat.read(notebook.path, as_version=4)
        disabled = neutralize_install_magics(document)
        if disabled:
            print(
                f"  Disabled {disabled} package-install line(s)",
                flush=True,
            )

        code_cell_indices = [
            index
            for index, cell in enumerate(document.cells)
            if cell.cell_type == "code" and cell.source.strip()
        ]
        cell_positions = {
            index: position
            for position, index in enumerate(code_cell_indices, start=1)
        }
        started_at: dict[int, float] = {}

        def on_cell_execute(*, cell: Any, cell_index: int) -> None:
            position = cell_positions[cell_index]
            started_at[cell_index] = time.monotonic()
            print(
                f"  Cell {position}/{len(code_cell_indices)} started: "
                f"{cell_preview(cell)}",
                flush=True,
            )

        def on_cell_executed(
            *,
            cell: Any,
            cell_index: int,
            execute_reply: Any,
        ) -> None:
            position = cell_positions[cell_index]
            elapsed = time.monotonic() - started_at[cell_index]
            status = execute_reply.get("content", {}).get("status", "ok")
            print(
                f"  Cell {position}/{len(code_cell_indices)} "
                f"{status} in {elapsed:.1f}s",
                flush=True,
            )
            print_cell_outputs(cell)

        executor = ExecutePreprocessor(
            timeout=timeout,
            kernel_name=KERNEL_NAME,
            allow_errors=False,
            on_cell_execute=on_cell_execute,
            on_cell_executed=on_cell_executed,
        )
        executor.preprocess(
            document,
            {"metadata": {"path": str(notebook.path.parent)}},
        )
        nbformat.write(document, output_path(output_dir, notebook))
    except Exception as exc:  # Report the failed notebook and continue the run.
        if document is not None:
            nbformat.write(document, output_path(output_dir, notebook))
        detail = traceback.format_exc()
        message = next(
            (line.strip() for line in str(exc).splitlines() if line.strip()),
            "execution failed",
        )
        reason = f"{type(exc).__name__}: {message}"
        return Result(notebook, "FAIL", reason=reason, detail=detail)

    return Result(notebook, "PASS")


def select_notebooks(
    labs: set[str],
    include_deploy: bool,
    include_cleanup: bool,
) -> list[tuple[Notebook, str | None]]:
    """Select notebooks and record why unsafe or missing ones are skipped."""
    selected = []
    for notebook in NOTEBOOKS:
        if notebook.lab not in labs:
            continue

        reason = None
        if notebook.deploys_resources and not include_deploy:
            reason = "deploys AWS resources; pass --include-deploy"
        elif notebook.deletes_resources and not include_cleanup:
            reason = "deletes AWS resources; pass --include-cleanup"
        elif not notebook.path.exists():
            reason = "notebook file not found"
        selected.append((notebook, reason))
    return selected


def print_notebooks() -> None:
    """Print the notebook registry without executing it."""
    for notebook in NOTEBOOKS:
        labels = []
        if notebook.deploys_resources:
            labels.append("deploy")
        if notebook.deletes_resources:
            labels.append("cleanup")
        suffix = f" ({', '.join(labels)})" if labels else ""
        path = notebook.path.relative_to(REPO_ROOT)
        print(f"{notebook.lab}: {path}{suffix}")


def print_summary(results: list[Result], kept_output: Path | None) -> None:
    """Print a compact result table and failure details."""
    print("\nResults")
    print("=" * 72)
    for result in results:
        path = result.notebook.path.relative_to(REPO_ROOT)
        suffix = f" ({result.reason})" if result.reason else ""
        print(f"{result.status:<4}  {path}{suffix}")

    passed = sum(result.status == "PASS" for result in results)
    failed = sum(result.status == "FAIL" for result in results)
    skipped = sum(result.status == "SKIP" for result in results)
    print(
        f"\nPassed: {passed}  Failed: {failed}  "
        f"Skipped: {skipped}  Total: {len(results)}"
    )

    for result in results:
        if result.status == "FAIL":
            path = result.notebook.path.relative_to(REPO_ROOT)
            print(f"\nFailure: {path}\n{result.detail.rstrip()}")

    if kept_output is not None:
        print(f"\nExecuted notebooks: {kept_output}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--labs",
        help="Labs to run: '4', '1,3,4', or '1-4'. Default: all.",
    )
    parser.add_argument(
        "--include-deploy",
        action="store_true",
        help="Run lab 5's deploy notebooks, which create AWS resources.",
    )
    parser.add_argument(
        "--include-cleanup",
        action="store_true",
        help="Run lab 5's teardown, which deletes tagged AWS resources.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-cell timeout in seconds (default: 1800).",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep executed notebooks under setup/notebook-output/.",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help=(
            "Allow Lab 4 reservation and Lab 6 memory writes. By default, "
            "their write scenarios execute as explicit skips."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered notebooks and exit.",
    )
    return parser


def main() -> int:
    """Run the selected notebooks and return a shell-compatible status."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        print_notebooks()
        return 0
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        labs = parse_labs(args.labs)
    except ValueError as exc:
        parser.error(str(exc))

    plan = select_notebooks(
        labs,
        include_deploy=args.include_deploy,
        include_cleanup=args.include_cleanup,
    )

    with tempfile.TemporaryDirectory(prefix="run_notebooks_") as temp_dir:
        work_dir = Path(temp_dir)
        kept_output = None
        if args.keep_output:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            kept_output = OUTPUT_ROOT / f"{timestamp}-{os.getpid()}"
            kept_output.mkdir(parents=True)
            result_dir = kept_output
        else:
            result_dir = work_dir / "output"

        results = []
        with runner_environment(args.allow_writes):
            with temporary_kernel(work_dir):
                for notebook, skip_reason in plan:
                    if skip_reason is not None:
                        path = notebook.path.relative_to(REPO_ROOT)
                        print(f"\nSkipping {path}: {skip_reason}")
                        results.append(
                            Result(notebook, "SKIP", reason=skip_reason)
                        )
                        continue
                    results.append(
                        run_notebook(notebook, result_dir, args.timeout)
                    )

        print_summary(results, kept_output)
        return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
