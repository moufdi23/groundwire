"""
Ragas-equivalent generation quality evaluation using Claude Haiku 4.5 as judge.

Samples 25 of 80 golden-set questions, generates answers via generate_answer(),
then scores each with four metrics that match Ragas' methodology exactly:

  Faithfulness     — fraction of answer claims grounded in the retrieved context
  Answer Relevancy — mean cosine similarity between the answer's implied questions
                     and the original question (Ragas ResponseRelevancy)
  Context Precision — average precision of context ranking (relevant chunks first)
  Context Recall    — fraction of ground-truth sentences attributable to the context

Why custom implementations instead of the ragas library:
  ragas 0.4.3 depends on scikit-network, which has no Python 3.14 wheel on Windows
  (requires MSVC C++ build tools). ragas 0.4.3 --no-deps also breaks because it
  hard-imports langchain_community.chat_models.vertexai, removed in langchain-community
  >=0.3. Both issues are irresolvable on this environment without MSVC.
  The implementations below use the same formulas and judge-prompt logic as Ragas.

Sample size: 25 questions (seed=42). Rationale: gives ~31% coverage, statistically
meaningful, keeps total Claude Haiku calls under 130 (~5 calls/sample × 25 samples +
25 generation calls = ~150 total) for an estimated cost of $0.25–$0.45.

Run: python scripts/evaluate_ragas.py
"""

import json
import random
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

import anthropic
from generate_answer import generate_answer

# ── Config ─────────────────────────────────────────────────────────────────────
GOLDEN_SET_PATH = Path("data/golden_set.jsonl")
RESULTS_PATH = Path("RESULTS.md")
SAMPLE_SIZE = 25
RANDOM_SEED = 42
JUDGE_MODEL = "claude-haiku-4-5"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # already loaded by retrieval stack

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _judge(prompt: str) -> str:
    """Single judge LLM call; returns raw text."""
    resp = _get_client().messages.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


def _parse_json(text: str) -> object:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# ── Metric implementations ─────────────────────────────────────────────────────


def faithfulness(question: str, answer: str, contexts: list[str]) -> float:
    """
    Ragas Faithfulness:
      1. Extract all factual claims from the answer.
      2. Check each claim against the context.
      Score = supported_claims / total_claims.
    """
    ctx_str = "\n\n---\n\n".join(f"[Passage {i + 1}]\n{c}" for i, c in enumerate(contexts))

    prompt = f"""You are evaluating an AI answer for faithfulness to its source context.

Context passages:
{ctx_str}

Question: {question}

Answer: {answer}

Task:
1. Extract every distinct factual claim or assertion from the answer (ignore filler phrases).
2. For each claim, determine whether it can be inferred from the context above.

Return ONLY a JSON object with exactly two keys:
  "claims"   : list of claim strings (extracted from the answer)
  "supported": list of booleans (true = supported by context, false = not supported),
               same length and order as "claims"

Example: {{"claims": ["X is true", "Y requires Z"], "supported": [true, false]}}"""

    try:
        data = _parse_json(_judge(prompt))
        claims = data.get("claims", [])
        supported = data.get("supported", [])
        if not claims:
            return 1.0  # no claims → trivially faithful
        supported = [bool(v) for v in supported[: len(claims)]]
        return sum(supported) / len(claims)
    except Exception:
        return float("nan")


def answer_relevancy(question: str, answer: str, embed_model) -> float:
    """
    Ragas ResponseRelevancy:
      Generate N reverse-questions the answer is most likely addressing.
      Score = mean cosine similarity(original_question, generated_question_i).
    A score near 1 means the answer squarely addresses the original question.
    """
    prompt = f"""Given the answer below, generate 3 different questions that this answer is most likely responding to.

Answer: {answer}

Return ONLY a JSON array of 3 question strings.
Example: ["What is X?", "How does Y work?", "Why is Z important?"]"""

    try:
        generated = _parse_json(_judge(prompt))
        if not isinstance(generated, list) or not generated:
            return float("nan")
        generated = [str(q) for q in generated[:3]]
    except Exception:
        return float("nan")

    all_qs = [question] + generated
    embs = embed_model.encode(all_qs, convert_to_numpy=True)

    orig = embs[0]
    sims = [
        float(np.dot(orig, g) / (np.linalg.norm(orig) * np.linalg.norm(g) + 1e-10))
        for g in embs[1:]
    ]
    return float(np.mean(sims))


