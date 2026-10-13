"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Moon, Sun } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { applyThemeToDOM } from "@/components/ThemeEffect";

type Theme = "light" | "dark";

/**
 * Landing navbar theme toggle — same circular view-transition reveal as the
 * original landing, but wired into the app store so the choice persists and
 * stays in sync with the rest of the system (sidebar toggle, /settings).
 */
export function ThemeToggle() {
  const storeTheme = useAppStore((s) => s.settings.theme);
  const setSettings = useAppStore((s) => s.setSettings);
  const [theme, setTheme] = useState<Theme>("light");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const transitioning = useRef(false);

  useEffect(() => {
    if (storeTheme === "system") {
      setTheme(
        window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
      );
    } else {
      setTheme(storeTheme);
    }
  }, [storeTheme]);

  const toggleTheme = useCallback(() => {
    const button = buttonRef.current;
    if (!button || transitioning.current) return;

    const nextTheme: Theme = theme === "dark" ? "light" : "dark";
    const applyTheme = () => {
      setSettings({ theme: nextTheme });
      applyThemeToDOM(nextTheme);
      setTheme(nextTheme);
    };

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || reduceMotion) {
      applyTheme();
      return;
    }

    const bounds = button.getBoundingClientRect();
    const x = bounds.left + bounds.width / 2;
    const y = bounds.top + bounds.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    transitioning.current = true;
    document.documentElement.dataset["themeTransition"] = "active";
    const transition = document.startViewTransition(() => flushSync(applyTheme));

    transition.ready
      .then(() => {
        document.documentElement.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 520, easing: "cubic-bezier(.16,1,.3,1)", pseudoElement: "::view-transition-new(root)" },
        );
      })
      .catch(() => undefined);

    transition.finished.finally(() => {
      transitioning.current = false;
      delete document.documentElement.dataset["themeTransition"];
    });
  }, [theme, setSettings]);

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={toggleTheme}
      className="brut-btn relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl border-2 border-ink bg-sheet text-ink shadow-[3px_3px_0_var(--ink)] hover:bg-paper-alt"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      <Sun className={`absolute transition-all duration-300 ${theme === "dark" ? "rotate-0 scale-100" : "rotate-90 scale-0"}`} />
      <Moon className={`absolute transition-all duration-300 ${theme === "dark" ? "-rotate-90 scale-0" : "rotate-0 scale-100"}`} />
    </button>
  );
}
