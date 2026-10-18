import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { ProviderId } from "@/features/providers/types";
import { ProviderSetUpLink } from "./ProviderSetUpLink";

interface ProviderNotSetUpAlertProps {
  providerId: ProviderId;
  providerName: string;
}

export function ProviderNotSetUpAlert({ providerId, providerName }: ProviderNotSetUpAlertProps) {
  return (
    <ErrorAlert>
      {providerName} is not set up — add its key in <ProviderSetUpLink providerId={providerId} />.
    </ErrorAlert>
  );
}
