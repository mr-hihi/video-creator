# Template — Redux slice

```ts
// features/jobs/uploadPreferencesSlice.ts
interface UploadPreferencesState {
  language: UploadLanguage;
}

const initialState: UploadPreferencesState = {
  language: DEFAULT_UPLOAD_LANGUAGE,
};

export const uploadPreferencesSlice = createSlice({
  name: "uploadPreferences",
  initialState,
  reducers: {
    languageChanged(state, action: PayloadAction<UploadLanguage>) {
      state.language = action.payload;
    },
  },
  selectors: {
    selectUploadLanguage: (state) => state.language,
  },
});

export const { languageChanged } = uploadPreferencesSlice.actions;
export const { selectUploadLanguage } = uploadPreferencesSlice.selectors;
```

```ts
// store/index.ts
reducer: { [uploadPreferencesSlice.reducerPath]: uploadPreferencesSlice.reducer },
```
