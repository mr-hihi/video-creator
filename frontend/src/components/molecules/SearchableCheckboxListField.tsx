"use client";

import { useState } from "react";
import type { SelectOption } from "@/components/atoms/Select";
import { TextInput } from "@/components/atoms/TextInput";
import { CheckboxList } from "./CheckboxList";

interface SearchableCheckboxListFieldProps {
  label: string;
  searchPlaceholder: string;
  options: readonly SelectOption<string>[];
  selectedValues: readonly string[];
  emptyText: string;
  isDisabled?: boolean;
  onChange: (selectedValues: string[]) => void;
}

export function SearchableCheckboxListField({ label, searchPlaceholder, options, ...checkboxListProps }: SearchableCheckboxListFieldProps) {
  const [searchText, setSearchText] = useState("");
  const normalizedSearchText = searchText.trim().toLowerCase();
  const matchingOptions = options.filter((option) => option.label.toLowerCase().includes(normalizedSearchText));

  return (
    <fieldset className="flex min-w-0 flex-col gap-2">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      <TextInput
        type="text"
        value={searchText}
        placeholder={searchPlaceholder}
        aria-label={`Search ${label}`}
        autoComplete="off"
        disabled={checkboxListProps.isDisabled}
        onChange={(event) => setSearchText(event.target.value)}
      />
      <CheckboxList options={matchingOptions} {...checkboxListProps} />
    </fieldset>
  );
}
