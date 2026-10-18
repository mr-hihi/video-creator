import {
  MAX_CONCURRENT_LOWER_LIMIT,
  MAX_CONCURRENT_UPPER_LIMIT,
  MIN_INTERVAL_LOWER_LIMIT_S,
  MIN_INTERVAL_UPPER_LIMIT_S,
} from "@/features/providers/constants";
import { NumberField } from "./NumberField";

interface ProviderPacingFieldsProps {
  maxConcurrent: string;
  minIntervalS: string;
  isDisabled: boolean;
  onMaxConcurrentChange: (maxConcurrent: string) => void;
  onMinIntervalChange: (minIntervalS: string) => void;
}

export function ProviderPacingFields({
  maxConcurrent,
  minIntervalS,
  isDisabled,
  onMaxConcurrentChange,
  onMinIntervalChange,
}: ProviderPacingFieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <NumberField
        label="Concurrent requests"
        value={maxConcurrent}
        min={MAX_CONCURRENT_LOWER_LIMIT}
        max={MAX_CONCURRENT_UPPER_LIMIT}
        isDisabled={isDisabled}
        onChange={onMaxConcurrentChange}
      />
      <NumberField
        label="Seconds between requests"
        value={minIntervalS}
        min={MIN_INTERVAL_LOWER_LIMIT_S}
        max={MIN_INTERVAL_UPPER_LIMIT_S}
        isDisabled={isDisabled}
        onChange={onMinIntervalChange}
      />
    </div>
  );
}
