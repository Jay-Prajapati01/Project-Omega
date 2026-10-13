import { createClient } from "@supabase/supabase-js";

type ContactSubmission = {
  name: string;
  email: string;
  company: string | null;
  topic: string;
  message: string;
};

type Database = {
  public: {
    Tables: {
      contact_submissions: {
        Row: ContactSubmission;
        Insert: ContactSubmission;
        Update: Partial<ContactSubmission>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
  };
};

let client: ReturnType<typeof createClient<Database>> | null = null;

/**
 * Lazily-created Supabase client (auth sessions, sign in/out, token refresh
 * for authenticated API calls). Created on first use — never at build time —
 * so missing env vars can't break prerendering.
 */
export function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase is not configured (NEXT_PUBLIC_SUPABASE_URL and an anon key)."
    );
  }
  if (!client) client = createClient<Database>(url, key);
  return client;
}
