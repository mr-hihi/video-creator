# Workflow — adding a component

Template: [template-component.md](../templates/template-component.md).

1. Search `components/` for an existing one ([components.md](../components.md) lists them).
2. Pick the level with [structure.md](../structure.md): no app imports → atom; composes atoms → molecule; needs a query or the store → organism; layout slots → template.
3. Create `components/<level>/<Name>.tsx` from the template; props interface, token classes only.
4. Add `"use client"` only if it uses state, effects, refs or browser APIs.
5. `npm run lint && npm run build`.
