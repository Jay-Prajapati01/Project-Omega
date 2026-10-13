import {
  Youtube,
  Instagram,
  FileText,
  Files,
  Mic,
  Globe,
  Database,
  type LucideIcon,
} from "lucide-react";

export type SourceType = "youtube" | "instagram" | "pdf" | "document" | "audio" | "web" | string;

export interface SourceTheme {
  name: string;
  accent: string;
  softDark: string;
  softLight: string;
  borderDark: string;
  borderLight: string;
  icon: LucideIcon;
}

export const SOURCE_THEMES: Record<string, SourceTheme> = {
  youtube: {
    name: "YouTube",
    accent: "#FF5C00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: Youtube,
  },
  instagram: {
    name: "Instagram",
    accent: "#FF5C00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: Instagram,
  },
  pdf: {
    name: "PDF",
    accent: "#E14E00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: FileText,
  },
  document: {
    name: "Document",
    accent: "#E14E00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: Files,
  },
  audio: {
    name: "Audio",
    accent: "#FF5C00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: Mic,
  },
  web: {
    name: "Web",
    accent: "#E14E00",
    softDark: "rgba(255, 107, 0, 0.16)",
    softLight: "rgba(255, 92, 0, 0.10)",
    borderDark: "#F5EEDD",
    borderLight: "#1A120B",
    icon: Globe,
  },
};

export function getSourceTheme(type: SourceType): SourceTheme {
  const normalized = (type || "").toLowerCase();
  return SOURCE_THEMES[normalized] || {
    name: type || "Source",
    accent: "var(--brand)",
    softDark: "var(--brand-soft)",
    softLight: "var(--brand-soft)",
    borderDark: "var(--border)",
    borderLight: "var(--border)",
    icon: Database,
  };
}

export function getSourceBadgeStyle(type: SourceType, isDark: boolean = true) {
  const theme = getSourceTheme(type);
  return {
    color: theme.accent,
    backgroundColor: isDark ? theme.softDark : theme.softLight,
    borderColor: isDark ? theme.borderDark : theme.borderLight,
  };
}
