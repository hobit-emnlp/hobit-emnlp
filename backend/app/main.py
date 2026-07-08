from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_json(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


DOCS: list[dict[str, Any]] = load_json("demo_documents.json")
QUESTIONS: list[dict[str, Any]] = load_json("questions.json")
SESSIONS: dict[str, dict[str, Any]] = {}


app = FastAPI(
    title="hoBIT EMNLP Demo API",
    version="1.0.0",
    description="Self-contained demo backend for the hoBIT EMNLP demo submission.",
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


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def score_doc(query: str, doc: dict[str, Any], profile: dict[str, Any]) -> int:
    q = normalize(query)
    score = 0
    for keyword in doc.get("keywords", []):
        if keyword.lower() in q:
            score += 4
    for field in ("department", "admission_year"):
        expected = doc.get(field)
        if expected and profile.get(field) and str(expected) == str(profile[field]):
            score += 3
    if doc.get("category", "").lower() in q:
        score += 2
    return score


def answer_cards(doc: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    text = doc["answer_ko"]
    if profile:
        profile_bits = []
        if profile.get("department"):
            profile_bits.append(f"학과: {profile['department']}")
        if profile.get("admission_year"):
            profile_bits.append(f"학번: {profile['admission_year']}학번")
        if profile_bits:
            text = f"입력한 프로필({', '.join(profile_bits)}) 기준입니다.\n\n{text}"

    return [
        {
            "answer": text,
            "url": doc.get("url", ""),
            "email": doc.get("email", ""),
            "phone": doc.get("phone", ""),
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
    cards = answer_cards(doc, profile)
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


def retrieve(question: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(
        ((score_doc(question, doc, profile), doc) for doc in DOCS),
        key=lambda item: item[0],
        reverse=True,
    )
    hits = [doc for score, doc in ranked if score > 0]
    return hits[:3] if hits else [DOCS[0]]


def required_profile(question: str) -> list[str]:
    q = normalize(question)
    if any(token in q for token in ["졸업", "graduation", "requirement", "요건"]):
        return ["admission_year", "department"]
    if any(token in q for token in ["전공", "major", "이중전공", "복수전공"]):
        return ["department"]
    return []


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "self-contained-emnlp-demo",
        "documents": len(DOCS),
    }


@app.get("/api/v0/all_questions")
def all_questions() -> dict[str, Any]:
    return {"questions": QUESTIONS}


@app.get("/api/v0/top_faqs")
def top_faqs() -> dict[str, Any]:
    return {
        "faqs": [faq_from_doc(doc, doc["sample_question_ko"], {}) for doc in DOCS[:3]]
    }


@app.get("/api/v0/all_faqs")
def all_faqs() -> dict[str, Any]:
    return {
        "faqs": [faq_from_doc(doc, doc["sample_question_ko"], {}) for doc in DOCS]
    }


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
def save_profile(
    req: ProfileRequest,
    x_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    sid = session_id(x_session_id)
    current = SESSIONS.setdefault(sid, {})
    for key, value in req.model_dump().items():
        if value is not None:
            current[key] = value
    return {"ok": True, "profile": current}


@app.post("/api/v0/question")
def question(
    req: QuestionRequest,
    x_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    text = req.question.strip()
    if not text:
        raise HTTPException(status_code=400, detail="question is required")

    q_norm = normalize(text)
    if q_norm in {"안녕", "안녕하세요", "hello", "hi"}:
        return {"faqs": None, **base_flags(is_greet=True), "id": -1}
    if "할 수" in text or "what can" in q_norm:
        return {"faqs": None, **base_flags(is_able=True), "id": -1}
    if "자주" in text or "faq" in q_norm:
        return {"faqs": None, **base_flags(is_freq=True), "id": -1}

    profile = SESSIONS.get(session_id(x_session_id), {})
    missing = [
        field for field in required_profile(text)
        if profile.get(field) in (None, "", 0)
    ]
    if missing:
        return {
            "faqs": None,
            **base_flags(needs_profile=True, missing_fields=missing),
            "id": -1,
        }

    docs = retrieve(text, profile)
    return {
        "faqs": [faq_from_doc(doc, text, profile) for doc in docs],
        **base_flags(),
        "id": -1,
    }


@app.post("/api/v0/chat")
def chat(req: QuestionRequest, x_session_id: str | None = Header(default=None)) -> dict[str, Any]:
    profile = SESSIONS.get(session_id(x_session_id), {})
    docs = retrieve(req.question, profile)
    return {
        "response": answer_cards(docs[0], profile)[0]["answer"],
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
