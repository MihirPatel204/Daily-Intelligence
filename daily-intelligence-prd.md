# Daily Intelligence — Product Requirements Document

**Version:** 1.1
**Status:** Draft
**Stack:** Next.js (frontend) · FastAPI (backend) · LangChain/LangGraph (orchestration) · PostgreSQL + pgvector · Claude API

---

## 1. Overview

Daily Intelligence is a web app that presents news in a traditional newspaper layout — stories sized by importance, pulled and synthesized from many outlets — and lets users chat with an AI about any individual story or about the news in general. It's both a portfolio project demonstrating RAG, LLM-based content processing, and full-stack engineering, and a genuinely useful way to consume news without doom-scrolling a feed.

The product has two primary surfaces:

1. **Newspaper tab** — a front-page-style grid of stories. Box size reflects a story's computed importance. Clicking a box opens a chat scoped to that specific story.
2. **News chat tab** — an open-ended chat interface that can answer questions about any recent news, drawing on the full indexed corpus.

---

## 2. Goals and non-goals

**Goals**
- Aggregate news from multiple independent outlets via RSS and synthesize per-event stories rather than just listing raw articles.
- Visually communicate story importance the way a print front page does, without manual editorial curation.
- Provide grounded, citation-aware chat about news — both story-specific and general — using RAG rather than relying on the LLM's parametric knowledge.
- Build this as a learning vehicle: raw SQL over heavy ORMs, an explicit ingestion pipeline rather than a managed "news AI" SDK, and a from-scratch RAG implementation.

**Non-goals (v1)**
- No personalized/recommendation feed — every user sees the same front page.
- No user accounts or saved history required for v1 (can be added later).
- No support for paywalled or scraped full-text content — RSS summaries and metadata only.
- No mobile app — responsive web only.
- No multi-region scaling or high-availability requirements; this is a single-instance, portfolio-scale deployment.

---

## 3. Target users

Primary: the builder, as a portfolio/demo piece for recruiters and as a personal news-reading tool.
Secondary persona for design purposes: someone who wants a quick, skimmable sense of "what's actually big today" across outlets, and the option to ask follow-up questions instead of opening five different articles.

---

## 4. Product scope

### 4.1 Newspaper tab

- Grid layout of story "boxes," front-page style. Box size has 3–4 tiers (e.g. lead, major, standard, brief) driven by an importance score (see §10).
- Each box shows: synthesized headline, 1–3 sentence summary, list of contributing outlets, category tag, published/updated time.
- Clicking a box opens a chat panel scoped to that story's full cluster of source articles.
- Optional v1.1: category filter (World, Business, Tech, Sports, etc.) and a simple search bar.

### 4.2 News chat tab

- Open chat box, no story pre-selected.
- Retrieval runs against the full recent corpus (rolling window, e.g. last 7–30 days).
- Responses cite which outlet(s) the answer is grounded in.
- Suggested starter prompts (e.g. "What happened in markets today?") to reduce blank-box friction.

---

## 5. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | System polls a curated list of RSS feeds on a fixed schedule and stores new articles. |
| FR-2 | System deduplicates articles by canonical URL on ingest. |
| FR-3 | System clusters articles across outlets that describe the same underlying event. |
| FR-4 | System computes an importance score per cluster and maps it to a box-size tier. |
| FR-5 | System generates a synthesized summary per cluster via LLM, citing which outlets contributed which facts. |
| FR-6 | Frontend renders the newspaper grid from cluster data, sized by tier. |
| FR-7 | Clicking a box opens a chat scoped to that cluster's articles only (no cross-story leakage). |
| FR-8 | News chat tab retrieves from the full recent-corpus vector index, not a single cluster. |
| FR-9 | Chat responses indicate source outlet(s) for grounded claims. |
| FR-10 | Ingestion, clustering, and scoring run as background jobs, decoupled from the request-serving API. |

---

## 6. System architecture

**Frontend** — Next.js, deployed on Vercel. Renders the newspaper grid and both chat UIs; calls the FastAPI backend for data and chat.

**Backend API** — FastAPI on Render (Web Service). Serves cluster/story data to the frontend, handles chat requests (retrieval + Claude call), and exposes an internal endpoint that the ingestion worker hits.

