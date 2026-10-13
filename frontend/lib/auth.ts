import { getSupabase } from "./supabaseClient";

export const cloudMode = ["modal", "cloud"].includes(process.env.NEXT_PUBLIC_EXECUTION_MODE || "");

export async function authHeaders(): Promise<Record<string, string>> {
  const { data, error } = await getSupabase().auth.getSession();
  if (error || !data.session) throw new Error("Please sign in to continue.");
  return { Authorization: `Bearer ${data.session.access_token}` };
}
