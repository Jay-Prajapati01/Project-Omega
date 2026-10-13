import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!base) return [];
  try {
    const origin = new URL(base);
    if (origin.protocol !== "https:") return [];
    return ["", "/contact", "/faq", "/privacy"].map((path) => ({
      url: new URL(path, origin).toString(),
      changeFrequency: path === "" ? "weekly" : "monthly",
      priority: path === "" ? 1 : 0.5,
    }));
  } catch {
    return [];
  }
}
