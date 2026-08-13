# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Idempotent self-paced preparation for Demo 01 and optional Demo 01b."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

os.environ["OTEL_SDK_DISABLED"] = "true"

from dotenv import load_dotenv

load_dotenv()

from graph_builder import connect, run_build  # noqa: E402
from graph_config import select_lite_files  # noqa: E402
from retrieval_setup import (  # noqa: E402
    ReadinessError,
    ensure_retrieval_indexes,
    report_readiness,
    verify_retrieval_indexes,
)

DATA_DIR = Path("data")
LITE_DOCUMENTS = 30


def selected_paths(mode: str) -> list[Path]:
    """Return the deterministic source paths for the requested build mode."""
    if mode == "lite":
        names = select_lite_files(DATA_DIR, LITE_DOCUMENTS)
        return [DATA_DIR / name for name in names]
    return sorted(DATA_DIR.glob("*.txt"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and verify the graph and indexes for Demo 01."
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
        finally:
            driver.close()

        if not problems:
            print("\n✅ Demo 01 and Demo 01b are ready; no rebuild needed.")
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
