"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Conversation, DocumentMeta } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("voiceai_token");
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error("Admin request failed");
  if (res.status === 204) return undefined as T;
  return res.json();
}

export default function AdminPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();

  useEffect(() => {
    if (user && !user.is_admin) router.replace("/dashboard");
  }, [user, router]);

  const { data: docs = [] } = useQuery({
    queryKey: ["admin-docs"],
    queryFn: () => adminFetch<DocumentMeta[]>("/admin/documents"),
    enabled: !!user?.is_admin,
  });

  const { data: convs = [] } = useQuery({
    queryKey: ["admin-convs"],
    queryFn: () => adminFetch<Conversation[]>("/admin/conversations"),
    enabled: !!user?.is_admin,
  });

  if (!user?.is_admin) return null;

  return (
    <div className="h-full overflow-y-auto p-6 lg:p-10">
      <h1 className="text-3xl font-bold text-white">Admin</h1>
      <p className="mt-2 text-zinc-400">Manage documents and conversations</p>

      <div className="mt-10 grid lg:grid-cols-2 gap-8">
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">All documents</h2>
          <div className="space-y-2">
            {docs.map((d) => (
              <Card key={d.id}>
                <CardHeader className="flex flex-row justify-between items-center py-3">
                  <CardTitle className="text-sm truncate">{d.filename}</CardTitle>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={async () => {
                      await adminFetch(`/admin/documents/${d.id}`, { method: "DELETE" });
                      qc.invalidateQueries({ queryKey: ["admin-docs"] });
                    }}
                  >
                    Delete
                  </Button>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">Conversations</h2>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {convs.map((c) => (
              <Card key={c.id}>
                <CardContent className="py-3 flex justify-between items-center gap-2">
                  <span className="text-sm truncate">{c.title}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      await adminFetch(`/admin/conversations/${c.id}`, { method: "DELETE" });
                      qc.invalidateQueries({ queryKey: ["admin-convs"] });
                    }}
                  >
                    Delete
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
