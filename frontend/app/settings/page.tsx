"use client";

import { useQuery } from "@tanstack/react-query";
import { API_URL, getStats } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  applyThemeToDOM,
  applyAccentToDOM,
  applyDensityToDOM,
} from "@/components/ThemeEffect";
import { Palette, Zap, LayoutGrid, Moon, Sun, Monitor } from "lucide-react";

export default function SettingsPage() {
  const { settings, setSettings } = useAppStore();
  const { data } = useQuery({ queryKey: ["stats"], queryFn: getStats });

  const segmentCls = (active: boolean) =>
    `flex flex-1 items-center justify-center gap-2 rounded-[12px] border-2 px-4 py-2.5 text-[13px] font-bold transition-all ${
      active
        ? "brut-btn bg-brand text-ink"
        : "border-ink bg-surface text-foreground-3 hover:bg-card hover:text-foreground"
    }`;

  return (
    <div className="max-w-2xl">
      <h1 className="mb-1 text-2xl font-bold text-foreground">Settings</h1>
      <p className="mb-6 text-sm text-muted">
        Appearance, backend configuration and retrieval preferences.
      </p>

      <div className="space-y-4">
        {/* Appearance */}
        <div className="rounded-[16px] border-2 border-ink bg-card p-5 shadow-card">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-foreground">
            <Palette className="h-4 w-4 text-brand" />
            Appearance
          </h2>

          {/* Theme */}
          <div className="mb-5">
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">
              Theme
            </div>
            <div className="flex gap-2">
              {[
                { id: "dark" as const, icon: Moon, label: "Dark" },
                { id: "light" as const, icon: Sun, label: "Light" },
                { id: "system" as const, icon: Monitor, label: "System" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => {
                    setSettings({ theme: t.id });
                    applyThemeToDOM(t.id);
                  }}
                  className={segmentCls(settings.theme === t.id)}
                >
                  <t.icon className="h-4 w-4" />
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Accent color */}
          <div className="mb-5">
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">
              Accent Color
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  setSettings({ accentColor: "orange" });
                  applyAccentToDOM("orange");
                }}
                aria-label="Orange accent"
                className="h-8 w-8 rounded-full border-2 border-ink bg-orange shadow-brut transition-transform hover:-translate-y-0.5"
              />
              <span className="text-[12px] text-muted">Orange — the only accent in the stack</span>
            </div>
          </div>

          {/* Density */}
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-muted">
              <LayoutGrid className="h-3.5 w-3.5" />
              Density
            </div>
            <div className="flex gap-2">
              {(["comfortable", "compact"] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => {
                    setSettings({ density: d });
                    applyDensityToDOM(d);
                  }}
                  className={`${segmentCls(settings.density === d)} capitalize`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Animations */}
          <div>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-muted">
              <Zap className="h-3.5 w-3.5" />
              Animations
            </div>
            <div className="flex gap-2">
              {(["enabled", "reduced"] as const).map((a) => (
                <button
                  key={a}
                  onClick={() => setSettings({ animations: a })}
                  className={`${segmentCls(settings.animations === a)} capitalize`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Backend */}
        <div className="rounded-[16px] border-2 border-ink bg-card p-5 shadow-card">
          <h2 className="mb-3 text-sm font-bold text-foreground">Backend</h2>
          <Row label="API URL" value={API_URL} />
          <Row label="Vector store" value={data?.vector_store ?? "qdrant"} />
          <Row label="Stored originals" value={data ? String(data.total_files_stored) : "—"} />
          <Row label="Original storage" value={data ? `${(data.total_storage_bytes / 1024 / 1024).toFixed(1)} MB` : "—"} />
          <Row
            label="Indexed chunks"
            value={data ? String(data.indexed_chunks) : "—"}
          />
        </div>

        {/* Retrieval */}
        <div className="rounded-[16px] border-2 border-ink bg-card p-5 shadow-card">
          <h2 className="mb-3 text-sm font-bold text-foreground">Retrieval</h2>
          <label className="mb-2 block text-sm text-muted">
            Results per query (top K)
          </label>
          <input
            type="number"
            min={1}
            max={20}
            aria-label="Results per query (top K)"
            value={settings.topK}
            onChange={(e) =>
              setSettings({ topK: Number(e.target.value) || 5 })
            }
            className="w-24 rounded-[12px] border-2 border-ink bg-surface px-3 py-1.5 text-sm text-foreground outline-none focus:border-brand"
          />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b-2 border-ink py-2 text-sm last:border-0">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-foreground">{value}</span>
    </div>
  );
}
