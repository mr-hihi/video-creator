const BYTES_PER_KILOBYTE = 1024;
const SCALED_FILE_SIZE_UNITS = ["KB", "MB", "GB", "TB"] as const;
const SCALED_FILE_SIZE_FRACTION_DIGITS = 1;
const MISSING_VALUE_PLACEHOLDER = "—";

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < BYTES_PER_KILOBYTE) return `${sizeBytes} B`;
  let scaledSize = sizeBytes / BYTES_PER_KILOBYTE;
  let unitIndex = 0;
  while (scaledSize >= BYTES_PER_KILOBYTE && unitIndex < SCALED_FILE_SIZE_UNITS.length - 1) {
    scaledSize /= BYTES_PER_KILOBYTE;
    unitIndex += 1;
  }
  return `${scaledSize.toFixed(SCALED_FILE_SIZE_FRACTION_DIGITS)} ${SCALED_FILE_SIZE_UNITS[unitIndex]}`;
}

export function formatDateTime(isoTimestamp: string): string {
  return dateTimeFormatter.format(new Date(isoTimestamp));
}

export function formatOptionalDateTime(isoTimestamp: string | null): string {
  if (isoTimestamp === null) return MISSING_VALUE_PLACEHOLDER;
  return formatDateTime(isoTimestamp);
}
