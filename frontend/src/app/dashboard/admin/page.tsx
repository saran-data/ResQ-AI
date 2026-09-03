"use client";

import { motion } from "framer-motion";
import {
  BarChart3, Users, Building2, Heart, Package, AlertTriangle,
  CheckCircle, TrendingUp, Brain, Zap, Activity,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from "recharts";

// -------------------------------------------------------
// Types
// -------------------------------------------------------
interface AdminStats {
  total_users: number;
  total_restaurants: number;
  total_ngos: number;
  total_donations: number;
  total_volunteers: number;
}

interface AgentStatus {
  agent: string;
  total_decisions: number;
  avg_confidence: number;
}

// -------------------------------------------------------
// System Health Gauge
// -------------------------------------------------------
function HealthIndicator({ label, status }: { label: string; status: "healthy" | "degraded" | "down" }) {
  const colors = { healthy: "bg-green-500", degraded: "bg-yellow-500", down: "bg-red-500" };
  const labels = { healthy: "Healthy", degraded: "Degraded", down: "Down" };
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
      <span className="text-sm font-medium">{label}</span>
      <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full text-white ${colors[status]}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-white/70 animate-pulse" />
        {labels[status]}
      </span>
    </div>
  );
}

// -------------------------------------------------------
// Agent Status Card
// -------------------------------------------------------
function AgentCard({ agent }: { agent: AgentStatus }) {
  const agentIcons: Record<string, string> = {
    food_analysis: "👁️", ngo_matching: "🎯", route_optimization: "🗺️",
    food_safety: "🛡️", demand_prediction: "📈", notification: "🔔",
    volunteer: "🚴", analytics: "📊", fraud_detection: "🕵️", admin_assistant: "🤖",
  };
  const confColor = agent.avg_confidence > 0.8 ? "text-green-500" : agent.avg_confidence > 0.6 ? "text-yellow-500" : "text-red-500";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-4 rounded-xl border border-border bg-card hover:shadow-card-hover transition-all"
    >
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl">{agentIcons[agent.agent] ?? "🤖"}</span>
        <div>
          <p className="text-sm font-semibold capitalize">{agent.agent.replace(/_/g, " ")}</p>
          <p className="text-xs text-muted-foreground">{agent.total_decisions} decisions</p>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Avg Confidence</span>
        <span className={`text-sm font-bold ${confColor}`}>
          {(agent.avg_confidence * 100).toFixed(0)}%
        </span>
      </div>
      <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${agent.avg_confidence * 100}%` }}
          className={`h-full rounded-full ${agent.avg_confidence > 0.8 ? "bg-green-500" : agent.avg_confidence > 0.6 ? "bg-yellow-500" : "bg-red-500"}`}
        />
      </div>
    </motion.div>
  );
}

// -------------------------------------------------------
// Main Admin Dashboard
// -------------------------------------------------------
export default function AdminDashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: AdminStats }>("/admin/stats/overview");
      return data.data;
    },
  });

  const { data: agentStatuses, isLoading: agentsLoading } = useQuery({
    queryKey: ["agent-statuses"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: AgentStatus[] }>("/agents/status");
      return data.data;
    },
  });

  const { data: systemHealth } = useQuery({
    queryKey: ["system-health"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: { database: { status: string }; redis: { status: string } } }>("/admin/system/health");
      return data.data;
    },
    refetchInterval: 30_000, // Refresh every 30s
  });

  const { data: kpis } = useQuery({
    queryKey: ["admin-kpis"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: { total_donations: number; total_meals_saved: number; confirmed_deliveries: number; success_rate: number; carbon_saved_kg: number } }>("/analytics/dashboard");
      return data.data;
    },
  });

  // Chart mock data (in production: fetch from analytics API)
  const weeklyDonations = [
    { day: "Mon", donations: 12, meals: 240 },
    { day: "Tue", donations: 19, meals: 380 },
    { day: "Wed", donations: 8, meals: 160 },
    { day: "Thu", donations: 23, meals: 460 },
    { day: "Fri", donations: 31, meals: 620 },
    { day: "Sat", donations: 28, meals: 560 },
    { day: "Sun", donations: 22, meals: 440 },
  ];

  const donationStatusDist = [
    { name: "Confirmed", value: 45, color: "#22c55e" },
    { name: "In Transit", value: 20, color: "#3b82f6" },
    { name: "Matched", value: 15, color: "#a855f7" },
    { name: "Pending", value: 12, color: "#f59e0b" },
    { name: "Cancelled", value: 8, color: "#6b7280" },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Platform overview and AI monitoring</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Activity className="w-4 h-4 text-green-500 animate-pulse" />
          Live
        </div>
      </motion.div>

      {/* Platform KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          { label: "Users", value: stats?.total_users ?? 0, icon: Users, color: "from-blue-500 to-cyan-500" },
          { label: "Restaurants", value: stats?.total_restaurants ?? 0, icon: Building2, color: "from-orange-500 to-red-500" },
          { label: "NGOs", value: stats?.total_ngos ?? 0, icon: Heart, color: "from-pink-500 to-rose-500" },
          { label: "Donations", value: stats?.total_donations ?? 0, icon: Package, color: "from-primary-500 to-emerald-500" },
          { label: "Volunteers", value: stats?.total_volunteers ?? 0, icon: Users, color: "from-purple-500 to-violet-500" },
        ].map((kpi, i) => (
          <motion.div
            key={kpi.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="stat-card"
          >
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${kpi.color} flex items-center justify-center mb-3`}>
              <kpi.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-2xl font-bold">{statsLoading ? "..." : kpi.value.toLocaleString()}</p>
            <p className="text-sm text-muted-foreground">{kpi.label}</p>
          </motion.div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Weekly Activity */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold mb-4">Weekly Activity</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={weeklyDonations}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
              <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
              />
              <Bar dataKey="donations" fill="#22c55e" radius={[4, 4, 0, 0]} name="Donations" />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Donation Status Distribution */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.35 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold mb-4">Donation Status</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={donationStatusDist}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={3}
                dataKey="value"
              >
                {donationStatusDist.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
              />
              <Legend formatter={(value) => <span style={{ color: "hsl(var(--foreground))", fontSize: "12px" }}>{value}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* System Health + AI Agents */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* System Health */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" /> System Health
          </h3>
          <div className="space-y-2">
            <HealthIndicator
              label="PostgreSQL"
              status={systemHealth?.database?.status === "healthy" ? "healthy" : "degraded"}
            />
            <HealthIndicator
              label="Redis Cache"
              status={systemHealth?.redis?.status === "healthy" ? "healthy" : "degraded"}
            />
            <HealthIndicator label="Qdrant (RAG)" status="healthy" />
            <HealthIndicator label="Kafka Events" status="healthy" />
            <HealthIndicator label="Celery Workers" status="healthy" />
            <HealthIndicator label="AI Orchestrator" status="healthy" />
          </div>

          {/* Impact Summary */}
          <div className="mt-6 p-4 rounded-xl bg-primary/10 border border-primary/20">
            <p className="text-sm font-semibold text-primary mb-2">Platform Impact</p>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Meals Saved</span>
                <span className="font-medium">{(kpis?.total_meals_saved ?? 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Carbon Saved</span>
                <span className="font-medium">{(kpis?.carbon_saved_kg ?? 0).toFixed(1)} kg</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Success Rate</span>
                <span className="font-medium text-green-500">{kpis?.success_rate ?? 0}%</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* AI Agents Grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="glass-card p-6 md:col-span-2"
        >
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" /> AI Agent Performance
          </h3>
          {agentsLoading ? (
            <div className="grid grid-cols-2 gap-3">
              {[...Array(10)].map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
            </div>
          ) : !agentStatuses || agentStatuses.length === 0 ? (
            <p className="text-muted-foreground text-sm">No agent activity recorded yet</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {agentStatuses.map((agent) => (
                <AgentCard key={agent.agent} agent={agent} />
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* Flagged Donations Alert */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="glass-card p-6 border border-yellow-500/20"
      >
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 text-yellow-600 dark:text-yellow-400">
          <AlertTriangle className="w-5 h-5" /> Fraud Detection Alerts
        </h3>
        <p className="text-sm text-muted-foreground">
          The Fraud Detection Agent continuously monitors all donations and entities for suspicious activity.
          Flagged items appear here for manual review.
        </p>
        <a href="/dashboard/admin/fraud" className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline">
          View flagged donations →
        </a>
      </motion.div>
    </div>
  );
}
