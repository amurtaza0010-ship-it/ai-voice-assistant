"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  MessageSquare,
  Mic,
  FileText,
  Shield,
  LogOut,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/voice", label: "Voice", icon: Mic },
  { href: "/documents", label: "Knowledge", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();

  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  return (
    <aside className="hidden lg:flex w-64 flex-col border-r border-white/10 bg-black/40 backdrop-blur-xl p-4">
      <Link
        href="/dashboard"
        className="flex items-center gap-2 px-2 py-3 mb-6"
      >
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-400 flex items-center justify-center">
          <Sparkles className="h-5 w-5 text-white" />
        </div>

        <span className="font-semibold text-white tracking-tight">
          VoiceAI
        </span>
      </Link>

      <nav className="flex-1 space-y-1">
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              className="relative block"
            >
              {active && (
                <motion.div
                  layoutId="nav-pill"
                  className="absolute inset-0 rounded-xl bg-white/10"
                  transition={{
                    type: "spring",
                    bounce: 0.2,
                    duration: 0.4,
                  }}
                />
              )}

              <span
                className={cn(
                  "relative z-10 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </span>
            </Link>
          );
        })}

        {user?.is_admin && (
          <Link
            href="/admin"
            className={cn(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm",
              pathname?.startsWith("/admin")
                ? "text-white bg-white/10"
                : "text-zinc-400"
            )}
          >
            <Shield className="h-4 w-4" />
            Admin
          </Link>
        )}
      </nav>

      <button
        onClick={() => {
          logout();
          window.location.href = "/login";
        }}
        className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-zinc-400 hover:text-white hover:bg-white/5"
      >
        <LogOut className="h-4 w-4" />
        Sign out
      </button>
    </aside>
  );
}