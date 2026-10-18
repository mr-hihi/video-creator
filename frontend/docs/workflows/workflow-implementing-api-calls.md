# Workflow — implementing API calls

Template: [template-api-client.md](../templates/template-api-client.md).

1. Confirm the route and JSON shape in [../../../docs/dependency-graph.md](../../../docs/dependency-graph.md); if the API side is new, build it first.
2. Add / update types in `features/<feature>/types.ts`.
3. Add the key to the `jobQueryKeys` factory, a private `fetchX` / `createX` using `apiFetch` / `apiUpload`, and an exported `useX` hook in `queries.ts`.
4. Mutations invalidate the affected list key in `onSuccess`. A follow-up that must still run when the result
   remounts or removes the calling component (a notice, a navigation after a save, restore or delete) goes in
   the hook's own `onSuccess`, not in the options passed to `mutate()`: TanStack Query skips those once the
   caller has unmounted.
5. Use the hook from an organism; show `isPending` / `error` states.
6. `npm run lint` (the TanStack Query plugin checks key and dependency rules) and `npm run build`.
