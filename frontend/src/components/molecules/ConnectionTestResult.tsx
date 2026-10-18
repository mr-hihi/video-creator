import { Badge } from "@/components/atoms/Badge";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { CONNECTION_TEST_OK_LABEL } from "@/features/providers/constants";
import type { ConnectionTest } from "@/features/providers/types";
import { formatDateTime } from "@/lib/format";

interface ConnectionTestResultProps {
  connectionTest: ConnectionTest;
}

export function ConnectionTestResult({ connectionTest }: ConnectionTestResultProps) {
  const testedAtLabel = formatDateTime(connectionTest.testedAt);

  if (!connectionTest.ok) {
    return (
      <ErrorAlert>
        {connectionTest.error} · {testedAtLabel}
      </ErrorAlert>
    );
  }
  return (
    <p className="flex flex-wrap items-center gap-2">
      <Badge tone="success">{CONNECTION_TEST_OK_LABEL}</Badge>
      <span className="text-xs text-muted">{testedAtLabel}</span>
    </p>
  );
}
