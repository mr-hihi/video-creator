import { configureStore } from "@reduxjs/toolkit";
import { uploadPreferencesSlice } from "@/features/jobs/uploadPreferencesSlice";

export function createAppStore() {
  return configureStore({
    reducer: {
      [uploadPreferencesSlice.reducerPath]: uploadPreferencesSlice.reducer,
    },
  });
}

export type AppStore = ReturnType<typeof createAppStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
