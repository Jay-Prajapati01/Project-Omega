"use client";

import { useEffect, useState } from "react";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";
import { useAppStore } from "@/lib/store";
import { applyThemeToDOM } from "./ThemeEffect";

/**
 * Controlled wrapper around AnimatedThemeToggler wired to the app's
 * zustand settings store (source of truth, persisted).
 *
 * `applyThemeToDOM` is called synchronously inside `onThemeChange` so the
 * `<html>` class flips inside the View Transition callback — React effects
 * run too late and the transition would snapshot the old theme.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useAppStore((s) => s.settings.theme);
  const setSettings = useAppStore((s) => s.setSettings);
  const [systemDark, setSystemDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemDark(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const resolved: "light" | "dark" =
    theme === "system" ? (systemDark ? "dark" : "light") : theme;

  return (
    <AnimatedThemeToggler
      className={className}
      theme={mounted ? resolved : "dark"}
      onThemeChange={(next) => {
        applyThemeToDOM(next);
        setSettings({ theme: next });
      }}
    />
  );
}
