# frontend coding conventions (delta)

Root rules first: [../../docs/coding-conventions.md](../../docs/coding-conventions.md). TypeScript / React additions:

## Naming — Critical

| Kind | Rule | Example |
| --- | --- | --- |
| Component / file | PascalCase, one per file | `JobListItem.tsx` |
| Hook | `use` + noun (+ `Query` / `Mutation`) | `useJobQuery`, `useCreateVideoToMarkdownJobMutation` |
| Util / file | camelCase verb + noun | `resolveJobImageUrl`, `formatFileSize` |
| Slice action | past-tense event | `languageChanged` |
| Constant | `UPPER_SNAKE_CASE`, unit in name | `JOB_POLL_INTERVAL_MS`, `DEFAULT_REQUEST_TIMEOUT_MS` |

## Code — Critical

- Import through the `@/` alias; relative imports only inside the same folder.
- Type every prop; type the return of exported functions in `lib/` and `features/*/utils.ts`; no `any`.
- API types mirror the contract in `features/<feature>/types.ts` (camelCase, `null` where the API sends null).
- Literals with meaning are named constants (`ACCEPTED_VIDEO_EXTENSIONS`, `HTTP_STATUS_*`).
- No `console.log`; surface errors through `ErrorAlert` using the `ApiError` message.

## Errors — Preferred

- `ApiError.isClientError` (4xx) is shown to the user as-is; transport errors say which URL failed.
- Queries don't retry 4xx (see `lib/query/queryClient.ts`).
