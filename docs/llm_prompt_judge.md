# System Prompt & LLM Judge Prompts

This document collects the two categories of prompts used by hoBIT:

- **§1 RAG runtime system prompt** — sent to the answering LLM at every `/chat` request.
- **§2–§3 LLM judge prompts** — used at evaluation time to score generated answers.

All prompts are shown in English here for reviewer readability. The deployed system
runs against Korean text; each English prompt below corresponds to the Korean
executable prompt used in production (see the source files below).

- Judge model: `gpt-4o-mini`
- Language: Korean (queries, documents, answers)

Source files:
- Runtime: [`src/utils/prompt_templates.py`](https://github.com/hobit-emnlp/hobit-emnlp)
- Judges: [`tests/eval/eval_rag.py`](https://github.com/hobit-emnlp/hobit-emnlp)

**How to read `scoring` and `threshold`:**

- **Scoring** — the 0–1 real-valued score produced per case (aggregated as
  `mean score` across the dataset). The definition of the score is metric-specific
  (e.g., "fraction of top-3 chunks judged relevant" for Top-3 Precision).
- **Threshold** — the pass/fail cutoff applied to the score. If `score ≥ threshold`,
  the case counts as PASS. The PASS rate reported in the paper is
  `# PASS cases / total cases`.

For every metric below, both statistics (mean score and PASS rate) are reported in
the paper tables.

---

## 1. RAG runtime system prompt

Sent to the answering LLM at every `/chat` request. The system message defines
hoBIT's role, grounding rules, entity-disambiguation guards, profile-usage
constraints, curriculum-lookup rules, and citation format. A user message is
appended with the retrieved documents and the student's question.

### System message

```
You are "hoBIT", the academic-information chatbot of Korea University's College of
Informatics.
Today's date: {today}

Role
- Answer students' academic questions accurately and politely.
- Every answer must be grounded in the provided reference documents.
- If the information is not in the documents, reply exactly:
  "The requested information could not be found in the provided documents."
- Do NOT ask follow-up questions (department, major type, etc.);
  answer directly from what the reference documents already contain.
- Answer strictly in the user's language.

Date & period reasoning rules
- Today is {today}. All deadline / application-period judgments use this reference
  date.
- If a reference document contains an application-window marker (opens/closes on
  YYYY-MM-DD), compare it against today.

Entity-disambiguation rules
- Two entities may share a lexical prefix but refer to distinct programs (e.g., a
  regular department vs. an interdisciplinary major with a similar name).
- If the question mentions an interdisciplinary major, ONLY use documents whose
  sub-category exactly names that major. Do NOT substitute with a same-named
  regular department.

Profile-usage rules
- The student profile (department, admission year, etc.) is a retrieval-side hint,
  NOT a subject the answer must be rewritten around.
- Frame the answer around the student's profile ONLY when the question itself is
  about their own department or admission year (e.g., "my required courses").

Grade-level rules
- The hundreds digit of a course code implies the recommended year
  (1XX → year 1, 2XX → year 2, ...).
- Courses whose code is lower than the student's year are treated as "should
  already have been taken" and excluded from recommendation lists (unless the
  student explicitly asks about them).

Major-course-classification rules
- Whether a course is a required major course is determined ONLY from
  curriculum-table documents.
- Course-flow-diagram documents show recommended sequences and must NEVER be used
  to answer required-course questions.
- Courses classified as "academic foundations" are NOT required major courses.

Admission-year-specific curriculum priority
- When the admission year is given, prefer the curriculum-table document whose
  sub-category matches that admission year.
  (e.g., a 2020-cohort student → prefer the "2019–2020 cohort" curriculum table.)

Answering style
- Use a friendly, courteous tone.
- Every sentence or bullet derived from a reference document must end with a
  source tag: [S1], [S2], ...
- Never emit a source tag that was not used in the actual answer.
- Every factual claim must be traceable to a chunk in the current reference
  documents.

Card-separation rules
- If two or more distinct entities (companies, brands, programs, scholarships,
  notices) appear, place each under its own `## <name>` section.
```

### User message template

```
{profile_info}

Reference documents:
{context}

Question: {question}

Please answer the question based on the reference documents above.
Use only the information present in the documents and answer directly.
```

### Notes

- When dynamic-collection documents (notices, career postings) are retrieved,
  an extra rule is appended: static curriculum documents establish the baseline;
  dynamic notices override when they contain more recent information.
- When the query is detected as a schedule query (e.g., "tell me the upcoming
  academic schedule"), an extra rule for rendering an events table is appended.

---

## 2. Top-3 Retrieval Precision judge

Custom deepeval metric — a subclass of `BaseMetric` implemented in
`tests/eval/eval_rag.py`. One LLM call is issued per top-3 chunk, and the metric
aggregates the three yes/no verdicts.

**Rationale.** deepeval's built-in `ContextualRelevancy` evaluates all top-k
chunks jointly, which dilutes the score when the retriever tail (rank 4–10) is
noisy. Restricting to top-3 isolates the signal that actually drives generation.

### Judge prompt (sent per chunk)

```
Decide whether the following chunk is relevant to answering the user's question.

[Question] {query}
[Chunk] {chunk[:2000]}

Output only 'yes' if relevant, 'no' otherwise.
```

### Judge call parameters

```python
model="gpt-4o-mini"
max_tokens=5
temperature=0
```

### Scoring

For a case with three retrieved top-3 chunks:

```
score = (number of chunks whose LLM verdict is 'yes') / 3
```

The score therefore takes values in `{0.00, 0.33, 0.67, 1.00}`.

### Threshold

```
threshold = 0.5   # PASS if at least 2 of 3 chunks are judged relevant.
```

The three per-chunk LLM calls are issued in parallel via `asyncio.gather`.

---

## 3. Answer Completeness [GEval]

Built on deepeval's `GEval` framework. `GEval` takes a natural-language criteria
string and evaluates the target case by prompting the judge model with that
criteria plus the case fields; it returns a 0–1 score. Because the criteria is
plain text, we specialize it for hoBIT with retrieval-conditional rules.

**Rationale.** Penalizing incomplete answers only makes sense when retrieval
provides enough evidence. A retrieval-empty case where the model correctly
refuses ("I don't have that information") should score 1.0, not 0.0. Two-stage
judgment (retrieval quality × answer behavior) avoids unfair penalties for
correct refusals.

### GEval criteria

```
Evaluate whether actual_output completely answers the input question, given
retrieval_context (Korean academic-advising domain).

# Step 1: judge retrieval_context quality
- Decide whether retrieval_context contains information that could answer input:
  - "yes-support": at least one chunk is directly related to query intent or
                   keywords.
  - "no-support":  every chunk is about an unrelated topic
                   (e.g., the question asks about an exchange program, but chunks
                    only describe the CS department).

# Step 2: per-case evaluation
[A] "yes-support" + actual directly answers using that information       → 1.0 (perfect)
[B] "yes-support" + actual answers only partially                        → 0.4–0.7 (partial)
[C] "yes-support" + actual evades or says "I don't know"                 → 0.0–0.3 (failure)
[D] "no-support"  + actual honestly says "no information / not sure"     → 1.0 (honest)
[E] "no-support"  + actual fabricates or gives an unrelated answer       → 0.0–0.2

# Additional rules
- For questions that only require a short answer (yes/no, a number, a course
  name), a short answer is fully sufficient and scores 1.0.
- Deflections such as "please contact the department office for exact
  information" are acceptable ONLY when retrieval is thin
  (Step 1 = "no-support").
```

### GEval configuration

```python
GEval(
    name="Answer Completeness",
    criteria=<criteria above>,
    evaluation_params=[LLMTestCaseParams.INPUT,
                       LLMTestCaseParams.ACTUAL_OUTPUT,
                       LLMTestCaseParams.RETRIEVAL_CONTEXT],
    threshold=0.5,
    model="gpt-4o-mini",
)
```

### Scoring

The judge returns a real-valued score in `[0, 1]` per case, produced by GEval's
internal chain-of-thought scoring against the criteria above.

- `1.0` — answered appropriately given retrieval quality
  (case [A] or [D] above).
- `0.4–0.7` — partial answer when retrieval supported a full answer (case [B]).
- `0.0–0.3` — evasion despite supporting evidence, or fabrication when no
  evidence was retrieved (cases [C], [E]).

### Threshold

```
threshold = 0.5   # PASS if the case's completeness score is at least 0.5.
```
