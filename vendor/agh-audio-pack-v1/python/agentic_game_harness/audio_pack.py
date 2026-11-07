"""Audio-pack manifest v1: game-neutral validation and EQ migration (stdlib only).

Contract: contracts/audio-pack/v1 (manifest.schema.json, README.md). The checks
here match the schema's keys and patterns, plus the cross-line and filesystem
rules the schema cannot express. Validation returns every error it finds and
never raises for a bad manifest. Migration raises ValueError for input it cannot
map.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
KNOWN_GAME_IDS = frozenset({"eqlegends", "wow"})
REQUIRED_KEYS = (
    "schema_version",
    "game_id",
    "zone_key",
    "zone_name",
    "packVersion",
    "provider",
    "voiceId",
    "enemies",
)
ALLOWED_KEYS = REQUIRED_KEYS
SPEAKER_KEYS = ("name", "statements")
LINE_KEYS = ("id", "text", "file")

GAME_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")
ZONE_KEY_RE = re.compile(r"^[a-z0-9-]{1,64}$")
LINE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _is_str(value: Any, max_len: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= max_len


def _check_file(value: Any, location: str, errors: list[str]) -> bool:
    if not _is_str(value, 512):
        errors.append(f"{location}.file must be a string of 1..512 characters")
        return False
    problems = []
    if value.startswith("/") or DRIVE_RE.match(value):
        problems.append("must be relative")
    if "\\" in value:
        problems.append("must use / separators")
    if ".." in value.split("/"):
        problems.append("contains traversal")
    if problems:
        errors.append(f"{location}.file {problems[0]}: {value!r}")
        return False
    return True


def _check_unknown(obj: dict, allowed: tuple[str, ...], location: str, errors: list[str]) -> None:
    for key in obj:
        if key not in allowed:
            errors.append(f"unknown {location} key: {key!r}")


def validate_manifest(obj: Any, pack_dir: Path | str | None = None) -> list[str]:
    """Return every error in a v1 manifest. An empty list means valid.

    When pack_dir is given, each line's file must also exist as a regular file
    under pack_dir and must not resolve outside it.
    """
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["manifest root must be an object"]

    _check_unknown(obj, ALLOWED_KEYS, "top-level", errors)
    for key in REQUIRED_KEYS:
        if key not in obj:
            errors.append(f"missing required key: {key}")

    schema_version = obj.get("schema_version")
    if not (isinstance(schema_version, int) and not isinstance(schema_version, bool)
            and schema_version == SCHEMA_VERSION):
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    game_id = obj.get("game_id")
    if not (isinstance(game_id, str) and GAME_ID_RE.match(game_id)):
        errors.append(f"game_id must match {GAME_ID_RE.pattern}: {game_id!r}")
    elif game_id not in KNOWN_GAME_IDS:
        errors.append(f"unknown game_id: {game_id!r} (known: {sorted(KNOWN_GAME_IDS)})")

    zone_key = obj.get("zone_key")
    if not (isinstance(zone_key, str) and ZONE_KEY_RE.match(zone_key)):
        errors.append(f"zone_key must match {ZONE_KEY_RE.pattern}: {zone_key!r}")

    if not _is_str(obj.get("zone_name"), 128):
        errors.append("zone_name must be a string of 1..128 characters")

    pack_version = obj.get("packVersion")
    if not (isinstance(pack_version, str) and SEMVER_RE.fullmatch(pack_version)):
        errors.append(f"packVersion is not supported semver: {pack_version!r}")

    if not _is_str(obj.get("provider"), 64):
        errors.append("provider must be a string of 1..64 characters")
    if not _is_str(obj.get("voiceId"), 128):
        errors.append("voiceId must be a string of 1..128 characters")

    pack_root = None
    if pack_dir is not None:
        pack_root = Path(pack_dir).resolve()
        if not pack_root.is_dir():
            errors.append(f"pack_dir does not exist: {str(pack_dir)!r}")
            pack_root = None

    enemies = obj.get("enemies")
    if not (isinstance(enemies, list) and enemies):
        errors.append("enemies must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    seen_triples: set[tuple[str, str, str]] = set()
    statement_files: dict[tuple[str, str], str] = {}
    file_statements: dict[str, tuple[str, str]] = {}
    line_count = 0

    for speaker_index, speaker in enumerate(enemies):
        location = f"enemies[{speaker_index}]"
        if not isinstance(speaker, dict):
            errors.append(f"{location} must be an object")
            continue
        _check_unknown(speaker, SPEAKER_KEYS, location, errors)
        name = speaker.get("name")
        if not _is_str(name, 128):
            errors.append(f"{location}.name must be a string of 1..128 characters")
            name = ""
        statements = speaker.get("statements")
        if not (isinstance(statements, list) and statements):
            errors.append(f"{location}.statements must be a non-empty array")
            continue

        for line_index, line in enumerate(statements):
            line_location = f"{location}.statements[{line_index}]"
            if not isinstance(line, dict):
                errors.append(f"{line_location} must be an object")
                continue
            _check_unknown(line, LINE_KEYS, line_location, errors)
            line_count += 1

            line_id = line.get("id")
            if not (isinstance(line_id, str) and LINE_ID_RE.match(line_id)):
                errors.append(f"{line_location}.id must match {LINE_ID_RE.pattern}: {line_id!r}")
            elif line_id in seen_ids:
                errors.append(f"duplicate line id: {line_id!r}")
            else:
                seen_ids.add(line_id)

            text = line.get("text")
            if not _is_str(text, 1024):
                errors.append(f"{line_location}.text must be a string of 1..1024 characters")
                continue

            if not _check_file(line.get("file"), line_location, errors):
                continue
            reference = line["file"]

            if pack_root is not None:
                resolved = (pack_root / reference).resolve()
                try:
                    resolved.relative_to(pack_root)
                except ValueError:
                    errors.append(f"{line_location}.file escapes pack root: {reference!r}")
                    continue
                if not resolved.is_file():
                    errors.append(f"{line_location}.file does not exist: {reference!r}")
                    continue

            triple = (name, text, reference)
            if triple in seen_triples:
                errors.append(f"duplicate statement-to-file entry: {triple!r}")
            seen_triples.add(triple)

            key = (name, text)
            previous_file = statement_files.get(key)
            if previous_file is not None and previous_file != reference:
                errors.append(
                    f"conflicting files for statement {name!r}/{text!r}: "
                    f"{previous_file!r} and {reference!r}"
                )
            statement_files[key] = reference

            previous_statement = file_statements.get(reference)
            if previous_statement is not None and previous_statement != key:
                errors.append(f"file is assigned to conflicting statements: {reference!r}")
            file_statements[reference] = key

    if line_count == 0:
        errors.append("manifest contains no statements")
    return errors


def _derive_line_id(file: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", file)
    if stem.startswith("audio/"):
        stem = stem[len("audio/"):]
    line_id = stem.replace("/", "-").lower()
    if not LINE_ID_RE.match(line_id):
        raise ValueError(f"cannot derive a line id from file {file!r}")
    return line_id


def migrate_eq_manifest(obj: dict, zone_key: str) -> dict:
    """Return a v1 copy of an EQ manifest. The input is not modified.

    Sets schema_version 1, game_id "eqlegends" and zone_key; renames zone to
    zone_name; adds an id to every line, derived from its file path. Every other
    field is kept. The result should be passed to validate_manifest.
    """
    if not isinstance(obj, dict):
        raise ValueError("EQ manifest root must be an object")
    if not (isinstance(zone_key, str) and ZONE_KEY_RE.match(zone_key)):
        raise ValueError(f"zone_key must match {ZONE_KEY_RE.pattern}: {zone_key!r}")
    zone_name = obj.get("zone_name", obj.get("zone"))
    if not isinstance(zone_name, str) or not zone_name:
        raise ValueError("EQ manifest needs a zone name")
    enemies = obj.get("enemies")
    if not isinstance(enemies, list):
        raise ValueError("EQ manifest enemies must be an array")

    source = copy.deepcopy(obj)
    rest = {k: v for k, v in source.items() if k not in ("zone", "zone_name", "enemies")}
    migrated: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "game_id": "eqlegends",
        "zone_key": zone_key,
        "zone_name": zone_name,
        **rest,
    }

    new_enemies = []
    seen: dict[str, str] = {}
    for speaker in enemies:
        if not isinstance(speaker, dict) or not isinstance(speaker.get("statements"), list):
            raise ValueError("each EQ enemy needs a statements array")
        new_statements = []
        for line in speaker["statements"]:
            if not isinstance(line, dict) or not isinstance(line.get("file"), str):
                raise ValueError("each EQ statement needs a file string")
            line_id = line.get("id") or _derive_line_id(line["file"])
            if line_id in seen:
                raise ValueError(f"line id collision: {line_id!r}")
            seen[line_id] = line["file"]
            new_statements.append({"id": line_id, **{k: v for k, v in line.items() if k != "id"}})
        new_enemies.append({**{k: v for k, v in speaker.items() if k != "statements"},
                            "statements": new_statements})
    migrated["enemies"] = new_enemies
    return migrated
