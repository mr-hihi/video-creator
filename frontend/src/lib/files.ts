export function hasAcceptedExtension(fileName: string, acceptedExtensions: readonly string[]): boolean {
  const lowerCaseFileName = fileName.toLowerCase();
  return acceptedExtensions.some((extension) => lowerCaseFileName.endsWith(extension));
}
