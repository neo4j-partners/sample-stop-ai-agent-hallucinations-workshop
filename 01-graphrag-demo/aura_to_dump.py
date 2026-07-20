#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Back up an Aura graph into a workshop-compatible neo4j-admin dump.

Pipeline (all Bolt / neo4j-cli, no Aura admin access required):

    1. Export the Aura graph over Bolt with apoc.export.cypher.all (stream mode).
    2. Spin up a local Community Neo4j via `neo4j-cli docker` and replay the Cypher.
    3. Verify node / relationship counts match the source.
    4. Stop the container and run `neo4j-admin database dump` against its data dir,
       producing a native .dump the workshop's central-neo4j.yaml can load.

Requires `neo4j-cli` and a running Docker daemon on PATH.

Example:
    ./aura_to_dump.py --env ./.env --out ./neo4j-hotel-graph.dump
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV = Path(__file__).with_name(".env")
SOURCE_DB_FALLBACK = "neo4j"
LOCAL_DB = "neo4j"  # Community edition is single-database.
CONTAINER_NAME = "aura-backup-local"

# Match static/cfn/central-neo4j.yaml, which loads the dump with
# neo4j:<version>-community. A dump only loads into an equal-or-newer
# Neo4j, so dumping with "latest" can produce a file the workshop rejects.
WORKSHOP_NEO4J_VERSION = "2026.03.1"


