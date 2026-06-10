const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  "ws://localhost:8000/api/v1/ws/chat";

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem("voiceai_token");
}

export function setToken(
  token: string | null
) {
  if (typeof window === "undefined") {
    return;
  }

  if (token) {
    localStorage.setItem(
      "voiceai_token",
      token
    );
  } else {
    localStorage.removeItem(
      "voiceai_token"
    );
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: HeadersInit = {
    ...(init.headers || {}),
  };

  if (!(init.body instanceof FormData)) {
    (
      headers as Record<string, string>
    )["Content-Type"] =
      (
        headers as Record<string, string>
      )["Content-Type"] ||
      "application/json";
  }

  if (token) {
    (
      headers as Record<string, string>
    )["Authorization"] =
      `Bearer ${token}`;
  }

  const res = await fetch(
    `${API_URL}${path}`,
    {
      ...init,
      headers,
    }
  );

  if (!res.ok) {
    let detail = res.statusText;

    try {
      const j = await res.json();

      detail =
        j.detail ||
        JSON.stringify(j);
    } catch {
      //
    }

    throw new Error(
      typeof detail === "string"
        ? detail
        : "Request failed"
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  register: (
    email: string,
    password: string,
    full_name?: string
  ) =>
    request<{
      access_token: string;
    }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        full_name,
      }),
    }),

  login: (
    email: string,
    password: string
  ) =>
    request<{
      access_token: string;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
      }),
    }),

  me: () =>
    request<import("@/types").User>(
      "/auth/me"
    ),

  conversations: (q?: string) =>
    request<
      import("@/types").Conversation[]
    >(
      `/chat/conversations${
        q
          ? `?q=${encodeURIComponent(
              q
            )}`
          : ""
      }`
    ),

  createConversation: (
    title?: string
  ) =>
    request<
      import("@/types").Conversation
    >("/chat/conversations", {
      method: "POST",
      body: JSON.stringify({
        title:
          title || "New chat",
      }),
    }),

  getConversation: (id: string) =>
    request<
      import("@/types").ConversationDetail
    >(
      `/chat/conversations/${id}`
    ),

  deleteConversation: (
    id: string
  ) =>
    request<void>(
      `/chat/conversations/${id}`,
      {
        method: "DELETE",
      }
    ),

  renameConversation: (
    id: string,
    title: string
  ) =>
    request<
      import("@/types").Conversation
    >(
      `/chat/conversations/${id}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          title,
        }),
      }
    ),

  documents: () =>
    request<
      import("@/types").DocumentMeta[]
    >("/documents"),

  uploadDocument: (file: File) => {
    const fd = new FormData();

    fd.append("file", file);

    return request<
      import("@/types").DocumentMeta
    >("/documents", {
      method: "POST",
      body: fd,
    });
  },

  deleteDocument: (id: string) =>
    request<void>(
      `/documents/${id}`,
      {
        method: "DELETE",
      }
    ),

  dashboard: () =>
    request<
      import("@/types").DashboardStats
    >("/analytics/dashboard"),

  voiceHistory: () =>
    request<
      import("@/types").VoiceSession[]
    >(
      "/analytics/voice-history"
    ),

  deleteVoiceSession: (id: string) =>
    request<void>(
      `/analytics/voice-history/${id}`,
      {
        method: "DELETE",
      }
    ),

  transcribe: (
    blob: Blob,
    filename = "audio.webm"
  ) => {
    const fd = new FormData();

    fd.append(
      "file",
      blob,
      filename
    );

    return request<{
      text: string;
    }>("/voice/transcribe", {
      method: "POST",
      body: fd,
    });
  },
};

export async function streamChatMessage(
  conversationId: string,
  content: string,
  onEvent: (
    ev: import("@/types").StreamEvent
  ) => void
) {
  const token = getToken();

  const res = await fetch(
    `${API_URL}/chat/conversations/${conversationId}/messages/stream`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Authorization: `Bearer ${token}`,
      },

      body: JSON.stringify({
        content,
      }),
    }
  );

  if (!res.ok || !res.body) {
    throw new Error(
      "Stream failed"
    );
  }

  const reader =
    res.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";

  while (true) {
    const { done, value } =
      await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true,
      }
    );

    const parts =
      buffer.split("\n\n");

    buffer = parts.pop() || "";

    for (const part of parts) {
      const line =
        part.trim();

      if (
        !line.startsWith(
          "data: "
        )
      ) {
        continue;
      }

      try {
        const json =
          line.replace(
            "data: ",
            ""
          );

        const ev = JSON.parse(
          json
        ) as import("@/types").StreamEvent;

        onEvent(ev);
      } catch (err) {
        console.error(
          "SSE parse error:",
          err
        );
      }
    }
  }
}

export async function streamVoiceReply(
  transcript: string,
  conversationId: string | null,
  onEvent: (
    ev: import("@/types").StreamEvent
  ) => void
) {
  const token = getToken();

  const res = await fetch(
    `${API_URL}/voice/reply-stream`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Authorization: `Bearer ${token}`,
      },

      body: JSON.stringify({
        transcript,
        conversation_id:
          conversationId,
      }),
    }
  );

  if (!res.ok || !res.body) {
    throw new Error(
      "Voice stream failed"
    );
  }

  const reader =
    res.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";

  while (true) {
    const { done, value } =
      await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true,
      }
    );

    const parts =
      buffer.split("\n\n");

    buffer = parts.pop() || "";

    for (const part of parts) {
      const line =
        part.trim();

      if (
        !line.startsWith(
          "data: "
        )
      ) {
        continue;
      }

      try {
        const ev = JSON.parse(
          line.slice(6)
        ) as import("@/types").StreamEvent;

        onEvent(ev);
      } catch {
        //
      }
    }
  }
}

export function connectChatWebSocket(
  onMessage: (
    data:
      | import("@/types").StreamEvent
      | {
          type: string;
          data: unknown;
        }
  ) => void
) {
  const token = getToken();

  const ws = new WebSocket(
    `${WS_URL}?token=${encodeURIComponent(
      token || ""
    )}`
  );

  ws.onmessage = (e) => {
    try {
      onMessage(
        JSON.parse(e.data)
      );
    } catch {
      onMessage({
        type: "token",
        data: e.data,
      });
    }
  };

  return ws;
}