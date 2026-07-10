from __future__ import annotations

import argparse
import json
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CASES: list[dict[str, Any]] = [
    {"slug": "01_Greeting", "query": "안녕! 너는 뭐 하는 챗봇이야?"},
    {"slug": "02_Ability", "query": "너는 어떤 질문에 답할 수 있어?"},
    {"slug": "03_FAQ", "query": "정보대 행정실 위치 알려줘."},
    {"slug": "04_Smalltalk", "query": "오늘 공부하기 너무 힘들다."},
    {"slug": "05_Academic", "query": "등록금 납부 기간 알려줘."},
    {"slug": "06_School_Life", "query": "정보대 동아리 추천해줘."},
    {
        "slug": "07_User_based_RAG",
        "query": "내 전공 필수 과목 알려줘.",
        "profile": {"department": "컴퓨터학과", "admission_year": 20, "major_type": "Intensive", "student_status": "current"},
        "probe_without_profile": True,
    },
    {
        "slug": "08_User_Profile",
        "query": "내 프로필 알려줘.",
        "profile": {"department": "컴퓨터학과", "admission_year": 20, "major_type": "Intensive", "student_status": "current"},
    },
    {
        "slug": "09_Profile_based_RAG",
        "query": "졸업요건 알려줘.",
        "profile": {"department": "컴퓨터학과", "admission_year": 21, "major_type": "Intensive", "student_status": "current"},
        "probe_without_profile": True,
    },
    {"slug": "10_Time_based_RAG", "query": "요즘 채용 중인 회사 알려줘."},
    {"slug": "11_Source_based_RAG", "query": "최근 공지사항 출처 포함해서 알려줘."},
    {"slug": "12_MySQL_based_Lexical_Search", "query": "추천 검색어와 메뉴 검색 결과를 비교해줘."},
]


