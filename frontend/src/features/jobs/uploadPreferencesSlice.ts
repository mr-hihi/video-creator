import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { DEFAULT_UPLOAD_LANGUAGE, type UploadLanguage } from "./constants";

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
