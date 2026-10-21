import { Button } from "@/components/atoms/Button";
import { TextField } from "./TextField";

interface ApiKeyFieldProps {
  value: string;
  placeholder: string | undefined;
  helpText: string;
  hasStoredKey: boolean;
  isDisabled: boolean;
  isRemoveDisabled: boolean;
  onChange: (apiKey: string) => void;
  onRemove: () => void;
}

export function ApiKeyField({
  value,
  placeholder,
  helpText,
  hasStoredKey,
  isDisabled,
  isRemoveDisabled,
  onChange,
  onRemove,
}: ApiKeyFieldProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <div className="min-w-0 flex-1">
        <TextField
          label="API key"
          type="password"
          value={value}
          placeholder={placeholder}
          helpText={helpText}
          isDisabled={isDisabled}
          onChange={onChange}
        />
      </div>
      {hasStoredKey && (
        <Button variant="secondary" disabled={isRemoveDisabled} onClick={onRemove}>
          Remove key
        </Button>
      )}
    </div>
  );
}
