# Workspace structure

```
video-tool/
├── api/            # Python FastAPI app — see api/docs/structure.md
├── frontend/       # Next.js app — see frontend/docs/structure.md
├── tools/local-servers/  # HTTP adapters for OmniVoice, ACE-Step, YuE — run by the user, see its README
├── tools/mock-providers/ # mock media providers for the test stack, see its README
├── tools/mock-ai/        # mock claude CLI, Gemini, OpenAI and whisper for the test stack, see its README
├── extension/google-flow/ # Chrome extension bridging Google Flow to the API, see its README
├── docs/           # workspace-wide docs (this hub); design/ holds one note per feature
├── .claude/        # reading-discipline hooks + settings (temp/ ignored)
├── run.sh          # workspace orchestrator
├── .node-version   # Node pin for frontend tooling
└── README.md
```

## Boundaries

- **Critical** — `frontend` talks to `api` over HTTP only. Never import across packages.
- **Critical** — runtime data stays in `api/storage/` (dev) and `api/storage-test/` (test stack). Both are ignored; never read or write them from the frontend.
- **Preferred** — add a `shared/` package only when both sides need the same generated types. Until then the contract lives in [dependency-graph.md](dependency-graph.md).
- A new app goes at the root as its own folder with its own `AGENTS.md` — see [workflows/workflow-adding-a-package.md](workflows/workflow-adding-a-package.md).
