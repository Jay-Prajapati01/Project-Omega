import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        card: "var(--card)",
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        border: "var(--border)",

        // Landing-page print-brutalism tokens
        paper: "var(--paper)",
        "paper-alt": "var(--paper-alt)",
        "paper-card": "var(--paper-card)",
        sheet: "var(--sheet)",
        ink: "var(--ink)",
        "ink-muted": "var(--ink-muted)",
        orange: "var(--orange)",
        "orange-hover": "var(--orange-hover)",

        foreground: "var(--foreground)",
        "foreground-2": "var(--foreground-2)",
        "foreground-3": "var(--foreground-3)",
        muted: "var(--muted)",
        subtle: "var(--subtle)",

        brand: {
          DEFAULT: "var(--brand)",
          hover: "var(--brand-hover)",
          soft: "var(--brand-soft)",
          light: "var(--brand-soft)",
        },

        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",

        // Backward compatibility mappings
        bg: "var(--background)",
        "primary-text": "var(--foreground)",
        "secondary-text": "var(--foreground-2)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        floating: "var(--shadow-floating)",
        brut: "4px 4px 0 var(--ink)",
        "brut-lg": "6px 6px 0 var(--ink)",
        "brut-xl": "8px 8px 0 var(--ink)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Anton", "Archivo Black", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      spacing: {
        page: "40px",
        section: "32px",
        card: "24px",
      },
      borderRadius: {
        card: "20px",
        button: "14px",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "slide-down": "slideDown 0.3s ease-out",
        "expand": "expand 0.3s ease-out",
        "typing": "typing 0.1s steps(1)",
        "check-pop": "checkPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)",
        "line-fill": "lineFill 0.5s ease-out forwards",
        "progress-stripe": "progressStripe 1s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideDown: {
          "0%": { opacity: "0", transform: "translateY(-8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        expand: {
          "0%": { opacity: "0", maxHeight: "0" },
          "100%": { opacity: "1", maxHeight: "500px" },
        },
        checkPop: {
          "0%": { transform: "scale(0)" },
          "60%": { transform: "scale(1.2)" },
          "100%": { transform: "scale(1)" },
        },
        lineFill: {
          "0%": { height: "0%" },
          "100%": { height: "100%" },
        },
        progressStripe: {
          "0%": { backgroundPosition: "1rem 0" },
          "100%": { backgroundPosition: "0 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
