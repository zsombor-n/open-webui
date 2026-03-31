# Open WebUI - Project Overview & Quick Reference

> A comprehensive guide for anyone who needs to understand the Open WebUI project quickly.
> For official docs, see [docs.openwebui.com](https://docs.openwebui.com/).

---

## Table of Contents

1. [What is Open WebUI?](#what-is-open-webui)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [Directory Structure](#directory-structure)
4. [Backend (Python / FastAPI)](#backend-python--fastapi)
5. [Frontend (Svelte / SvelteKit)](#frontend-svelte--sveltekit)
6. [How Frontend and Backend Connect](#how-frontend-and-backend-connect)
7. [Database Layer](#database-layer)
8. [API Routes](#api-routes)
9. [Real-Time Communication](#real-time-communication)
10. [Key Features](#key-features)
11. [Plugin / Extensibility System](#plugin--extensibility-system)
12. [Authentication & RBAC](#authentication--rbac)
13. [RAG (Retrieval Augmented Generation)](#rag-retrieval-augmented-generation)
14. [Getting Started (Quick Start)](#getting-started-quick-start)
15. [Build & Deployment](#build--deployment)
16. [Environment Variables (Key Ones)](#environment-variables-key-ones)
17. [Contributing](#contributing)
18. [Further Reading](#further-reading)

---

## What is Open WebUI?

Open WebUI is a **self-hosted, provider-agnostic AI platform** that provides a ChatGPT-style web interface for interacting with LLMs. It runs entirely offline if needed and supports both local models (via Ollama) and cloud APIs (OpenAI, Anthropic, Google, etc.).

**Core value proposition:**
- One UI for many model backends (Ollama, OpenAI-compatible APIs, custom pipelines)
- Full data ownership - everything stored locally on your infrastructure
- Enterprise-ready with RBAC, OAuth/LDAP, groups, and SCIM
- Extensible via Tools, Functions, and Pipelines (Python plugins)
- Built-in RAG for chatting with your documents

**Current version:** 0.8.12

---

## Architecture at a Glance

```
+--------------------------------------------------+
|                   Browser Client                  |
|         (SvelteKit SPA + Socket.IO client)        |
+---------------------------+----------------------+
                            |
              HTTP REST + WebSocket (Socket.IO)
                            |
+---------------------------v----------------------+
|                   FastAPI Backend                 |
|   (Uvicorn, port 8080, serves API + static build)|
+----+--------+--------+--------+---------+--------+
     |        |        |        |         |
  SQLite/  Ollama   OpenAI   Vector    Redis
  Postgres  (local)  (cloud)   DB      (optional,
  /MySQL             APIs    (Chroma    for scaling)
                              default)
```

**In production**, FastAPI serves both the API and the pre-built frontend static files from a single process on port 8080.

**In development**, Vite dev server (port 5173) proxies API requests to FastAPI (port 8080).

---

## Directory Structure

```
open-webui/
├── backend/                     # Python backend
│   └── open_webui/             # Main package
│       ├── main.py             # FastAPI app entry point
│       ├── config.py           # All configuration logic
│       ├── env.py              # Environment variable parsing
│       ├── models/             # SQLAlchemy ORM models (~23 files)
│       ├── routers/            # API route handlers (~28 files)
│       ├── socket/             # Socket.IO server (real-time)
│       ├── retrieval/          # RAG engine (loaders, vector DBs, embeddings)
│       ├── utils/              # Auth, access control, MCP, helpers
│       ├── internal/           # DB engine setup, migrations
│       └── storage/            # File/blob storage abstraction
│
├── src/                         # SvelteKit frontend
│   ├── lib/
│   │   ├── apis/               # API client modules (~28 modules)
│   │   ├── components/         # Svelte components (by feature area)
│   │   ├── stores/             # Svelte reactive stores (state management)
│   │   ├── i18n/               # Internationalization (JSON locale files)
│   │   ├── utils/              # Frontend utility functions
│   │   ├── workers/            # Web Workers
│   │   └── constants.ts        # Base URLs, API endpoint constants
│   └── routes/                  # SvelteKit file-based routing
│       ├── (app)/              # Authenticated app pages
│       │   ├── c/[id]/         # Chat view (dynamic route)
│       │   ├── admin/          # Admin dashboard
│       │   ├── workspace/      # Workspace management
│       │   └── ...
│       └── auth/               # Login / signup pages
│
├── static/                      # Static assets (fonts, themes, images)
├── docs/                        # Project documentation (you are here)
├── cypress/                     # E2E tests
├── scripts/                     # Build scripts
│
├── package.json                 # Frontend deps & scripts
├── pyproject.toml               # Python deps & project metadata
├── svelte.config.js             # SvelteKit config
├── vite.config.ts               # Vite build config
├── Dockerfile                   # Multi-stage Docker build
└── docker-compose.yaml          # Docker Compose for development
```

---

## Backend (Python / FastAPI)

| Aspect | Details |
|--------|---------|
| **Framework** | FastAPI 0.135+ with Uvicorn |
| **Entry point** | `backend/open_webui/main.py` |
| **CLI** | `backend/open_webui/__init__.py` (Typer-based, `open-webui serve`) |
| **ORM** | SQLAlchemy 2.0 (primary) + Peewee (legacy migrations) |
| **Auth** | PyJWT / python-jose, Authlib (OAuth2), LDAP support |
| **Real-time** | Socket.IO 5.x (Redis manager for multi-instance) |
| **AI/ML libs** | Transformers, sentence-transformers, faster-whisper, ONNX |
| **RAG** | LangChain + ChromaDB (default), plus Pinecone/Qdrant/Milvus/etc. |
| **File parsing** | pypdf, docx2txt, python-pptx, BeautifulSoup |
| **Task scheduling** | APScheduler for background jobs |

### Key backend files to know

| File | What it does |
|------|-------------|
| `main.py` | App init, middleware, route mounting, startup/shutdown events |
| `config.py` | Central configuration (reads env vars, DB settings, feature flags) |
| `env.py` | Environment variable parsing and defaults |
| `routers/chats.py` | Chat CRUD and conversation management |
| `routers/auths.py` | Login, signup, token refresh, OAuth callbacks |
| `routers/retrieval.py` | RAG: document upload, embedding, search (largest router ~123KB) |
| `routers/ollama.py` | Proxy to local Ollama instance |
| `routers/openai.py` | Proxy to OpenAI-compatible APIs + streaming |
| `socket/main.py` | Socket.IO event handlers (chat streaming, presence, collab) |
| `internal/db.py` | Database engine creation, connection pooling, session management |

---

## Frontend (Svelte / SvelteKit)

| Aspect | Details |
|--------|---------|
| **Framework** | SvelteKit 2.5+ with Svelte 5 |
| **Build tool** | Vite 5.x |
| **Styling** | Tailwind CSS 4.0 |
| **State** | Svelte stores (built-in reactive state) |
| **Rich editor** | TipTap 3.0 (ProseMirror-based) |
| **Code editor** | CodeMirror 6 |
| **Rendering** | Mermaid diagrams, KaTeX math, Highlight.js code |
| **Charts** | Chart.js, Vega/Vega-Lite |
| **PDF** | PDF.js for viewing, jsPDF for generation |
| **Collab** | Yjs CRDT for real-time collaborative editing |
| **i18n** | i18next with browser language detection |
| **Adapter** | SvelteKit Static Adapter (SSG) |

### Key frontend files to know

| File | What it does |
|------|-------------|
| `src/lib/constants.ts` | Base URLs (`WEBUI_BASE_URL`, `WEBUI_API_BASE_URL`) |
| `src/lib/apis/index.ts` | Central API barrel exports, `getModels()` |
| `src/lib/apis/chats/` | Chat API client functions |
| `src/lib/apis/auths/` | Authentication API client functions |
| `src/routes/(app)/+layout.svelte` | Main app layout (sidebar, auth guard) |
| `src/routes/(app)/c/[id]/+page.svelte` | Chat page (the core UI) |
| `src/routes/auth/+page.svelte` | Login/signup page |

---

## How Frontend and Backend Connect

### Development mode
```
Browser :5173 → Vite Dev Server → Proxy → FastAPI :8080
```
Vite proxies `/api`, `/ollama`, `/openai` requests to `localhost:8080`.

### Production mode
```
Browser :8080 → FastAPI (serves static build + API from single origin)
```
The built frontend is bundled into the Python package at `backend/build/`.

### API communication pattern
```
Svelte Component
  → Svelte Store (reactive state)
  → API Client (src/lib/apis/*)
  → fetch() with Authorization header
  → FastAPI Router
  → SQLAlchemy Model / External API
  → JSON response → Store update → UI re-render
```

### Authentication flow
1. User submits credentials to `/api/v1/auths/signin`
2. Backend returns JWT token
3. Frontend stores token (localStorage) and includes `Authorization: Bearer <token>` on all requests
4. Backend middleware validates token on protected routes

---

## Database Layer

**Location:** `backend/open_webui/models/` (ORM models), `backend/open_webui/internal/db.py` (engine)

**Supported databases:**
| Database | Use case |
|----------|----------|
| **SQLite** | Default, zero-config, good for single-instance |
| **PostgreSQL** | Recommended for production / multi-replica |
| **MySQL / MariaDB** | Supported alternative |
| **SQLCipher** | Encrypted SQLite variant |

**Key models:**

| Model file | Purpose |
|------------|---------|
| `users.py` | User accounts, roles, settings |
| `chats.py` | Conversations (JSON payload with messages) |
| `chat_messages.py` | Individual messages |
| `channels.py` | Group chat channels |
| `knowledge.py` | RAG document/file metadata |
| `functions.py` | Custom function definitions |
| `tools.py` | Tool definitions |
| `groups.py` | User groups for RBAC |
| `access_grants.py` | Fine-grained permission grants |
| `files.py` | Uploaded file metadata |
| `prompts.py` | Saved prompt templates |
| `feedbacks.py` | Model/response feedback |
| `oauth_sessions.py` | OAuth session state |

---

## API Routes

**Base path:** `/api/v1/`

| Route prefix | Router file | Purpose |
|-------------|-------------|---------|
| `/auths` | `auths.py` | Login, signup, token refresh, OAuth |
| `/users` | `users.py` | User CRUD, profiles, settings |
| `/chats` | `chats.py` | Chat conversations |
| `/models` | `models.py` | List/manage available models |
| `/ollama` | `ollama.py` | Proxy to Ollama API |
| `/openai` | `openai.py` | Proxy to OpenAI-compatible APIs |
| `/retrieval` | `retrieval.py` | RAG: upload, embed, search documents |
| `/files` | `files.py` | File upload/download |
| `/knowledge` | `knowledge.py` | Knowledge base management |
| `/tools` | `tools.py` | Tool CRUD |
| `/functions` | `functions.py` | Function CRUD |
| `/prompts` | `prompts.py` | Prompt template CRUD |
| `/channels` | `channels.py` | Channel management |
| `/audio` | `audio.py` | Speech-to-text (Whisper), TTS |
| `/images` | `images.py` | Image generation |
| `/tasks` | `tasks.py` | Background task management |
| `/configs` | `configs.py` | System configuration |
| `/groups` | `groups.py` | User group management |
| `/analytics` | `analytics.py` | Usage analytics |
| `/evaluations` | `evaluations.py` | Model evaluation |
| `/memories` | `memories.py` | Conversation memory |
| `/notes` | `notes.py` | Note-taking |
| `/terminals` | `terminals.py` | Code execution terminals |

---

## Real-Time Communication

Open WebUI uses **Socket.IO** for real-time features:

- **Chat streaming** - LLM responses streamed token-by-token to the UI
- **User presence** - Online/offline status indicators
- **Collaborative editing** - Yjs CRDT sync for shared documents
- **Live updates** - New messages, channel activity

**Backend:** `backend/open_webui/socket/main.py`
**Frontend:** Socket.IO client (`socket.io-client` package)

For multi-instance deployments, Socket.IO uses a **Redis adapter** to broadcast events across instances.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-model support** | Ollama (local), OpenAI, Anthropic, Google, any OpenAI-compatible API |
| **Chat interface** | ChatGPT-style UI with markdown, code highlighting, LaTeX math |
| **RAG** | Chat with documents (PDF, DOCX, TXT, etc.) using vector search |
| **Tools & Functions** | Python plugins that extend LLM capabilities or platform behavior |
| **Pipelines** | Advanced distributed processing (OpenAI API-compatible format) |
| **Image generation** | DALL-E, Stable Diffusion, and other image APIs |
| **Voice** | Speech-to-text (Whisper) and text-to-speech |
| **Channels** | Group chat rooms for team collaboration |
| **Knowledge bases** | Organize documents into searchable collections |
| **Prompt library** | Save and share prompt templates |
| **Model management** | Pull, delete, and configure Ollama models from UI |
| **Admin dashboard** | User management, system settings, usage analytics |
| **Internationalization** | 45+ languages via i18next |
| **Theming** | Dark/light mode, custom themes |
| **MCP support** | Model Context Protocol for tool integration |
| **Collaborative editing** | Real-time document co-editing via Yjs |

---

## Plugin / Extensibility System

Open WebUI has three extension mechanisms:

### Tools
- **What:** Plugins that give LLMs access to external data (weather, APIs, databases)
- **Who can create:** Users with `workspace.tools` permission (admin-only by default)
- **Security note:** Creating tools is equivalent to shell access - only grant to trusted users
- **Location:** Managed via Workspace tab in UI, stored in `tools` DB table

### Functions
- **What:** Platform-level extensions that customize Open WebUI itself
- **Examples:** Add new model providers, custom data filters, UI modifications
- **Who can create:** Admins only (via Admin Panel)
- **Location:** Managed via Admin Panel, stored in `functions` DB table

### Pipelines
- **What:** Advanced, distributed processing chains compatible with OpenAI's API format
- **Use case:** Complex multi-machine setups, expert users
- **Location:** Separate infrastructure, managed via `routers/pipelines.py`

> **Security warning:** All three execute arbitrary Python code on the server. Review code carefully before installing community plugins.

---

## Authentication & RBAC

### Authentication methods
- **Local accounts** - Email/password with JWT tokens
- **OAuth2** - Via Authlib (Google, GitHub, Microsoft, etc.)
- **LDAP** - Enterprise directory integration
- **SCIM** - Automated user provisioning from identity providers
- **Single-user mode** - Set `WEBUI_AUTH=False` to disable auth entirely

### Role-Based Access Control
- **Admin** - Full system access, user management, function creation
- **User** - Chat, use tools (if permitted), manage own data
- **Pending** - New signups awaiting admin approval (configurable)

### Key RBAC concepts
- **Groups** (`models/groups.py`) - Organize users into groups
- **Access Grants** (`models/access_grants.py`) - Fine-grained permission assignments
- **Model visibility** - Models are private by default, explicitly shared
- **Tool permissions** - `workspace.tools` permission controls who can create tools

### Important: First account = Admin
The first account created after installation automatically receives Administrator privileges.

---

## RAG (Retrieval Augmented Generation)

RAG lets users chat with their documents by embedding them into a vector database and retrieving relevant chunks during conversations.

### How it works
1. **Upload** - User uploads documents (PDF, DOCX, TXT, etc.)
2. **Parse** - Backend extracts text using format-specific loaders
3. **Chunk** - Text split into overlapping chunks
4. **Embed** - Chunks converted to vectors using an embedding model
5. **Store** - Vectors stored in the configured vector database
6. **Query** - During chat, user's question is embedded and similar chunks retrieved
7. **Augment** - Retrieved chunks injected into the LLM prompt as context

### Supported vector databases
| Database | Notes |
|----------|-------|
| **ChromaDB** | Default, embedded, zero-config |
| **PostgreSQL (pgvector)** | Production-grade, with main DB |
| **Qdrant** | High-performance vector search |
| **Milvus** | Scalable vector DB |
| **Pinecone** | Managed cloud vector DB |
| **OpenSearch** | AWS-compatible search engine |
| **Weaviate** | AI-native vector DB |

### Supported document formats
PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, Markdown, and more (via loaders in `backend/open_webui/retrieval/loaders/`).

### Web search integration
RAG can also search the web (DuckDuckGo, Firecrawl, etc.) and include results as context.

### Backend location
- Core logic: `backend/open_webui/retrieval/`
- Vector DB adapters: `backend/open_webui/retrieval/vector/`
- Document loaders: `backend/open_webui/retrieval/loaders/`
- Embedding models: `backend/open_webui/retrieval/models/`
- API router: `backend/open_webui/routers/retrieval.py`

---

## Getting Started (Quick Start)

### Docker (recommended)
```bash
# Pull and run
docker run -d -p 3000:8080 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main

# With GPU support
docker run -d -p 3000:8080 --gpus all \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:cuda

# Connect to remote Ollama
docker run -d -p 3000:8080 \
  -e OLLAMA_BASE_URL=https://your-ollama-server.com \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main
```

Access at **http://localhost:3000**

### Python (via uv - recommended for non-Docker)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
DATA_DIR=~/.open-webui uvx --python 3.11 open-webui@latest serve
```

Access at **http://localhost:8080**

### Python (via pip)
```bash
pip install open-webui
open-webui serve
```

### Docker Compose
```yaml
services:
  openwebui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "3000:8080"
    volumes:
      - open-webui:/app/backend/data
volumes:
  open-webui:
```
```bash
docker compose up -d
```

### Development setup
```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 --reload

# Frontend (separate terminal)
npm install
npm run dev   # Starts Vite on :5173, proxies API to :8080
```

---

## Build & Deployment

### Docker build (multi-stage)
1. **Stage 1:** Node 22 Alpine - builds frontend (`npm ci && npm run build`)
2. **Stage 2:** Python 3.11 Slim - installs backend deps, copies frontend build
3. Result: Single image serving everything on port 8080

### Image variants
| Tag | Description |
|-----|-------------|
| `main` | Standard image |
| `cuda` | Nvidia GPU support |
| `main-slim` | Reduced size (fewer ML dependencies) |
| `ollama` | Bundled with Ollama |

### Production considerations
- Use **PostgreSQL** instead of SQLite for multi-instance
- Add **Redis** for Socket.IO scaling across replicas
- Configure an **external vector DB** (not embedded ChromaDB) for HA
- Set `UVICORN_WORKERS=1` during updates to prevent DB corruption
- Use sticky sessions if running multiple replicas behind a load balancer

---

## Environment Variables (Key Ones)

| Variable | Default | Purpose |
|----------|---------|---------|
| `WEBUI_AUTH` | `True` | Enable/disable authentication |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OPENAI_API_BASE_URL` | — | OpenAI-compatible API endpoint |
| `OPENAI_API_KEY` | — | API key for OpenAI-compatible service |
| `DATA_DIR` | `/app/backend/data` | Persistent data directory |
| `DATABASE_URL` | `sqlite:///...` | Database connection string |
| `VECTOR_DB` | `chroma` | Vector database backend |
| `CHROMA_HTTP_HOST` | — | Remote ChromaDB hostname |
| `CHROMA_HTTP_PORT` | `8000` | Remote ChromaDB port |
| `WEBUI_SECRET_KEY` | auto-generated | JWT signing secret |
| `UVICORN_WORKERS` | `1` | Number of worker processes |
| `ENABLE_OAUTH_SIGNUP` | — | Allow OAuth-based registration |
| `REDIS_URL` | — | Redis URL for multi-instance Socket.IO |

Full configuration is managed in `backend/open_webui/config.py` and `backend/open_webui/env.py`.

---

## Contributing

- **Issues:** [github.com/open-webui/open-webui/issues](https://github.com/open-webui/open-webui/issues)
- **Discussions:** [github.com/open-webui/open-webui/discussions](https://github.com/open-webui/open-webui/discussions)
- **Discord:** [discord.gg/5rJgQTnV4s](https://discord.gg/5rJgQTnV4s)
- **Docs repo:** [github.com/open-webui/docs](https://github.com/open-webui/docs)
- **Security:** See [SECURITY.md](./SECURITY.md)
- **Contribution guide:** See [CONTRIBUTING.md](./CONTRIBUTING.md)

**Key rules:**
1. Open a discussion before submitting a PR
2. Follow coding standards, include tests
3. Keep translation PRs separate from feature PRs
4. Security vulnerabilities go through [GitHub Security Advisories](https://github.com/open-webui/open-webui/security), not Issues

---

## Further Reading

| Resource | URL |
|----------|-----|
| Official docs | [docs.openwebui.com](https://docs.openwebui.com/) |
| Quick start | [docs.openwebui.com/getting-started/quick-start](https://docs.openwebui.com/getting-started/quick-start) |
| Plugin security | [docs.openwebui.com/features/extensibility/plugin](https://docs.openwebui.com/features/extensibility/plugin/) |
| GitHub repo | [github.com/open-webui/open-webui](https://github.com/open-webui/open-webui) |
| Ollama | [ollama.com](https://ollama.com/) |
| Apache reverse proxy setup | [apache.md](./apache.md) |
