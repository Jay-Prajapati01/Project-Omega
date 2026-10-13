export function metadataBaseForSite(): URL | undefined {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!siteUrl) return undefined;
  try {
    const parsed = new URL(siteUrl);
    return parsed.protocol === "https:" ? parsed : undefined;
  } catch {
    return undefined;
  }
}
