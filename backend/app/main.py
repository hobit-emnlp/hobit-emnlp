from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import redis
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
COLLECTION = os.getenv("QDRANT_COLLECTION", "hobit_demo_documents")
VECTOR_SIZE = 64
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
USE_LLM_GENERATION = os.getenv("USE_LLM_GENERATION", "auto").lower()


def load_json(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


DOCS: list[dict[str, Any]] = load_json("demo_documents.json")
QUESTIONS: list[dict[str, Any]] = load_json("questions.json")


def connect_qdrant() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    last_error: Exception | None = None
    for _ in range(30):
        try:
            client = QdrantClient(url=url)
            client.get_collections()
            return client
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Qdrant is not available at {url}: {last_error}")


def connect_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(url, decode_responses=True)
    last_error: Exception | None = None
    for _ in range(30):
        try:
            client.ping()
            return client
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Redis is not available at {url}: {last_error}")


qdrant = connect_qdrant()
redis_client = connect_redis()


app = FastAPI(
    title="hoBIT EMNLP Demo API",
    version="1.1.0",
    description=(
        "Reproducible demo backend for the hoBIT EMNLP demo submission. "
        "It keeps the paper-style architecture: FastAPI + Redis session memory + "
        "Qdrant retrieval over bundled mock/local advising data."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    language: str = "KO"


class ProfileRequest(BaseModel):
    department: str | None = None
    major_type: str | None = None
    grade: int | None = None
    admission_year: int | None = None
    student_status: str | None = None
    language: str | None = "KO"


class FeedbackRequest(BaseModel):
    feedback_detail: str | None = None
    language: str | None = "KO"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def embed_text(text: str) -> list[float]:
    """Deterministic local embedding for an offline, no-API-key demo."""
    vector = [0.0] * VECTOR_SIZE
    tokens = re.findall(r"[\w가-힣]+", normalize(text))
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = sum(v * v for v in vector) ** 0.5 or 1.0
    return [v / norm for v in vector]


def doc_text(doc: dict[str, Any]) -> str:
    fields = [
        doc.get("title", ""),
        doc.get("category", ""),
        doc.get("maincategory_ko", ""),
        doc.get("subcategory_ko", ""),
        doc.get("sample_question_ko", ""),
        " ".join(doc.get("keywords", [])),
        doc.get("answer_ko", ""),
    ]
    return "\n".join(fields)


def ensure_qdrant_data() -> None:
    collections = {c.name for c in qdrant.get_collections().collections}
    if COLLECTION not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=int(doc["id"]),
            vector=embed_text(doc_text(doc)),
            payload=doc,
        )
        for doc in DOCS
    ]
    qdrant.upsert(collection_name=COLLECTION, points=points)


ensure_qdrant_data()


def base_flags(**override: Any) -> dict[str, Any]:
    flags = {
        "is_greet": False,
        "is_able": False,
        "is_freq": False,
        "is_smalltalk": False,
        "needs_profile": False,
        "missing_fields": [],
    }
    flags.update(override)
    return flags


def session_id(header_value: str | None) -> str:
    return header_value or "anonymous-demo-session"


def profile_key(sid: str) -> str:
    return f"profile:{sid}"


def history_key(sid: str) -> str:
    return f"history:{sid}"


def get_profile(sid: str) -> dict[str, Any]:
    raw = redis_client.hgetall(profile_key(sid))
    profile: dict[str, Any] = {}
    for key, value in raw.items():
        if key in {"grade", "admission_year"}:
            try:
                profile[key] = int(value)
            except ValueError:
                profile[key] = value
        else:
            profile[key] = value
    return profile


def save_profile_to_redis(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    current = get_profile(sid)
    for key, value in data.items():
        if value is not None:
            current[key] = value
    if current:
        redis_client.hset(profile_key(sid), mapping={k: str(v) for k, v in current.items()})
        redis_client.expire(profile_key(sid), 60 * 60 * 24)
    return current


def add_history(sid: str, user: str, assistant: str) -> None:
    raw = redis_client.get(history_key(sid))
    history = json.loads(raw) if raw else []
    history.append({"role": "user", "content": user})
    history.append({"role": "assistant", "content": assistant})
    history = history[-6:]
    redis_client.set(history_key(sid), json.dumps(history, ensure_ascii=False), ex=60 * 60 * 24)


def generate_with_llm(question: str, doc: dict[str, Any], profile: dict[str, Any]) -> str | None:
    if not OPENAI_API_KEY or USE_LLM_GENERATION in {"0", "false", "off", "disabled"}:
        return None

    profile_text = ", ".join(f"{key}: {value}" for key, value in profile.items() if value not in (None, "", 0))
    prompt = (
        "You are hoBIT, a Korean academic-advising chatbot. "
        "Answer in Korean using only the provided source evidence. "
        "Keep numbers, course names, and source-grounded requirements precise. "
        "Preserve concrete bullet items from the evidence when they answer the user's question. "
        "If the evidence is insufficient, say that the student should confirm with the department office.\n\n"
        f"Student profile: {profile_text or 'not provided'}\n"
        f"Question: {question}\n"
        f"Source title: {doc.get('source_title', doc.get('title', ''))}\n"
        f"Evidence:\n{doc.get('answer_ko', '')}"
    )
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You produce concise, source-grounded Korean advising answers."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    req = urllib.request.Request(
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"LLM generation failed; falling back to bundled answer: {exc}")
        return None


def answer_cards(doc: dict[str, Any], profile: dict[str, Any], question: str = "") -> list[dict[str, Any]]:
    generated_text = generate_with_llm(question, doc, profile)
    text = generated_text or doc["answer_ko"]
    generation_mode = "openai-compatible" if generated_text else "offline-bundled-answer"
    profile_bits = []
    if profile.get("department"):
        profile_bits.append(f"학과: {profile['department']}")
    if profile.get("admission_year"):
        profile_bits.append(f"학번: {profile['admission_year']}학번")
    if profile.get("major_type"):
        profile_bits.append(f"전공 유형: {profile['major_type']}")
    if profile.get("grade"):
        profile_bits.append(f"학년: {profile['grade']}학년")
    if profile_bits:
        text = f"입력한 프로필({', '.join(profile_bits)}) 기준입니다.\n\n{text}"

    return [
        {
            "answer": text,
            "url": doc.get("url", ""),
            "email": doc.get("email", ""),
            "phone": doc.get("phone", ""),
            "generation": generation_mode,
            "sources": [
                {
                    "source_label": doc.get("source_label", "Demo data"),
                    "source_title": doc.get("source_title", doc["title"]),
                    "source_category": doc.get("category", ""),
                    "source_link": doc.get("url", ""),
                    "attachments": [],
                }
            ],
        }
    ]


def faq_from_doc(doc: dict[str, Any], question: str, profile: dict[str, Any]) -> dict[str, Any]:
    cards = answer_cards(doc, profile, question)
    return {
        "id": int(doc["id"]),
        "maincategory_ko": doc.get("maincategory_ko", doc.get("category", "RAG")),
        "maincategory_en": doc.get("maincategory_en", "RAG"),
        "subcategory_ko": doc.get("subcategory_ko", doc["title"]),
        "subcategory_en": doc.get("subcategory_en", doc["title"]),
        "question_ko": question,
        "question_en": question,
        "answer_ko": json.dumps(cards, ensure_ascii=False),
        "answer_en": json.dumps(cards, ensure_ascii=False),
        "manager": doc.get("manager", "hoBIT demo"),
        "category_order": str(doc.get("category_order", 0)),
        "subcategory_order": str(doc.get("subcategory_order", 0)),
        "created_by": None,
        "updated_by": None,
    }


def keyword_score(query: str, doc: dict[str, Any], profile: dict[str, Any]) -> int:
    q = normalize(query)
    score = 0
    for keyword in doc.get("keywords", []):
        if normalize(keyword) in q:
            score += 4
    if any(token in q for token in ["전공 필수", "필수 과목", "전공필수", "major courses", "required major"]):
        if doc.get("subcategory_ko") == "졸업요건":
            score += 8
    if doc.get("department") and profile.get("department") and str(doc["department"]) == str(profile["department"]):
        score += 3
    if doc.get("admission_year") and profile.get("admission_year") and str(doc["admission_year"]) == str(profile["admission_year"]):
        score += 3
    if doc.get("admission_years") and profile.get("admission_year"):
        if int(profile["admission_year"]) in [int(year) for year in doc["admission_years"]]:
            score += 3
    return score


def matches_profile(doc: dict[str, Any], profile: dict[str, Any]) -> bool:
    department = profile.get("department")
    if doc.get("department") and department and str(doc["department"]) != str(department):
        return False

    admission_year = profile.get("admission_year")
    if doc.get("admission_year") and admission_year and int(doc["admission_year"]) != int(admission_year):
        return False
    if doc.get("admission_years") and admission_year:
        years = [int(year) for year in doc["admission_years"]]
        if int(admission_year) not in years:
            return False

    return True


def retrieve(question: str, profile: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    query_vec = embed_text(question)
    hits = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vec,
        limit=max(limit, 10),
        with_payload=True,
    ).points

    ranked: list[tuple[float, dict[str, Any]]] = []
    for hit in hits:
        doc = dict(hit.payload or {})
        if not matches_profile(doc, profile):
            continue
        score = float(hit.score or 0.0) + keyword_score(question, doc, profile)
        ranked.append((score, doc))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in ranked[:limit]]


