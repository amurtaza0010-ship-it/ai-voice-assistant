export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface DocumentMeta {
  id: string;
  filename: string;
  mime_type: string;
  chunk_count: number;
  created_at: string;
}

export interface DashboardStats {
  total_conversations: number;
  total_messages: number;
  total_voice_sessions: number;
  total_documents: number;
  tokens_prompt_30d: number;
  tokens_completion_30d: number;
}

export interface VoiceSession {
  id: string;
  transcript: string | null;
  assistant_reply: string | null;
  duration_ms: number | null;
  created_at: string;
}

export type StreamEvent =
  | { type: "token"; data: string }
  | { type: "status"; data: string }
  | { type: "error"; data: string }
  | { type: "done"; data: { message_id?: string; conversation_id?: string; has_tts?: boolean } };
