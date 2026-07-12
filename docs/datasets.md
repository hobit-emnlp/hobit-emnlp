# Datasets

Four evaluation tracks were constructed for hoBIT, each targeting a distinct capability
of the proFILL profile-aware RAG pipeline.

<table>
  <thead>
    <tr>
      <th width="30%">Track</th>
      <th width="18%">Size</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Profile-based Indexing</b></td>
      <td>951 chunks</td>
      <td>Static offline indexing over profile-conditioned document facets (<code>hobit_static</code> 689 + <code>hobit_dynamic</code> 262)</td>
    </tr>
    <tr>
      <td><b>Intent Routing</b></td>
      <td>1,600 queries</td>
      <td>5-class routing (greeting / ability / faq / smalltalk / retrieval)</td>
    </tr>
    <tr>
      <td><b>Profile-grounded QA</b></td>
      <td>1,800 QA pairs</td>
      <td>Verifiable QA under known student profiles</td>
    </tr>
    <tr>
      <td><b>Open-ended Advising</b></td>
      <td>1,200 queries</td>
      <td>Open-ended retrieval quality without ground-truth documents</td>
    </tr>
  </tbody>
</table>

All datasets were generated with `gpt-4o-mini` (temperature=0.7) using anchors extracted
from real hoBIT RASA deployment logs (2024–2025) as seed material.

### Availability

This repository ships the demo runtime only. Full evaluation resources are kept
outside the demo package during the review period for privacy and license reasons,
but are available on request.

- **Runtime document corpus** is bundled at `backend/data/demo_documents.json` as
  license-safe curated mock data derived from public university notices. Reviewers
  can rebuild the Qdrant profile-tagged index from this file end-to-end without any
  private credentials.
- **Full evaluation benchmarks** (Intent Routing 1,600 · Profile-grounded QA 1,800 ·
  Open-ended Advising 1,200) and their **design specifications**
  (`gt_spec.json`, `rag_no_gt_spec_v3.json`), along with the **reproduction scripts**
  used to produce every reported number, are available on request. Please open a
  GitHub issue at
  [`hobit-emnlp/hobit-emnlp/issues`](https://github.com/hobit-emnlp/hobit-emnlp/issues)
  and we will share access.
- **Real deployment logs** used to seed anchor generation are withheld to protect
  student privacy; only their aggregated statistics (distribution, coverage) are
  reported.

---

## 1. Profile-based Indexing (n=951 chunks)

<p align="center">
  <img src="assets/datasets/profile_based_indexing.png" alt="Profile-based indexing overview" width="700">
</p>

Static Qdrant index built offline. Each document chunk is tagged with structured profile
facets (department, admission year, major type, grade, student status) so that on-demand
retrieval can restrict the candidate space using hard filters before dense/sparse scoring.
Unset facets remain `null` so that generic administrative documents remain retrievable
by any student, while curriculum tables narrow to the correct cohort.

Two collections make up the profile-tagged corpus:

- `hobit_static` — 689 chunks (regulations, curriculum tables, static advising documents)
- `hobit_dynamic` — 262 chunks (notices, career postings, time-sensitive documents)

---

## 2. Intent Routing (n=1,600)

<p align="center">
  <img src="assets/datasets/intent_routing.png" alt="Intent routing composition" width="700">
</p>

Five-class dataset for the routing layer that decides whether a query enters the RAG
pipeline (`retrieval`) or is served by a lightweight response path
(`greeting` · `ability` · `faq` · `smalltalk`).

| Source | Count | Method |
|---|---:|---|
| Manual seed | 22 | Representative utterances per non-academic intent |
| LLM augmentation | 378 | GPT-4o-mini expansion to 100 per non-academic intent |
| Open-ended reuse | 1,200 | Open-ended advising track relabeled as `retrieval` |

Final accuracy: **96.0%** (academic F1 0.99, FAQ F1 0.985).

---

## 3. Profile-grounded QA (n=1,800)

<p align="center">
  <img src="assets/datasets/profile_grounded_qa.png" alt="Profile-grounded QA design" width="700">
</p>

Constructed as `60 unique profiles × 10 categories × 3 types = 1,800` cases, where each
case's ground-truth answer is anchored to a specific curriculum-table chunk that matches
the profile (admission year, department, major type).

Three query types per profile-category cell:
- **formal** — standard advising question in a formal register.
- **personal** — question framed around the student's own situation.
- **verification** — yes/no or containment checks against the ground-truth requirement.

---

## 4. Open-ended Advising (n=1,200)

<p align="center">
  <img src="assets/datasets/open_ended_advising.png" alt="Open-ended advising construction" width="700">
</p>

Twelve top-level categories × ten sub-categories × ten queries. The taxonomy was
designed to cover Qdrant document domains that the profile-grounded track does not
address (facilities · scholarships · course registration · career · etc.), so the two
tracks are complementary and non-overlapping.

Anchor validation against 797 real user log utterances:

<table>
  <thead>
    <tr>
      <th width="30%">Axis</th>
      <th width="18%">Value</th>
      <th>Interpretation</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Category coverage</td>
      <td><b>14 / 15 (93.3%)</b></td>
      <td>Practical full coverage</td>
    </tr>
    <tr>
      <td>Pearson r (top-8 ratios)</td>
      <td><b>0.65</b></td>
      <td>Strong distributional alignment with real logs</td>
    </tr>
    <tr>
      <td>Semantic coverage @ θ=0.5</td>
      <td><b>82.4%</b></td>
      <td>Dense embedding-space overlap under <code>text-embedding-3-small</code> — the same model used by the deployed Qdrant retrieval index</td>
    </tr>
  </tbody>
</table>

The `text-embedding-3-small` overlap is retrieval-relevant, not merely surface-lexical,
because the deployed hoBIT retrieval index uses the same embedding model.