def required_profile(question: str) -> list[str]:
    q = normalize(question)
    if any(token in q for token in ["졸업", "graduation", "requirement", "요건", "전공 필수", "필수 과목", "major courses", "required major"]):
        return ["admission_year", "department"]
    if any(token in q for token in ["이중전공", "복수전공", "전공", "dual major", "double major"]):
        return ["department"]
    return []


def answer_smalltalk(text: str) -> str:
    q = normalize(text)
    if any(token in q for token in ["고마워", "thanks", "thank you"]):
        return "천만에요. 정보대학 생활이나 학사 제도에 대해 더 궁금한 점이 있으면 언제든 물어보세요."
    if any(token in q for token in ["날씨", "점심", "심심", "기분", "힘들", "피곤", "쉬고", "공부하기"]):
        return "저는 정보대학 안내에 집중하는 데모 챗봇이라 학교생활, 공지사항, 취업, 진로, 학사 질문을 도와드릴 수 있어요."
    return "좋아요. 정보대학 학부 생활과 학사 제도에 관해 궁금한 점을 편하게 물어보세요."


def single_card_response(question: str, answer: str, category: str = "대화") -> dict[str, Any]:
    doc = {
        "id": -1,
        "title": category,
        "category": category,
        "maincategory_ko": category,
        "maincategory_en": "Chat",
        "subcategory_ko": "데모 응답",
        "subcategory_en": "Demo response",
        "answer_ko": answer,
        "url": "",
        "email": "",
        "phone": "",
        "source_label": "hoBIT demo",
        "source_title": "Built-in demo response",
    }
    return {"faqs": [faq_from_doc(doc, question, {})], **base_flags(is_smalltalk=True), "id": -1}


