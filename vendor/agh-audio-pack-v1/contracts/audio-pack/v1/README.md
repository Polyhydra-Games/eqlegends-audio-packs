# audio-pack contract v1

Game-neutral manifest for a pre-generated voice clip pack covering one zone.
A pack is a directory holding `manifest.json` and the clip files it names.
The manifest carries text and relative paths only. Audio is never described
or embedded here.

Schema: `manifest.schema.json` (JSON Schema draft 2020-12). Python binding:
`python/agentic_game_harness/audio_pack.py` (`validate_manifest`,
`migrate_eq_manifest`, stdlib only). Tests: `python/tests/test_audio_pack.py`.

## Top-level keys (all required, no others allowed)

| key | rule |
| --- | --- |
| `schema_version` | the integer `1` |
| `game_id` | `^[a-z0-9-]{1,32}$`. The validator also requires a known id: `eqlegends` or `wow` |
| `zone_key` | `^[a-z0-9-]{1,64}$`, the same rule as mmo `zone.changed` |
| `zone_name` | string 1..128 |
| `packVersion` | semver string |
| `provider` | string 1..64 |
| `voiceId` | string 1..128 |
| `enemies` | non-empty array of speakers |

The key `enemies` keeps its EQ name. For other games it is the list of
speakers the pack covers, whether hostile or not.

## Speaker and line

- A speaker is `{name, statements}`. `name` is 1..128 characters and
  `statements` is a non-empty array. No other keys.
- A line is `{id, text, file}`, with no other keys.
  - `id` matches `^[a-z0-9][a-z0-9-]{0,127}$` and is unique across the whole manifest.
  - `text` is 1..1024 characters.
  - `file` is relative to the pack directory. It uses `/` separators and has no
    leading `/`, no drive letter and no `..` segment. It is 1..512 characters.
- No two lines may share the same (speaker, text, file) triple. One file maps to
  one (speaker, text) pair, and one (speaker, text) pair maps to one file.

## Validator checks

`validate_manifest(obj, pack_dir=None) -> list[str]` returns every error it finds.
An empty list means valid. When `pack_dir` is given it also checks that each
`file` exists as a regular file under `pack_dir`, and that it does not resolve
outside it.

## Migrating an EQ manifest (one-line change per pack)

EQ manifests (`eqlegends-audio-packs`, `packs/<zone>/manifest.json`) are
migrated with `migrate_eq_manifest(obj, zone_key)`. It:

1. sets `schema_version` to 1 and `game_id` to `eqlegends`,
2. sets `zone_key` from the argument,
3. renames `zone` to `zone_name`,
4. adds `id` to every line, derived from its file path. For example
   `audio/orc-legionnaire/01.mp3` gives `orc-legionnaire-01`.

Every other EQ field is kept unchanged.

Fixtures under `fixtures/valid/` hold migrated copies of the EQ Crushbone and
Befallen manifests (text only) and a WoW zone pack for `thunder-bluff`.
`fixtures/invalid/` holds one case per rejection rule. `missing-file.json` is
checked against an empty pack directory.
