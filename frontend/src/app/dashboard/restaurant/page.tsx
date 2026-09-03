"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Leaf, Package, TrendingUp, Award, Clock, MapPin, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth-store";

// -------------------------------------------------------
// Types
// -------------------------------------------------------
interface RestaurantKPIs {
  total_donations: number;
  total_meals_saved: number;
  carbon_saved_kg: number;
  sustainability_score: number;
  impact_rank: number | null;
  weekly_change: number;
  active_donations: number;
}

interface DonationSummary {
  id: string;
  status: string;
  total_servings: number;
  total_weight_kg: number;
  pickup_window_start: string;
  matched_ngo_id: string | null;
  created_at: string;
}

// -------------------------------------------------------
// KPI Card Component
// -------------------------------------------------------
function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  color,
  trend,
  delay = 0,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  trend?: number;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="stat-card group"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground font-medium">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center flex-shrink-0`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
      {trend !== undefined && (
        <div className={`flex items-center gap-1 mt-3 text-xs font-medium ${trend >= 0 ? "text-green-500" : "text-red-500"}`}>
          <TrendingUp className={`w-3 h-3 ${trend < 0 ? "rotate-180" : ""}`} />
          {Math.abs(trend).toFixed(1)}% vs last week
        </div>
      )}
    </motion.div>
  );
}

// -------------------------------------------------------
// Status Badge
// -------------------------------------------------------
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    in_transit: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    matched: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    pending_analysis: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    safety_failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
  };
  return (
    <span className={`status-badge ${styles[status] ?? styles.cancelled}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

// -------------------------------------------------------
// Main Dashboard
// -------------------------------------------------------
export default function RestaurantDashboardPage() {
  const user = useAuthStore((s) => s.user);

  const { data: kpiData, isLoading: kpiLoading } = useQuery({
    queryKey: ["restaurant-kpis"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: RestaurantKPIs }>("/analytics/dashboard");
      return data.data;
    },
  });

  const { data: donationsData, isLoading: donationsLoading } = useQuery({
    queryKey: ["my-donations"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: DonationSummary[] }>("/donations?page=1&page_size=10");
      return data.data;
    },
  });

  const kpis = kpiData ?? {
    total_donations: 0,
    total_meals_saved: 0,
    carbon_saved_kg: 0,
    sustainability_score: 0,
    impact_rank: null,
    weekly_change: 0,
    active_donations: 0,
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="text-2xl font-bold">Restaurant Dashboard</h1>
          <p className="text-muted-foreground">Welcome back, {user?.name ?? "there"}</p>
        </motion.div>
        <motion.a
          href="/dashboard/restaurant/donate"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary rounded-lg text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors shadow-glow"
        >
          <Plus className="w-4 h-4" />
          New Donation
        </motion.a>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Total Donations"
          value={kpiLoading ? "..." : kpis.total_donations}
          subtitle="All time"
          icon={Package}
          color="bg-gradient-to-br from-blue-500 to-cyan-500"
          trend={kpis.weekly_change}
          delay={0}
        />
        <KPICard
          title="Meals Saved"
          value={kpiLoading ? "..." : kpis.total_meals_saved.toLocaleString()}
          subtitle="Servings delivered"
          icon={Leaf}
          color="bg-gradient-to-br from-primary-500 to-emerald-500"
          delay={0.1}
        />
        <KPICard
          title="Carbon Saved"
          value={kpiLoading ? "..." : `${kpis.carbon_saved_kg.toFixed(1)} kg`}
          subtitle="CO₂ prevented"
          icon={TrendingUp}
          color="bg-gradient-to-br from-green-500 to-teal-500"
          delay={0.2}
        />
        <KPICard
          title="Impact Rank"
          value={kpiLoading ? "..." : kpis.impact_rank ? `#${kpis.impact_rank}` : "—"}
          subtitle="Platform leaderboard"
          icon={Award}
          color="bg-gradient-to-br from-yellow-500 to-orange-500"
          delay={0.3}
        />
      </div>

      {/* Recent Donations Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Recent Donations</h2>
          <a href="/dashboard/restaurant/donations" className="text-primary text-sm hover:underline">
            View all →
          </a>
        </div>

        {donationsLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton h-12 rounded-lg" />
            ))}
          </div>
        ) : !donationsData || donationsData.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No donations yet. Create your first donation to get started!</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Servings</th>
                  <th>Weight</th>
                  <th>Pickup Window</th>
                  <th>NGO Matched</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {donationsData.map((d) => (
                  <tr key={d.id} className="cursor-pointer hover:bg-muted/50 transition-colors">
                    <td className="font-mono text-xs">{d.id.slice(0, 8)}...</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td className="font-medium">{d.total_servings}</td>
                    <td>{d.total_weight_kg.toFixed(1)} kg</td>
                    <td className="text-xs text-muted-foreground">{new Date(d.pickup_window_start).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}</td>
                    <td>{d.matched_ngo_id ? <span className="text-primary text-xs">✓ Matched</span> : <span className="text-muted-foreground text-xs">Pending</span>}</td>
                    <td className="text-xs text-muted-foreground">{new Date(d.created_at).toLocaleDateString("en-IN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* AI Insights Panel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="glass-card p-6"
      >
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-primary">🤖</span> AI Insights
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            {
              title: "Peak Donation Times",
              insight: "Your highest-impact donations happen on weekends. Consider scheduling bulk pickups on Friday evenings.",
              icon: "📅",
            },
            {
              title: "Carbon Milestone",
              insight: `You've saved ${kpis.carbon_saved_kg.toFixed(0)}kg of CO₂ — equivalent to planting ${Math.floor(kpis.carbon_saved_kg / 21)} trees!`,
              icon: "🌳",
            },
            {
              title: "Demand Forecast",
              insight: "NGO capacity increases by 30% during weekends in your area. Align surplus donations accordingly.",
              icon: "📊",
            },
          ].map((insight) => (
            <div key={insight.title} className="p-4 rounded-xl bg-muted/50 border border-border">
              <div className="text-2xl mb-2">{insight.icon}</div>
              <h3 className="text-sm font-semibold mb-1">{insight.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{insight.insight}</p>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
