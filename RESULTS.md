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