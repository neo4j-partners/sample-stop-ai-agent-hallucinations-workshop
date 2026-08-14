from __future__ import annotations

from pathlib import Path

from workshop.env_file import remove_env_keys, update_env_file

HEADER = "# --- managed ---"
LEGACY_HEADER = "# --- old managed ---"


def test_update_removes_all_live_and_commented_duplicates(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "KEEP=one\n"
        f"{LEGACY_HEADER}\n"
        "# API_URL=placeholder\n"
        "API_URL=stale\n"
        "  # TOKEN=old-comment\n"
        "TOKEN=stale\n"
        "ALSO_KEEP=two\n",
        encoding="utf-8",
    )

    update_env_file(
        path,
        {"API_URL": "https://example.test", "TOKEN": "current"},
        header=HEADER,
        legacy_headers=(LEGACY_HEADER,),
    )

    assert path.read_text(encoding="utf-8") == (
        "KEEP=one\n"
        "ALSO_KEEP=two\n\n"
        f"{HEADER}\n"
        "API_URL=https://example.test\n"
        "TOKEN=current\n"
    )


def test_update_dry_run_returns_diff_without_writing(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("KEEP=one\nAPI_URL=stale\n", encoding="utf-8")

    diff = update_env_file(
        path,
        {"API_URL": "current"},
        header=HEADER,
        dry_run=True,
    )

    assert path.read_text(encoding="utf-8") == "KEEP=one\nAPI_URL=stale\n"
    assert "-API_URL=stale" in diff
    assert "+API_URL=current" in diff


def test_remove_deletes_live_and_commented_assignments(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        f"KEEP=one\n{HEADER}\nAPI_URL=current\n# API_URL=placeholder\n",
        encoding="utf-8",
    )

    remove_env_keys(path, ("API_URL",), headers=(HEADER,))

    assert path.read_text(encoding="utf-8") == "KEEP=one\n"