def profile_response(question: str, profile: dict[str, Any]) -> dict[str, Any]:
    if profile:
        lines = ["현재 세션에 저장된 프로필은 다음과 같습니다."]
        if profile.get("department"):
            lines.append(f"- 학과: {profile['department']}")
        if profile.get("admission_year"):
            lines.append(f"- 학번: {profile['admission_year']}학번")
        if profile.get("major_type"):
            lines.append(f"- 전공 유형: {profile['major_type']}")
        if profile.get("grade"):
            lines.append(f"- 학년: {profile['grade']}학년")
        if profile.get("student_status"):
            lines.append(f"- 학적 상태: {profile['student_status']}")
        answer = "\n".join(lines)
    else:
        answer = "현재 세션에 저장된 프로필이 없습니다. 학번/학과가 필요한 질문을 하면 hoBIT이 먼저 필요한 정보를 물어봅니다."

    doc = {
        "id": 16,
        "title": "프로필 조회 안내",
        "category": "프로필",
        "maincategory_ko": "프로필",
        "maincategory_en": "Profile",
        "subcategory_ko": "사용자 프로필",
        "subcategory_en": "User profile",
        "answer_ko": answer,
        "url": "",
        "email": "",
        "phone": "",
        "source_label": "Redis session profile",
        "source_title": "사용자 프로필 상태",
    }
    return {"faqs": [faq_from_doc(doc, question, {})], **base_flags(), "id": -1}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "qdrant-redis-demo",
        "documents": len(DOCS),
        "qdrant_collection": COLLECTION,
        "redis": "connected",
        "generation": "openai-compatible" if OPENAI_API_KEY else "offline-bundled-answer",
        "openai_model": OPENAI_MODEL if OPENAI_API_KEY else None,
    }


@app.get("/api/v0/all_questions")
def all_questions() -> dict[str, Any]:
    return {"questions": QUESTIONS}


@app.get("/api/v0/top_faqs")
def top_faqs() -> dict[str, Any]:
    return {"faqs": [faq_from_doc(doc, doc["sample_question_ko"], {}) for doc in DOCS[:4]]}


