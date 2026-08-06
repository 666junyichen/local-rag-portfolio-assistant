# Knowledge Studio Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver consistent Dify-style preprocessing, general/resume/parent-child chunking, catalog migration, and high-quality vector/full-text/hybrid/reranked retrieval for the local Knowledge Studio.

**Architecture:** Add a versioned processing profile that is persisted in SQLite and consumed by one canonical chunking pipeline. The pipeline returns parent and child records; children are indexed, while parents are deduplicated and returned to generation. Existing `ChunkConfig` and scripts remain compatibility entry points while the Streamlit pages adopt the new profile.

**Tech Stack:** Python 3.11, Streamlit, SQLite, MongoDB Atlas Local Vector Search and Search, SentenceTransformers, Cross-Encoder, pytest.

---

## File Map

- Create `src/processing_profiles.py`: profile types, validation, legacy migration, recommendations, and profile hashing.
- Create `src/hierarchical_chunking.py`: parent-child construction and canonical chunk result types.
- Modify `src/document_processing.py`: configurable cleaning, structural splitting, and compatibility entry points.
- Modify `src/local_catalog.py`: SQLite schema migration and profile persistence.
- Create `scripts/migrate_processing_profiles.py`: explicit idempotent migration command.
- Modify `src/ingestion.py`: index child records and preserve parent evidence.
- Modify `src/retrieval.py`: parent expansion, semantic-group deduplication, and diagnostics.
- Modify `src/portfolio_rag.py`: expose hierarchy-aware retrieval through compatibility APIs.
- Modify `pages/1_Knowledge_Studio.py`: processing controls, editable cleaning flow, preview, and migration actions.
- Modify `pages/2_Retrieval_Lab.py`: shared retrieval settings and parent/child diagnostics.
- Modify `tests/test_document_processing.py`, `tests/test_local_catalog.py`, `tests/test_ingestion.py`, `tests/test_retrieval.py`, and `tests/test_streamlit_contract.py`.
- Modify `README.md` and `.env.example`: explain Phase A behavior and defaults.

### Task 1: Versioned Processing Profiles

**Files:**
- Create: `src/processing_profiles.py`
- Test: `tests/test_processing_profiles.py`

- [ ] **Step 1: Write failing validation and migration tests**

```python
from src.processing_profiles import ProcessingProfile, profile_from_legacy


def test_parent_child_profile_has_valid_child_and_parent_budgets():
    profile = ProcessingProfile.parent_child()
    assert profile.chunk_mode == "parent_child"
    assert profile.child_max_tokens == 180
    assert profile.parent_max_tokens == 700
    assert profile.overlap_tokens == 20


def test_legacy_resume_profile_migrates_to_semantic():
    profile = profile_from_legacy(
        title="陈君奕简历 - Master",
        file_type="docx",
        strategy="recursive",
        chunk_size=600,
        overlap=60,
        unit="tokens",
    )
    assert profile.chunk_mode == "resume_semantic"
    assert profile.max_tokens == 320
    assert profile.overlap_tokens == 0
```

- [ ] **Step 2: Run the focused tests and confirm import failure**

Run: `python -m pytest tests/test_processing_profiles.py -q`

Expected: FAIL because `src.processing_profiles` does not exist.

- [ ] **Step 3: Implement immutable profile types and deterministic hashes**

```python
@dataclass(frozen=True)
class PreprocessingProfile:
    normalize_whitespace: bool = True
    remove_urls: bool = False
    remove_emails: bool = False


@dataclass(frozen=True)
class ProcessingProfile:
    profile_version: int = 1
    chunk_mode: str = "general"
    delimiter: str = "\n\n"
    max_tokens: int = 800
    overlap_tokens: int = 80
    parent_mode: str = "paragraph"
    parent_max_tokens: int = 700
    child_max_tokens: int = 180
    preprocessing: PreprocessingProfile = field(default_factory=PreprocessingProfile)
    index_mode: str = "high_quality"

    @classmethod
    def parent_child(cls) -> "ProcessingProfile":
        return cls(
            chunk_mode="parent_child",
            max_tokens=180,
            overlap_tokens=20,
            parent_mode="paragraph",
            parent_max_tokens=700,
            child_max_tokens=180,
        )

    def digest(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Validate modes, token ranges, overlap at no more than 25%, and child size below parent size. Implement `profile_from_legacy()` and per-file recommendations from the approved design.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_processing_profiles.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/processing_profiles.py tests/test_processing_profiles.py
git commit -m "Add versioned knowledge processing profiles"
```

