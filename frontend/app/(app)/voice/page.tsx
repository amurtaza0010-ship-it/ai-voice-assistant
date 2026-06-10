"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Mic, Square, Trash2, Volume2, VolumeX } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, streamVoiceReply } from "@/services/api";
import type { VoiceSession } from "@/types";
import { Button } from "@/components/ui/button";
import { Waveform } from "@/components/voice/waveform";
import { MarkdownMessage } from "@/components/chat/markdown-message";
import { cn } from "@/lib/utils";

export default function VoicePage() {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [streaming, setStreaming] = useState("");
  const [toolStatus, setToolStatus] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const [speaking, setSpeaking] = useState(false);

  const stopSpeaking = useCallback(() => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    setSpeaking(false);
  }, []);

  const speak = useCallback(
    async (text: string) => {
      stopSpeaking();

      if (!("speechSynthesis" in window)) {
        return;
      }

      setSpeaking(true);

      const utterance = new SpeechSynthesisUtterance(text);

      utterance.lang = "en-US";
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.volume = 1;

      utterance.onend = () => {
        setSpeaking(false);
      };

      utterance.onerror = () => {
        setSpeaking(false);
      };

      window.speechSynthesis.speak(utterance);
    },
    [stopSpeaking]
  );

  useEffect(() => {
    const SR =
      typeof window !== "undefined" &&
      (window.SpeechRecognition ||
        window.webkitSpeechRecognition);

    if (!SR) return;

    const rec = new SR();

    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (e: SpeechRecognitionEvent) => {
      let text = "";

      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }

      setTranscript(text);
    };

    recognitionRef.current = rec;
  }, []);

  function toggleListen() {
    const rec = recognitionRef.current;

    if (!rec) {
      alert("Speech recognition not supported in this browser.");
      return;
    }

    if (listening) {
      rec.stop();
      setListening(false);
    } else {
      setTranscript("");
      rec.start();
      setListening(true);
    }
  }

  async function sendVoice() {
    const text = transcript.trim();

    if (!text) return;

    setReply("");
    setStreaming("");
    setToolStatus("");

    let full = "";

    await streamVoiceReply(
      text,
      conversationId,
      (ev) => {
        if (ev.type === "status") {
          setToolStatus(String(ev.data || ""));
        }

        if (ev.type === "token") {
          setToolStatus("");
          full += ev.data;

          setStreaming(full);
        }

        if (ev.type === "done" && ev.data.conversation_id) {
          setConversationId(ev.data.conversation_id);

          setReply(full);

          setStreaming("");
          setToolStatus("");

          speak(full);
        }

        if (ev.type === "error") {
          setToolStatus("");
          setStreaming(`Error: ${ev.data}`);
        }
      }
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 lg:p-10">
      <h1 className="text-3xl font-bold text-white">
        Voice assistant
      </h1>

      <p className="mt-2 text-zinc-400">
        Push-to-talk · streaming AI · browser speech synthesis
      </p>

      <div className="mt-12 flex flex-col items-center">
        <Waveform active={listening || !!streaming} />

        <motion.div
          className={cn(
            "mt-8 h-28 w-28 rounded-full flex items-center justify-center transition-all",
            listening
              ? "bg-gradient-to-br from-red-500 to-orange-500 shadow-lg shadow-red-500/40"
              : "bg-gradient-to-br from-violet-500 to-cyan-500 shadow-lg shadow-violet-500/40"
          )}
          whileTap={{ scale: 0.95 }}
        >
          <Button
            size="icon"
            variant="ghost"
            className="h-20 w-20 rounded-full hover:bg-transparent"
            onClick={toggleListen}
          >
            {listening ? (
              <Square className="h-10 w-10 text-white" />
            ) : (
              <Mic className="h-10 w-10 text-white" />
            )}
          </Button>
        </motion.div>

        <p className="mt-4 text-sm text-zinc-500">
          {listening
            ? "Listening… tap to stop"
            : "Tap to talk"}
        </p>

        <div className="mt-8 flex gap-3">
          <Button
            onClick={sendVoice}
            disabled={!transcript.trim() || !!streaming}
          >
            Send to AI
          </Button>

          <Button
            variant="secondary"
            onClick={stopSpeaking}
            disabled={!speaking}
          >
            {speaking ? (
              <VolumeX className="h-4 w-4" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}

            Stop speech
          </Button>
        </div>

        {transcript && (
          <div className="mt-8 w-full max-w-2xl glass rounded-2xl p-4">
            <p className="text-xs text-zinc-500 mb-2">
              You said
            </p>

            <p className="text-white">
              {transcript}
            </p>
          </div>
        )}

        {(toolStatus || streaming || reply) && (
          <div className="mt-4 w-full max-w-2xl glass rounded-2xl p-4">
            <p className="text-xs text-zinc-500 mb-2">
              Assistant
            </p>

            {toolStatus && !streaming && !reply && (
              <p className="text-zinc-400 text-sm">{toolStatus}</p>
            )}

            {(streaming || reply) && (
              <MarkdownMessage
                content={streaming || reply}
              />
            )}
          </div>
        )}
      </div>

      <VoiceSessionList />
    </div>
  );
}

function VoiceSessionList() {
  const qc = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: sessions = [] } = useQuery({
    queryKey: ["voice-history"],
    queryFn: () => api.voiceHistory(),
  });

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await api.deleteVoiceSession(id);
      qc.setQueryData<VoiceSession[]>(["voice-history"], (old) =>
        (old ?? []).filter((s) => s.id !== id)
      );
    } catch (err) {
      console.error(err);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="mt-16 max-w-3xl">
      <h2 className="text-lg font-semibold text-white mb-4">
        Recent voice sessions
      </h2>

      <div className="space-y-3">
        {sessions.slice(0, 10).map((s) => (
          <div
            key={s.id}
            className="group glass rounded-xl p-4 text-sm flex items-start gap-2"
          >
            <div className="flex-1 min-w-0">
              <p className="text-zinc-400 truncate">
                {s.transcript}
              </p>

              <p className="text-zinc-500 mt-1 line-clamp-2">
                {s.assistant_reply}
              </p>
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="shrink-0 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-red-400"
              onClick={() => handleDelete(s.id)}
              disabled={deletingId === s.id}
              aria-label="Delete session"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}