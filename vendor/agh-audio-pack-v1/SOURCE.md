# Vendored: AGH audio-pack manifest v1

- Source repo: lancer1977/agentic-game-harness
- Source SHA: 172274122e5850bbb66f19736121338776f713e7 (origin/dev)
- Copied paths:
  - contracts/audio-pack/v1 (README.md, manifest.schema.json, fixtures/)
  - python/agentic_game_harness/audio_pack.py (validate_manifest, migrate_eq_manifest; stdlib only)
- Read-only copy. Do not edit here. Refresh by re-running:
  git -C ~/code/agentic-game-harness archive <sha> contracts/audio-pack/v1 python/agentic_game_harness/audio_pack.py | tar -x -C vendor/agh-audio-pack-v1
- Consumer: scripts/validate_pack.py (eqlegends-audio-packs#6).
