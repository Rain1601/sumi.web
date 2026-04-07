# Kodama

Real-time Voice AI Agent Platform.

## Project Structure

- `backend/` - Python FastAPI backend + LiveKit Agent Worker
- `frontend/` - Next.js React frontend
- `docker-compose.yml` - Local dev services (LiveKit Server, Redis)

## Development

### Prerequisites
- Python 3.12+ (conda env `kodama`)
- Node.js 20+ with pnpm
- Docker (for LiveKit Server + Redis)

### Backend
```bash
conda activate kodama
pip install -e "backend/.[all,dev]"
# Seed database:
python -m backend.db.seed
# Run API server:
uvicorn backend.main:app --reload --port 8000
# Worker (separate terminal):
python -m backend.pipeline.worker start
```

### Frontend
```bash
cd frontend && pnpm install && pnpm dev
```

### Infrastructure
```bash
docker compose up -d  # LiveKit Server + Redis
```

## Architecture

- **Auth:** Supabase Auth (JWT verification, supports Google OAuth + email/password)
- **Audio pipeline:** Browser -> WebRTC -> LiveKit Server -> Agent Worker (VAD -> ASR -> NLP -> TTS) -> WebRTC -> Browser
- **Providers:** Pluggable ASR/TTS/NLP via abstract interfaces in `backend/providers/base.py`
- **Agents:** Defined in DB, each with provider configs + tools + system prompt
- **Memory:** Hybrid structured facts (SQLite) + vector search (ChromaDB)
- **Tracing:** All pipeline events collected and broadcasted via WebSocket
- **DB:** SQLite (aiosqlite) now, migrate to Supabase (PostgreSQL/asyncpg) later. Alembic for migrations.

## Key Files

- `backend/providers/base.py` - Provider abstract interfaces (ASR/TTS/NLP)
- `backend/providers/registry.py` - Provider registry + `register_default_providers()`
- `backend/pipeline/worker.py` - LiveKit Agent Worker entry point
- `backend/agents/definition.py` - Agent configuration model
- `backend/db/models.py` - SQLAlchemy ORM models
- `backend/api/deps.py` - Auth dependency (Supabase JWT verification)
- `frontend/src/app/(app)/conversation/page.tsx` - Main conversation UI
- `frontend/src/hooks/useAuth.ts` - Supabase Auth hook
- `frontend/src/lib/supabase.ts` - Supabase client
