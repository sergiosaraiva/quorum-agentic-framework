---
chunk_id: QF-023
title: The embedding stub and how to plug in a real model
topics: [search, caveats, infrastructure]
links: [QF-011, QF-032]
sources: ["scripts/kb/lib.py", "scripts/kb/README.md", "kb/schema.sql"]
---
The vector mode of the Quorum knowledge bases ships with a stub embedding, not a semantic model. Treat retrieval quality in PostgreSQL mode as unproven until a real provider is configured.

`EMBED_PROVIDER=hash` is the default. `hash_embedding` in `scripts/kb/lib.py` is documented in its own docstring as a demo stub: it hashes each token into one of `dim` buckets with a sign and normalises the vector. It gives lexical-overlap similarity only, matches shared words, and lets the pgvector pipeline run offline with no model or key. Because pgvector mode ranks by vector distance only, it is not semantic with this stub, and retrieval quality should not be judged with it.

For a real model set `EMBED_PROVIDER=http` with an OpenAI-compatible embeddings endpoint, using environment variables `EMBED_BASE_URL`, `EMBED_MODEL`, optionally `EMBED_API_KEY` taken from a secret store and never committed, and `EMBED_DIM` equal to the model's output size. The request shape should be verified for the chosen provider. Another provider needs a new branch in `lib.embed()` that returns a list of `EMBED_DIM` floats.

The vector column is typed. The default dimension is 384, and ingest replaces it with `EMBED_DIM`. After changing the model or the dimension, re-ingest everything. If the dimension changed, ingest stops with a message naming the mismatching table; drop the tables first (`kb_links`, `kb_chunks` and `qa_records`) because the column type cannot change in place.

Local mode does not use embeddings at all; it ranks by BM25 keyword scoring, so it works with no setup and is unaffected by this caveat.
