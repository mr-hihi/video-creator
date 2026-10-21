import { LOCAL_MODEL_LINE, MODEL_FIELD_HELP_TEXTS, MODEL_FIELD_LABELS } from "@/features/providers/constants";
import type { GenerationMediaKind, ModelIdsByKind, Provider } from "@/features/providers/types";
import {
  buildModelOptions,
  buildProviderHelpText,
  listModelMediaKinds,
  resolveSavedModelId,
} from "@/features/providers/utils";
import { SelectField } from "./SelectField";

interface ProviderModelFieldsProps {
  provider: Provider;
  mediaKinds: readonly GenerationMediaKind[];
  draftModelIdsByKind: ModelIdsByKind;
  isDisabled: boolean;
  onChange: (mediaKind: GenerationMediaKind, modelId: string) => void;
}

export function ProviderModelFields({
  provider,
  mediaKinds,
  draftModelIdsByKind,
  isDisabled,
  onChange,
}: ProviderModelFieldsProps) {
  if (provider.kind === "local") return <p className="text-sm text-muted">{LOCAL_MODEL_LINE}</p>;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {listModelMediaKinds(provider, mediaKinds).map((mediaKind) => (
        <SelectField
          key={mediaKind}
          label={MODEL_FIELD_LABELS[mediaKind]}
          value={draftModelIdsByKind[mediaKind] ?? resolveSavedModelId(provider, mediaKind)}
          options={buildModelOptions(provider.catalog[mediaKind] ?? [])}
          helpText={buildProviderHelpText(MODEL_FIELD_HELP_TEXTS[mediaKind], provider.name)}
          isDisabled={isDisabled}
          onChange={(modelId) => onChange(mediaKind, modelId)}
        />
      ))}
    </div>
  );
}
