# Workflow — adding Redux state

Template: [template-redux-state.md](../templates/template-redux-state.md).

1. Check [state-management.md](../state-management.md): server data → TanStack Query, one component → `useState`. Only shared UI state goes to Redux.
2. Create `features/<feature>/<name>Slice.ts` with `createSlice` (`reducers` named as events, `selectors`).
3. Register it in `store/index.ts` under `[slice.reducerPath]`.
4. Read with `useAppSelector(selectX)`, write with `useAppDispatch()(eventHappened(payload))`.
