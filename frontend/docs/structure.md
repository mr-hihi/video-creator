# frontend structure (Atomic Design)

```
src/
├── app/                       # routes + layout + providers; assemble templates + organisms only
├── components/
│   ├── atoms/                 # no app imports: Button, Badge, Select, ProgressBar, Panel, ErrorAlert…
│   ├── molecules/             # atoms composed: Captcha, FileDropField, JobStatusBadge, JobStepProgress…
│   ├── organisms/             # molecules + queries/store: UploadVideoForm, JobList, JobDetailPanel, MarkdownPreview
│   └── templates/             # page skeletons taking slots: PageTemplate, HomeTemplate, JobDetailTemplate
├── features/<feature>/        # types.ts, constants.ts, utils.ts, queries.ts, <name>Slice.ts
├── store/                     # createAppStore + typed hooks (useAppDispatch / useAppSelector)
└── lib/                       # api/client.ts, query/queryClient.ts, captcha/, format.ts, files.ts, constants.ts
```

## Placement rules

| Level | May import | Must not |
| --- | --- | --- |
| atom | React, other atoms' style helpers | features, store, lib/api |
| molecule | atoms, sibling molecules, `lib/` helpers, `features/*/{types,constants,utils}.ts` | queries, store |
| organism | molecules, atoms, `features/*/queries.ts`, store hooks, URL builders from `lib/api/client.ts` | `apiFetch` / `apiUpload` |
| template | atoms, other templates, `lib/constants.ts` | queries, store |
| page (`app/`) | templates, organisms | data fetching |

- **Critical** — organisms live in `components/organisms/`, not in `features/`; `features/` holds types, constants, pure helpers, query hooks and slices.
- **Preferred** — a pure helper used by one feature goes to `features/<feature>/utils.ts`; used app-wide → `lib/`.
- **Preferred** — shared class strings go in a sibling `*Styles.ts` (`buttonStyles.ts`), not duplicated.
