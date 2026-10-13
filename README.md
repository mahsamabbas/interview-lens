# InterviewLens

InterviewLens is a local interview studio. It turns an interview recording, or a pasted transcript, plus a job description into **two evidence-backed reports**:

- **Candidate report:** constructive feedback, strengths and improvements.
- **Hiring report:** fit, scores and a PASS / borderline / NO decision.

The flow has three steps: **Setup** (job description and source) → **Transcript** (review and edit speakers and text) → **Reports**.

Everything runs on your machine. Speech-to-text uses faster-whisper with pyannote diarization. The LLM is a local Ollama model (`qwen2.5:7b` by default). The browser never calls Ollama.

| Piece | Port |
| --- | --- |
| Frontend (React + Vite + Tailwind) | 3004 |
| API (FastAPI + SQLite) | 8004 |
| Ollama (on the host) | 11434 |

## Prerequisites

- Python 3.12 and Node 22
- [Ollama](https://ollama.com) running on the host
- For audio/video transcription only: a free [Hugging Face](https://huggingface.co) account for the pyannote token

## 1. Ollama

```bash
ollama pull qwen2.5:7b
ollama serve   # if it is not already running
```

To use a different model, set `OLLAMA_CHAT_MODEL`.

## 2. Hugging Face token (speaker diarization)

pyannote needs a Hugging Face token and accepted model terms:

1. Create a read token at <https://huggingface.co/settings/tokens>.
2. Accept the terms (same HF account as the token) for:
   - [`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [`pyannote/segmentation-3.0`](https://huggingface.co/pyannote/segmentation-3.0)
   - [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1) (newer `pyannote.audio` pulls this too)
3. Put the token in root `.env` for Docker (`HF_TOKEN=...`) and/or `backend/.env` for local uvicorn.

Without a token (or if diarization fails), transcription still works. Every segment is labelled `unknown` — click the speaker chip to set **Interviewer** / **Candidate**, then Analyze.

**Speed tip:** Docker STT runs on CPU. A ~20 minute `.mov` can take a long time. For demos use a **2–5 minute** clip, or set `WHISPER_MODEL=tiny` in root `.env` (faster, slightly less accurate than `base`).

## 3. Run locally (recommended, full STT)

The local virtualenv is the primary way to run InterviewLens with speech-to-text, because the Whisper, torch and pyannote stack is heavy.

```bash
# Backend (API on :8004)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-stt.txt   # drop the STT file for paste-only
cp .env.example .env                                      # then set HF_TOKEN
uvicorn app.main:app --reload --port 8004
```

```bash
# Frontend (UI on :3004), in a second terminal
cd frontend
cp .env.example .env     # VITE_API_BASE=http://localhost:8004
npm install
npm run dev -- --port 3004
```

Open <http://localhost:3004>. `GET http://localhost:8004/health` reports `ollama` and `whisper_ready`.

**Requirements split**

| File | Contents |
| --- | --- |
| `backend/requirements.txt` | API core: FastAPI, uvicorn, httpx, pytest. Enough for paste, sample and analyze. |
| `backend/requirements-stt.txt` | faster-whisper, torch, pyannote.audio. Needed for upload transcription. |

## 4. Run with Docker

Ollama stays on the host. The backend container reaches it at `http://host.docker.internal:11434`.

```bash
docker compose up --build
```

- UI: <http://localhost:3004>
- API: <http://localhost:8004>
- SQLite and uploads persist in `./backend/data` (mounted at `/app/data`).

By default the backend image is **core only** (paste and analyze). It starts without the STT stack, and `whisper_ready` reports `false`. To bake in the STT stack (several GB) **once**:

```bash
# Put HF_TOKEN=... and INSTALL_STT=1 in root `.env`, then:
docker compose build backend   # heavy the first time only
docker compose up              # day-to-day: no rebuild
```

**Do not** use `--no-cache` unless you intentionally want a full reinstall. After the first STT image exists:

| Change | Command |
| --- | --- |
| Just run again | `docker compose up` (no `--build`) |
| Only `backend/app` code | `docker compose up --build` — pip layer is **cached**, rebuild is fast |
| `requirements*.txt` changed | `docker compose build backend` — pip runs again (cache mount still helps) |

Fastest loop for STT work: run the **backend in a local venv** (`pip install -r requirements-stt.txt` once on the Mac) and only use Docker for the frontend, or paste-path demos without STT.

Copy `.env.example` to `.env` to change ports, models or CORS origins. `VITE_API_BASE` is baked into the frontend bundle at build time, so rebuild the frontend if you change it.

## 5. Sample data

`backend/data/` ships with:

- `sample_jd.md` and `sample_transcript.md`. The **Sample** source loads these. It works without any audio and without STT.
- `sample_interview.wav`. A tiny 3-second placeholder tone that wires up the sample media path. It contains no speech. If the file is missing, the sample flow still works from the transcript alone.

To regenerate the placeholder with the standard library:

```bash
python3 - <<'EOF'
import wave, struct, math
sr = 16000
with wave.open("backend/data/sample_interview.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b"".join(
        struct.pack("<h", int((0.2 if (i / sr) % 1.0 < 0.4 else 0.0) * 32767 * math.sin(2 * math.pi * 440 * i / sr)))
        for i in range(sr * 3)))
EOF
```

To use real speech, record or convert a clip with `ffmpeg -i input.mp4 -ac 1 -ar 16000 backend/data/sample_interview.wav`.

## 6. Tests

```bash
# Backend (STT and Ollama are mocked, core requirements are enough)
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest -v

# Frontend
cd frontend && npx vitest run
```

## Limitations

- **Local only.** There are no cloud STT or LLM calls, no auth, no multi-user support, no PDF export, and no Zoom or Meet integration.
- **Diarization is heuristic.** The first speaker is mapped to interviewer and the second to candidate. Review and correct labels before analyzing.
- **Heavy STT stack.** Whisper, torch and pyannote need several GB and are slow on CPU. The Docker image omits them by default.
- **Model quality varies.** The reports come from a 7B local model. Output is validated against a schema and quotes are checked against the transcript, but treat results as decision support, not a hiring verdict. This is not legal or HR compliance advice.
- **Sample wav has no speech.** Use the sample transcript for the demo.

## Docs

- Design spec: [`docs/superpowers/specs/2026-10-13-interview-lens-design.md`](docs/superpowers/specs/2026-10-13-interview-lens-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-10-13-interview-lens.md`](docs/superpowers/plans/2026-10-13-interview-lens.md)
