import { Checkbox } from "@/components/atoms/Checkbox";

interface CheckboxFieldProps {
  label: string;
  isChecked: boolean;
  isDisabled?: boolean;
  onChange: (isChecked: boolean) => void;
}

export function CheckboxField({ label, isChecked, isDisabled = false, onChange }: CheckboxFieldProps) {
  return (
    <label className="inline-flex items-center gap-2 text-sm has-[:disabled]:cursor-not-allowed has-[:disabled]:text-muted">
      <Checkbox checked={isChecked} disabled={isDisabled} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}
