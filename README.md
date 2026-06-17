# Local RAG Portfolio Assistant

A fully local Retrieval-Augmented Generation assistant that answers questions about Junyi Chen's projects, skills, internships, and technical background.

This project adapts a Google/MongoDB local RAG workshop into a portfolio-focused assistant. Instead of asking about MongoDB documentation, the assistant retrieves from `data/portfolio_docs.json` and answers as Junyi's portfolio assistant.

![Local RAG Portfolio Assistant Streamlit demo](assets/streamlit-answer.png)

## Local Demo

This is a fully local AI demo. The portfolio data, vector database, embedding model, and LLM runtime all run on the local machine.

- No cloud deployment is required.
- No online LLM API key is required.
- Requires local Docker/MongoDB Local Atlas and Ollama.
- Answers are grounded in the curated knowledge base at `data/portfolio_docs.json`.

## Demo Questions

Try questions like:

- What are Junyi Chen's strongest AI and data projects?
- What MongoDB experience does Junyi have?
- Summarize Junyi for a full-stack role.
- Which projects show LLM or AI application experience?

## Example Answer

For an AI/data project question, the assistant retrieves Junyi's strongest matching portfolio entries and summarizes projects such as the Accessibility Testing QA Engine, QANet question answering work, PulseScape emotion-aware recommender, diabetes prediction, and spatial resource accessibility analysis. The response is generated from local portfolio context rather than a generic resume prompt.

## Tech Stack

- Python
- MongoDB Local Atlas and MongoDB Vector Search
- `voyageai/voyage-4-nano` local embeddings
- Ollama-hosted Gemma model
- Streamlit UI
- Jupyter notebook for experimentation

## Project Structure

```text
.
|-- app.py
|-- assets/
|   |-- streamlit-answer.png
|   `-- streamlit-home.png
|-- data/
|   `-- portfolio_docs.json
|-- docs/
|   `-- architecture.md
|-- notebooks/
|   `-- rag_pipeline.ipynb
|-- scripts/
|   |-- ingest.py
|   `-- smoke_test.py
|-- src/
|   `-- portfolio_rag.py
|-- .env.example
|-- pyproject.toml
`-- uv.lock
```

## Setup

Copy the environment file:

```powershell
Copy-Item .env.example .env
```

Update `MONGODB_URI` if your Local Atlas port is different:

```dotenv
MONGODB_URI=mongodb://localhost:62262/?directConnection=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma:2b
```

Install dependencies:

```powershell
uv sync
```

## Required Local Services

MongoDB Local Atlas should be running, for example:

```powershell
atlas local start local-rag
atlas local connect local-rag --connectWith connectionString
```

Ollama should expose port `11434` and include the model named in `.env`:

```powershell
docker ps
curl http://localhost:11434/api/tags
```

## Ingest Portfolio Data

Run:

```powershell
uv run python scripts/ingest.py
```

If `uv run` cannot access the local cache on Windows, use the project virtual environment directly:

```powershell
.\.venv\Scripts\python.exe scripts\ingest.py
```

This loads `data/portfolio_docs.json`, chunks the documents, creates embeddings, inserts them into MongoDB, and creates the vector index.

## Run a Smoke Test

```powershell
uv run python scripts/smoke_test.py
```

Or:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

## Run the Chat UI

```powershell
uv run streamlit run app.py
```

Or:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8505
```

## Resume Description

- Built a fully local RAG portfolio assistant using MongoDB Atlas Vector Search, local `voyageai/voyage-4-nano` embeddings, and Ollama-hosted Gemma; implemented document ingestion, chunking, vector indexing, semantic retrieval, local LLM answer generation, smoke testing, and a Streamlit chat interface for private portfolio Q&A.

## Next Customization Steps

- Expand `data/portfolio_docs.json` with more accurate personal resume, internship, certificate, and project details.
- Add screenshots or a short demo video to the README.
- Replace `gemma:2b` with a stronger Gemma model if your machine can run it.
- Add deployment notes if you later convert this from a local-only app to a cloud demo.
