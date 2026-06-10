"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Mic, Brain, FileSearch, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

const features = [
  { icon: Mic, title: "Real-time voice", desc: "Push-to-talk, streaming STT, and natural TTS replies." },
  { icon: Brain, title: "Agentic AI", desc: "Tool calling, multi-step reasoning, and smart actions." },
  { icon: FileSearch, title: "RAG knowledge", desc: "Upload PDFs and docs for context-aware answers." },
  { icon: Zap, title: "Streaming chat", desc: "OpenRouter-powered responses with memory." },
];

export default function LandingPage() {
  return (
    <div className="mesh-bg min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="text-xl font-semibold tracking-tight">VoiceAI</span>
        <nav className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-zinc-400 hover:text-white">
            Sign in
          </Link>
          <Button asChild>
            <Link href="/register">Get started</Link>
          </Button>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          className="pt-16 pb-20 text-center"
        >
          <p className="mb-4 inline-block rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1 text-xs font-medium text-violet-300">
            Production-grade AI Voice SaaS
          </p>
          <h1 className="mx-auto max-w-4xl text-5xl font-bold tracking-tight md:text-7xl bg-gradient-to-b from-white to-zinc-500 bg-clip-text text-transparent">
            Talk, think, and act with your AI assistant
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400">
            Voice-first conversations, document intelligence, and agentic workflows — built for teams who ship fast.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Button size="lg" asChild>
              <Link href="/register">
                Start free <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <Link href="/login">View demo</Link>
            </Button>
          </div>
        </motion.section>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i }}
              className="glass rounded-2xl p-6"
            >
              <f.icon className="h-8 w-8 text-violet-400 mb-4" />
              <h3 className="font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-zinc-400">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}
