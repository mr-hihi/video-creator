import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { ProviderId, ProviderSettings, RouteName } from "@/features/providers/types";
import {
  buildMediaProviderOptions,
  mediaProviderToOptionValue,
  optionValueToMediaProvider,
  resolveMediaProvider,
} from "@/features/settings/utils";
import { ProviderSetUpLink } from "./ProviderSetUpLink";
import { SelectField } from "./SelectField";

interface MediaProviderSelectFieldProps<TProviderId extends ProviderId> {
  label: string;
  hint: string;
  route: RouteName;
  value: TProviderId | null;
  providerIds: readonly TProviderId[];
  providerSettings: ProviderSettings;
  isDisabled: boolean;
  onChange: (providerId: TProviderId | null) => void;
}

export function MediaProviderSelectField<TProviderId extends ProviderId>({
  label,
  hint,
  route,
  value,
  providerIds,
  providerSettings,
  isDisabled,
  onChange,
}: MediaProviderSelectFieldProps<TProviderId>) {
  const routeProvider = resolveMediaProvider(providerSettings, route, null);
  const pickedProvider = resolveMediaProvider(providerSettings, route, value);

  return (
    <div className="flex flex-col gap-2">
      <SelectField
        label={label}
        value={mediaProviderToOptionValue(value)}
        options={buildMediaProviderOptions(routeProvider.name, providerIds)}
        hint={hint}
        isDisabled={isDisabled}
        onChange={(optionValue) => onChange(optionValueToMediaProvider(optionValue, providerIds))}
      />
      {!pickedProvider.isSetUp && (
        <ErrorAlert>
          {pickedProvider.name} is not set up — set it up in <ProviderSetUpLink providerId={pickedProvider.id} />.
        </ErrorAlert>
      )}
    </div>
  );
}
