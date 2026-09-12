import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_pack import PackValidationError, validate_pack


class ValidatePackTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack = Path(self.temp_dir.name) / "pack"
        (self.pack / "audio").mkdir(parents=True)
        (self.pack / "audio" / "orc.mp3").write_bytes(b"fixture")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_manifest(self, **overrides):
        manifest = {
            "zone": "Fixture",
            "packVersion": "1.0.0",
            "provider": "fixture",
            "voiceId": "fixture-voice",
            "enemies": [
                {
                    "name": "Orc",
                    "statements": [
                        {"text": "You shall fall!", "file": "audio/orc.mp3"}
                    ],
                }
            ],
        }
        manifest.update(overrides)
        (self.pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_valid_fixture_passes(self):
        self.write_manifest()
        validate_pack(self.pack)

    def test_missing_referenced_file_fails(self):
        self.write_manifest()
        (self.pack / "audio" / "orc.mp3").unlink()
        with self.assertRaisesRegex(PackValidationError, "does not reference a file"):
            validate_pack(self.pack)

    def test_traversal_reference_fails(self):
        self.write_manifest(
            enemies=[
                {
                    "name": "Orc",
                    "statements": [{"text": "You shall fall!", "file": "../secret.mp3"}],
                }
            ]
        )
        with self.assertRaisesRegex(PackValidationError, "traversal"):
            validate_pack(self.pack)

    def test_empty_enemy_records_fail(self):
        self.write_manifest(enemies=[])
        with self.assertRaisesRegex(PackValidationError, "non-empty array"):
            validate_pack(self.pack)

    def test_conflicting_statement_files_fail(self):
        (self.pack / "audio" / "orc-2.mp3").write_bytes(b"fixture")
        self.write_manifest(
            enemies=[
                {
                    "name": "Orc",
                    "statements": [
                        {"text": "You shall fall!", "file": "audio/orc.mp3"},
                        {"text": "You shall fall!", "file": "audio/orc-2.mp3"},
                    ],
                }
            ]
        )
        with self.assertRaisesRegex(PackValidationError, "conflicting files"):
            validate_pack(self.pack)

    def test_duplicate_statement_file_fails(self):
        self.write_manifest(
            enemies=[
                {
                    "name": "Orc",
                    "statements": [
                        {"text": "You shall fall!", "file": "audio/orc.mp3"},
                        {"text": "You shall fall!", "file": "audio/orc.mp3"},
                    ],
                }
            ]
        )
        with self.assertRaisesRegex(PackValidationError, "duplicate statement"):
            validate_pack(self.pack)


if __name__ == "__main__":
    unittest.main()