def context_precision(question: str, contexts: list[str], ground_truth: str) -> float:
    """
    Ragas LLMContextPrecisionWithReference:
      For each context chunk (in retrieval order), judge relevance to the ground truth.
      Score = Average Precision = Σ(precision@k × rel@k) / total_relevant.
    Penalises irrelevant chunks ranked before relevant ones.
    """
    ctx_str = "\n\n".join(f"[Chunk {i + 1}]\n{c}" for i, c in enumerate(contexts))

    prompt = f"""You are evaluating whether retrieved context chunks are useful for answering a question.

Question: {question}

Ground-truth answer: {ground_truth}

Context chunks (in retrieval order):
{ctx_str}

For each chunk, output true if it contains information useful for producing the ground-truth answer, false otherwise.
Return ONLY a JSON array of booleans, one per chunk, in order.
Example (3 chunks): [true, false, true]"""

    try:
        verdicts = _parse_json(_judge(prompt))
        if not isinstance(verdicts, list):
            return float("nan")
        verdicts = [bool(v) for v in verdicts[: len(contexts)]]
    except Exception:
        return float("nan")

    total_relevant = sum(verdicts)
    if total_relevant == 0:
        return 0.0

    ap, running_hits = 0.0, 0
    for k, rel in enumerate(verdicts, 1):
        if rel:
            running_hits += 1
            ap += running_hits / k
    return ap / total_relevant


def context_recall(question: str, contexts: list[str], ground_truth: str) -> float:
    """
    Ragas LLMContextRecall:
      Break the ground-truth into sentences; check which can be attributed to context.
      Score = attributed_sentences / total_sentences.
    """
    ctx_str = "\n\n---\n\n".join(f"[Passage {i + 1}]\n{c}" for i, c in enumerate(contexts))

    prompt = f"""You are evaluating whether retrieved context passages contain the information
needed to reconstruct a ground-truth answer.

Context passages:
{ctx_str}

Ground-truth answer: {ground_truth}

Task:
1. Split the ground-truth answer into individual sentences or distinct claims.
2. For each sentence/claim, determine whether it can be attributed to (inferred from) the context.

Return ONLY a JSON object with exactly two keys:
  "sentences"   : list of sentence strings (from the ground truth)
  "attributable": list of booleans (true = found in context, false = not found),
                  same length and order as "sentences"

Example: {{"sentences": ["X is Y.", "Z requires W."], "attributable": [true, false]}}"""

    try:
        data = _parse_json(_judge(prompt))
        sentences = data.get("sentences", [])
        attributable = data.get("attributable", [])
        if not sentences:
            return float("nan")
        attributable = [bool(v) for v in attributable[: len(sentences)]]
        return sum(attributable) / len(sentences)
    except Exception:
        return float("nan")


# ── Main ───────────────────────────────────────────────────────────────────────


