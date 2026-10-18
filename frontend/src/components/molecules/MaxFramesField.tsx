import { MAX_FRAMES_HINT, MAX_FRAMES_LOWER_LIMIT, MAX_FRAMES_UPPER_LIMIT } from "@/features/jobs/constants";
import { NumberField } from "./NumberField";

interface MaxFramesFieldProps {
  value: string;
  isDisabled: boolean;
  onChange: (value: string) => void;
}

export function MaxFramesField({ value, isDisabled, onChange }: MaxFramesFieldProps) {
  return (
    <NumberField
      label="Max frames"
      value={value}
      min={MAX_FRAMES_LOWER_LIMIT}
      max={MAX_FRAMES_UPPER_LIMIT}
      hint={MAX_FRAMES_HINT}
      isDisabled={isDisabled}
      onChange={onChange}
    />
  );
}
