#!/usr/bin/env python3
"""Validate an EQ Legends audio pack without contacting external services.

Manifests are checked against the vendored AGH audio-pack manifest v1 contract
(vendor/agh-audio-pack-v1, read-only). A manifest with a schema_version key is
validated as v1 directly. A legacy EQ manifest (no schema_version) is migrated
in memory with migrate_eq_manifest, using the pack directory name as zone_key,
and the migrated copy is validated as v1. The manifest file on disk is never
rewritten.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


VENDOR_MODULE = (
    Path(__file__).resolve().parents[1]
    / "vendor"
    / "agh-audio-pack-v1"
    / "python"
    / "agentic_game_harness"
    / "audio_pack.py"
)
LEGACY_MISSING_FILE_NOTE = " (does not reference a file)"


def _load_audio_pack(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("agh_audio_pack_v1", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load vendored audio pack contract: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_audio_pack = _load_audio_pack(VENDOR_MODULE)


class PackValidationError(ValueError):
    """A pack failed a validation rule."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PackValidationError(message)


def _legacy_precheck_errors(document: dict) -> list[str]:
    """Report v1 shape and duplicate errors before migration.

    migrate_eq_manifest derives line ids from file paths and raises on paths it
    cannot map (for example "../x.mp3"), and two lines that share a file collide
    there. Either would hide the v1 error text, so check those rules first.
    """
    enemies = document.get("enemies")
    if not isinstance(enemies, list):
        return []

    shape_errors: list[str] = []
    duplicate_errors: list[str] = []
    seen_triples: set[tuple[Any, Any, Any]] = set()
    file_owner: dict[Any, tuple[Any, Any]] = {}
    for enemy_index, enemy in enumerate(enemies):
        if not isinstance(enemy, dict) or not isinstance(enemy.get("statements"), list):
            continue
        for line_index, statement in enumerate(enemy["statements"]):
            if not isinstance(statement, dict) or not isinstance(statement.get("file"), str):
                continue
            location = f"enemies[{enemy_index}].statements[{line_index}]"
            file = statement["file"]
            _audio_pack._check_file(file, location, shape_errors)
            key = (enemy.get("name"), statement.get("text"))
            triple = (*key, file)
            if triple in seen_triples:
                duplicate_errors.append(f"duplicate statement-to-file entry: {triple!r}")
            seen_triples.add(triple)
            owner = file_owner.get(file)
            if owner is not None and owner != key:
                duplicate_errors.append(f"file is assigned to conflicting statements: {file!r}")
            file_owner[file] = key
    return shape_errors or duplicate_errors


def validate_document(document: Any, pack_dir: Path | str | None = None) -> list[str]:
    """Return every v1 error for a manifest document. An empty list means valid."""
    if isinstance(document, dict) and "schema_version" in document:
        return _audio_pack.validate_manifest(document, pack_dir=pack_dir)

    if not isinstance(document, dict):
        return ["manifest root must be an object"]
    if pack_dir is None:
        return ["legacy manifest needs a pack directory to derive zone_key"]

    pack_root = Path(pack_dir).resolve()
    precheck = _legacy_precheck_errors(document)
    if precheck:
        return precheck
    try:
        migrated = _audio_pack.migrate_eq_manifest(document, zone_key=pack_root.name)
    except ValueError as exc:
        return [f"legacy manifest cannot be migrated to v1: {exc}"]

    errors = _audio_pack.validate_manifest(migrated, pack_dir=pack_root)
    return [
        error + LEGACY_MISSING_FILE_NOTE if "file does not exist" in error else error
        for error in errors
    ]


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

    errors = validate_document(document, pack_dir=pack_dir)
    if errors:
        raise PackValidationError("; ".join(errors))


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