@app.get("/api/v0/all_faqs")
def all_faqs() -> dict[str, Any]:
    return {"faqs": [faq_from_doc(doc, doc["sample_question_ko"], {}) for doc in DOCS]}


@app.get("/api/v0/faq")
def faq(id: int = Query(...)) -> dict[str, Any]:
    matches = [doc for doc in DOCS if int(doc["id"]) == id]
    if not matches:
        raise HTTPException(status_code=404, detail="FAQ not found")
    doc = matches[0]
    return {"faqs": [faq_from_doc(doc, doc["sample_question_ko"], {})]}


@app.get("/api/v0/all_senior_faqs")
def all_senior_faqs() -> dict[str, Any]:
    return {"seniorFaqs": []}


@app.post("/api/v0/profile")
def save_profile(req: ProfileRequest, x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    sid = session_id(x_session_id)
    profile = save_profile_to_redis(sid, req.model_dump())
    return {"ok": True, "profile": profile}


@app.get("/api/v0/profile")
def read_profile(x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    sid = session_id(x_session_id)
    return {"profile": get_profile(sid)}


@app.delete("/api/v0/profile")
def reset_profile(x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    sid = session_id(x_session_id)
    redis_client.delete(profile_key(sid))
    return {"ok": True, "profile": {}}


@app.post("/api/v0/question")
def question(req: QuestionRequest, x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    text = req.question.strip()
    if not text:
        raise HTTPException(status_code=400, detail="question is required")

    sid = session_id(x_session_id)
    q_norm = normalize(text)
    if any(token in q_norm for token in ["안녕", "안녕하세요", "hello", "hi", "뭐 하는 챗봇"]):
        return {"faqs": None, **base_flags(is_greet=True), "id": -1}
    if any(token in q_norm for token in ["할 수", "기능", "어떤 질문", "무슨 질문", "what can"]):
        return {"faqs": None, **base_flags(is_able=True), "id": -1}
    if "자주" in text or "faq" in q_norm:
        return {"faqs": None, **base_flags(is_freq=True), "id": -1}
    if any(token in q_norm for token in ["고마워", "날씨", "심심", "힘들", "피곤", "공부하기", "thanks", "thank you"]):
        answer = answer_smalltalk(text)
        add_history(sid, text, answer)
        return single_card_response(text, answer)

    profile = get_profile(sid)
    if any(token in q_norm for token in ["내 프로필", "프로필 알려", "tell me my profile", "my profile"]):
        return profile_response(text, profile)
    missing = [field for field in required_profile(text) if profile.get(field) in (None, "", 0)]
    if missing:
        return {"faqs": None, **base_flags(needs_profile=True, missing_fields=missing), "id": -1}

    docs = retrieve(text, profile, limit=1)
    answer = docs[0]["answer_ko"] if docs else ""
    add_history(sid, text, answer)
    return {"faqs": [faq_from_doc(doc, text, profile) for doc in docs], **base_flags(), "id": -1}


@app.post("/api/v0/chat")
def chat(req: QuestionRequest, x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    sid = session_id(x_session_id)
    profile = get_profile(sid)
    docs = retrieve(req.question, profile)
    answer = answer_cards(docs[0], profile)[0]["answer"] if docs else ""
    add_history(sid, req.question, answer)
    return {
        "response": answer,
        "sources": [
            {
                "source_id": f"S{i + 1}",
                "text": doc["answer_ko"],
                "score": 1.0 / (i + 1),
                "source": doc.get("source_label", "demo"),
                "source_label": doc.get("source_label", "Demo data"),
                "main_category": doc.get("maincategory_ko", ""),
                "sub_category": doc.get("subcategory_ko", ""),
                "original_title": doc.get("source_title", doc["title"]),
                "link": doc.get("url", ""),
                "attachments": [],
            }
            for i, doc in enumerate(docs)
        ],
        "top_k": len(docs),
        "missing_profile": [],
    }


@app.post("/api/v0/rate")
def rate() -> dict[str, Any]:
    return {"success": True}


@app.post("/api/v0/direct_user_feedback")
def direct_user_feedback(req: FeedbackRequest) -> dict[str, Any]:
    return {"success": True, "received": bool(req.feedback_detail)}


@app.post("/api/v0/moderate")
def moderate() -> dict[str, Any]:
    return {"allowed": True, "reason": {"code": "demo"}}