### Task 2: Configurable Cleaning and Structural Units

**Files:**
- Modify: `src/document_processing.py`
- Modify: `tests/test_document_processing.py`

- [ ] **Step 1: Write failing preprocessing tests**

```python
def test_clean_text_respects_url_and_email_options():
    profile = PreprocessingProfile(
        normalize_whitespace=True,
        remove_urls=True,
        remove_emails=True,
    )
    cleaned = clean_text(
        "Contact  a@example.com\n\nhttps://example.com\tProject",
        profile,
    )
    assert "a@example.com" not in cleaned
    assert "https://example.com" not in cleaned
    assert cleaned.endswith("Project")


def test_clean_text_preserves_whitespace_when_disabled():
    value = "First\n\n\nSecond\tValue"
    assert clean_text(value, PreprocessingProfile(normalize_whitespace=False)) == value
```

- [ ] **Step 2: Run focused tests and confirm signature failure**

Run: `python -m pytest tests/test_document_processing.py -q`

Expected: FAIL because `clean_text` does not accept a preprocessing profile.

- [ ] **Step 3: Extend cleaning without breaking old callers**

```python
def clean_text(
    value: str,
    profile: PreprocessingProfile | None = None,
) -> str:
    options = profile or PreprocessingProfile()
    value = html.unescape(value.replace("\x00", " "))
    value = SCRIPT_STYLE_TAG_PATTERN.sub(" ", value)
    if options.remove_urls:
        value = URL_PATTERN.sub(" ", value)
    if options.remove_emails:
        value = EMAIL_PATTERN.sub(" ", value)
    if options.normalize_whitespace:
        value = normalize_document_whitespace(value)
    return value.strip()
```

Expose structural units for DOCX paragraphs, Markdown headings, delimiter-separated general text, CSV rows, and resume semantic sections. Preserve heading/style metadata when available.

- [ ] **Step 4: Run document processing tests**

Run: `python -m pytest tests/test_document_processing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/document_processing.py tests/test_document_processing.py
git commit -m "Add configurable text preprocessing"
```

### Task 3: Canonical General, Resume, and Parent-child Chunking

**Files:**
- Create: `src/hierarchical_chunking.py`
- Modify: `src/document_processing.py`
- Modify: `tests/test_document_processing.py`

- [ ] **Step 1: Write failing hierarchy tests**

```python
def test_parent_child_indexes_children_and_returns_parent_evidence():
    result = build_chunk_hierarchy(long_markdown_document(), ProcessingProfile.parent_child())
    assert result.parents
    assert result.children
    assert all(child.parent_chunk_id for child in result.children)
    assert all(child.token_count <= 180 for child in result.children)
    assert all(parent.token_count <= 700 for parent in result.parents)
    assert {child.parent_chunk_id for child in result.children} <= {
        parent.chunk_id for parent in result.parents
    }


def test_resume_parent_never_crosses_top_level_sections():
    result = build_chunk_hierarchy(master_resume_fixture(), resume_profile())
    assert not any(
        "教育背景" in parent.raw_body and "项目经验" in parent.raw_body
        for parent in result.parents
    )
```

- [ ] **Step 2: Run tests and confirm missing hierarchy API**

Run: `python -m pytest tests/test_document_processing.py -q`

Expected: FAIL because `build_chunk_hierarchy` does not exist.

- [ ] **Step 3: Implement canonical hierarchy result**

