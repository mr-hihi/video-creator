import { createContext, useCallback, useContext, useEffect, useId, useState } from "react";

export type UnsavedChangesReporter = (formKey: string, hasUnsavedChanges: boolean) => void;

export interface UnsavedPageChanges {
  hasUnsavedChanges: boolean;
  reportUnsavedChanges: UnsavedChangesReporter;
}

export const UNSAVED_CHANGES_CONFIRMATION = "Discard unsaved changes?";

const NO_UNSAVED_FORM_KEYS: ReadonlySet<string> = new Set();
const PRIMARY_MOUSE_BUTTON = 0;
const SAME_TAB_LINK_TARGETS: ReadonlySet<string> = new Set(["", "_self"]);
const CAPTURE_PHASE_LISTENER_OPTIONS = { capture: true } as const;

function ignoreUnsavedChanges(): void {}

export const UnsavedChangesContext = createContext<UnsavedChangesReporter>(ignoreUnsavedChanges);

export function useUnsavedChangesReport(hasUnsavedChanges: boolean): void {
  const reportUnsavedChanges = useContext(UnsavedChangesContext);
  const formKey = useId();

  useEffect(() => {
    reportUnsavedChanges(formKey, hasUnsavedChanges);
    return () => reportUnsavedChanges(formKey, false);
  }, [reportUnsavedChanges, formKey, hasUnsavedChanges]);
}

export function useUnsavedPageChanges(): UnsavedPageChanges {
  const [unsavedFormKeys, setUnsavedFormKeys] = useState(NO_UNSAVED_FORM_KEYS);
  const hasUnsavedChanges = unsavedFormKeys.size > 0;

  useLeavePageConfirmation(hasUnsavedChanges);

  const reportUnsavedChanges = useCallback((formKey: string, hasFormUnsavedChanges: boolean) => {
    setUnsavedFormKeys((currentFormKeys) => updateUnsavedFormKeys(currentFormKeys, formKey, hasFormUnsavedChanges));
  }, []);

  return { hasUnsavedChanges, reportUnsavedChanges };
}

function useLeavePageConfirmation(hasUnsavedChanges: boolean): void {
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    const confirmLeavingThroughLink = (event: MouseEvent) => {
      if (!isInAppNavigationClick(event) || window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    window.addEventListener("click", confirmLeavingThroughLink, CAPTURE_PHASE_LISTENER_OPTIONS);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      window.removeEventListener("click", confirmLeavingThroughLink, CAPTURE_PHASE_LISTENER_OPTIONS);
    };
  }, [hasUnsavedChanges]);
}

function updateUnsavedFormKeys(
  unsavedFormKeys: ReadonlySet<string>,
  formKey: string,
  hasUnsavedChanges: boolean,
): ReadonlySet<string> {
  if (unsavedFormKeys.has(formKey) === hasUnsavedChanges) return unsavedFormKeys;
  const nextFormKeys = new Set(unsavedFormKeys);
  if (hasUnsavedChanges) nextFormKeys.add(formKey);
  else nextFormKeys.delete(formKey);
  return nextFormKeys;
}

function isInAppNavigationClick(event: MouseEvent): boolean {
  if (event.button !== PRIMARY_MOUSE_BUTTON || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return false;
  }
  const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!(link instanceof HTMLAnchorElement) || link.hasAttribute("download")) return false;
  const isSameTabLink = SAME_TAB_LINK_TARGETS.has(link.target);
  return isSameTabLink && link.origin === window.location.origin && link.href !== window.location.href;
}
