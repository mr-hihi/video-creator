import type { SelectOption } from "./Select";

const SELECTED_TAB_CLASS_NAME = "border-accent text-foreground";
const UNSELECTED_TAB_CLASS_NAME = "border-transparent text-muted hover:text-foreground";

interface TabListProps<TValue extends string> {
  label: string;
  value: TValue;
  tabs: readonly SelectOption<TValue>[];
  onChange: (value: TValue) => void;
}

export function TabList<TValue extends string>({ label, value, tabs, onChange }: TabListProps<TValue>) {
  return (
    <div role="tablist" aria-label={label} className="-mx-1 flex overflow-x-auto border-b border-border px-1">
      {tabs.map((tab) => {
        const isSelected = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            onClick={() => onChange(tab.value)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
              isSelected ? SELECTED_TAB_CLASS_NAME : UNSELECTED_TAB_CLASS_NAME
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