```python
@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    parent_chunk_id: str | None
    semantic_group_id: str
    raw_body: str
    retrieval_text: str
    parent_body: str
    section_type: str
    section_path: str
    entity_title: str
    token_count: int
    character_count: int
    retrieval_priority: str


@dataclass(frozen=True)
class ChunkHierarchy:
    parents: tuple[ChunkRecord, ...]
    children: tuple[ChunkRecord, ...]
```

Implement `build_chunk_hierarchy(document, profile)`. General mode uses the configured delimiter and respects structural boundaries. Resume mode uses existing semantic units as parents. Parent-child mode splits each parent into focused children and repeats the parent title in child retrieval text. Legacy `split_document()` returns serialised child records so existing callers keep working.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_document_processing.py -q`

Expected: PASS, including the existing resume tests.

- [ ] **Step 5: Commit**

```powershell
git add src/hierarchical_chunking.py src/document_processing.py tests/test_document_processing.py
git commit -m "Add hierarchical parent child chunking"
```

### Task 4: SQLite Profile Migration and Persistence

**Files:**
- Modify: `src/local_catalog.py`
- Create: `scripts/migrate_processing_profiles.py`
- Modify: `tests/test_local_catalog.py`

- [ ] **Step 1: Write failing idempotent migration tests**

```python
def test_catalog_migrates_legacy_resume_profile_idempotently(tmp_path):
    catalog = legacy_catalog_with_resume(tmp_path)
    first = catalog.migrate_processing_profiles()
    second = catalog.migrate_processing_profiles()
    saved = catalog.get("resume-id")
    assert first == 1
    assert second == 0
    assert saved["processing_profile"]["chunk_mode"] == "resume_semantic"
    assert saved["processing_profile_hash"]


def test_update_profile_accepts_parent_child(tmp_path):
    catalog = populated_catalog(tmp_path)
    assert catalog.update_processing_profile("doc-id", ProcessingProfile.parent_child())
```

- [ ] **Step 2: Run tests and confirm missing columns/API**

Run: `python -m pytest tests/test_local_catalog.py -q`

Expected: FAIL.

- [ ] **Step 3: Add additive schema migration**

Add `profile_version`, `processing_profile_json`, and `processing_profile_hash` columns. Populate them using `profile_from_legacy()`. Keep legacy chunk columns synchronised for backwards compatibility. Update `active_documents()` to include the complete profile under `metadata.processing_profile`.

```python
def update_processing_profile(self, doc_id: str, profile: ProcessingProfile) -> bool:
    payload = json.dumps(profile.to_dict(), ensure_ascii=False, sort_keys=True)
    with self._connect() as connection:
        cursor = connection.execute(
            """UPDATE documents
               SET profile_version=?, processing_profile_json=?,
                   processing_profile_hash=?, chunk_strategy=?, chunk_size=?,
                   chunk_overlap=?, chunk_unit='tokens', updated_at=?
               WHERE doc_id=?""",
            profile.to_catalog_values(doc_id, _utc_now()),
        )
    return cursor.rowcount > 0
```

- [ ] **Step 4: Add explicit migration script and run tests**

Run: `python -m pytest tests/test_local_catalog.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/local_catalog.py scripts/migrate_processing_profiles.py tests/test_local_catalog.py
git commit -m "Migrate catalog processing profiles"
```

### Task 5: Hierarchy-aware Ingestion and Retrieval

**Files:**
- Modify: `src/ingestion.py`
- Modify: `src/retrieval.py`
- Modify: `src/portfolio_rag.py`
- Modify: `tests/test_ingestion.py`
- Modify: `tests/test_retrieval.py`

- [ ] **Step 1: Write failing ingestion and parent expansion tests**

```python
def test_ingestion_embeds_children_and_stores_parent_body():
    chunks = prepare_chunks([long_document()], profile=ProcessingProfile.parent_child())
    assert all(chunk["parent_chunk_id"] for chunk in chunks)
    assert all(chunk["parent_body"] for chunk in chunks)
    assert all(chunk["processing_profile_hash"] for chunk in chunks)


