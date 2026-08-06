# Knowledge Studio A/B Upgrade Design

## Goal

Upgrade the local Knowledge Studio in two strictly ordered deliveries:

1. Phase A makes chunking, preprocessing, parent-child retrieval, indexing, and retrieval configuration complete and internally consistent.
2. Phase B adds free-only economical indexing, model selection, local OCR, and optional Gemini enhancement for public data.

The project remains a dual-mode Portfolio RAG product. Private data never leaves the local machine. Public data may use cloud enhancement, but all workflows must continue to work with free local models.

## Non-negotiable Boundaries

- Private documents may only use local parsing, OCR, embedding, reranking, and generation.
- Public documents use the same local pipeline by default. `PUBLIC_CLOUD_ENHANCEMENT=auto` is the default: Gemini enhancement runs without per-document approval only when a configured free model is healthy and within quota, otherwise processing immediately falls back to local.
- `FREE_ONLY=true` forbids paid-provider fallback. Quota exhaustion must produce a visible status and a local fallback where technically possible.
- Preview, saved configuration, and ingestion must call the same chunking implementation.
- Changing an embedding model creates a distinct index identity and requires re-embedding. Embeddings with different dimensions are never mixed.
- Existing public JSON, private SQLite catalog, MongoDB data, and source files are migrated without destructive deletion.

## Phase A: Product-complete Knowledge Processing

### 1. Unified Processing Configuration

Each catalog document stores a versioned processing profile:

```text
profile_version
chunk_mode                 general / parent_child / resume_semantic
delimiter
max_tokens
overlap_tokens
parent_mode                paragraph / full_document / semantic_section
parent_max_tokens
child_max_tokens
normalize_whitespace
remove_urls
remove_emails
index_mode                 high_quality
embedding_provider
embedding_model
retrieval_mode             vector / full_text / hybrid
fusion_mode                rrf / weighted
vector_weight
keyword_weight
reranker_enabled
reranker_model
top_k
score_threshold
```

Old `strategy/chunk_size/overlap/unit` records are migrated to this profile. Resume records still using `recursive / 600 / 60` are explicitly migrated to `resume_semantic`; the Knowledge Studio preview and ingestion then show the same result.

### 2. Chunk Modes

#### General

- Split first on the configured delimiter, defaulting to blank lines.
- Merge adjacent units only while they remain within `max_tokens` and the same structural section.
- Apply overlap only inside a structural section.
- Markdown headings and DOCX paragraph/style boundaries are retained as metadata.

#### Resume Semantic

- Automatically selected for DOCX/PDF/Markdown documents recognized as resumes.
- Top-level semantic parents are profile, education, summary, internship, project, award, and skill sections.
- A project title, technology stack, and outcomes remain together.
- Different projects, schools, and employers never share a semantic parent.
- Oversized parents are split internally while repeating the entity title.

#### Parent-child

- Recommended for long PDF, Markdown, documentation, and tutorial content.
- Child chunks, approximately 180 tokens, are embedded and searched.
- Parent chunks, approximately 700 tokens, are returned to the prompt and source panel.
- For resumes, semantic project/education/internship blocks are parents and their focused facts are children.
- CSV rows and short JSON summaries do not use generic parent-child mode.

### 3. Preprocessing

The UI provides independent options to normalize consecutive spaces/newlines/tabs, remove URLs, and remove email addresses. It shows parsed text, editable cleaned text, and the exact post-cleaning text used for chunking.

Editing parsed or cleaned text invalidates downstream chunks immediately. A visible `Apply changes and regenerate preview` action recomputes cleaning, PII detection, chunk statistics, and temporary retrieval. Unsaved edits never silently enter the index.

### 4. Chunk Records

MongoDB chunk records add:

```text
chunk_id, parent_chunk_id, semantic_group_id
raw_body, retrieval_text, parent_body
section_type, section_path, entity_title
token_count, character_count
retrieval_priority
processing_profile_hash
content_hash, visibility
```

Vector and text indexes operate on child `retrieval_text`. Generation and citations use the corresponding parent `parent_body`, deduplicated by parent or semantic group.

### 5. Retrieval Configuration

Knowledge Studio and Retrieval Lab expose the same settings:

- Vector Search with Top-K and optional score threshold.
- Full-text BM25 search.
- Hybrid search using RRF or explicit vector/keyword weights.
- Optional local Cross-Encoder reranking.
- Candidate count, selected context count, source channel, pre-rerank rank, final rank, and latency.

Unavailable indexes or rerankers degrade to the nearest working mode and display the exact reason. They never make the page fail to render.

### 6. Phase A Acceptance

- The Master resume no longer previews as seven mixed chunks.
- Resume chunks never cross top-level semantic sections.
- Temporary retrieval and MongoDB retrieval use identical saved profiles.
- Parent-child search embeds children and returns parents.
- Editing cleaned text changes the preview before save.
- Existing catalog records migrate idempotently.
- Vector, BM25, hybrid, and reranked retrieval remain testable in the Retrieval Lab.

## Phase B: Free-only Extended Capabilities

### 1. Economical Index

Economical mode creates a local inverted index from deterministic keywords. It uses local tokenization and keyword extraction rather than a paid LLM. Each chunk stores up to ten normalized keywords. It is presented as a low-resource option, not as equivalent accuracy to high-quality embeddings.

### 2. Processing Engine Selection

The UI separates data visibility from processing engine:

- Visibility: public or private.
- Engine: local automatic, local explicit model, or public cloud enhanced.

Private plus cloud is rejected by backend validation even if a malformed request bypasses the UI.

Local defaults:

- Text embedding: current multilingual SentenceTransformer.
- Generation: Ollama Qwen, with Gemma as workshop-compatible option.
- Reranking: local Cross-Encoder.
- OCR: PaddleOCR for Chinese and English.

Public cloud enhancement may use Gemini embedding and multimodal parsing. Cloud results are stored only in the public collection/index.

### 3. OCR and Multimodal Processing

- Text PDFs continue to use deterministic text extraction.
- Scanned PDFs and images are detected before OCR.
- PaddleOCR is the default for both private and public files.
- Public files may use Gemini multimodal enhancement for complex layouts when configured.
- OCR output, confidence, page number, engine, and failure reason are visible in Knowledge Studio.
- Original files remain local and Git ignored.

### 4. Free-only Failure Policy

Provider errors are normalized into:

```text
quota_exhausted
rate_limited
invalid_credentials
model_unavailable
network_unavailable
local_runtime_unavailable
```

The UI displays the provider, model, error class, fallback, and suggested action. No paid model is selected automatically. When Gemini generation is unavailable on Vercel, retrieval evidence remains visible and the response explains that free generation is temporarily unavailable.

### 5. Phase B Acceptance

- Economical mode works without API calls or token charges.
- Private documents cannot trigger Gemini under any UI or API path.
- Public documents can use local processing or automatic Gemini enhancement.
- Scanned Chinese/English documents can be processed locally with OCR.
- Gemini quota failures are distinguishable from authentication and network failures.
- The app never silently switches to a paid provider.

## Delivery and Verification

Phase A is implemented, tested, reviewed, and committed before Phase B begins. Each phase includes unit tests, Streamlit AppTest coverage, local integration tests, retrieval benchmark comparison, privacy checks, README updates, and a dedicated commit.

The final browser verification covers Chat, Upload & Chunk, Library, Versions & Duplicates, Index Maintenance, and Retrieval Lab at desktop and mobile widths.
