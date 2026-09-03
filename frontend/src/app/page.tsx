"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Leaf, Users, Building2, BarChart3, Shield, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-950 via-gray-900 to-primary-900 text-white overflow-hidden">
      {/* Animated background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/20 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-primary-300/10 rounded-full blur-3xl animate-float" style={{ animationDelay: "1.5s" }} />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex items-center gap-3"
        >
          <div className="w-10 h-10 rounded-xl bg-primary-500 flex items-center justify-center shadow-glow">
            <Leaf className="w-6 h-6 text-white" />
          </div>
          <span className="text-2xl font-bold gradient-text">ResQAI</span>
        </motion.div>
        <nav className="hidden md:flex items-center gap-6">
          <Link href="#features" className="text-gray-300 hover:text-white transition-colors text-sm">Features</Link>
          <Link href="#impact" className="text-gray-300 hover:text-white transition-colors text-sm">Impact</Link>
          <Link href="/(auth)/login" className="text-gray-300 hover:text-white transition-colors text-sm">Login</Link>
          <Link
            href="/(auth)/register"
            className="px-4 py-2 bg-primary-500 hover:bg-primary-400 rounded-lg text-sm font-medium transition-colors shadow-glow"
          >
            Get Started
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center justify-center text-center px-6 pt-20 pb-32 max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary-500/20 border border-primary-500/30 text-primary-300 text-sm font-medium mb-6">
            <Zap className="w-3.5 h-3.5" />
            AI-Powered Food Rescue Platform
          </span>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            <span className="gradient-text">Rescue Food.</span>
            <br />
            Feed Communities.
          </h1>

          <p className="text-xl text-gray-300 mb-10 max-w-2xl mx-auto leading-relaxed">
            ResQAI autonomously connects surplus food from restaurants and hotels
            to NGOs and shelters — powered by 10 specialized AI agents, RAG, and real-time routing.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/(auth)/register"
              className="group inline-flex items-center gap-2 px-8 py-4 bg-primary-500 hover:bg-primary-400 rounded-xl font-semibold text-white transition-all shadow-glow hover:shadow-glow-lg hover:-translate-y-0.5"
            >
              Start Rescuing Food
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 px-8 py-4 glass-card rounded-xl font-semibold text-gray-200 hover:text-white transition-all"
            >
              View Architecture
            </Link>
          </div>
        </motion.div>

        {/* Stats bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-20 w-full"
        >
          {[
            { value: "10", label: "AI Agents", icon: "🤖" },
            { value: "6", label: "LLM Models", icon: "🧠" },
            { value: "15", label: "MCP Servers", icon: "🔗" },
            { value: "5", label: "Vector Collections", icon: "🗃️" },
          ].map((stat) => (
            <div key={stat.label} className="glass-card p-4 text-center">
              <div className="text-2xl mb-1">{stat.icon}</div>
              <div className="text-3xl font-bold text-primary-400">{stat.value}</div>
              <div className="text-sm text-gray-400">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Features */}
      <section id="features" className="relative z-10 px-6 py-24 max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">
          Enterprise-Grade <span className="gradient-text">AI Architecture</span>
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              icon: <Zap className="w-6 h-6" />,
              title: "10 Specialized AI Agents",
              desc: "Food Analysis (Gemini), Safety (Claude), NGO Matching (GPT-4o), Route Optimization (DeepSeek), and 6 more agents working in concert.",
              color: "from-blue-500 to-cyan-500",
            },
            {
              icon: <Shield className="w-6 h-6" />,
              title: "Enterprise RAG + Vector DB",
              desc: "Qdrant-powered semantic search over FSSAI guidelines, NGO profiles, donation history, and government regulations.",
              color: "from-primary-500 to-emerald-500",
            },
            {
              icon: <BarChart3 className="w-6 h-6" />,
              title: "Real-Time Intelligence",
              desc: "Live GPS tracking, WebSocket updates, Kafka event streaming, and AI-generated insights with explainability.",
              color: "from-purple-500 to-pink-500",
            },
            {
              icon: <Building2 className="w-6 h-6" />,
              title: "Restaurant Dashboard",
              desc: "Upload food donations, track pickups in real-time, view impact metrics, leaderboard position, and AI sustainability insights.",
              color: "from-orange-500 to-red-500",
            },
            {
              icon: <Users className="w-6 h-6" />,
              title: "NGO Management",
              desc: "Accept donations, manage capacity, track inventory, view beneficiary metrics, and receive demand forecasts.",
              color: "from-yellow-500 to-orange-500",
            },
            {
              icon: <Leaf className="w-6 h-6" />,
              title: "Carbon Impact Tracking",
              desc: "Every rescued meal calculates CO₂ saved, water preserved, and land footprint — with certificate generation.",
              color: "from-teal-500 to-primary-500",
            },
          ].map((feature) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="glass-card p-6 hover:shadow-glow transition-all duration-300 hover:-translate-y-1"
            >
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4 text-white`}>
                {feature.icon}
              </div>
              <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 text-center px-6 py-24">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="glass-card max-w-3xl mx-auto p-12"
        >
          <h2 className="text-4xl font-bold mb-4">Ready to rescue food?</h2>
          <p className="text-gray-300 mb-8">
            Join restaurants, NGOs, and volunteers already using ResQAI to fight food waste.
          </p>
          <Link
            href="/(auth)/register"
            className="inline-flex items-center gap-2 px-8 py-4 bg-primary-500 hover:bg-primary-400 rounded-xl font-semibold text-white transition-all shadow-glow hover:-translate-y-0.5"
          >
            Register Your Organization
            <ArrowRight className="w-4 h-4" />
          </Link>
        </motion.div>
      </section>

      <footer className="relative z-10 text-center py-8 text-gray-500 text-sm">
        © 2026 ResQAI — AI Powered Intelligent Food Rescue Ecosystem
      </footer>
    </main>
  );
}
