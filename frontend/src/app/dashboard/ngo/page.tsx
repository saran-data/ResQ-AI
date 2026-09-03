"use client";

import { motion } from "framer-motion";
import { Users, Package, CheckCircle, Clock, BarChart3, MapPin, RefreshCw } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { toast } from "sonner";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth-store";

interface NGODashboardData {
  ngo: {
    id: string;
    name: string;
    capacity_per_day: number;
    current_capacity: number;
    beneficiaries_count: number;
    total_received: number;
    acceptance_rate: number;
  };
  pending_donations: Array<{
    id: string;
    restaurant_name: string;
    total_servings: number;
    total_weight_kg: number;
    pickup_window_start: string;
    ai_safety_score: number;
    food_items: Array<{ name: string; category: string }>;
  }>;
  active_deliveries: number;
}

function CapacityBar({ current, max }: { current: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0;
  const color = pct > 80 ? "bg-green-500" : pct > 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-muted-foreground">Current Capacity</span>
        <span className="font-medium">{current} / {max} servings</span>
      </div>
      <div className="h-3 bg-muted rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`h-full ${color} rounded-full`}
        />
      </div>
      <p className="text-xs text-muted-foreground mt-1">{pct.toFixed(0)}% capacity available</p>
    </div>
  );
}

export default function NGODashboardPage() {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [updatingCapacity, setUpdatingCapacity] = useState(false);
  const [newCapacity, setNewCapacity] = useState<string>("");

  const { data: ngoData, isLoading } = useQuery({
    queryKey: ["ngo-dashboard"],
    queryFn: async () => {
      const [ngoResp, donationsResp] = await Promise.all([
        apiClient.get<{ data: NGODashboardData["ngo"] }>("/ngos/my"),
        apiClient.get<{ data: NGODashboardData["pending_donations"] }>("/donations?status=matched&page_size=10"),
      ]);
      return {
        ngo: ngoResp.data.data,
        pending_donations: donationsResp.data.data,
        active_deliveries: 0,
      } as NGODashboardData;
    },
  });

  const updateCapacityMutation = useMutation({
    mutationFn: async (capacity: number) => {
      if (!ngoData?.ngo?.id) throw new Error("NGO not found");
      await apiClient.patch(`/ngos/${ngoData.ngo.id}/capacity`, { current_capacity: capacity });
    },
    onSuccess: () => {
      toast.success("Capacity updated");
      queryClient.invalidateQueries({ queryKey: ["ngo-dashboard"] });
      setUpdatingCapacity(false);
      setNewCapacity("");
    },
    onError: () => toast.error("Failed to update capacity"),
  });

  const acceptDonationMutation = useMutation({
    mutationFn: async (donationId: string) => {
      await apiClient.post(`/donations/${donationId}/confirm`, { food_condition: "good" });
    },
    onSuccess: () => {
      toast.success("Donation accepted!");
      queryClient.invalidateQueries({ queryKey: ["ngo-dashboard"] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(8)].map((_, i) => <div key={i} className="skeleton h-32 rounded-xl" />)}
      </div>
    );
  }

  const ngo = ngoData?.ngo;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="text-2xl font-bold">{ngo?.name ?? "NGO Dashboard"}</h1>
          <p className="text-muted-foreground">Managing food distribution for {ngo?.beneficiaries_count ?? 0} beneficiaries</p>
        </motion.div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { title: "Total Received", value: ngo?.total_received ?? 0, icon: Package, color: "bg-blue-500", delay: 0 },
          { title: "Beneficiaries", value: ngo?.beneficiaries_count ?? 0, icon: Users, color: "bg-primary-500", delay: 0.1 },
          { title: "Acceptance Rate", value: `${((ngo?.acceptance_rate ?? 0) * 100).toFixed(0)}%`, icon: CheckCircle, color: "bg-green-500", delay: 0.2 },
          { title: "Active Deliveries", value: ngoData?.active_deliveries ?? 0, icon: Clock, color: "bg-orange-500", delay: 0.3 },
        ].map((kpi) => (
          <motion.div
            key={kpi.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: kpi.delay }}
            className="stat-card"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{kpi.title}</p>
                <p className="text-3xl font-bold mt-1">{typeof kpi.value === "number" ? kpi.value.toLocaleString() : kpi.value}</p>
              </div>
              <div className={`w-12 h-12 rounded-xl ${kpi.color} flex items-center justify-center`}>
                <kpi.icon className="w-6 h-6 text-white" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Capacity Management */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Capacity Management</h2>
          <button
            onClick={() => setUpdatingCapacity(true)}
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Update
          </button>
        </div>
        <CapacityBar current={ngo?.current_capacity ?? 0} max={ngo?.capacity_per_day ?? 1} />
        {updatingCapacity && (
          <div className="mt-4 flex items-center gap-3">
            <input
              type="number"
              value={newCapacity}
              onChange={(e) => setNewCapacity(e.target.value)}
              placeholder="New capacity"
              className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm"
              min="0"
              max={ngo?.capacity_per_day}
            />
            <button
              onClick={() => {
                const val = parseInt(newCapacity);
                if (!isNaN(val)) updateCapacityMutation.mutate(val);
              }}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm"
            >
              Save
            </button>
            <button
              onClick={() => setUpdatingCapacity(false)}
              className="px-4 py-2 bg-muted rounded-lg text-sm"
            >
              Cancel
            </button>
          </div>
        )}
      </motion.div>

      {/* Pending Donations */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="glass-card p-6"
      >
        <h2 className="text-lg font-semibold mb-4">Available Donations</h2>
        {!ngoData?.pending_donations || ngoData.pending_donations.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No pending donations at the moment. Check back soon!</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {ngoData.pending_donations.map((d) => (
              <div key={d.id} className="p-4 rounded-xl border border-border bg-muted/30 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-sm">{d.restaurant_name ?? "Restaurant"}</p>
                    <p className="text-xs text-muted-foreground">{d.total_servings} servings • {d.total_weight_kg.toFixed(1)}kg</p>
                  </div>
                  {d.ai_safety_score && (
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${d.ai_safety_score > 0.7 ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                      AI: {(d.ai_safety_score * 100).toFixed(0)}% safe
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  Pickup by {new Date(d.pickup_window_start).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="flex flex-wrap gap-1">
                  {d.food_items?.slice(0, 3).map((item, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full">
                      {item.name}
                    </span>
                  ))}
                </div>
                <button
                  onClick={() => acceptDonationMutation.mutate(d.id)}
                  disabled={acceptDonationMutation.isPending}
                  className="w-full py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {acceptDonationMutation.isPending ? "Accepting..." : "Accept Donation"}
                </button>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
