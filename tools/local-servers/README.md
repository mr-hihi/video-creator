# Local adapter servers

OmniVoice, ACE-Step and YuE ship no server the API can call, so each one gets a small HTTP adapter here
(Provider Settings 7.6). The API only calls the adapter at the `Base URL` entered in `/settings`.

Every adapter answers:

```
GET  /health  → 200 { "ok": true }
POST /speech  — multipart text, language, sample (file), sampleText → 200 audio/wav        (OmniVoice)
POST /music   — JSON { "prompt", "durationS", "instrumental": true } → 200 audio/wav        (ACE-Step, YuE)
```

Any failure answers `500` with the error as plain text (at most 500 characters); the API shows that text
and retries the request.

## Run

Each adapter runs inside the Python environment where its model is installed. Install the adapter's own
packages there first:

```bash
pip install -r tools/local-servers/requirements.txt
```

| Adapter | Install the model | Start | Default `Base URL` |
|---|---|---|---|
| OmniVoice | `pip install omnivoice` (PyTorch first) | `python tools/local-servers/omnivoice_server.py` | `http://127.0.0.1:8010` |
| ACE-Step | clone `ACE-Step-1.5`, `uv sync`, then `uv run acestep-api` (port 8001) | `python tools/local-servers/ace_step_server.py` | `http://127.0.0.1:8011` |
| YuE | `pip install .` in a clone of the YuE repo (YuE2) | `python tools/local-servers/yue_server.py` | `http://127.0.0.1:8012` |

Every adapter takes `--host` (default `127.0.0.1`) and `--port`.

## Environment

| Variable | Adapter | Default | Meaning |
|---|---|---|---|
| `OMNIVOICE_MODEL` | OmniVoice | `k2-fsa/OmniVoice` | model id for `OmniVoice.from_pretrained` |
| `OMNIVOICE_DEVICE` | OmniVoice | `cuda:0`, else `mps`, else `cpu` | torch device |
| `ACESTEP_API_URL` | ACE-Step | `http://127.0.0.1:8001` | the running `acestep-api` |
| `ACESTEP_INSTRUMENTAL_LYRICS` | ACE-Step | `[Instrumental]` | lyrics sent for an instrumental track |
| `ACESTEP_WAIT_LIMIT_SEC` | ACE-Step | `1800` | longest wait for one track |
| `YUE_MODEL` | YuE | `m-a-p/YuE2-3B` | model id for `YuE2Pipeline.from_pretrained` |
| `YUE_DEVICE` | YuE | `cuda` | torch device |
| `YUE_INSTRUMENTAL_LYRICS` | YuE | empty | lyrics sent for an instrumental track |

## Limits

- OmniVoice takes no language argument; it speaks the language of the text. The `language` field is
  accepted and ignored. Its output is 24 kHz WAV.
- ACE-Step makes tracks of 10–600 s; `durationS` is clamped to that range.
- YuE takes no length: the track is as long as the model makes it. A track shorter than the episode plays
  once (Film Studio 4.4).
