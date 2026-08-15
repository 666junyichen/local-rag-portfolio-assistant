# Shared Chunking Contract And Owner Knowledge Entry

## Goal

Make cloud publication follow the local hierarchy rules without shipping the local Python or embedding runtime to Vercel, and place the Owner upload workflow where it is discoverable from the public Knowledge page.

## Changes

- Added a fail-closed Owner-only `上传与管理` entry on Knowledge that links to protected Publish Studio.
- Added one versioned processing-profile JSON source consumed by Python and TypeScript.
- Aligned cloud token estimation, resume section metadata, semantic groups, and retrieval priority with the local contract.
- Added fixed post-parser resume, Markdown, and CSV fixtures plus Python export and TypeScript parity tests.

## Verification

- `npm test -- --run tests/cloud-knowledge-owner-entry.test.ts tests/cloud-shared-processing-profiles.test.ts tests/cloud-chunking-parity.test.ts tests/cloud-publish-processing.test.ts`: 23 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_chunking_contract.py tests\test_shared_processing_profiles.py tests\test_processing_profiles.py tests\test_hierarchical_chunking.py -q`: 62 passed.
- `npm run build`: passed.

## Decisions

- Python hierarchy output is canonical; TypeScript must match it through fixtures.
- SentenceTransformer remains local and Gemini remains cloud-only.
- Owner discovery may live on Knowledge, while authorization and management routes remain separate.

## Next Entry

Upload one trusted document to each runtime and compare Retrieval Lab evidence before changing any retrieval or embedding configuration.
