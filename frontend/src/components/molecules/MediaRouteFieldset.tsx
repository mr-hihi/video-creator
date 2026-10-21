import { Badge } from "@/components/atoms/Badge";
import { IN_USE_BADGE_LABEL, type RouteField } from "@/features/providers/constants";
import type {
  GenerationMediaKind,
  ModelIdsByKind,
  ModelIdsByProvider,
  Provider,
  ProviderId,
} from "@/features/providers/types";
import { buildRouteOptions, listRouteProviders } from "@/features/providers/utils";
import { ProviderModelFields } from "./ProviderModelFields";
import { ProviderSetUpLink } from "./ProviderSetUpLink";
import { SelectField } from "./SelectField";

interface MediaRouteFieldsetProps {
  routeField: RouteField;
  routeProviderId: ProviderId;
  providers: readonly Provider[];
  inUseProviderIds: ReadonlySet<ProviderId>;
  draftModelIdsByProvider: ModelIdsByProvider;
  isDisabled: boolean;
  onRouteChange: (providerId: ProviderId) => void;
  onModelChange: (providerId: ProviderId, mediaKind: GenerationMediaKind, modelId: string) => void;
}

interface MediaProviderModelRowProps {
  provider: Provider;
  mediaKinds: readonly GenerationMediaKind[];
  isInUse: boolean;
  draftModelIdsByKind: ModelIdsByKind;
  isDisabled: boolean;
  onModelChange: (mediaKind: GenerationMediaKind, modelId: string) => void;
}

export function MediaRouteFieldset({
  routeField,
  routeProviderId,
  providers,
  inUseProviderIds,
  draftModelIdsByProvider,
  isDisabled,
  onRouteChange,
  onModelChange,
}: MediaRouteFieldsetProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-4 rounded-lg border border-border p-4">
      <legend className="px-1 text-sm font-semibold">{routeField.label}</legend>
      <SelectField
        label={routeField.label}
        value={routeProviderId}
        options={buildRouteOptions(routeField.providerIds)}
        hint={routeField.hint}
        helpText={routeField.helpText}
        isDisabled={isDisabled}
        onChange={onRouteChange}
      />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {listRouteProviders(providers, routeField.providerIds).map((provider) => (
          <MediaProviderModelRow
            key={provider.id}
            provider={provider}
            mediaKinds={routeField.mediaKinds}
            isInUse={inUseProviderIds.has(provider.id)}
            draftModelIdsByKind={draftModelIdsByProvider[provider.id] ?? {}}
            isDisabled={isDisabled}
            onModelChange={(mediaKind, modelId) => onModelChange(provider.id, mediaKind, modelId)}
          />
        ))}
      </div>
    </fieldset>
  );
}

function MediaProviderModelRow({
  provider,
  mediaKinds,
  isInUse,
  draftModelIdsByKind,
  isDisabled,
  onModelChange,
}: MediaProviderModelRowProps) {
  return (
    <article className="flex min-w-0 flex-col gap-3 rounded-lg border border-border p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 text-base font-semibold break-words">{provider.name}</h3>
        {isInUse && <Badge tone="info">{IN_USE_BADGE_LABEL}</Badge>}
      </header>
      {!provider.setUp && (
        <p className="text-xs text-muted">
          Not set up — set it up in <ProviderSetUpLink providerId={provider.id} />.
        </p>
      )}
      <ProviderModelFields
        provider={provider}
        mediaKinds={mediaKinds}
        draftModelIdsByKind={draftModelIdsByKind}
        isDisabled={isDisabled}
        onChange={onModelChange}
      />
    </article>
  );
}
