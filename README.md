# VoiceAI — Production AI Voice Assistant SaaS

Full-stack AI voice assistant platform with real-time voice, streaming chat, RAG knowledge base, agentic tool calling, local app launching, web search & news, analytics dashboard, and Docker deployment.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15, TypeScript, Tailwind, Framer Motion, Zustand, React Query |
| Backend | FastAPI, SQLAlchemy, WebSockets, LangChain |
| Database | PostgreSQL |
| Vector DB | ChromaDB |
| AI | OpenRouter (`openai/gpt-4o-mini` default) |
| Voice | Browser Speech API + optional OpenAI Whisper/TTS |

## Quick start (Docker)

1. Copy environment file and add your OpenRouter key:

```bash
cp .env.example .env
```

2. Set `OPENROUTER_API_KEY` in `.env`.

3. Build and run:

```bash
docker-compose up --build
```

4. Open **http://localhost:3000** — register a new account.

### Optional: OpenAI for server-side Whisper/TTS

Set `OPENAI_API_KEY` in `.env` for `/voice/transcribe` and `/voice/tts`. Without it, the voice UI uses the browser Web Speech API and `speechSynthesis`.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Start PostgreSQL locally or use docker-compose up postgres
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

## Project structure

```
backend/app/
  api/v1/endpoints/   # REST + WebSocket routes
  core/               # config, security, logging
  models/             # SQLAlchemy models
  services/           # AI, RAG, voice, analytics
  rag/                # (via services/rag_service)
  tools/              # tool registry (time, calculator, app launcher, web search)
frontend/
  app/                # Next.js App Router pages
  components/         # UI, chat, voice, layout
  services/           # API client
  store/              # Zustand auth
```

## Features

- **Auth** — JWT register/login, protected app routes
- **Chat** — SSE streaming, markdown, multi-session, search
- **Voice** — push-to-talk, live transcription, streaming replies, TTS
- **RAG** — PDF/DOCX/TXT upload, ChromaDB semantic retrieval
- **Agents** — OpenRouter tool calling (time, calculator, local app launcher, web search & news)
- **Local App Calling** — voice/chat command se system apps open karo (Calculator, Notepad, Browser, File Explorer, etc.)
- **Web Search & News** — real-time web search aur latest news retrieval via agentic tool calling
- **Dashboard** — usage stats and token estimates
- **Admin** — list/delete documents and conversations (`is_admin` users)

### Create an admin user

After registering, set admin in PostgreSQL:

```sql
UPDATE users SET is_admin = true WHERE email = 'you@example.com';
```

## API overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login |
| GET | `/api/v1/auth/me` | Current user |
| GET/POST | `/api/v1/chat/conversations` | List/create chats |
| POST | `/api/v1/chat/conversations/{id}/messages/stream` | SSE chat stream |
| POST | `/api/v1/voice/reply-stream` | Voice AI stream |
| POST | `/api/v1/documents` | Upload for RAG |
| GET | `/api/v1/analytics/dashboard` | Stats |
| WS | `/api/v1/ws/chat?token=` | WebSocket chat |

Docs: **http://localhost:8000/docs**

## Environment variables

See `.env.example` for all options.

## License

MIT