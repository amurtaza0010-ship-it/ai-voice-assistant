"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, FileText, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DocumentsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const [error, setError] = useState("");

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.documents(),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="h-full overflow-y-auto p-6 lg:p-10">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Knowledge base</h1>
          <p className="mt-2 text-zinc-400">Upload PDF, DOCX, or TXT for RAG-powered answers</p>
        </div>
        <Button onClick={() => inputRef.current?.click()}>
          <Upload className="h-4 w-4" /> Upload
        </Button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.txt,.md"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
            e.target.value = "";
          }}
        />
      </div>
      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {isLoading && <p className="text-zinc-500">Loading…</p>}
        {docs.map((d) => (
          <Card key={d.id}>
            <CardHeader className="flex flex-row items-start justify-between">
              <FileText className="h-5 w-5 text-cyan-400 shrink-0" />
              <Button
                variant="ghost"
                size="icon"
                onClick={async () => {
                  await api.deleteDocument(d.id);
                  qc.invalidateQueries({ queryKey: ["documents"] });
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <CardTitle className="text-base truncate">{d.filename}</CardTitle>
              <p className="text-xs text-zinc-500 mt-2">{d.chunk_count} chunks · {d.mime_type}</p>
            </CardContent>
          </Card>
        ))}
        {!isLoading && docs.length === 0 && (
          <p className="text-zinc-500 col-span-full">No documents yet. Upload your first file.</p>
        )}
      </div>
    </div>
  );
}
