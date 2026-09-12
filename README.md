# EQ Legends Audio Packs

Pre-generated enemy voice clips for the [EQ Legends Sidecar](https://github.com/Polyhydra-Games/eqlegends-support) companion app, distributed one pack per zone/dungeon.

Clips are generated once (via ElevenLabs, through the Sidecar's own tts-gateway integration) from **real captured in-game dialogue** for that zone, then compressed to a low bitrate purely to keep pack downloads small — ElevenLabs bills per character regardless of output quality, so this is a file-size optimization, not a cost one.

## Layout

```
packs/
  <zone-slug>/
    manifest.json
    audio/
      <enemy-slug>/
        01.mp3
        02.mp3
        ...
```

## manifest.json format

```json
{
  "zone": "Crushbone",
  "packVersion": "1.0.0",
  "provider": "elevenlabs",
  "voiceId": "<elevenlabs voice id used for this pack>",
  "enemies": [
    {
      "name": "Orc legionnaire",
      "statements": [
        { "text": "You are no match for a legionnaire!", "file": "audio/orc-legionnaire/01.mp3" }
      ]
    }
  ]
}
```

`name`/`text` match the exact enemy name and captured statement text as they appear in the Sidecar's `enemy_statements` table — the app's install step uses these to key its local `rendered_sayings` cache, so playback picks up installed clips with no further changes needed.

## Releases

Each pack is published as a GitHub Release with the pack's zip attached (e.g. `crushbone-v1.0.0`). The Sidecar app's Settings → Audio Packs section lists available releases and installs one on request — nothing is downloaded automatically.

## Packs

| Zone | Status |
|---|---|
| Crushbone | manifest scaffolded (39 enemy entries), clips not yet generated |
| Befallen | manifest scaffolded (6 enemy entries — thinner dataset, less time spent there), clips not yet generated |

## Validation

Pack manifests and their referenced clips are checked by the credential-free
validator before a tagged release is zipped. To validate one pack locally:

```bash
python3 scripts/validate_pack.py --pack-dir packs/<zone-slug>
```

The pull request workflow also runs the validator tests and checks every pack
when pack content changes. The current scaffold entries intentionally fail
until their referenced audio clips have been added.
