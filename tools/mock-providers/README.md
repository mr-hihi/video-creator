# Mock providers

Stand-ins for the media providers, so the fenced test stack (`sh run.sh start_test`) can run Film Studio and
Film Clone end to end without credit, keys or a signed-in Flow tab. Nothing in the API changes: the API talks
to the mocks through the same adapters it uses for the real providers.

| Mock | Replaces | How the API reaches it |
|---|---|---|
| Flow extension | Google Flow (`image`, `edit_image`, `video`) | connects to the API's `FLOW_WS_PORT` (test: `5074`) like the Chrome extension, and answers every Flow RPC |
| Flow content | the `flow-content.google` image and video links | HTTPS on `127.0.0.1:5079`; the API trusts it through `SSL_CERT_FILE` |
| Local providers | SD WebUI (`/sdapi/v1/*`), OmniVoice (`/speech`), ACE-Step / YuE (`/music`) | HTTP on `127.0.0.1:5078`, entered as the provider's `Base URL` in `/settings` |

Answers:

- Images: a plain-colour PNG — 1376×768 or 768×1376 from Flow, the asked size from SD WebUI.
- Clips: an `ffmpeg` test pattern with a tone, 1280×720 or 720×1280, as long as the model id says (`abra_i2v_6s` → 6 s),
  else 8 s. Every Flow operation is done at the first status check.
- Speech: a WAV tone, 0.06 s per character of the text (1–7 s). Music: a WAV tone of the asked `durationS`.

Every call is appended to `calls.jsonl` in the state directory: prompt, model, inputs, size.

## Run

From `api/` (the mock uses the API's `websockets` and `certifi`):

```bash
uv run python ../tools/mock-providers/mock_providers.py
```

On its first start it writes a self-signed certificate for `127.0.0.1` and a CA bundle (certifi + that
certificate) to the state directory, and logs the bundle path. Start the test stack with it:

```bash
SSL_CERT_FILE=/path/from/the/log/ca-bundle.pem sh run.sh start_test
```

Then, in `/settings?tab=general&provider=google_flow`, Google Flow reads `Connected`. Point the local providers
you need at `http://127.0.0.1:5078`, and route `Speech` / `Music` to them in `/settings?tab=ai-models` when a
case needs narration or music.

| Option | Default | Meaning |
|---|---|---|
| `--local-port` | `5078` | local providers |
| `--content-port` | `5079` | Flow content (HTTPS) |
| `--flow-ws-port` | `5074` | the API's `FLOW_WS_PORT` |
| `--state-dir` | `{tmp}/video-tool-mock-providers` | certificate, bundle, rendered clips, `calls.jsonl` |
| `--ffmpeg-bin` | `ffmpeg` | renders the clips |
| `--no-flow-extension` | off | serve media only; Google Flow then reads `Not connected` |

## Limits

- `SSL_CERT_FILE` replaces the CA list of every HTTPS call the API makes. The bundle keeps certifi's roots, so
  real providers still work in the same run.
- No failure modes: every request succeeds. Retry and error rules are covered by the API unit tests.
- The extension popup (`Agent port`) is not mocked; the mock always connects to `--flow-ws-port`.
