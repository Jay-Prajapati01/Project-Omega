"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { BadgeCheck, Building2, CalendarDays, CheckCircle2, Globe2, Mail, MapPin, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "@/components/CloudAuthGate";
import { getSupabase } from "@/lib/supabaseClient";
import { useToast } from "@/components/ui";
import { getEntitlement, type Entitlement } from "@/lib/commerce";

type ProfileData = {
  full_name: string;
  preferred_name: string;
  organization: string;
  role: string;
  location: string;
  website: string;
  bio: string;
};

const emptyProfile: ProfileData = {
  full_name: "", preferred_name: "", organization: "", role: "", location: "", website: "", bio: "",
};

function metadataValue(metadata: Record<string, unknown>, key: keyof ProfileData) {
  const value = metadata[key];
  return typeof value === "string" ? value : "";
}

export default function ProfilePage() {
  const { session, ready } = useAuth();
  const { notify } = useToast();
  const user = session?.user;
  const [profile, setProfile] = useState<ProfileData>(emptyProfile);
  const [saving, setSaving] = useState(false);
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);

  useEffect(() => {
    if (!user) return;
    const metadata = user.user_metadata as Record<string, unknown>;
    setProfile({
      full_name: metadataValue(metadata, "full_name"),
      preferred_name: metadataValue(metadata, "preferred_name"),
      organization: metadataValue(metadata, "organization"),
      role: metadataValue(metadata, "role"),
      location: metadataValue(metadata, "location"),
      website: metadataValue(metadata, "website"),
      bio: metadataValue(metadata, "bio"),
    });
  }, [user]);
  useEffect(() => { if (user) getEntitlement().then(setEntitlement).catch(() => undefined); }, [user]);

  const displayName = profile.preferred_name || profile.full_name || user?.email?.split("@")[0] || "Member";
  const initials = useMemo(() => displayName.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase(), [displayName]);
  const joined = user?.created_at ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(user.created_at)) : "—";
  const lastSignIn = user?.last_sign_in_at ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(user.last_sign_in_at)) : "—";

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setSaving(true);
    try {
      const normalized = Object.fromEntries(Object.entries(profile).map(([key, value]) => [key, value.trim()]));
      const { error } = await getSupabase().auth.updateUser({ data: normalized });
      if (error) throw error;
      notify("Profile saved.", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to save your profile.", "error");
    } finally { setSaving(false); }
  }

  if (!ready || !user) return <p role="status">Loading your profile…</p>;
  const field = "mt-1.5 w-full rounded-xl border-2 border-ink bg-surface px-3 py-2.5 text-sm text-foreground outline-none focus:border-brand";

  return <div className="mx-auto max-w-5xl">
    <div className="mb-7 flex flex-col gap-5 rounded-3xl border-2 border-ink bg-card p-6 shadow-card sm:flex-row sm:items-center">
      <div className="grid h-20 w-20 shrink-0 place-items-center rounded-2xl border-2 border-ink bg-orange font-display text-3xl">{initials || <UserRound />}</div>
      <div className="min-w-0 flex-1">
        <p className="font-mono text-xs font-bold uppercase tracking-widest text-muted">Account profile</p>
        <h1 className="mt-1 truncate text-3xl font-extrabold">{displayName}</h1>
        <p className="mt-1 flex items-center gap-2 text-sm text-muted"><Mail className="h-4 w-4" />{user.email}</p>
      </div>
      <div className="flex items-center gap-2 rounded-full border-2 border-ink bg-surface px-3 py-2 text-sm font-bold"><ShieldCheck className="h-4 w-4 text-brand" /><span className="capitalize">{entitlement?.effective_plan || "Free"} plan</span></div>
    </div>

    <div className="grid gap-6 lg:grid-cols-[1fr_290px]">
      <form onSubmit={saveProfile} className="rounded-3xl border-2 border-ink bg-card p-5 shadow-card sm:p-6">
        <div className="mb-6"><h2 className="text-xl font-extrabold">About you</h2><p className="mt-1 text-sm text-muted">This information appears only in your MindMesh account.</p></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name"><input value={profile.full_name} maxLength={100} autoComplete="name" onChange={e => setProfile(current => ({ ...current, full_name: e.target.value }))} className={field} placeholder="Your full name" /></Field>
          <Field label="Preferred name"><input value={profile.preferred_name} maxLength={60} onChange={e => setProfile(current => ({ ...current, preferred_name: e.target.value }))} className={field} placeholder="How MindMesh should address you" /></Field>
          <Field label="Organization"><input value={profile.organization} maxLength={120} autoComplete="organization" onChange={e => setProfile(current => ({ ...current, organization: e.target.value }))} className={field} placeholder="Company, school, or team" /></Field>
          <Field label="Role"><input value={profile.role} maxLength={100} autoComplete="organization-title" onChange={e => setProfile(current => ({ ...current, role: e.target.value }))} className={field} placeholder="Your role" /></Field>
          <Field label="Location"><input value={profile.location} maxLength={120} autoComplete="address-level2" onChange={e => setProfile(current => ({ ...current, location: e.target.value }))} className={field} placeholder="City, country" /></Field>
          <Field label="Website"><input value={profile.website} maxLength={240} inputMode="url" autoComplete="url" onChange={e => setProfile(current => ({ ...current, website: e.target.value }))} className={field} placeholder="https://example.com" /></Field>
        </div>
        <Field label="About"><textarea value={profile.bio} maxLength={500} rows={5} onChange={e => setProfile(current => ({ ...current, bio: e.target.value }))} className={`${field} resize-y`} placeholder="A short note about how you use MindMesh." /></Field>
        <div className="mt-6 flex items-center justify-between gap-4 border-t-2 border-ink pt-5"><p className="text-xs text-muted">Your email and sign-in security are managed through your account.</p><button disabled={saving} className="brut-btn shrink-0 rounded-xl bg-orange px-5 py-2.5 text-sm font-bold disabled:opacity-60">{saving ? "Saving…" : "Save profile"}</button></div>
      </form>

      <aside className="space-y-4">
        <InfoCard icon={Mail} label="Email" value={user.email || "—"} />
        <InfoCard icon={BadgeCheck} label="Email status" value={user.email_confirmed_at ? "Confirmed" : "Confirmation pending"} />
        <InfoCard icon={CalendarDays} label="Member since" value={joined} />
        <InfoCard icon={CheckCircle2} label="Last sign in" value={lastSignIn} />
        <InfoCard icon={ShieldCheck} label="Current plan" value={entitlement ? `${entitlement.effective_plan} · ${entitlement.ai_mode === "byok" ? "Your AI key" : "MindMesh managed"}` : "Free"} />
        {(profile.organization || profile.role || profile.location || profile.website) && <div className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><p className="font-mono text-xs font-bold uppercase tracking-widest text-muted">Profile summary</p>{profile.organization && <p className="mt-3 flex gap-2 text-sm"><Building2 className="h-4 w-4 shrink-0" />{profile.organization}{profile.role && ` · ${profile.role}`}</p>}{profile.location && <p className="mt-3 flex gap-2 text-sm"><MapPin className="h-4 w-4 shrink-0" />{profile.location}</p>}{profile.website && <p className="mt-3 flex gap-2 break-all text-sm"><Globe2 className="h-4 w-4 shrink-0" />{profile.website}</p>}</div>}
      </aside>
    </div>
  </div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="mt-4 block text-sm font-bold">{label}{children}</label>; }
function InfoCard({ icon: Icon, label, value }: { icon: typeof Mail; label: string; value: string }) { return <div className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted"><Icon className="h-4 w-4 text-brand" />{label}</div><p className="mt-2 break-words text-sm font-bold text-foreground">{value}</p></div>; }
