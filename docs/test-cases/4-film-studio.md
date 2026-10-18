## 4. Tạo phim (Film Studio) (4-film-studio.md)

Test cases for [business/4-film-studio.md](../business/4-film-studio.md). Acronym `FS`. The cases are split
like the business doc; IDs never change when a case moves between files.

| File | Cases |
|---|---|
| [4.1-projects-and-library.md](./4-film-studio/4.1-projects-and-library.md) | TC-FS-01 → TC-FS-10, TC-FS-49 |
| [4.2-episodes-and-script.md](./4-film-studio/4.2-episodes-and-script.md) | TC-FS-11 → TC-FS-21, TC-FS-47 → TC-FS-48, TC-FS-53 |
| [4.3-scenes-and-generation.md](./4-film-studio/4.3-scenes-and-generation.md) | TC-FS-22 → TC-FS-31, TC-FS-50 → TC-FS-51, TC-FS-54 |
| [4.4-audio-and-assembly.md](./4-film-studio/4.4-audio-and-assembly.md) | TC-FS-32 → TC-FS-40 |
| [4.5-screens.md](./4-film-studio/4.5-screens.md) | TC-FS-41 → TC-FS-46, TC-FS-52 |

## Test environment

- Stack, captcha switch and app labels: as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment). Storage of this
  domain: `api/storage-test/films/`.
- Shorthand: `F` = `http://localhost:5070/films`.
- `claude` CLI logged in for every case that writes a script outside **API unit**.
- **Fake provider** — **API unit** cases register a `FakeProvider` for every media kind. It answers with the
  fixture of that kind, can be told to fail with a given error text or to hang, and records every call
  (prompt, input files, params). No credit is spent.
- *(real provider)* — a case marked so needs Google Flow (extension connected to a signed-in Flow tab) or an
  API provider set in Provider Settings, and spends credit. Keep its target length short. Without credit, run it
  against the mock providers of [tools/mock-providers/](../../tools/mock-providers/README.md): the mock Flow
  extension makes the images and clips, and the local mock speaks the narration once `Speech` is routed to
  OmniVoice at `http://127.0.0.1:5078`.
- Fixtures under `api/tests/fixtures/films/`, created with the implementation:

| Id | File | How it is made |
|---|---|---|
| IMG-P | `portrait.png` (1080×1920) | `ffmpeg -f lavfi -i color=c=navy:s=1080x1920 -frames:v 1 portrait.png` |
| IMG-L | `landscape.png` (1920×1080) | `ffmpeg -f lavfi -i color=c=teal:s=1920x1080 -frames:v 1 landscape.png` |
| IMG-BIG | `big.png` (21 MB) | `head -c 21000000 /dev/urandom > big.png` |
| CLIP-8 | `clip-8s.mp4` (8 s, 1920×1080, 24 fps, 440 Hz tone) | `ffmpeg -f lavfi -i testsrc2=size=1920x1080:rate=24 -f lavfi -i sine=frequency=440:sample_rate=48000 -t 8 -c:v libx264 -pix_fmt yuv420p -c:a aac clip-8s.mp4` |
| VOICE | `voice-sample.wav` (3–30 s of speech) | `say -o v.aiff "The solar warning flashes across the terminal. Nobody in the city knows yet."` then `ffmpeg -i v.aiff -ar 48000 voice-sample.wav` |
| VOICE-2 | `voice-2s.wav` | `ffmpeg -f lavfi -i sine=frequency=300 -t 2 voice-2s.wav` |
| NAR-3 / NAR-8 | `narration-3200ms.wav` / `narration-8s.wav` | `ffmpeg -f lavfi -i sine=frequency=500 -t 3.2 …` / `-t 8 …` |
| MUS-5 / MUS-60 | `music-5s.mp3` / `music-60s.mp3` | `ffmpeg -f lavfi -i sine=frequency=220 -t 5 …` / `-t 60 …` |

- Reference data, created through the API before the cases that name it:

| Id | Request |
|---|---|
| P1 | `POST F/projects` `{"name":"Test Series","language":"en","orientation":"landscape","styleId":"realistic","clipDurationS":8,"allowDialogue":true,"allowNarration":false,"allowMusic":false}` |
| C1 | `POST F/characters` `{"name":"Mai","entityType":"character","description":"A young woman in a red raincoat with short black hair","styleId":"realistic"}`, linked to P1 |
| C2 | `POST F/characters` `{"name":"Old Harbor","entityType":"location","description":"A foggy fishing harbor at dawn","styleId":"realistic"}`, linked to P1 |
| VT1 | `POST F/voices` with VOICE, `name=narrator-en`, `sampleText=The solar warning flashes across the terminal. Nobody in the city knows yet.` |
| FA1 | the `done` job of TC-FA-01 (domain 3) |
| K2 | the `done` film clone K2 of [5-film-clone.md](./5-film-clone.md) (`scriptLanguage` = `ja`, `aspect` = `16:9`) |
