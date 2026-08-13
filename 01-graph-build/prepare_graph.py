# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Idempotent self-paced preparation of the Lab 1 graph and its indexes."""

import argparse
import asyncio
import os
import sys
import zipfile
from pathlib import Path

os.environ["OTEL_SDK_DISABLED"] = "true"

from dotenv import load_dotenv

load_dotenv()

from graph_builder import connect, report, run_build  # noqa: E402
from graph_config import select_lite_files  # noqa: E402
from workshop.retrieval_setup import (  # noqa: E402
    ReadinessError,
    ensure_retrieval_indexes,
    report_readiness,
    verify_retrieval_indexes,
)

DATA_DIR = Path("data")
CORPUS_ZIP = Path("hotel-faqs.zip")
LITE_DOCUMENTS = 30


def ensure_corpus_extracted(data_dir: Path = DATA_DIR) -> int:
    """Extract the committed corpus zip when no documents are present yet.

    `data/` is gitignored, so a fresh clone has only `hotel-faqs.zip`. The
    notebook's first cell extracts it, and the script path has to do the same
    or a participant who starts here stops at an empty directory. Returns the
    number of source documents now on disk.
    """
    extracted = sorted(data_dir.glob("*.txt"))
    if extracted or not CORPUS_ZIP.exists():
        return len(extracted)

    with zipfile.ZipFile(CORPUS_ZIP) as archive:
        archive.extractall(data_dir)
    extracted = sorted(data_dir.glob("*.txt"))
    print(f"Extracted {len(extracted)} source documents into {data_dir}/")
    return len(extracted)


def selected_paths(mode: str) -> list[Path]:
    """Return the deterministic source paths for the requested build mode."""
    if mode == "lite":
        names = select_lite_files(DATA_DIR, LITE_DOCUMENTS)
        return [DATA_DIR / name for name in names]
    return sorted(DATA_DIR.glob("*.txt"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and verify the Lab 1 graph and its retrieval indexes."
    )
    parser.add_argument("--mode", choices=("lite", "full"), default="lite")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report readiness without rebuilding an incomplete graph.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild even when the selected graph is already ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_corpus_extracted()
    paths = selected_paths(args.mode)
    if not paths:
        print(f"No source documents found in {DATA_DIR.resolve()}.")
        return 1

    if not args.rebuild:
        driver = connect()
        try:
            if args.check_only:
                problems = []
                try:
                    verify_retrieval_indexes(driver)
                except ReadinessError as exc:
                    problems.append(str(exc))
                problems.extend(
                    report_readiness(driver, expected_documents=len(paths))
                )
            else:
                try:
                    ensure_retrieval_indexes(driver)
                except ReadinessError as exc:
                    print(f"\n❌ {exc}")
                    return 1
                problems = report_readiness(driver, expected_documents=len(paths))
            # The acceptance queries print whether or not a build runs, so a
            # ready graph still shows what Lab 2 will be asking it.
            if not problems:
                report(driver)
        finally:
            driver.close()

        if not problems:
            print("\n✅ Lab 1 is ready; no rebuild needed.")
            return 0
        print("\nGraph preparation is incomplete:")
        for problem in problems:
            print(f"  - {problem}")
        if args.check_only:
            return 1

    title = "🚀 LITE BUILD" if args.mode == "lite" else "FULL BUILD"
    return asyncio.run(run_build(paths, title))


if __name__ == "__main__":
    sys.exit(main())
