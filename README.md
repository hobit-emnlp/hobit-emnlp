# hoBIT EMNLP Demo

This repository contains a self-contained, reproducible demo package for the hoBIT academic-advising chatbot. It is prepared for the EMNLP demo-track requirement that submissions provide either a live demo website or a downloadable/installable demo package.

The package intentionally avoids private infrastructure dependencies. It does **not** require MySQL, Qdrant, Redis, OpenAI API keys, or university-internal credentials. Instead, it ships with a small mock/local advising dataset that exercises the same user flow: server health check, Korean chatbot UI, profile-dependent query handling, retrieval-style answers, and source display.

## Demo Link / Installable Package

- Installable package: this GitHub repository can be downloaded or cloned and run locally with Docker Compose.
- Live demo URL: add the deployed URL here after deployment, if available.

If no live URL is provided, this repository is the downloadable installation package for reproducing the demo.

## What Is Included

```text
.
├── backend/             # Self-contained FastAPI backend with mock/local RAG data
├── frontend/            # React hoBIT chat UI
├── docker-compose.yml   # One-command demo runner
└── README.md
```

The backend implements the API shape expected by the original hoBIT frontend:

- `GET /health`
- `GET /api/v0/all_questions`
- `GET /api/v0/top_faqs`
- `GET /api/v0/all_faqs`
- `GET /api/v0/all_senior_faqs`
- `GET /api/v0/faq?id=...`
- `POST /api/v0/question`
- `POST /api/v0/profile`
- `POST /api/v0/chat`
- `POST /api/v0/rate`
- `POST /api/v0/direct_user_feedback`
- `POST /api/v0/moderate`

## Quick Start

Requirements:

- Docker Desktop or Docker Engine
- Docker Compose v2

Run:

```bash
git clone https://github.com/hobit-emnlp/hobit-emnlp.git
cd hobit-emnlp
docker compose up --build
```

Open:

- Frontend: <http://localhost:3000>
- Backend health check: <http://localhost:8000/health>

## Demo Script

Use the Korean UI.

1. Open <http://localhost:3000>.
2. Ask: `졸업요건 알려줘`
3. The system asks for profile information because the answer depends on the student's department and admission year.
4. Select:
   - `20학번`
   - `컴퓨터학과`
5. Click `확인`.
6. The chatbot returns a profile-conditioned answer with source metadata.

Other sample questions:

- `수강신청 기간에 신청을 못했어요`
- `외국인 학생 상담은 어디서 받아요?`
- `포스터를 게시하고 싶은데 어떻게 해야 하나요?`

## Local Development Without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
cp .env.example .env
npm ci
npm start
```

The frontend defaults to `http://localhost:8000` if `REACT_APP_HOBIT_BACKEND_ENDPOINT` is not set.

## Reproducibility Notes

This demo is designed for anonymous review and reproducibility:

- No database dump is required.
- No private university MySQL data is required.
- No LLM API key is required.
- The included `backend/data/demo_documents.json` is a small mock/local dataset shaped after academic-advising content.
- The original hoBIT frontend interaction pattern is preserved.

The production research system can use crawled university pages, vector retrieval, and LLM generation. This installable package focuses on making the demo behavior reproducible from source code alone.

## API Smoke Test

After starting the backend:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v0/question \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: demo" \
  -d "{\"question\":\"졸업요건 알려줘\",\"language\":\"KO\"}"
```

The first graduation query should request profile fields. Then save a profile:

```bash
curl -X POST http://localhost:8000/api/v0/profile \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: demo" \
  -d "{\"department\":\"컴퓨터학과\",\"admission_year\":20,\"language\":\"KO\"}"
```

Repeat the question to receive an answer.

## License

This demo package is provided for academic review. Add the final project license before public release if a different license is required.
