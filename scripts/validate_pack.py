#!/usr/bin/env python3
"""Validate an EQ Legends audio pack without contacting external services."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class PackValidationError(ValueError):
    """A pack failed a validation rule."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PackValidationError(message)


def _nonempty_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value


def _safe_reference(pack_root: Path, value: Any, location: str) -> Path:
    reference = _nonempty_string(value, f"{location}.file")
    candidate = Path(reference)
    _require(not candidate.is_absolute(), f"{location}.file must be relative: {reference!r}")
    _require("\\" not in reference, f"{location}.file must use / separators: {reference!r}")
    _require(".." not in candidate.parts, f"{location}.file contains traversal: {reference!r}")

    root = pack_root.resolve()
    resolved = (pack_root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PackValidationError(
            f"{location}.file escapes pack root: {reference!r}"
        ) from exc
    _require(resolved.is_file(), f"{location}.file does not reference a file: {reference!r}")
    return resolved


def validate_pack(pack_dir: Path) -> None:
    """Validate one pack directory, raising PackValidationError on failure."""

    pack_dir = pack_dir.resolve()
    _require(pack_dir.is_dir(), f"pack directory does not exist: {pack_dir}")
    manifest_path = pack_dir / "manifest.json"
    _require(manifest_path.is_file(), f"missing manifest: {manifest_path}")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackValidationError(f"manifest is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise PackValidationError(f"could not read manifest: {exc}") from exc

    _require(isinstance(document, dict), "manifest root must be an object")
    _nonempty_string(document.get("zone"), "zone")
    version = _nonempty_string(document.get("packVersion"), "packVersion")
    _require(bool(SEMVER.fullmatch(version)), f"packVersion is not supported semver: {version!r}")
    _nonempty_string(document.get("provider"), "provider")
    _nonempty_string(document.get("voiceId"), "voiceId")

    enemies = document.get("enemies")
    _require(isinstance(enemies, list) and enemies, "enemies must be a non-empty array")

    seen_pairs: set[tuple[str, str, str]] = set()
    statement_files: dict[tuple[str, str], str] = {}
    file_statements: dict[str, tuple[str, str]] = {}
    total_statements = 0

    for enemy_index, enemy in enumerate(enemies):
        location = f"enemies[{enemy_index}]"
        _require(isinstance(enemy, dict), f"{location} must be an object")
        name = _nonempty_string(enemy.get("name"), f"{location}.name")
        statements = enemy.get("statements")
        _require(
            isinstance(statements, list) and statements,
            f"{location}.statements must be a non-empty array",
        )
        for statement_index, statement in enumerate(statements):
            statement_location = f"{location}.statements[{statement_index}]"
            _require(isinstance(statement, dict), f"{statement_location} must be an object")
            text = _nonempty_string(statement.get("text"), f"{statement_location}.text")
            resolved = _safe_reference(pack_dir, statement.get("file"), statement_location)
            reference = resolved.relative_to(pack_dir).as_posix()
            pair = (name, text, reference)
            _require(pair not in seen_pairs, f"duplicate statement-to-file entry: {pair!r}")
            seen_pairs.add(pair)

            statement_key = (name, text)
            previous_file = statement_files.get(statement_key)
            _require(
                previous_file is None or previous_file == reference,
                f"conflicting files for statement {name!r}/{text!r}: "
                f"{previous_file!r} and {reference!r}",
            )
            statement_files[statement_key] = reference

            previous_statement = file_statements.get(reference)
            _require(
                previous_statement is None or previous_statement == (name, text),
                f"file is assigned to conflicting statements: {reference!r}",
            )
            file_statements[reference] = (name, text)
            total_statements += 1

    _require(total_statements > 0, "manifest contains no statements")


def _pack_dirs(root: Path) -> list[Path]:
    packs = root / "packs"
    _require(packs.is_dir(), f"packs directory does not exist: {packs}")
    return sorted(path for path in packs.iterdir() if path.is_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pack-dir", type=Path, help="directory containing manifest.json")
    group.add_argument("--all", action="store_true", help="validate every directory under packs/")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    try:
        targets = [args.pack_dir] if args.pack_dir else _pack_dirs(args.repo_root)
        _require(bool(targets), "no pack directories found")
        for target in targets:
            validate_pack(target)
            print(f"valid: {target}")
    except PackValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
