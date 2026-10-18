import {
  CLONE_MAX_FRAMES_HINT,
  CLONE_MAX_FRAMES_LOWER_LIMIT,
  CLONE_MAX_FRAMES_UPPER_LIMIT,
} from "@/features/filmClones/constants";
import { NumberField } from "./NumberField";

interface CloneMaxFramesFieldProps {
  value: string;
  isDisabled: boolean;
  onChange: (value: string) => void;
}

export function CloneMaxFramesField({ value, isDisabled, onChange }: CloneMaxFramesFieldProps) {
  return (
    <NumberField
      label="Max frames"
      value={value}
      min={CLONE_MAX_FRAMES_LOWER_LIMIT}
      max={CLONE_MAX_FRAMES_UPPER_LIMIT}
      hint={CLONE_MAX_FRAMES_HINT}
      isDisabled={isDisabled}
      onChange={onChange}
    />
  );
}