**Ingestion & processing worker** — implemented as a LangGraph state graph (see §8) and triggered on a schedule via a Render Cron Job, rather than running inside the user-facing API process. Render's cron jobs run as scheduled one-off tasks, replacing the Cloud Scheduler + Cloud Run Job pattern with a single native Render service type.

**Orchestration** — LangChain supplies the building blocks (RSS/document loaders, prompt templates, the retrieval chain shared by both chat surfaces) while LangGraph models the ingestion pipeline as a stateful graph with explicit nodes and edges. This is where loops fit naturally: steps like cluster-match confirmation and summary quality-checking become conditional edges that cycle back to an earlier node instead of always moving forward — see §8 for exactly where each loop sits.

**Database** — PostgreSQL with the `pgvector` extension (Neon, serverless — Render also offers managed Postgres if you'd rather keep DB and compute on one platform). One database serves both relational data (articles, clusters, scores) and vector search — no separate vector DB service.

**LLM** — Claude API, called via LangChain's Anthropic integration, used for: (a) cluster-summary generation, (b) tie-breaking ambiguous clustering decisions, (c) chat responses over retrieved context.

**Embeddings** — recommend starting with a local open-source model (e.g. `sentence-transformers/all-MiniLM-L6-v2`) run inside the FastAPI worker — free, fast enough for this corpus size, and a good learning component for the Python backend. Swap to a hosted embeddings API later only if quality becomes a bottleneck.

**Images** — store the source article's thumbnail/og-image URL directly (most RSS feeds include one); no need for object storage like R2 in v1 since images aren't being re-hosted or transformed.

---

## 7. Data model (high level)

```
sources
  id, name, rss_url, category, active

articles
  id, source_id, url (unique), title, summary, published_at,
  image_url, raw_text, embedding (vector), cluster_id, created_at

clusters
  id, headline, synthesized_summary, category, score,
  size_tier, outlet_count, first_seen_at, last_updated_at

cluster_articles
  cluster_id, article_id   -- join table if many-to-many is ever needed

chat_messages   (optional, if conversation history is persisted)
  id, session_id, cluster_id (nullable), role, content, created_at
```

`articles.embedding` and a cluster-level summary embedding both live in pgvector columns so retrieval can hit either granularity depending on the query.

---

## 8. Ingestion and processing pipeline

Modeled as a LangGraph `StateGraph`, with shared pipeline state (the article being processed, its embedding, the candidate cluster, and a retry count) passed between nodes:

1. **Fetch** — poll each active source's RSS feed on a schedule (e.g. every 15–30 minutes). LangChain's RSS/web loaders work well here; isolate per-source failures so one dead feed doesn't block the rest.
2. **Parse & dedupe** — extract title, summary, link, image, published time; insert with `ON CONFLICT (url) DO NOTHING`.
3. **Embed** — generate an embedding for the new article's title + summary.
4. **Cluster match** — compare against recent open clusters by cosine similarity. Clear matches and clear non-matches proceed directly. Borderline cases route to a **verify node**: ask Claude whether the two articles describe the same event; the edge back from verify loops to cluster match with the LLM's judgment folded into state, so it isn't re-asked on retry. This is the first loop — bounded by a retry count in state to avoid cycling forever.
5. **Score** — compute the importance score (see §10) whenever cluster membership changes.
6. **Summarize** — generate the cluster's synthesized summary via Claude. A **critique node** checks the summary against the source snippets for unsupported claims; if it fails, the edge loops back to summarize with the critique appended to state as feedback. Second loop, also bounded by a retry count.
7. **Store** — persist updated cluster, score, tier, and summary; this is what the frontend reads.

---

## 9. RAG and chat design

Two retrieval scopes share the same retrieval mechanics but differ in filter scope:

- **Story chat**: vector search constrained to `WHERE cluster_id = :id`. Grounds the conversation entirely in that story's coverage across outlets.
- **News chat**: vector search across all articles/clusters within a rolling time window (e.g. last 7–30 days), ranked by similarity to the user's query.

In both cases: retrieve top-k chunks → build a context block listing source outlet per chunk → pass to Claude with an instruction to cite outlets for factual claims and to say so explicitly if the retrieved context doesn't cover the question. Both scopes can share a single LangChain retrieval chain, parameterized by an optional `cluster_id` filter — the only difference between story chat and news chat is whether that filter is set.

---

## 10. Importance scoring (v1 approach)

A simple weighted score per cluster, recomputed on update:

```
score = w1 * outlet_count
      + w2 * recency_decay(first_seen_at)
      + w3 * category_weight
      (+ optional LLM-assigned newsworthiness adjustment)
```

- `outlet_count`: number of distinct sources covering the story — the core "this is big" signal.
- `recency_decay`: exponential decay so older stories fade out of lead position even if outlet count was high.
- `category_weight`: optional tunable per category (e.g. breaking world news weighted slightly above lifestyle).

Map score into 3–4 percentile-based tiers (lead / major / standard / brief) that the frontend uses to size boxes. Start with fixed weights; revisit once you have real data to see if the ranking "feels right."

---

## 11. Non-functional requirements

- **Cost**: stay within free/low-cost tiers — Neon free tier, Render free/starter web service, local embeddings model, Claude API calls budgeted per day (cap summarization/chat calls to avoid runaway cost on a demo project). Render's free tier spins down on inactivity, so the first request after idle time will be slow — fine for a portfolio demo, worth upgrading to a paid starter instance if it needs to feel responsive for reviewers.
- **Latency**: newspaper grid should load from cached cluster data, not live LLM calls — summaries are precomputed by the worker, not generated on page view. Chat responses target a few seconds end-to-end.
- **Security**: no sensitive user data in v1; if accounts are added later, DIY JWT auth consistent with prior project preferences, not a third-party auth SDK.
- **Reliability**: ingestion worker failures (a feed timing out) should not block other feeds — isolate per-source fetch failures.

---

## 12. Tech stack summary

| Layer | Choice |
|-------|--------|
| Frontend | Next.js, deployed on Vercel |
| Backend API | FastAPI (Python), deployed on Render (Web Service) |
| Orchestration | LangChain (chains, loaders, prompts) + LangGraph (ingestion pipeline, loop steps) |
| Ingestion worker | LangGraph pipeline, triggered by a Render Cron Job |
| Database | PostgreSQL (Neon) with pgvector |
| Embeddings | sentence-transformers (local, free) initially |
| LLM | Claude API — summarization, cluster tie-breaks, chat |
| News source | Curated RSS feed list across major outlets |
| Image handling | Direct use of source-provided image URLs |

---

## 13. Phased roadmap

**Phase 1 — Foundation**: source list, ingestion worker, raw article storage, basic Next.js page listing raw articles (no clustering yet).

**Phase 2 — Clustering & scoring**: embeddings, the LangGraph clustering/scoring/summarization pipeline (including the verify and critique loops), synthesized summaries. Newspaper grid now reflects real story groupings and sizes.

**Phase 3 — Story chat**: pgvector retrieval scoped to a cluster, chat panel wired to a clicked box.

**Phase 4 — General news chat tab**: corpus-wide retrieval, second tab UI.

**Phase 5 — Polish**: category filters, search, error handling, deploy, write-up for portfolio.

---

## 14. Open questions and risks

- **Clustering quality at low article volume**: with a small curated source list, some real-world stories may only get 1–2 outlets, making the "size by outlet count" signal noisy early on — may need a manual category-weight fallback.
- **Source ToS**: confirm each RSS feed's terms permit the kind of summarization/display planned here, especially if this goes beyond a private portfolio demo.
- **Clustering edge cases**: fast-moving stories (e.g. live events) may fragment into multiple clusters before merging — needs a periodic "recluster" pass, not just append-only matching.
- **Cost creep**: LLM calls for cluster summarization and tie-breaking scale with article volume; worth instrumenting call counts early.

---

## 15. Success criteria (portfolio scope)

- Live, deployed demo with a real, auto-updating newspaper front page.
- Clustering and scoring produce a front page that qualitatively "looks right" (big stories are visually big).
- Both chat modes return grounded, cited answers rather than hallucinated claims.
- Codebase demonstrates the explicit pipeline (no opaque managed "news AI" service) as a clear talking point for interviews/portfolio review.
