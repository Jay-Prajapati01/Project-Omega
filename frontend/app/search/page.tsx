import { redirect } from "next/navigation";

/** Preserve old bookmarks while keeping retrieval inside the Ask AI experience. */
export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  const params = await searchParams;
  const query = Array.isArray(params.q) ? params.q[0] : params.q;
  redirect(query ? `/chat?q=${encodeURIComponent(query)}` : "/chat");
}
