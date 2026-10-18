# Workflow — adding a page

Template: [template-page.md](../templates/template-page.md).

1. Read the App Router routing guide in `node_modules/next/dist/docs/` (dynamic `params` is a Promise in Next 16).
2. Create `src/app/<route>/page.tsx`: export `metadata`, render a template with organisms in its slots — no data fetching.
3. Add a template in `components/templates/` if the layout is new.
4. Link to it with a path builder in `features/<feature>/utils.ts` (see `buildJobDetailPath`).
5. `npm run build` and confirm the route appears in the build output.
