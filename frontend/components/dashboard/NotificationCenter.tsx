"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import {
  Bell,
  Check,
  CheckCheck,
  Trash2,
  Brain,
  Search,
  MessageSquare,
  Network,
  AlertCircle,
  Clock,
} from "lucide-react";
import { useAppStore, Notification } from "@/lib/store";

const TYPE_CONFIG: Record<string, { icon: typeof Bell; color: string }> = {
  processing_started: { icon: Clock, color: "var(--brand)" },
  processing_completed: { icon: Check, color: "var(--success)" },
  processing_failed: { icon: AlertCircle, color: "var(--danger)" },
  knowledge_added: { icon: Brain, color: "var(--brand)" },
  graph_updated: { icon: Network, color: "var(--info)" },
  embedding_finished: { icon: Brain, color: "var(--brand)" },
  search_completed: { icon: Search, color: "var(--success)" },
  ai_finished: { icon: MessageSquare, color: "var(--success)" },
  system_update: { icon: AlertCircle, color: "var(--warning)" },
  warning: { icon: AlertCircle, color: "var(--warning)" },
};

function timeAgo(ts: number) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function NotificationCard({
  notification,
  onRead,
}: {
  notification: Notification;
  onRead: (id: string) => void;
}) {
  const router = useRouter();
  const config = TYPE_CONFIG[notification.type] || TYPE_CONFIG.system_update;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      onClick={() => {
        onRead(notification.id);
        if (notification.href) router.push(notification.href);
      }}
      className={`flex gap-3 rounded-[12px] p-3 transition-colors cursor-pointer ${
        notification.read
          ? "hover:bg-surface"
          : "bg-brand-soft/20 hover:bg-brand-soft/40"
      }`}
    >
      <div
        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[8px] bg-surface"
      >
        <Icon className="h-4 w-4" style={{ color: config.color }} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-[12px] font-medium ${notification.read ? "text-foreground-3" : "text-foreground font-semibold"}`}>
            {notification.title}
          </span>
          {!notification.read && (
            <div className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand" />
          )}
        </div>
        <p className="text-[11px] text-muted line-clamp-2">{notification.description}</p>
        <span className="text-[10px] text-subtle">{timeAgo(notification.timestamp)}</span>
      </div>
    </motion.div>
  );
}

export function NotificationCenter() {
  const drawerOpen = useAppStore((s) => s.notificationDrawerOpen);
  const setDrawerOpen = useAppStore((s) => s.setNotificationDrawerOpen);
  const notifications = useAppStore((s) => s.notifications);
  const markRead = useAppStore((s) => s.markNotificationRead);
  const markAllRead = useAppStore((s) => s.markAllNotificationsRead);
  const clearAll = useAppStore((s) => s.clearNotifications);
  const drawerRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        setDrawerOpen(false);
      }
    };
    if (drawerOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [drawerOpen, setDrawerOpen]);

  return (
    <div ref={drawerRef} className="relative">
      <button
        onClick={() => setDrawerOpen(!drawerOpen)}
        aria-label="Notifications"
        aria-expanded={drawerOpen}
        className="relative flex h-10 w-10 items-center justify-center rounded-[12px] border-2 border-ink bg-card text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-brand px-1"
          >
            <span className="text-[9px] font-bold text-ink">{unreadCount > 9 ? "9+" : unreadCount}</span>
          </motion.div>
        )}
      </button>

      <AnimatePresence>
        {drawerOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-[380px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-[16px] border-2 border-ink bg-card text-foreground shadow-floating"
          >
            <div className="flex items-center justify-between border-b-2 border-ink px-4 py-3">
              <div className="flex items-center gap-2">
                <h3 className="text-[13px] font-semibold text-foreground">Notifications</h3>
                {unreadCount > 0 && (
                  <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-semibold text-brand">
                    {unreadCount} new
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] text-muted transition-colors hover:bg-surface hover:text-foreground"
                  >
                    <CheckCheck className="h-3 w-3" />
                    Mark all read
                  </button>
                )}
                <button
                  onClick={clearAll}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] text-muted transition-colors hover:bg-surface hover:text-foreground"
                >
                  <Trash2 className="h-3 w-3" />
                  Clear
                </button>
              </div>
            </div>

            <div className="max-h-[400px] overflow-y-auto p-2">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center py-10 text-center">
                  <Bell className="mb-2 h-6 w-6 text-subtle" />
                  <p className="text-[12px] text-muted">No notifications yet</p>
                  <p className="text-[10px] text-subtle">Activity will appear here</p>
                </div>
              ) : (
                <AnimatePresence>
                  {notifications.map((n) => (
                    <NotificationCard key={n.id} notification={n} onRead={markRead} />
                  ))}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
