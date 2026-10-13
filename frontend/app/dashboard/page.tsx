"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Plus,
  Home,
  Youtube,
  Instagram,
  Network,
  Clock,
  Database,
  Activity,
  TrendingUp,
  ArrowRight,
  Command,
  Boxes,
  MessageSquare,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from "recharts";
import { getStats } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { useAuth } from "@/components/CloudAuthGate";
import { getChartTheme } from "@/lib/chartTheme";
import { getSourceTheme } from "@/lib/sourceTheme";
import {
  NotificationCenter,
  ActivityFeed,
  BackgroundTasks,
  AISummaryBrief,
  LiveSystemStatus,
} from "@/components/dashboard";
import { AnimatedCounter } from "@/components/search/AnimatedCounter";

const PIE_COLORS = ["#FF5C00", "#E14E00", "#FF8A3D", "#B96A00", "#C64A00", "#6B5B4D"];

function getGreeting(now: Date) {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) return { text: "Good morning", emoji: "☀️" };
  if (hour >= 12 && hour < 17) return { text: "Good afternoon", emoji: "👋" };
  if (hour >= 17 && hour < 21) return { text: "Good evening", emoji: "🌆" };
  return { text: "Good night", emoji: "🌙" };
}

function getCurrentTime(now: Date) {
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const day = days[now.getDay()];
  const month = months[now.getMonth()];
  const date = now.getDate();
  const hours = now.getHours();
  const mins = now.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  const h12 = hours % 12 || 12;
  return {
    date: `${day}, ${month} ${date}`,
    time: `${h12}:${mins} ${ampm}`,
  };
}

const ADD_SOURCE_ITEMS = [
  { icon: Youtube, label: "YouTube Video", desc: "Extract & summarize", color: "#FF5C00", href: "/youtube" },
  { icon: Instagram, label: "Instagram Reel", desc: "Extract captions", color: "#FF5C00", href: "/instagram" },
  { icon: MessageSquare, label: "Ask AI", desc: "Ask across saved sources", color: "var(--brand)", href: "/chat" },
  { icon: Database, label: "Stored", desc: "Browse your knowledge", color: "#B96A00", href: "/stored" },
];

