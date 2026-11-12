# Krishi RAG

A question-answering service for Indian farmers, built on official crop and government-scheme documents. It uses retrieval-augmented generation (RAG): it finds the relevant passages first, then writes an answer that cites the source document and page for every claim. It's built with FastAPI, PostgreSQL with pgvector, Redis and the Claude API, and it comes with a published evaluation.

**Status:** planning. See [PLAN.md](PLAN.md) for the full build plan.
