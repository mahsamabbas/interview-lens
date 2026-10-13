# InterviewLens

Local interview studio: turn a recording (or pasted transcript) plus a job description into **two evidence-backed reports**.

- **Candidate report** — constructive feedback, strengths, improvements
- **Hiring report** — fit scores and a `pass` / `borderline` / `no` recommendation

**Flow:** Setup (JD + source) → Transcript studio (edit speakers / wording) → Reports.

Everything runs on your machine. The browser talks only to FastAPI — never to Ollama or Whisper directly.

## Tech stack

| Layer | Choices |
| --- | --- |
| Frontend | React 19, TypeScript, Vite 8 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) + custom CSS |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| Persistence | SQLite (`sqlite3` stdlib) — sessions, segments, jobs, reports |
| Chat LLM | Local [Ollama](https://ollama.com) — default `qwen2.5:7b` (structured JSON via `/api/chat`) |
| HTTP client | `httpx` (Ollama + tests) |
| ASR (Docker / CPU) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + CTranslate2 |
| ASR (Apple Silicon host) | [mlx-whisper](https://github.com/ml-explore/mlx-examples) + Apple Metal (`mlx`) |
| Diarization | [pyannote.audio](https://github.com/pyannote/pyannote-audio) — `pyannote/speaker-diarization-community-1` |
| Audio decode | FFmpeg (system or `imageio-ffmpeg`), PyAV (`av`) for faster-whisper |
| Uploads | `python-multipart` — `.wav` `.mp3` `.m4a` `.webm` `.mp4` `.mov` |
| Config | `python-dotenv` + `.env` / `.env.example` |
| Delivery | Docker Compose (backend + nginx frontend) |
| Tests | Backend: `pytest` + FastAPI `TestClient` / `httpx`. Frontend: Vitest + Testing Library + jsdom |

### Libraries & smaller pieces

**Backend**

- `fastapi` / `uvicorn[standard]` — sessions, JD, paste/upload, transcribe & analyze jobs, reports, health
- `pydantic` — request/response and report schemas
- `faster-whisper` + `torch` — CPU STT in Docker / Linux
- `mlx-whisper` + `mlx` — Metal STT on Mac host (optional `requirements-mlx.txt`)
- `pyannote.audio` — speaker turns; labels mapped to interviewer / candidate by first appearance
- `ffmpeg` — normalize media to 16 kHz mono before ASR / diarization
- `httpx` — Ollama chat; large `num_ctx` so long interviews don’t stall
- SQLite — async-style background jobs with status polling (`queued` → `transcribing` / `diarizing` / `analyzing` → `done`)

**Frontend**

- `react` / `react-dom` / `vite` / `typescript` — three-step studio UI
- `tailwindcss` — layout and report chrome
- Vitest + Testing Library — job copy, setup, transcript helpers

**Requirements split**

| File | Contents |
| --- | --- |
| `backend/requirements.txt` | API core (paste + analyze + tests) |
| `backend/requirements-stt.txt` | faster-whisper, torch, pyannote, av |
| `backend/requirements-mlx.txt` | mlx-whisper + imageio-ffmpeg (Mac host only) |

**API surface (browser → FastAPI only)**

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness; `ollama`, `whisper_ready`, `stt_backend`, `hf_token_set` |
| `POST` | `/sessions` | Create session |
| `GET` | `/sessions` / `/sessions/{id}` | List / detail + segments |
| `PUT` | `/sessions/{id}/jd` | Save job description |
| `POST` | `/sessions/{id}/source/paste` | Parse labeled transcript |
| `POST` | `/sessions/{id}/source/upload` | Upload media |
| `POST` | `/sessions/{id}/source/sample` | Load sample JD + transcript |
| `POST` | `/sessions/{id}/transcribe` | Start STT + diarization job |
| `PATCH` | `/sessions/{id}/transcript` | Edit segments / speakers |
| `POST` | `/sessions/{id}/analyze` | Start dual-report LLM job |
| `GET` | `/sessions/{id}/jobs/{job_id}` | Poll job status |
| `GET` | `/sessions/{id}/reports` | Candidate + hiring reports |

## Ports

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3004 |
| API | http://localhost:8004 |
| Ollama (host) | http://localhost:11434 |

## Prerequisites

- Python 3.12 and Node 22
- [Ollama](https://ollama.com) on the host
- For upload transcription: free [Hugging Face](https://huggingface.co) token (pyannote gated models)
- Optional on Apple Silicon: Metal MLX stack for faster ASR

## 1. Ollama

```bash
ollama pull qwen2.5:7b
ollama serve   # if it is not already running
```

Override with `OLLAMA_CHAT_MODEL`.

## 2. Hugging Face token (speaker diarization)

1. Create a read token at <https://huggingface.co/settings/tokens>.
2. Accept model terms (same account) for:
   - [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1)
   - [`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [`pyannote/segmentation-3.0`](https://huggingface.co/pyannote/segmentation-3.0)
3. Set `HF_TOKEN=...` in root `.env` (Docker) and/or `backend/.env` (local uvicorn).

Without a token (or if diarization fails), ASR still works; segments are `unknown` until you label them in Transcript studio.

### STT backends

| Where | Backend | Notes |
| --- | --- | --- |
| **Docker** | `faster-whisper` (CPU) | Works; Apple GPU is **not** available in the Linux container |
| **Mac host** | `STT_BACKEND=mlx` + `mlx-community/whisper-large-v3-turbo` | Metal — much faster on M-series |

Both paths: FFmpeg → 16 kHz mono, `WHISPER_LANGUAGE=en`, VAD / beam where supported.

No local ASR is 100% on a long interview — edit wording in Transcript studio before Analyze.

**Mac host STT example**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt -r requirements-stt.txt -r requirements-mlx.txt
# backend/.env: STT_BACKEND=mlx, WHISPER_MODEL=mlx-community/whisper-large-v3-turbo, HF_TOKEN=...
uvicorn app.main:app --reload --port 8004
```

## 3. Run locally (recommended for full STT)

```bash
# Backend (:8004)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-stt.txt   # omit STT file for paste-only
cp .env.example .env                                      # set HF_TOKEN
uvicorn app.main:app --reload --port 8004
```

```bash
# Frontend (:3004)
cd frontend
cp .env.example .env     # VITE_API_BASE=http://localhost:8004
npm install
npm run dev -- --port 3004
```

Open <http://localhost:3004>. Check `GET http://localhost:8004/health`.

## 4. Run with Docker

Ollama stays on the host (`http://host.docker.internal:11434` from the container).

```bash
docker compose up --build
```

- UI: <http://localhost:3004>
- API: <http://localhost:8004>
- Data: `./backend/data` → `/app/data`

Default image is **core only** (paste + analyze). Bake STT once:

```bash
# root .env: HF_TOKEN=... and INSTALL_STT=1
docker compose build backend
docker compose up
```

Avoid `--no-cache` unless you need a full pip reinstall. `VITE_API_BASE` is baked at frontend build time.

## 5. Sample data

In `backend/data/`:

- `sample_jd.md` / `sample_transcript.md` — **Sample** source (no audio / STT required)
- `sample_interview.wav` — short placeholder tone (no real speech)

Real speech: `ffmpeg -i input.mp4 -ac 1 -ar 16000 backend/data/sample_interview.wav`.

## 6. Tests

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest -v
cd frontend && npx vitest run
```

## Limitations

- **Local only** — no cloud STT/LLM, auth, multi-user, PDF export, or Zoom/Meet sync
- **Diarization is heuristic** — first distinct speaker → interviewer, second → candidate; always review labels
- **Heavy STT stack** — Whisper / torch / pyannote need several GB; Docker omits them unless `INSTALL_STT=1`
- **7B model quality varies** — schema + quote checks help, but treat reports as assistive only (not legal/HR advice)
- **Long transcripts are truncated** for the LLM prompt so analyze stays practical on local hardware

## Docs

- Design spec: [`docs/superpowers/specs/2026-10-13-interview-lens-design.md`](docs/superpowers/specs/2026-10-13-interview-lens-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-10-13-interview-lens.md`](docs/superpowers/plans/2026-10-13-interview-lens.md)
