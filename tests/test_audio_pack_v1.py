import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_pack import PackValidationError, validate_document, validate_pack

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS = REPO_ROOT / "packs"
FIXTURES = REPO_ROOT / "vendor" / "agh-audio-pack-v1" / "contracts" / "audio-pack" / "v1" / "fixtures"


def _load_fixture(relative: str) -> dict:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


class ExistingPackTests(unittest.TestCase):
    """Both shipped EQ packs go through the new path without edits to their manifests."""

    def test_existing_packs_are_structurally_valid_v1_after_migration(self):
        for zone in ("crushbone", "befallen"):
            with self.subTest(zone=zone):
                pack = PACKS / zone
                legacy = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
                self.assertNotIn("schema_version", legacy)
                # Structural checks only: clips are not generated yet, so the file
                # existence rule is the only one that may fire on the scaffolds.
                errors = validate_document(legacy, pack_dir=pack)
                self.assertTrue(errors, "scaffold clips are expected to be missing")
                self.assertTrue(
                    all("does not exist" in e for e in errors),
                    f"non-file errors for {zone}: {errors}",
                )

    def test_migration_is_in_memory_and_leaves_manifests_untouched(self):
        for zone in ("crushbone", "befallen"):
            with self.subTest(zone=zone):
                path = PACKS / zone / "manifest.json"
                before = path.read_bytes()
                validate_document(json.loads(before), pack_dir=PACKS / zone)
                self.assertEqual(before, path.read_bytes())

    def test_validate_pack_reports_only_missing_clips_for_existing_packs(self):
        for zone in ("crushbone", "befallen"):
            with self.subTest(zone=zone):
                with self.assertRaises(PackValidationError) as ctx:
                    validate_pack(PACKS / zone)
                for part in str(ctx.exception).split("; "):
                    self.assertIn("does not exist", part)


class NativeV1Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack = Path(self.temp_dir.name) / "thunder-bluff"
        self.pack.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _materialise(self, manifest: dict) -> None:
        for speaker in manifest["enemies"]:
            for line in speaker["statements"]:
                target = self.pack / line["file"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fixture")
        (self.pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_wow_fixture_copy_validates_as_v1(self):
        manifest = _load_fixture("valid/wow-thunder-bluff.json")
        self._materialise(manifest)
        validate_pack(self.pack)

    def test_native_manifest_is_not_migrated(self):
        manifest = _load_fixture("valid/wow-thunder-bluff.json")
        self._materialise(manifest)
        bad = copy.deepcopy(manifest)
        bad["schema_version"] = 2
        errors = validate_document(bad, pack_dir=self.pack)
        self.assertIn("schema_version must be 1", errors)


class VendoredInvalidFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _errors(self, name: str) -> list[str]:
        return validate_document(_load_fixture(f"invalid/{name}.json"), pack_dir=self.pack)

    def test_duplicate_line_id_is_rejected(self):
        self.assertTrue(any("duplicate line id" in e for e in self._errors("duplicate-line-id")))

    def test_dotdot_path_is_rejected(self):
        self.assertTrue(any("traversal" in e for e in self._errors("dotdot-path")))

    def test_unknown_top_level_key_is_rejected(self):
        self.assertTrue(any("unknown top-level key" in e for e in self._errors("unknown-top-level-key")))

    def test_bad_game_id_is_rejected(self):
        self.assertTrue(any("game_id must match" in e for e in self._errors("bad-game-id-format")))


class LegacyPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack = Path(self.temp_dir.name) / "orc-camp"
        (self.pack / "audio").mkdir(parents=True)
        (self.pack / "audio" / "orc.mp3").write_bytes(b"fixture")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_manifest_migrates_with_directory_name_as_zone_key(self):
        legacy = {
            "zone": "Orc Camp",
            "packVersion": "1.0.0",
            "provider": "fixture",
            "voiceId": "fixture-voice",
            "enemies": [{"name": "Orc", "statements": [{"text": "Hi", "file": "audio/orc.mp3"}]}],
        }
        self.assertEqual(validate_document(legacy, pack_dir=self.pack), [])

    def test_legacy_duplicate_file_reports_v1_text(self):
        legacy = {
            "zone": "Orc Camp",
            "packVersion": "1.0.0",
            "provider": "fixture",
            "voiceId": "fixture-voice",
            "enemies": [
                {
                    "name": "Orc",
                    "statements": [
                        {"text": "Hi", "file": "audio/orc.mp3"},
                        {"text": "Hi", "file": "audio/orc.mp3"},
                    ],
                }
            ],
        }
        errors = validate_document(legacy, pack_dir=self.pack)
        self.assertTrue(any("duplicate statement-to-file entry" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
