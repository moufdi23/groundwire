# Groundwire — Retrieval Evaluation Results

## Day 3 Baseline

Day 3 baseline — before hybrid search + reranking (Week 2)

| Metric | k=3 | k=5 | k=10 |
|--------|-----|-----|------|
| Recall@k | 0.8125 | 0.8750 | 0.8875 |
| Precision@k | 0.7625 | 0.6775 | 0.5963 |

Questions with 0 recall (source chunk not found at any k): **9/80**

### Notes
- Recall@k: fraction of 80 golden-set questions where the source chunk appeared in the top-k results.
- Precision@k: fraction of top-k retrieved chunks sharing the same section as the source chunk (section-match used as relevance proxy).
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine similarity via pgvector).

## Day 5 — Hybrid Search (Vector + BM25 with RRF)

| Metric | k=3 | k=5 | k=10 |
|--------|-----|-----|------|
| Recall@k | 0.8500 | 0.9125 | 0.9625 |
| Precision@k | 0.7917 | 0.7200 | 0.6238 |

Questions with 0 recall: **3/80**

### Delta vs Day 3 Baseline
- recall@3:    0.8125 → 0.8500  (+3.7 pts)
- recall@5:    0.8750 → 0.9125  (+3.7 pts)
- recall@10:   0.8875 → 0.9625  (+7.5 pts)
- precision@3: 0.7625 → 0.7917  (+2.9 pts)
- precision@5: 0.6775 → 0.7200  (+4.2 pts)
- precision@10: 0.5963 → 0.6238  (+2.7 pts)

### Notes
- Fusion: Reciprocal Rank Fusion (RRF, k=60), vector pool=50, BM25 pool=50.
- BM25 index: `data/bm25_index.pkl` (BM25Okapi via rank_bm25).
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine similarity via pgvector).


## Day 6 — Hybrid + Reranking (cross-encoder/ms-marco-MiniLM-L-6-v2)

| Metric | k=3 | k=5 | k=10 |
|--------|-----|-----|------|
| Recall@k | 0.9125 | 0.9750 | 0.9875 |
| Precision@k | 0.8042 | 0.7225 | 0.6337 |

Questions with 0 recall: **1/80**

### Delta vs Day 5 (Hybrid Search)
- recall@3:    0.8500 → 0.9125  (+6.2 pts)
- recall@5:    0.9125 → 0.9750  (+6.2 pts)
- recall@10:   0.9625 → 0.9875  (+2.5 pts)
- precision@3: 0.7917 → 0.8042  (+1.2 pts)
- precision@5: 0.7200 → 0.7225  (+0.2 pts)
- precision@10: 0.6238 → 0.6337  (+1.0 pts)

### Notes
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` (local CPU inference, ~2s per query).
- Candidate pool: top-50 from hybrid RRF, then re-scored and re-sorted by cross-encoder.
- Hybrid: vector (pgvector cosine) + BM25 (rank_bm25), fused with RRF k=60.
- Reranking improves precision by surfacing the most semantically relevant chunk first.


## Day 7 — Generation Quality (Ragas)

Sample: 25/80 questions · random seed 42 · k=3 chunks
Generator: Claude Haiku 4.5 (`claude-haiku-4-5`)
Judge: Claude Haiku 4.5 · Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (for Answer Relevancy)

| Metric | Score | Definition |
|--------|-------|------------|
| Faithfulness | 0.9619 | Fraction of answer claims grounded in the retrieved context |
| Answer Relevancy | 0.7518 | Mean cosine sim(original question, reverse-generated questions) |
| Context Precision | 0.9367 | Average precision of context ranking (relevant chunks first) |
| Context Recall | 0.9233 | Fraction of ground-truth sentences attributable to context |

### Metric Methodology
Implemented using the same formulas as the Ragas library (ragas.ai).
Ragas 0.4.3 could not be installed on Python 3.14 / Windows (scikit-network
requires MSVC C++ build tools; langchain-community version conflict).

- **Faithfulness**: Extract claims → check each against context via LLM.
- **Answer Relevancy**: LLM generates 3 reverse-questions → cosine similarity with original.
- **Context Precision**: LLM judges chunk relevance per position → compute Average Precision.
- **Context Recall**: LLM checks which ground-truth sentences appear in context.