def test_selection_deduplicates_children_to_parent():
    selected = select_results(two_children_from_same_parent(), RetrievalSettings(top_k=5))
    assert len(selected) == 1
    assert selected[0]["body"] == selected[0]["parent_body"]
```

- [ ] **Step 2: Run focused tests and confirm missing fields/behavior**

Run: `python -m pytest tests/test_ingestion.py tests/test_retrieval.py -q`

Expected: FAIL.

- [ ] **Step 3: Index children and expand evidence to parents**

Use `child.retrieval_text` for embeddings and BM25. Persist parent text and identifiers on each child record so Atlas Local can return evidence without a second collection lookup. Apply score threshold before parent expansion, then deduplicate by `parent_chunk_id` or `semantic_group_id`, retaining the best child score and match diagnostics.

```python
def expand_parent_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("parent_chunk_id") or row.get("semantic_group_id") or row["chunk_id"])
        candidate = {**row, "matched_child_body": row["raw_body"], "body": row.get("parent_body") or row["raw_body"]}
        if key not in best or candidate["score"] > best[key]["score"]:
            best[key] = candidate
    return sorted(best.values(), key=lambda row: row["score"], reverse=True)
```

- [ ] **Step 4: Run ingestion and retrieval tests**

Run: `python -m pytest tests/test_ingestion.py tests/test_retrieval.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ingestion.py src/retrieval.py src/portfolio_rag.py tests/test_ingestion.py tests/test_retrieval.py
git commit -m "Use parent evidence for hierarchical retrieval"
```

### Task 6: Dify-style Knowledge Studio Controls

**Files:**
- Modify: `pages/1_Knowledge_Studio.py`
- Modify: `tests/test_streamlit_contract.py`

- [ ] **Step 1: Write failing Streamlit contract tests**

```python
def test_knowledge_studio_exposes_processing_modes_and_preprocessing_controls():
    page = load_knowledge_studio()
    assert not page.exception
    labels = widget_labels(page)
    assert "General" in labels
    assert "Parent-child" in labels
    assert "Resume semantic" in labels
    assert "Normalize whitespace" in labels
    assert "Remove URLs" in labels
    assert "Remove email addresses" in labels


def test_edited_clean_text_regenerates_preview():
    page = loaded_upload_page()
    before = preview_bodies(page)
    edit_clean_text(page, "Only this edited project remains")
    click(page, "Apply changes and regenerate preview")
    assert preview_bodies(page) != before
    assert preview_bodies(page) == ["Only this edited project remains"]
```

- [ ] **Step 2: Run Streamlit tests and confirm controls are absent**

Run: `python -m pytest tests/test_streamlit_contract.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement explicit draft state and shared preview**

Use session-state keys scoped by `doc_id` and content hash:

```python
draft_key = f"processing_draft:{document['doc_id']}:{document['content_hash']}"
st.session_state.setdefault(draft_key, ProcessingDraft.from_document(document, profile))
```

Render mode, delimiter, token limits, overlap, parent mode, preprocessing toggles, and recommendation reset. Parsed text and cleaned text are separately editable. The apply button calls the canonical preprocessing and hierarchy builder, stores the result, and refreshes PII/chunk/temporary retrieval panels. Saving writes the exact profile and cleaned body used by the preview.

- [ ] **Step 4: Run Streamlit tests**

Run: `python -m pytest tests/test_streamlit_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pages/1_Knowledge_Studio.py tests/test_streamlit_contract.py
git commit -m "Add complete Knowledge Studio processing controls"
```

### Task 7: Retrieval Lab Consistency and Diagnostics

**Files:**
- Modify: `pages/2_Retrieval_Lab.py`
- Modify: `src/retrieval.py`
- Modify: `tests/test_streamlit_contract.py`
- Modify: `tests/test_retrieval.py`

- [ ] **Step 1: Write failing diagnostics tests**

