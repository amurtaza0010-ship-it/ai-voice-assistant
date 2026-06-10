"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { MessageSquare, Mic, FileText, Coins } from "lucide-react";
import { api } from "@/services/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.dashboard(),
  });

  const cards = [
    { label: "Conversations", value: stats?.total_conversations ?? 0, icon: MessageSquare },
    { label: "Messages", value: stats?.total_messages ?? 0, icon: MessageSquare },
    { label: "Voice sessions", value: stats?.total_voice_sessions ?? 0, icon: Mic },
    { label: "Documents", value: stats?.total_documents ?? 0, icon: FileText },
    { label: "Tokens (30d)", value: (stats?.tokens_prompt_30d ?? 0) + (stats?.tokens_completion_30d ?? 0), icon: Coins },
  ];

  return (
    <div className="h-full overflow-y-auto p-6 lg:p-10">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <p className="mt-2 text-zinc-400">Usage analytics and workspace overview</p>
      </motion.div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((c, i) => (
          <motion.div key={c.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-zinc-400">{c.label}</CardTitle>
                <c.icon className="h-4 w-4 text-violet-400" />
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-white">{isLoading ? "—" : c.value.toLocaleString()}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