export default function DashboardPage() {
  const { session } = useAuth();
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  });

  const theme = useAppStore((s) => s.settings.theme);
  const chartTheme = useMemo(() => getChartTheme(theme), [theme]);

  const [now, setNow] = useState<Date | null>(null);
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const addSourceRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  const greeting = now ? getGreeting(now) : { text: "Hello", emoji: "👋" };
  const currentTime = now ? getCurrentTime(now) : { date: "", time: "" };
  const profileMeta = (session?.user.user_metadata ?? {}) as Record<string, unknown>;
  const greetingName =
    (typeof profileMeta.preferred_name === "string" && profileMeta.preferred_name.trim()) ||
    (typeof profileMeta.full_name === "string" && profileMeta.full_name.trim().split(/\s+/)[0]) ||
    "";

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (addSourceRef.current && !addSourceRef.current.contains(e.target as Node)) {
        setAddSourceOpen(false);
      }
    };
    if (addSourceOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [addSourceOpen]);

  const knowledgeGrowthData = useMemo(() => {
    if (stats?.knowledge_growth && stats.knowledge_growth.length > 0) {
      return stats.knowledge_growth;
    }
    return [
      { name: "Mon", chunks: 0 },
      { name: "Tue", chunks: 0 },
      { name: "Wed", chunks: 0 },
      { name: "Thu", chunks: 0 },
      { name: "Fri", chunks: 0 },
      { name: "Sat", chunks: 0 },
      { name: "Sun", chunks: 0 },
    ];
  }, [stats]);

  const contentDistributionData = useMemo(() => {
    if (!stats?.sources_by_type) return [];
    const total = Object.values(stats.sources_by_type).reduce((a, b) => a + b, 0);
    return Object.entries(stats.sources_by_type)
      .map(([type, count]) => {
        const src = getSourceTheme(type);
        return {
          name: type.charAt(0).toUpperCase() + type.slice(1),
          value: count,
          percentage: total > 0 ? Math.round((count / total) * 100) : 0,
          color: src.accent,
        };
      })
      .sort((a, b) => b.value - a.value);
  }, [stats]);

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mb-8 rounded-[24px] border-2 border-ink bg-card p-8 shadow-card"
      >
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <motion.h1
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="text-[32px] font-bold text-foreground tracking-tight"
            >
              {greetingName ? `${greeting.text}, ${greetingName}` : greeting.text}{" "}
              <span className="inline-block">{greeting.emoji}</span>
            </motion.h1>
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25 }}
              className="mt-1 flex items-center gap-3"
            >
              <span className="text-[13px] text-muted">{currentTime.date}</span>
              <span className="text-[13px] font-semibold text-foreground-3">{currentTime.time}</span>
            </motion.div>
            <motion.p
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-1 text-[13px] text-muted"
            >
              Your personal intelligence operating system.
            </motion.p>

            <AISummaryBrief stats={stats} isLoading={isLoading} />

            {/* Quick Stats */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="mt-5 flex flex-wrap items-center gap-5"
            >
              {[
                { icon: Boxes, label: "Knowledge Chunks", value: stats?.indexed_chunks ?? 0, color: "var(--brand)" },
                { icon: Database, label: "Sources", value: stats?.total_sources ?? 0, color: "var(--success)" },
                { icon: Network, label: "Embeddings", value: stats?.indexed_chunks ?? 0, color: "var(--info)" },
                { icon: Activity, label: "Vector Collections", value: 1, color: "var(--warning)" },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center gap-2">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface"
                  >
                    <stat.icon className="h-4 w-4" style={{ color: stat.color }} />
                  </div>
                  <div>
                    <div className="text-[18px] font-bold text-foreground">
                      {isLoading ? "..." : <AnimatedCounter value={stat.value} />}
                    </div>
                    <div className="text-[11px] text-muted">{stat.label}</div>
                  </div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Right - Actions */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
            className="flex flex-col items-end gap-3"
          >
            {/* Search Bar */}
            <Link
              href="/chat"
              className="flex w-full lg:w-80 items-center gap-3 rounded-[14px] border-2 border-ink bg-surface px-4 py-3 text-left transition-all hover:border-brand/40 hover:shadow-elevated"
            >
              <MessageSquare className="h-4 w-4 text-muted" />
              <span className="flex-1 text-[13px] text-subtle">Ask AI about your knowledge...</span>
              <div className="flex items-center gap-1 rounded-md bg-card border-2 border-ink px-2 py-1">
                <span className="text-[11px] text-muted">Ask</span>
              </div>
            </Link>

            {/* Quick Actions */}
            <div className="flex items-center gap-2">
              <div ref={addSourceRef} className="relative">
                <button
                  onClick={() => setAddSourceOpen(!addSourceOpen)}
                  className="flex items-center gap-2 rounded-[12px] bg-brand px-4 py-2.5 text-[12px] font-semibold text-ink transition-all hover:bg-brand/90 shadow-sm"
                >
                  <Plus className="h-4 w-4" />
                  Add Source
                </button>
                <AnimatePresence>
                  {addSourceOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -8, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8, scale: 0.98 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 top-full z-50 mt-2 w-[260px] overflow-hidden rounded-[14px] border-2 border-ink bg-card shadow-floating text-foreground"
                    >
                      <div className="border-b-2 border-ink px-4 py-3">
                        <h3 className="text-[12px] font-semibold text-foreground">Add Source</h3>
                      </div>
                      <div className="p-2">
                        {ADD_SOURCE_ITEMS.map((item) => (
                          <a
                            key={item.href}
                            href={item.href}
                            onClick={() => setAddSourceOpen(false)}
                            className="group flex items-center gap-3 rounded-[10px] px-3 py-2.5 transition-colors hover:bg-surface"
                          >
                            <div
                              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[8px] bg-surface"
                            >
                              <item.icon className="h-4 w-4" style={{ color: item.color }} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-[12px] font-medium text-foreground">{item.label}</div>
                              <div className="text-[10px] text-muted">{item.desc}</div>
                            </div>
                            <ArrowRight className="h-3.5 w-3.5 text-subtle group-hover:text-brand transition-colors" />
                          </a>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <NotificationCenter />
              <Link
                href="/"
                title="Back to landing page"
                aria-label="Back to landing page"
                className="flex h-10 w-10 items-center justify-center rounded-[12px] border-2 border-ink bg-card text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
              >
                <Home className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* KPI Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {/* Indexed Chunks */}
        <div className="group rounded-[20px] border-2 border-ink bg-card p-5 transition-all hover:border-brand/40 hover:shadow-elevated">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-brand-soft">
              <Boxes className="h-5 w-5 text-brand" />
            </div>
            <span className="flex items-center gap-1 text-[11px] font-medium text-success">
              <TrendingUp className="h-3 w-3" />
              +12%
            </span>
          </div>
          <div className="text-[28px] font-bold text-foreground">
            {isLoading ? "..." : <AnimatedCounter value={stats?.indexed_chunks ?? 0} />}
          </div>
          <div className="mt-1 text-[12px] text-muted">Indexed Chunks</div>
          <div className="mt-3 h-8">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={knowledgeGrowthData}>
                <defs>
                  <linearGradient id="colorChunks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--brand)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--brand)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="chunks" stroke="var(--brand)" strokeWidth={2} fillOpacity={1} fill="url(#colorChunks)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sources */}
        <div className="group rounded-[20px] border-2 border-ink bg-card p-5 transition-all hover:border-success/40 hover:shadow-elevated">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-success/10">
              <Database className="h-5 w-5 text-success" />
            </div>
            <span className="flex items-center gap-1 text-[11px] font-medium text-success">
              <TrendingUp className="h-3 w-3" />
              +2 new
            </span>
          </div>
          <div className="text-[28px] font-bold text-foreground">
            {isLoading ? "..." : <AnimatedCounter value={stats?.total_sources ?? 0} />}
          </div>
          <div className="mt-1 text-[12px] text-muted">Knowledge Sources</div>
          <div className="mt-3 flex flex-wrap gap-1">
            {stats?.sources_by_type &&
              Object.entries(stats.sources_by_type)
                .slice(0, 4)
                .map(([type, count]) => {
                  const src = getSourceTheme(type);
                  const Icon = src.icon;
                  return (
                    <span
                      key={type}
                      className="inline-flex items-center gap-1 rounded-full bg-surface border-2 border-ink px-2 py-0.5 text-[10px] text-foreground-2"
                    >
                      <Icon className="h-3 w-3" style={{ color: src.accent }} />
                      {count}
                    </span>
                  );
                })}
          </div>
        </div>

        {/* Vector Database */}
        <div className="group rounded-[20px] border-2 border-ink bg-card p-5 transition-all hover:border-info/40 hover:shadow-elevated">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-info/10">
              <Database className="h-5 w-5 text-info" />
            </div>
            <span className="flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
              <Activity className="h-3 w-3" />
              Connected
            </span>
          </div>
          <div className="text-[22px] font-bold text-foreground">Qdrant</div>
          <div className="mt-1 text-[12px] text-muted">Vector Database</div>
          <div className="mt-3 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface">
              <div className="h-full bg-info transition-all duration-1000" style={{ width: "100%" }} />
            </div>
            <span className="text-[10px] text-muted">100%</span>
          </div>
        </div>

        {/* AI Status */}
        <div className="group rounded-[20px] border-2 border-ink bg-card p-5 transition-all hover:border-success/40 hover:shadow-elevated">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-success/10">
              <Brain className="h-5 w-5 text-success" />
            </div>
            <div className="relative">
              <div className="h-3 w-3 rounded-full bg-success animate-pulse" />
              <div className="absolute inset-0 h-3 w-3 rounded-full bg-success animate-ping opacity-75" />
            </div>
          </div>
          <div className="text-[22px] font-bold text-success">Online</div>
          <div className="mt-1 text-[12px] text-muted">System Health</div>
          <div className="mt-3 flex items-center gap-3 text-[10px] text-muted">
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              qwen2.5:3b
            </span>
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              nomic-embed
            </span>
          </div>
        </div>
      </motion.div>

      {/* Main Content - Two Columns */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Left: Recent Activity + Charts */}
        <div className="space-y-4 lg:col-span-2">
          {/* Recent Activity */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="rounded-[20px] border-2 border-ink bg-card p-5"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-foreground">Live Activity</h3>
              <span className="flex items-center gap-1.5 text-[10px] text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                Live
              </span>
            </div>
            <ActivityFeed />
          </motion.div>

          {/* Charts Row */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="grid grid-cols-1 gap-4 sm:grid-cols-2"
          >
            {/* Knowledge Growth */}
            <div className="rounded-[20px] border-2 border-ink bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-[13px] font-semibold text-foreground">Knowledge Growth</h3>
                <span className="rounded-full bg-surface border-2 border-ink px-3 py-1 text-[10px] font-medium text-muted">
                  This Week
                </span>
              </div>
              <div className="mb-2">
                <span className="text-[24px] font-bold text-foreground">
                  +{knowledgeGrowthData.reduce((a, b) => a + b.chunks, 0)}
                </span>
                <span className="ml-2 text-[12px] text-muted">Chunks added</span>
              </div>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={knowledgeGrowthData}>
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: chartTheme.mutedText, fontSize: 10 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: chartTheme.mutedText, fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: chartTheme.tooltipBackground, borderColor: chartTheme.tooltipBorder, borderRadius: "12px", color: chartTheme.tooltipText }}
                      labelStyle={{ color: chartTheme.tooltipText }}
                      itemStyle={{ color: "var(--brand)" }}
                    />
                    <Bar dataKey="chunks" fill="var(--brand)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Content Distribution */}
            <div className="rounded-[20px] border-2 border-ink bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-[13px] font-semibold text-foreground">Content Distribution</h3>
                <span className="text-[18px] font-bold text-foreground">{stats?.total_sources ?? 0}</span>
              </div>
              <div className="flex items-center justify-center">
                <div className="relative h-40 w-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsPieChart>
                      <Pie
                        data={contentDistributionData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={70}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {contentDistributionData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                      contentStyle={{ backgroundColor: chartTheme.tooltipBackground, borderColor: chartTheme.tooltipBorder, borderRadius: "12px", color: chartTheme.tooltipText }}
                      labelStyle={{ color: chartTheme.tooltipText }}
                    />
                  </RechartsPieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-[20px] font-bold text-foreground">{stats?.total_sources ?? 0}</span>
                    <span className="text-[9px] text-muted">Total</span>
                  </div>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-1.5">
                {contentDistributionData.map((item) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-[10px] text-foreground-3">{item.name}</span>
                    <span className="ml-auto text-[10px] font-medium text-foreground">{item.percentage}%</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Background Tasks */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
            className="rounded-[20px] border-2 border-ink bg-card p-5"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-foreground">Background Tasks</h3>
            </div>
            <BackgroundTasks />
          </motion.div>

          {/* System Status */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.7 }}
            className="rounded-[20px] border-2 border-ink bg-card p-5"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-foreground">System Status</h3>
              <div className="flex items-center gap-1.5">
                <div className="relative">
                  <div className="h-2 w-2 rounded-full bg-success" />
                  <div className="absolute inset-0 h-2 w-2 rounded-full bg-success animate-ping opacity-75" />
                </div>
                <span className="text-[10px] font-medium text-success">All Systems Operational</span>
              </div>
            </div>
            <LiveSystemStatus />
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.8 }}
            className="rounded-[20px] border-2 border-ink bg-card p-5"
          >
            <div className="mb-4">
              <h3 className="text-[13px] font-semibold text-foreground">Quick Actions</h3>
            </div>
            <div className="space-y-1.5">
              {[
                { icon: Youtube, label: "Add YouTube Video", desc: "Extract & summarize", color: "#FF5C00", href: "/youtube" },
                { icon: Instagram, label: "Add Instagram Reel", desc: "Extract captions", color: "#FF5C00", href: "/instagram" },
                { icon: MessageSquare, label: "Ask AI", desc: "Ask across saved sources", color: "var(--brand)", href: "/chat" },
                { icon: Database, label: "Stored", desc: "Browse your knowledge", color: "#B96A00", href: "/stored" },
              ].map((action) => (
                <a
                  key={action.href}
                  href={action.href}
                  className="group flex items-center gap-3 rounded-[12px] p-2.5 transition-all hover:bg-surface"
                >
                  <div
                    className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[9px] bg-surface"
                  >
                    <action.icon className="h-4 w-4" style={{ color: action.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-medium text-foreground group-hover:text-brand transition-colors">
                      {action.label}
                    </div>
                    <div className="text-[9px] text-muted">{action.desc}</div>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-subtle group-hover:text-brand group-hover:translate-x-1 transition-all" />
                </a>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
