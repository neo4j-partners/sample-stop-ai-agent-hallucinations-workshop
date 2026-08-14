# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Update workshop-owned values in dotenv files safely."""

from __future__ import annotations

import difflib
import os
import re
import stat
import tempfile
from collections.abc import Collection, Mapping
from pathlib import Path


def update_env_file(
    path: Path,
    values: Mapping[str, str],
    *,
    header: str,
    legacy_headers: Collection[str] = (),
    dry_run: bool = False,
) -> str:
    """Replace one managed dotenv block and return its unified diff.

    Every live or commented assignment for a managed key is removed before a
    single canonical block is appended. Unmanaged lines keep their order.
    When ``dry_run`` is true, the diff is returned without changing ``path``.
    """
    if not values:
        return ""

    existing = _read(path)
    managed_headers = {header, *legacy_headers}
    patterns = _key_patterns(values)
    lines = [
        line
        for line in existing.splitlines()
        if line.strip() not in managed_headers
        and not _matches_any_key(line, patterns)
    ]
    _trim_trailing_blank_lines(lines)
    if lines:
        lines.append("")
    lines.extend([header, *(f"{key}={value}" for key, value in values.items())])
    updated = "\n".join(lines) + "\n"
    diff = _unified_diff(path, existing, updated)
    if not dry_run and updated != existing:
        _atomic_write(path, updated)
    return diff


def remove_env_keys(
    path: Path,
    keys: Collection[str],
    *,
    headers: Collection[str] = (),
    dry_run: bool = False,
) -> str:
    """Remove every managed dotenv assignment and return its unified diff."""
    if not path.exists() or not keys:
        return ""

    existing = _read(path)
    patterns = _key_patterns(keys)
    header_set = set(headers)
    lines = [
        line
        for line in existing.splitlines()
        if line.strip() not in header_set
        and not _matches_any_key(line, patterns)
    ]
    _trim_trailing_blank_lines(lines)
    updated = "\n".join(lines) + ("\n" if lines else "")
    diff = _unified_diff(path, existing, updated)
    if not dry_run and updated != existing:
        _atomic_write(path, updated)
    return diff


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _key_patterns(keys: Collection[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(
        re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=") for key in keys
    )


def _matches_any_key(line: str, patterns: Collection[re.Pattern[str]]) -> bool:
    return any(pattern.match(line) for pattern in patterns)


def _trim_trailing_blank_lines(lines: list[str]) -> None:
    while lines and not lines[-1].strip():
        lines.pop()


def _unified_diff(path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def _atomic_write(path: Path, content: str) -> None:
    """Write content beside the target, then atomically replace the target."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