# --------------------------------------------------------------------------- #
# Shell helpers
# --------------------------------------------------------------------------- #
def run(
    cmd: list[str],
    *,
    stdin: str | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it to stderr. Returns the completed process."""
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=capture,
        check=check,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        sys.exit(f"error: `{name}` not found on PATH")


def collect_key(obj: object, key: str) -> list[str]:
    """Recursively collect string values stored under `key`, in document order."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, value in obj.items():
            if k == key and isinstance(value, str):
                found.append(value)
            else:
                found.extend(collect_key(value, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_key(item, key))
    return found


def collect_ints(obj: object) -> list[int]:
    """Recursively collect every integer leaf value (booleans excluded)."""
    found: list[int] = []
    if isinstance(obj, dict):
        for value in obj.values():
            found.extend(collect_ints(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_ints(item))
    elif isinstance(obj, int) and not isinstance(obj, bool):
        found.append(obj)
    return found


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Local:
    """Connection details for the local Community container."""

    uri: str
    password: str
    image: str
    data_dir: Path


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        sys.exit(f"error: env file not found: {path}")
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        env[name.strip()] = value.strip().strip('"').strip("'")
    return env


# --------------------------------------------------------------------------- #
# Pipeline steps
# --------------------------------------------------------------------------- #
def test_connection(env_path: Path) -> None:
    proc = run(
        ["neo4j-cli", "query", "RETURN 1 AS ok", "--env", str(env_path), "--format", "json"],
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"error: could not connect to Aura over Bolt:\n{proc.stderr}")
    print("  connected to Aura", file=sys.stderr)


EXPORT_CONFIG = (
    "{stream: true, format: 'plain', "
    "useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 100}}"
)

FULL_EXPORT = (
    f"CALL apoc.export.cypher.all(null, {EXPORT_CONFIG}) "
    "YIELD cypherStatements RETURN cypherStatements"
)

def sample_export(limit: int) -> str:
    """Export `limit` nodes plus the relationships wholly between them.

    The limit is interpolated rather than passed via --param: neo4j-cli
    JSON-types numeric params, yielding a float, and LIMIT requires an
    integer. `limit` is an argparse int, so interpolation is safe.
    """
    return f"""
MATCH (n) WITH n LIMIT {limit}
WITH collect(n) AS nodes
UNWIND nodes AS a
OPTIONAL MATCH (a)-[r]->(b) WHERE b IN nodes
WITH nodes, [x IN collect(DISTINCT r) WHERE x IS NOT NULL] AS rels
CALL apoc.export.cypher.data(nodes, rels, null, {EXPORT_CONFIG})
YIELD cypherStatements
RETURN cypherStatements
""".strip()


def export_cypher(env_path: Path, out_file: Path, limit: int, max_rows: int) -> None:
    base = [
        "neo4j-cli", "query",
        sample_export(limit) if limit > 0 else FULL_EXPORT,
        "--env", str(env_path),
        "--format", "json",
        "--max-rows", str(max_rows),
        "--truncate-arrays-over", "0",
    ]
    if limit > 0:
        print(f"  sampling {limit} nodes", file=sys.stderr)

    proc = run(base, capture=True, check=False)
    # apoc.export streaming is read-only, but if the EXPLAIN preflight
    # misclassifies it, retry once with --rw.
    if proc.returncode != 0 and "--rw" in (proc.stderr or ""):
        print("  retrying export with --rw", file=sys.stderr)
        proc = run([*base, "--rw"], capture=True, check=False)
    if proc.returncode != 0:
        sys.exit(f"error: export failed:\n{proc.stderr}")

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: could not parse export output: {exc}") from exc

    statements = collect_key(payload, "cypherStatements")
    if not statements:
        sys.exit("error: export returned no statements (is APOC available on the source?)")

    script = "".join(statements)
    out_file.write_text(script)
    lines = script.count("\n") + 1
    print(f"  wrote {out_file} ({out_file.stat().st_size:,} bytes, ~{lines:,} lines)",
          file=sys.stderr)


def create_local(container: str, data_dir: Path, version: str) -> Local:
    # Start clean so a leftover container / port does not force a rename.
    run(["neo4j-cli", "docker", "delete", container, "--yes", "--force", "--rw"], check=False)
    data_dir.mkdir(parents=True, exist_ok=True)

    password = secrets.token_urlsafe(18)
    run([
        "neo4j-cli", "docker", "create",
        "--name", container,
        "--edition", "community",
        "--version", version,
        "--data-dir", str(data_dir),
        "--password", password,
        "--no-print-password",
        "--wait",
        "--rw",
    ])

    port = run(
        ["docker", "inspect", container, "--format",
         '{{ (index (index .NetworkSettings.Ports "7687/tcp") 0).HostPort }}'],
        capture=True,
    ).stdout.strip()
    image = run(
        ["docker", "inspect", container, "--format", "{{ .Config.Image }}"],
        capture=True,
    ).stdout.strip()

    uri = f"bolt://localhost:{port}"
    print(f"  local Community Neo4j at {uri} (image {image})", file=sys.stderr)
    return Local(uri=uri, password=password, image=image, data_dir=data_dir)


def load_cypher(local: Local, cypher_file: Path, lenient: bool) -> None:
    cmd = [
        "neo4j-cli", "query",
        "--uri", local.uri,
        "--username", "neo4j",
        "--password", local.password,
        "--database", LOCAL_DB,
        "--rw",
        "--format", "json",
    ]
    if lenient:
        cmd.append("--continue-on-error")
    proc = run(cmd, stdin=cypher_file.read_text(), capture=True, check=False)
    if proc.returncode != 0:
        sys.exit(
            f"error: load into local Neo4j failed:\n{proc.stderr}\n"
            "hint: re-run with --lenient to skip failing statements."
        )
    print("  replayed export into local Neo4j", file=sys.stderr)


def count_graph(*, uri: str | None, password: str | None, env_path: Path | None,
                database: str) -> tuple[int, int]:
    """Return (node_count, rel_count) for a database."""
    def scalar(cypher: str) -> int:
        cmd = ["neo4j-cli", "query", cypher, "--database", database, "--format", "json"]
        if env_path is not None:
            cmd += ["--env", str(env_path)]
        else:
            cmd += ["--uri", uri or "", "--username", "neo4j", "--password", password or ""]
        proc = run(cmd, capture=True)
        ints = collect_ints(json.loads(proc.stdout))
        return max(ints) if ints else 0

    nodes = scalar("MATCH (n) RETURN count(n) AS c")
    rels = scalar("MATCH ()-[r]->() RETURN count(r) AS c")
    return nodes, rels


def verify(env_path: Path, source_db: str, local: Local, sampled: bool) -> None:
    src_nodes, src_rels = count_graph(
        uri=None, password=None, env_path=env_path, database=source_db,
    )
    loc_nodes, loc_rels = count_graph(
        uri=local.uri, password=local.password, env_path=None, database=LOCAL_DB,
    )
    print(f"  source: {src_nodes:,} nodes / {src_rels:,} rels", file=sys.stderr)
    print(f"  local:  {loc_nodes:,} nodes / {loc_rels:,} rels", file=sys.stderr)
    if sampled:
        print("  (sampled export: local is expected to be a subset)", file=sys.stderr)
    elif (src_nodes, src_rels) != (loc_nodes, loc_rels):
        print("  WARNING: counts differ between source and local copy", file=sys.stderr)
    else:
        print("  counts match", file=sys.stderr)


def dump(container: str, local: Local, out_path: Path) -> None:
    run(["neo4j-cli", "docker", "stop", container, "--rw"])

    dump_out = local.data_dir.parent / "out"
    dump_out.mkdir(parents=True, exist_ok=True)
    dump_out.chmod(0o777)  # neo4j runs as a non-host uid inside the container

    run([
        "docker", "run", "--rm",
        "-v", f"{local.data_dir}:/data",
        "-v", f"{dump_out}:/dump",
        local.image,
        "neo4j-admin", "database", "dump", LOCAL_DB,
        "--to-path=/dump", "--overwrite-destination=true",
    ])

    produced = dump_out / f"{LOCAL_DB}.dump"
    if not produced.is_file():
        sys.exit(f"error: dump not produced at {produced}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(produced), str(out_path))
    print(f"  dump written to {out_path} ({out_path.stat().st_size:,} bytes)",
          file=sys.stderr)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV,
                        help=f"Aura .env file (default: {DEFAULT_ENV})")
    parser.add_argument("--out", type=Path, default=Path("neo4j-hotel-graph.dump"),
                        help="output .dump path (default: ./neo4j-hotel-graph.dump)")
    parser.add_argument("--container", default=CONTAINER_NAME,
                        help=f"local container name (default: {CONTAINER_NAME})")
    parser.add_argument("--source-database", default=None,
                        help="source database on Aura (default: NEO4J_DATABASE or 'neo4j')")
    parser.add_argument("--neo4j-version", default=WORKSHOP_NEO4J_VERSION,
                        help=f"local Neo4j version tag (default: {WORKSHOP_NEO4J_VERSION}, "
                             "matching central-neo4j.yaml)")
    parser.add_argument("--limit", type=int, default=0,
                        help="export only N sampled nodes (0 = whole graph). Use for smoke tests")
    parser.add_argument("--max-rows", type=int, default=0,
                        help="neo4j-cli row cap on the export query (0 = unlimited)")
    parser.add_argument("--lenient", action="store_true",
                        help="skip failing statements during load instead of aborting")
    parser.add_argument("--keep", action="store_true",
                        help="keep the local container and work dir for inspection")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_tool("neo4j-cli")
    require_tool("docker")
    run(["docker", "info"], capture=True)  # fail early if the daemon is down

    env = load_env(args.env)
    source_db = args.source_database or env.get("NEO4J_DATABASE") or SOURCE_DB_FALLBACK

    work_dir = Path(tempfile.mkdtemp(prefix="aura-backup-"))
    data_dir = work_dir / "data"
    cypher_file = work_dir / "export.cypher"
    local: Local | None = None

    try:
        print("[1/4] testing Aura connection", file=sys.stderr)
        test_connection(args.env)

        print("[2/4] exporting graph over Bolt", file=sys.stderr)
        export_cypher(args.env, cypher_file, args.limit, args.max_rows)

        print("[3/4] loading into local Community Neo4j", file=sys.stderr)
        local = create_local(args.container, data_dir, args.neo4j_version)
        load_cypher(local, cypher_file, args.lenient)
        verify(args.env, source_db, local, sampled=args.limit > 0)

        print("[4/4] dumping with neo4j-admin", file=sys.stderr)
        dump(args.container, local, args.out)

        print(f"\nDone. Backup: {args.out}", file=sys.stderr)
    finally:
        if not args.keep:
            run(
                ["neo4j-cli", "docker", "delete", args.container,
                 "--yes", "--force", "--rw"],
                check=False,
            )
            shutil.rmtree(work_dir, ignore_errors=True)
        else:
            print(f"  kept container '{args.container}' and work dir {work_dir}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
