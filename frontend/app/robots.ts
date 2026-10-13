import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  let sitemap: string | undefined;
  try {
    const origin = siteUrl ? new URL(siteUrl) : undefined;
    if (origin?.protocol === "https:") sitemap = new URL("/sitemap.xml", origin).toString();
  } catch { /* Keep robots usable until a valid production domain is configured. */ }
  return {
    rules: [{ userAgent: "*", allow: ["/", "/contact", "/faq", "/privacy"], disallow: ["/admin", "/dashboard", "/workspace", "/profile", "/settings", "/stored", "/chat", "/search", "/pricing", "/thank-you"] }],
    ...(sitemap ? { sitemap } : {}),
  };
}