```python
def test_hybrid_result_reports_channels_and_parent_expansion():
    result = hybrid_fixture_result()
    assert result["matched_by"] == ["vector", "bm25"]
    assert result["vector_rank"] == 1
    assert result["bm25_rank"] == 2
    assert result["parent_expanded"] is True


def test_retrieval_lab_renders_all_supported_modes():
    page = load_retrieval_lab()
    assert not page.exception
    assert set(select_options(page, "Retrieval mode")) == {
        "vector", "full_text", "hybrid", "hybrid_rerank"
    }
```

- [ ] **Step 2: Run tests and confirm diagnostics are incomplete**

Run: `python -m pytest tests/test_retrieval.py tests/test_streamlit_contract.py -q`

Expected: FAIL.

- [ ] **Step 3: Share settings and render evidence flow**

Expose Top-K, threshold, candidate count, RRF/weighted fusion, weights, and reranker. Show matched child, returned parent, vector/BM25 ranks, fusion score, rerank score, and latency. If BM25 index or reranker is unavailable, return a typed warning and continue in vector or hybrid mode rather than raising at page import.

- [ ] **Step 4: Run retrieval and Streamlit tests**

Run: `python -m pytest tests/test_retrieval.py tests/test_streamlit_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pages/2_Retrieval_Lab.py src/retrieval.py tests/test_retrieval.py tests/test_streamlit_contract.py
git commit -m "Expose hierarchy aware retrieval diagnostics"
```

### Task 8: Migration, Integration, and Documentation

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `scripts/start-local.ps1`
- Modify: `scripts/check-local.ps1`
- Modify: `tests/test_local_runtime.py`

- [ ] **Step 1: Add failing runtime contract tests**

```python
def test_start_script_runs_profile_migration_before_index_check():
    script = START_SCRIPT.read_text(encoding="utf-8")
    assert script.index("migrate_processing_profiles.py") < script.index("check_index_state.py")


def test_example_env_documents_phase_a_defaults():
    env = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "DEFAULT_CHUNK_MODE=auto" in env
    assert "DEFAULT_RETRIEVAL_MODE=hybrid" in env
```

- [ ] **Step 2: Run runtime tests and confirm missing migration/defaults**

Run: `python -m pytest tests/test_local_runtime.py -q`

Expected: FAIL.

- [ ] **Step 3: Integrate migration and document the workflow**

Run the idempotent profile migration before checking whether the index is current. Mark the index outdated when `processing_profile_hash` differs. Document General, Resume semantic, Parent-child, preprocessing, rebuilding, and retrieval modes. State that Phase A uses only high-quality local embedding and does not introduce paid services.

- [ ] **Step 4: Run complete automated verification**

Run: `python -m pytest`

Expected: all tests PASS.

Run: `python scripts/check_streamlit_pages.py`

Expected: Chat, Knowledge Studio, and Retrieval Lab load without uncaught exceptions.

- [ ] **Step 5: Run local integration verification**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1 -Reindex
```

Expected: MongoDB and Ollama healthy, profile migration completes, ingestion reports child/parent counts, smoke test passes, and Streamlit opens on `http://localhost:8505`.

- [ ] **Step 6: Browser acceptance**

Verify the Master resume recommendation is `Resume semantic`, preview has semantic chunks rather than seven mixed chunks, cleaned-text edits change the preview, parent-child temporary retrieval shows matched child and returned parent, and all Retrieval Lab modes return evidence.

- [ ] **Step 7: Commit Phase A delivery**

```powershell
git add README.md .env.example scripts/start-local.ps1 scripts/check-local.ps1 tests/test_local_runtime.py
git commit -m "Complete Knowledge Studio phase A"
```

## Self-review Results

- Every Phase A requirement in the approved design maps to Tasks 1-8.
- Existing `ChunkConfig`, `split_document`, Python scripts, public JSON, and local SQLite data remain compatible.
- Parent-child behavior is tested at chunk construction, ingestion, retrieval, and UI layers.
- Migration is additive and idempotent; no source files or existing catalog records are deleted.
- Phase B concerns such as economical indexing, OCR, and Gemini provider selection are intentionally excluded until Phase A passes acceptance.

