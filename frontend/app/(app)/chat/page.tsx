"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Search, Send, Trash2 } from "lucide-react";

import { api, streamChatMessage } from "@/services/api";
import type { Message } from "@/types";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MarkdownMessage } from "@/components/chat/markdown-message";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const qc = useQueryClient();

  const [activeId, setActiveId] = useState<string | null>(null);

  const [search, setSearch] = useState("");

  const [input, setInput] = useState("");

  const [streaming, setStreaming] = useState("");
  const [toolStatus, setToolStatus] = useState("");

  const [loading, setLoading] = useState(false);

  const [localMessages, setLocalMessages] = useState<Message[]>([]);

  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations", search],
    queryFn: () => api.conversations(search || undefined),
  });

  const { data: detail } = useQuery({
    queryKey: ["conversation", activeId],
    queryFn: () => api.getConversation(activeId!),
    enabled: !!activeId,
  });

  useEffect(() => {
    if (detail?.messages) {
      setLocalMessages(detail.messages);
    }
  }, [detail]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [localMessages, streaming]);

  async function newChat() {
    const c = await api.createConversation();

    setActiveId(c.id);

    setLocalMessages([]);

    qc.invalidateQueries({
      queryKey: ["conversations"],
    });
  }

  async function send() {
    if (!input.trim() || loading) return;

    setLoading(true);

    let convId = activeId;

    try {
      if (!convId) {
        const c = await api.createConversation();

        convId = c.id;

        setActiveId(c.id);
      }

      const content = input.trim();

      setInput("");

      const tempUser: Message = {
        id: `tmp-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };

      setLocalMessages((m) => [...m, tempUser]);

      setStreaming("");
      setToolStatus("");

      let assistant = "";

      await streamChatMessage(
        convId,
        content,
        (ev) => {
          console.log("STREAM EVENT:", ev);

          if (ev.type === "status") {
            setToolStatus(String(ev.data || ""));
          }

          if (ev.type === "token") {
            setToolStatus("");
            const token =
              typeof ev.data === "string"
                ? ev.data
                : String(ev.data || "");

            assistant += token;

            setStreaming(assistant);
          }

          if (ev.type === "error") {
            setStreaming(`Error: ${String(ev.data)}`);
          }

          if (ev.type === "done") {
            setLocalMessages((m) => [
              ...m,
              {
                id:
                  (ev.data as any)?.message_id ||
                  `a-${Date.now()}`,

                role: "assistant",

                content: assistant,

                created_at:
                  new Date().toISOString(),
              },
            ]);

            setStreaming("");
            setToolStatus("");

            qc.invalidateQueries({
              queryKey: ["conversations"],
            });

            qc.invalidateQueries({
              queryKey: [
                "conversation",
                convId,
              ],
            });
          }
        }
      );
    } catch (err) {
      console.error(err);

      setStreaming("Failed to get AI response.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh)]">
      <aside className="w-72 border-r border-white/10 flex flex-col bg-black/30">
        <div className="p-4 space-y-3">
          <Button
            className="w-full"
            onClick={newChat}
          >
            <Plus className="h-4 w-4" />
            New chat
          </Button>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />

            <Input
              className="pl-9"
              placeholder="Search…"
              value={search}
              onChange={(e) =>
                setSearch(e.target.value)
              }
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveId(c.id)}
              className={cn(
                "w-full text-left rounded-xl px-3 py-2 text-sm truncate transition-colors",
                activeId === c.id
                  ? "bg-white/10 text-white"
                  : "text-zinc-400 hover:bg-white/5"
              )}
            >
              {c.title}
            </button>
          ))}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
          <h2 className="font-semibold text-white truncate">
            {detail?.title ||
              "New conversation"}
          </h2>

          {activeId && (
            <Button
              variant="ghost"
              size="icon"
              onClick={async () => {
                await api.deleteConversation(
                  activeId
                );

                setActiveId(null);

                setLocalMessages([]);

                qc.invalidateQueries({
                  queryKey: [
                    "conversations",
                  ],
                });
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </header>

        <div className="flex-1 overflow-y-auto px-4 lg:px-8 py-6 space-y-6">
          <AnimatePresence>
            {localMessages.map((m) => (
              <motion.div
                key={m.id}
                initial={{
                  opacity: 0,
                  y: 8,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                className={cn(
                  "max-w-3xl",
                  m.role === "user"
                    ? "ml-auto"
                    : ""
                )}
              >
                <div
                  className={cn(
                    "rounded-2xl px-4 py-3 text-sm",
                    m.role === "user"
                      ? "bg-gradient-to-r from-violet-600/80 to-cyan-600/60 text-white"
                      : "glass text-zinc-100"
                  )}
                >
                  {m.role ===
                  "assistant" ? (
                    <MarkdownMessage
                      content={m.content}
                    />
                  ) : (
                    m.content
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {(toolStatus || streaming) && (
            <div className="glass max-w-3xl rounded-2xl px-4 py-3 text-sm">
              {toolStatus && !streaming && (
                <p className="text-zinc-400 mb-2">{toolStatus}</p>
              )}
              {streaming && (
                <>
                  <MarkdownMessage
                    content={streaming}
                  />
                  <span className="inline-block w-2 h-4 ml-1 bg-violet-400 animate-pulse" />
                </>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="border-t border-white/10 p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();

              send();
            }}
            className="max-w-3xl mx-auto flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) =>
                setInput(e.target.value)
              }
              placeholder="Message VoiceAI…"
              disabled={loading}
            />

            <Button
              type="submit"
              size="icon"
              disabled={loading}
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}