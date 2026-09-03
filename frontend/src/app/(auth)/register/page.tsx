"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Leaf, Loader2 } from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth-store";
import { UserRole } from "@/types";

const ROLE_OPTIONS = [
  { value: UserRole.RESTAURANT_OWNER, label: "Restaurant Owner", icon: "🍽️", desc: "I donate surplus food" },
  { value: UserRole.NGO_MANAGER, label: "NGO Manager", icon: "🤝", desc: "I distribute food to beneficiaries" },
  { value: UserRole.VOLUNTEER, label: "Volunteer", icon: "🚴", desc: "I help with pickups and deliveries" },
];

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading, error, clearError } = useAuthStore();

  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: "", email: "", phone: "", password: "", confirm_password: "",
    role: UserRole.RESTAURANT_OWNER, organization_name: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    clearError();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm_password) return;
    try {
      await register(form);
      const role = useAuthStore.getState().user?.role;
      if (role === "restaurant_owner") router.push("/dashboard/restaurant");
      else if (role === "ngo_manager") router.push("/dashboard/ngo");
      else router.push("/dashboard/volunteer");
    } catch {
      // handled by store
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-950 via-gray-900 to-primary-900 flex items-center justify-center p-4 py-12">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-primary-500/10 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-lg"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary-500 flex items-center justify-center shadow-glow">
              <Leaf className="w-7 h-7 text-white" />
            </div>
            <span className="text-3xl font-bold text-white">ResQAI</span>
          </Link>
          <p className="text-gray-400 mt-2 text-sm">Create your account</p>
        </div>

        <div className="glass-card p-8 text-white">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Role Selection */}
            <div>
              <label className="block text-sm font-medium mb-3 text-gray-300">I am a...</label>
              <div className="grid grid-cols-3 gap-2">
                {ROLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setForm((p) => ({ ...p, role: opt.value }))}
                    className={`p-3 rounded-xl border text-center transition-all ${
                      form.role === opt.value
                        ? "border-primary-500 bg-primary-500/20 text-white"
                        : "border-white/10 bg-white/5 text-gray-400 hover:border-white/20"
                    }`}
                  >
                    <div className="text-2xl mb-1">{opt.icon}</div>
                    <div className="text-xs font-medium">{opt.label}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Name */}
            <div>
              <label className="block text-sm font-medium mb-1.5 text-gray-300">Full Name</label>
              <input
                name="name"
                value={form.name}
                onChange={handleChange}
                required
                placeholder="Your full name"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
              />
            </div>

            {/* Organization name */}
            {form.role !== UserRole.VOLUNTEER && (
              <div>
                <label className="block text-sm font-medium mb-1.5 text-gray-300">
                  {form.role === UserRole.RESTAURANT_OWNER ? "Restaurant Name" : "NGO Name"}
                </label>
                <input
                  name="organization_name"
                  value={form.organization_name}
                  onChange={handleChange}
                  placeholder={form.role === UserRole.RESTAURANT_OWNER ? "e.g. Grand Palace Hotel" : "e.g. Helping Hands Foundation"}
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
                />
              </div>
            )}

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-1.5 text-gray-300">Email</label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                required
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium mb-1.5 text-gray-300">Phone</label>
              <input
                type="tel"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                required
                placeholder="+91 98765 43210"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
              />
            </div>

            {/* Password */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-gray-300">Password</label>
                <input
                  type="password"
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  required
                  placeholder="Min 8 chars"
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-gray-300">Confirm</label>
                <input
                  type="password"
                  name="confirm_password"
                  value={form.confirm_password}
                  onChange={handleChange}
                  required
                  placeholder="Repeat password"
                  className={`w-full px-4 py-3 rounded-xl bg-white/5 border text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all ${
                    form.confirm_password && form.password !== form.confirm_password
                      ? "border-red-500"
                      : "border-white/10"
                  }`}
                />
              </div>
            </div>
            {form.confirm_password && form.password !== form.confirm_password && (
              <p className="text-red-400 text-xs">Passwords do not match</p>
            )}

            <button
              type="submit"
              disabled={isLoading || (!!form.confirm_password && form.password !== form.confirm_password)}
              className="w-full py-3 bg-primary-500 hover:bg-primary-400 disabled:bg-primary-500/50 rounded-xl font-semibold text-white transition-all shadow-glow flex items-center justify-center gap-2 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" />Creating account...</>
              ) : "Create Account"}
            </button>
          </form>

          <p className="text-center text-gray-400 text-sm mt-6">
            Already have an account?{" "}
            <Link href="/(auth)/login" className="text-primary-400 hover:text-primary-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </main>
  );
}
