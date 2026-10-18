# Google Flow extension

Chrome extension (Manifest V3) that lets the video-tool API generate images and clips with Google Flow
through a signed-in `flow.google.com` tab. Business rules: [docs/business/7-provider-settings.md § 7.7](../../docs/business/7-provider-settings.md).

Ported from [flowkit](https://github.com/crisng95/flowkit) — MIT © 2026 tuannguyenhoangit-droid, see
[LICENSE](LICENSE). `recaptcha__en.js` and `recaptcha_enterprise.js` are Google's reCAPTCHA scripts as
flowkit ships them.

## Load it

1. Open `chrome://extensions`, turn on **Developer mode**.
2. **Load unpacked** → pick this `video-tool/extension/google-flow/` folder.
3. Open `https://flow.google.com/` in the same Chrome profile and sign in.
4. Click the extension icon and set **Agent port**:

| Stack | Agent port | API setting |
| --- | --- | --- |
| Dev (`sh run.sh start`) | `4024` (default) | `FLOW_WS_PORT=4024` |
| Test (`sh run.sh start_test`) | `5074` | `FLOW_WS_PORT=5074` in `api/.env.test` |

The extension reconnects to `ws://127.0.0.1:{Agent port}` within about 5 s of a change. The Google Flow
sub-tab on `/settings?tab=general&provider=google_flow` then reads `Connected`.

After editing a file here, press the reload button of the extension in `chrome://extensions`.

## Protocol

The API runs the WebSocket server; the extension is the client.

| Direction | Message | Meaning |
| --- | --- | --- |
| API → extension | `{ "id", "method": "batch_rpc", "params": { "rpcid", "freq", "captchaAction"?, "match"? } }` | run one Flow `batchexecute` call inside the Flow tab; `__CAPTCHA__` in `freq` is replaced by a fresh reCAPTCHA token |
| API → extension | `{ "type": "open_flow_tab" }` | focus a Flow tab, or open one |
| API → extension | `{ "type": "pong" }` | answer to the extension's keep-alive |
| extension → API | `{ "id", "status", "data" \| "error" }` | answer to a call with the same `id` |
| extension → API | `{ "type": "extension_ready" \| "ping" \| "netlog" \| "media_urls_refresh", … }` | events; the API answers `ping` and ignores the rest |

The extension ignores every other message. Whatever listens on the agent port gets these three commands
only, never code to run in the Flow tab or the Flow bearer token.

## Changes from flowkit

- The agent address is `ws://127.0.0.1:{Agent port}` (popup field, stored in `chrome.storage.local`)
  instead of the fixed `ws://127.0.0.1:9222`.
- Answers and netlog records go over the WebSocket; flowkit's HTTP callbacks to `127.0.0.1:8100` and that
  host permission are gone.
- `{ "type": "open_flow_tab" }` from the API opens or focuses a Flow tab, sharing the popup's
  `Open Flow Tab` code.
- Only `batch_rpc`, `open_flow_tab` and `pong` are handled. flowkit's other agent commands are gone —
  `eval_tab`, `debug_tab`, `find_actions`, `api_request`, `trpc_request`, `solve_captcha`, `reload_extension`,
  `reload_flow_tab`, `list_tabs`, `submit_ui_prompt`, `get_status`, `callback_secret` — and so are the
  `token_captured` event and the `customPath` param of `batch_rpc`.
