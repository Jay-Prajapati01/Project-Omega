import { create } from "zustand";
import { persist } from "zustand/middleware";

interface Settings {
  topK: number;
  defaultSourceFilter: string;
  theme: "dark" | "light" | "system";
  accentColor: "orange" | "purple" | "blue" | "green" | "rose";
  density: "comfortable" | "compact";
  animations: "enabled" | "reduced";
  apiKey: string;
}

export interface Notification {
  id: string;
  type: "processing_started" | "processing_completed" | "processing_failed" | "knowledge_added" | "graph_updated" | "embedding_finished" | "search_completed" | "ai_finished" | "system_update" | "warning";
  title: string;
  description: string;
  timestamp: number;
  read: boolean;
  sourceType?: string;
  sourceId?: string;
  href?: string;
}

interface AppState {
  settings: Settings;
  recentSearches: string[];
  recentQuestions: string[];
  notifications: Notification[];
  commandPaletteOpen: boolean;
  notificationDrawerOpen: boolean;
  settingsDropdownOpen: boolean;
  addSourceDropdownOpen: boolean;
  setSettings: (partial: Partial<Settings>) => void;
  addSearch: (q: string) => void;
  addQuestion: (q: string) => void;
  addNotification: (n: Omit<Notification, "id" | "timestamp" | "read">) => void;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  clearNotifications: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setNotificationDrawerOpen: (open: boolean) => void;
  setSettingsDropdownOpen: (open: boolean) => void;
  setAddSourceDropdownOpen: (open: boolean) => void;
}

const MAX = 10;
const MAX_NOTIFICATIONS = 50;

let notifCounter = 0;

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      settings: {
        topK: 5,
        defaultSourceFilter: "",
        theme: "light",
        accentColor: "orange",
        density: "comfortable",
        animations: "enabled",
        apiKey: "",
      },
      recentSearches: [],
      recentQuestions: [],
      notifications: [],
      commandPaletteOpen: false,
      notificationDrawerOpen: false,
      settingsDropdownOpen: false,
      addSourceDropdownOpen: false,
      setSettings: (partial) =>
        set((s) => ({ settings: { ...s.settings, ...partial } })),
      addSearch: (q) =>
        set((s) => ({
          recentSearches: [q, ...s.recentSearches.filter((x) => x !== q)].slice(
            0,
            MAX
          ),
        })),
      addQuestion: (q) =>
        set((s) => ({
          recentQuestions: [
            q,
            ...s.recentQuestions.filter((x) => x !== q),
          ].slice(0, MAX),
        })),
      addNotification: (n) =>
        set((s) => ({
          notifications: [
            { ...n, id: `notif_${Date.now()}_${notifCounter++}`, timestamp: Date.now(), read: false },
            ...s.notifications,
          ].slice(0, MAX_NOTIFICATIONS),
        })),
      markNotificationRead: (id) =>
        set((s) => ({
          notifications: s.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),
      markAllNotificationsRead: () =>
        set((s) => ({
          notifications: s.notifications.map((n) => ({ ...n, read: true })),
        })),
      clearNotifications: () => set({ notifications: [] }),
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
      setNotificationDrawerOpen: (open) => set({ notificationDrawerOpen: open }),
      setSettingsDropdownOpen: (open) => set({ settingsDropdownOpen: open }),
      setAddSourceDropdownOpen: (open) => set({ addSourceDropdownOpen: open }),
    }),
    { name: "mindmesh-store" }
  )
);