def load_golden_set(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main() -> None:
    if not GOLDEN_SET_PATH.exists():
        sys.exit(f"Golden set not found at {GOLDEN_SET_PATH}")

    all_entries = load_golden_set(GOLDEN_SET_PATH)
    print(f"Loaded {len(all_entries)} golden-set entries.")

    random.seed(RANDOM_SEED)
    sample = random.sample(all_entries, min(SAMPLE_SIZE, len(all_entries)))
    print(f"Sampled {len(sample)} questions (seed={RANDOM_SEED}).\n")

    # Load the embedding model (reuses the model already loaded by the retrieval stack).
    print("Loading embedding model for Answer Relevancy ...")
    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer(EMBED_MODEL)
    print("  Ready.\n")

    # ── Generate answers ─────────────────────────────────────────────────────
    print("Step 1/2 — Generating answers (retrieval + Haiku generation) ...")
    results_data = []
    for i, entry in enumerate(sample, 1):
        q = entry["question"]
        gt = entry["expected_answer_summary"]
        answer, contexts = generate_answer(q, k=3)
        results_data.append({"question": q, "answer": answer, "contexts": contexts, "ground_truth": gt})
        if i % 5 == 0 or i == len(sample):
            print(f"  [{i}/{len(sample)}] generated")

    # ── Score each sample ────────────────────────────────────────────────────
    print(f"\nStep 2/2 — Scoring {len(sample)} samples with 4 metrics (Haiku judge) ...")
    scores: dict[str, list[float]] = {
        "faithfulness": [],
        "answer_relevancy": [],
        "context_precision": [],
        "context_recall": [],
    }

    for i, d in enumerate(results_data, 1):
        q, ans, ctxs, gt = d["question"], d["answer"], d["contexts"], d["ground_truth"]

        scores["faithfulness"].append(faithfulness(q, ans, ctxs))
        scores["answer_relevancy"].append(answer_relevancy(q, ans, embed_model))
        scores["context_precision"].append(context_precision(q, ctxs, gt))
        scores["context_recall"].append(context_recall(q, ctxs, gt))

        if i % 5 == 0 or i == len(sample):
            print(f"  [{i}/{len(sample)}] scored")

    # ── Aggregate ────────────────────────────────────────────────────────────
    def _mean(vals: list[float]) -> float:
        valid = [v for v in vals if v == v]  # exclude NaN
        return float(np.mean(valid)) if valid else float("nan")

    averages = {k: _mean(v) for k, v in scores.items()}

    # ── Terminal output ───────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Day 7 — Generation Quality (Ragas-equivalent, n=25)")
    print("=" * 60)
    print(f"  {'Metric':<25} {'Score':>8}")
    print("  " + "-" * 35)
    for metric, score in averages.items():
        score_str = f"{score:.4f}" if score == score else "N/A"
        print(f"  {metric:<25} {score_str:>8}")
    print()

    # ── Append to RESULTS.md ─────────────────────────────────────────────────
    existing = RESULTS_PATH.read_text(encoding="utf-8") if RESULTS_PATH.exists() else ""

    marker = "## Day 7"
    if marker in existing:
        existing = existing[: existing.index(marker)].rstrip()

    def fmt(v: float) -> str:
        return f"{v:.4f}" if v == v else "N/A"

    new_section = "\n".join([
        "",
        "## Day 7 — Generation Quality (Ragas)",
        "",
        f"Sample: {len(sample)}/{len(all_entries)} questions · random seed {RANDOM_SEED} · k=3 chunks",
        f"Generator: Claude Haiku 4.5 (`{JUDGE_MODEL}`)",
        f"Judge: Claude Haiku 4.5 · Embeddings: `{EMBED_MODEL}` (for Answer Relevancy)",
        "",
        "| Metric | Score | Definition |",
        "|--------|-------|------------|",
        f"| Faithfulness | {fmt(averages['faithfulness'])} | Fraction of answer claims grounded in the retrieved context |",
        f"| Answer Relevancy | {fmt(averages['answer_relevancy'])} | Mean cosine sim(original question, reverse-generated questions) |",
        f"| Context Precision | {fmt(averages['context_precision'])} | Average precision of context ranking (relevant chunks first) |",
        f"| Context Recall | {fmt(averages['context_recall'])} | Fraction of ground-truth sentences attributable to context |",
        "",
        "### Metric Methodology",
        "Implemented using the same formulas as the Ragas library (ragas.ai).",
        "Ragas 0.4.3 could not be installed on Python 3.14 / Windows (scikit-network",
        "requires MSVC C++ build tools; langchain-community version conflict).",
        "",
        "- **Faithfulness**: Extract claims → check each against context via LLM.",
        "- **Answer Relevancy**: LLM generates 3 reverse-questions → cosine similarity with original.",
        "- **Context Precision**: LLM judges chunk relevance per position → compute Average Precision.",
        "- **Context Recall**: LLM checks which ground-truth sentences appear in context.",
        "",
    ])

    RESULTS_PATH.write_text(existing + "\n" + new_section, encoding="utf-8")
    print(f"Results appended to {RESULTS_PATH.resolve()}")


if __name__ == "__main__":
    main()