def post(base_url: str, path: str, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v0{path}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8", "X-Session-ID": session_id},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_health(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_answer(response: dict[str, Any]) -> dict[str, Any]:
    faqs = response.get("faqs") or []
    if not faqs:
        if response.get("is_greet"):
            answer = (
                "안녕하세요. 저는 고려대학교 정보대학 챗봇 hoBIT입니다.\n\n"
                "정보대학 학부 관련 궁금한 점이 있다면 언제든지 질문할 수 있고, "
                "FAQ, 학교생활, 취업/진로, 학사 제도, 프로필 기반 RAG 질문을 도와드립니다."
            )
        elif response.get("is_able"):
            answer = (
                "hoBIT은 다음 유형의 질문을 처리할 수 있습니다.\n\n"
                "- Greeting and onboarding\n"
                "- Ability/category menu\n"
                "- FAQ and MySQL lexical search\n"
                "- Smalltalk fallback\n"
                "- Academic advising\n"
                "- School-life retrieval\n"
                "- User/profile-based RAG\n"
                "- Time/source-based RAG"
            )
        elif response.get("is_freq"):
            answer = "자주 묻는 질문 목록을 보여주는 intent response입니다. 실제 프론트엔드는 FAQ 목록 카드를 렌더링합니다."
        elif response.get("needs_profile"):
            missing = ", ".join(response.get("missing_fields") or [])
            answer = f"이 질문은 프로필 정보가 필요합니다. 필요한 필드: {missing}"
        else:
            answer = json.dumps(response, ensure_ascii=False)
        return {
            "id": None,
            "category": "intent",
            "source": "",
            "generation": "frontend-intent",
            "answer": answer,
        }
    faq = faqs[0]
    card = json.loads(faq["answer_ko"])[0]
    return {
        "id": faq["id"],
        "category": f"{faq['maincategory_ko']} > {faq['subcategory_ko']}",
        "source": (card.get("sources") or [{}])[0].get("source_title", ""),
        "generation": card.get("generation", ""),
        "answer": card["answer"],
    }


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_width(text: str, fnt: ImageFont.ImageFont) -> float:
    if hasattr(fnt, "getlength"):
        return float(fnt.getlength(text))
    left, _, right, _ = fnt.getbbox(text)
    return float(right - left)


def break_long_token(token: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in token:
        if current and text_width(current + char, fnt) > max_width:
            pieces.append(current)
            current = char
        else:
            current += char
    if current:
        pieces.append(current)
    return pieces


def wrapped_lines(text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for token in paragraph.split(" "):
            candidate = token if not current else f"{current} {token}"
            if text_width(candidate, fnt) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            if text_width(token, fnt) <= max_width:
                current = token
            else:
                token_pieces = break_long_token(token, fnt, max_width)
                lines.extend(token_pieces[:-1])
                current = token_pieces[-1] if token_pieces else ""

        if current:
            lines.append(current)
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.ImageFont, fill: str, width: int, line_gap: int = 8) -> int:
    x, y = xy
    for line in wrapped_lines(text, fnt, width):
        if line:
            draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def save_card_image(path: Path, title: str, query: str, answer: dict[str, Any]) -> None:
    title_font = font(34)
    small_font = font(22)
    body_font = font(26)
    body_line_height = body_font.size + 8
    body_lines = wrapped_lines(answer["answer"], body_font, 760)
    body_height = max(440, len(body_lines) * body_line_height + 245)
    card_bottom = 370 + body_height
    footer_top = card_bottom + 40
    img_height = footer_top + 100

    img = Image.new("RGB", (900, img_height), "#f7f7f8")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((40, 40, 860, 180), radius=24, fill="#750E21")
    draw.text((70, 72), title, font=title_font, fill="white")
    draw.text((70, 125), "actual generated demo output", font=small_font, fill="#f3dfe4")

    draw.rounded_rectangle((40, 220, 860, 330), radius=20, fill="white")
    draw.text((70, 245), "User query", font=small_font, fill="#666666")
    draw.text((70, 282), query, font=body_font, fill="#111111")

    draw.rounded_rectangle((40, 370, 860, card_bottom), radius=20, fill="white")
    y = 400
    draw.text((70, y), f"Category: {answer['category']}", font=small_font, fill="#666666")
    y += 38
    draw.text((70, y), f"Source: {answer['source'] or '-'}", font=small_font, fill="#666666")
    y += 38
    draw.text((70, y), f"Generation: {answer['generation']}", font=small_font, fill="#666666")
    y += 55
    draw.line((70, y, 830, y), fill="#dddddd", width=2)
    y += 35
    draw_wrapped(draw, (70, y), answer["answer"], body_font, "#111111", 760)

    draw.rounded_rectangle((40, footer_top, 860, footer_top + 60), radius=16, fill="#eeeeef")
    draw.text((70, footer_top + 18), "Saved for EMNLP demo project page assets", font=small_font, fill="#555555")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8013")
    parser.add_argument("--out-dir", default=r"C:\Users\SEONGMIN\Documents\Workspace\Projects\2026-emnlp-demo\resources\demo\actual")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    health = get_health(args.base_url)
    summary = {"health": health, "cases": []}

    for case in CASES:
        slug = case["slug"]
        case_dir = out_dir / slug
        case_dir.mkdir(parents=True, exist_ok=True)
        session_id = f"actual-{slug}-{uuid.uuid4().hex[:8]}"

        probe = None
        if case.get("probe_without_profile"):
            probe = post(args.base_url, "/question", session_id, {"question": case["query"], "language": "KO"})

        if case.get("profile"):
            post(args.base_url, "/profile", session_id, case["profile"] | {"language": "ko"})

        response = post(args.base_url, "/question", session_id, {"question": case["query"], "language": "KO"})
        answer = extract_answer(response)

        payload = {"case": case, "session_id": session_id, "probe_without_profile": probe, "response": response, "answer": answer}
        (case_dir / "response.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "answer.md").write_text(
            f"# {slug}\n\n"
            f"**Query:** {case['query']}\n\n"
            f"**Category:** {answer['category']}\n\n"
            f"**Source:** {answer['source'] or '-'}\n\n"
            f"**Generation:** {answer['generation']}\n\n"
            f"## Answer\n\n{answer['answer']}\n",
            encoding="utf-8",
        )
        save_card_image(case_dir / "answer_card.png", slug, case["query"], answer)
        summary["cases"].append({"slug": slug, "query": case["query"], **answer})

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# Actual Demo Outputs\n\n"
        f"Generated from `{args.base_url}`.\n\n"
        f"Backend health:\n\n```json\n{json.dumps(health, ensure_ascii=False, indent=2)}\n```\n\n"
        "Each folder contains `response.json`, `answer.md`, and `answer_card.png`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
