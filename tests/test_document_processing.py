from __future__ import annotations

import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from src.document_processing import (
    ChunkConfig,
    chunk_metrics,
    clean_text,
    count_tokens,
    detect_pii,
    normalize_document,
    parse_uploaded_file,
    persist_and_parse_upload,
    rank_preview_chunks,
    recommend_chunk_config,
    replace_document_body,
    split_document,
)
from src.processing_profiles import PreprocessingProfile


class DocumentProcessingTests(unittest.TestCase):
    def test_clean_text_default_profile_matches_legacy_normalization(self) -> None:
        value = "\x00 <p>Hello&nbsp;&nbsp; world</p>\t\n \n\nNext "

        expected = "Hello\xa0\xa0 world\n\nNext"
        self.assertEqual(clean_text(value), expected)
        self.assertEqual(clean_text(value, PreprocessingProfile()), expected)

    def test_clean_text_normalizes_horizontal_and_vertical_whitespace(self) -> None:
        profile = PreprocessingProfile(normalize_whitespace=True)

        result = clean_text(" First\t\tline  \n  \n\n\nSecond\f\v line ", profile)

        self.assertEqual(result, "First line\n\nSecond line")

    def test_clean_text_preserves_user_whitespace_when_normalization_is_disabled(self) -> None:
        profile = PreprocessingProfile(normalize_whitespace=False)
        value = "\tFirst  <b>line</b>  \n\n\nSecond\fline\v"

        result = clean_text(value, profile)

        self.assertEqual(result, "\tFirst   line   \n\n\nSecond\fline\v")

    def test_clean_text_still_removes_unsafe_markup_without_whitespace_normalization(self) -> None:
        profile = PreprocessingProfile(normalize_whitespace=False)
        value = "A&amp;\x00<script>alert('x')</script>\n<style>.x { color: red; }</style><p>B</p>"

        result = clean_text(value, profile)

        self.assertEqual(result, "A&  \n  B ")
        self.assertNotIn("\x00", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("color", result)

    def test_clean_text_removes_urls_without_removing_emails_or_surrounding_punctuation(self) -> None:
        profile = PreprocessingProfile(remove_urls=True)
        value = (
            "Links: https://example.com/path?q=1, www.portfolio.dev/demo; "
            "and docs.example.org. Email dev@example.com remains."
        )

        result = clean_text(value, profile)

        self.assertEqual(result, "Links: , ; and . Email dev@example.com remains.")

    def test_clean_text_removes_emails_without_removing_urls(self) -> None:
        profile = PreprocessingProfile(remove_emails=True)
        value = "Contact dev.team+rag@example.co.uk; visit https://example.com/contact."

        result = clean_text(value, profile)

        self.assertEqual(result, "Contact ; visit https://example.com/contact.")

    def test_clean_text_removes_urls_and_emails_across_lines(self) -> None:
        profile = PreprocessingProfile(remove_urls=True, remove_emails=True)
        value = "Site: https://example.com\nEmail: me@example.com\nMirror: portfolio.dev/docs"

        result = clean_text(value, profile)

        self.assertEqual(result, "Site:\nEmail:\nMirror:")

    def test_clean_text_removal_does_not_overreach_into_github_text_or_invalid_emails(self) -> None:
        profile = PreprocessingProfile(remove_urls=True, remove_emails=True)
        value = "GitHub projects use @mentions, team@localhost, and words@inside without domains."
        before = profile.to_dict()

        result = clean_text(value, profile)

        self.assertEqual(result, value)
        self.assertEqual(profile.to_dict(), before)

    def test_blank_document_body_behavior_remains_compatible(self) -> None:
        with self.assertRaisesRegex(ValueError, "document body cannot be empty"):
            normalize_document({"title": "Blank", "body": "\x00<script>x</script>  \n\t"})

    def test_token_counter_handles_english_terms_and_chinese_characters(self) -> None:
        self.assertEqual(count_tokens("MongoDB Vector Search"), 3)
        self.assertEqual(count_tokens("中文检索"), 4)

    def test_recommends_resume_chunking_from_docx_metadata(self) -> None:
        document = normalize_document(
            {
                "title": "Master Resume",
                "body": "Resume evidence. " * 500,
                "metadata": {"file_type": "docx", "source": "Master Resume.docx"},
            }
        )
        config = recommend_chunk_config(document)
        self.assertEqual(config, ChunkConfig("resume_semantic", 320, 0, unit="tokens"))
        self.assertEqual(config.unit, "tokens")

    def test_resume_semantic_chunking_keeps_entities_and_sections_separate(self) -> None:
        resume = normalize_document(
            {
                "title": "Junyi Resume",
                "body": """个人简历

陈君奕

求职方向：AI应用工程

教育背景

悉尼大学｜数据科学硕士｜2025.02 - 2026.12

相关课程：机器学习、深度学习

个人简介

具备全栈开发、AI 应用和数据分析经验。

面向数据科学岗位的定制个人简介。

实习经历

南京软通动力｜AI实习生｜2025.06 - 2025.07

参与 AI Agent、RAG 和 Dify 工作流实现。

项目经验

本地RAG知识库问答系统｜Local RAG Portfolio Assistant｜2026

技术栈：Python、MongoDB Vector Search、Ollama

构建文档切片、向量检索和回答生成链路。

Owlswap Marketplace｜2026

技术栈：Next.js、TypeScript、MongoDB Atlas

实现商品发布、收藏和后台管理。

专业技能

AI 与数据能力

PyTorch、NLP、RAG、模型评估
""",
                "metadata": {"file_type": "docx", "source": "resume.docx"},
            }
        )

        chunks = split_document(resume, ChunkConfig("resume_semantic", 320, 0, unit="tokens"))
        rag_chunk = next(chunk for chunk in chunks if chunk["entity_title"].startswith("本地RAG"))
        owl_chunk = next(chunk for chunk in chunks if chunk["entity_title"].startswith("Owlswap"))
        summaries = [chunk for chunk in chunks if chunk["section_type"] == "summary"]

        self.assertIn("MongoDB Vector Search", rag_chunk["body"])
        self.assertNotIn("Owlswap", rag_chunk["body"])
        self.assertEqual(rag_chunk["section_type"], "project")
        self.assertEqual(rag_chunk["section_path"], "项目经验 > 本地RAG知识库问答系统｜Local RAG Portfolio Assistant｜2026")
        self.assertTrue(rag_chunk["semantic_group_id"])
        self.assertEqual(rag_chunk["retrieval_priority"], "primary")
        self.assertGreater(rag_chunk["token_count"], 0)
        self.assertEqual(owl_chunk["section_type"], "project")
        self.assertEqual([item["retrieval_priority"] for item in summaries], ["primary", "secondary"])
        self.assertFalse(any("教育背景" in chunk["body"] and "项目经验" in chunk["body"] for chunk in chunks))

    def test_resume_semantic_chunking_repeats_entity_title_for_oversized_chunks(self) -> None:
        title = "Large AI Project｜2026"
        resume = normalize_document(
            {
                "title": "Resume",
                "body": "项目经验\n\n" + title + "\n\n技术栈：Python、MongoDB\n\n" + ("项目成果与模型评估。" * 180),
                "metadata": {"file_type": "docx"},
            }
        )

        chunks = split_document(resume, ChunkConfig("resume_semantic", 200, 0, unit="tokens"))

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["body"].startswith(title) for chunk in chunks))
        self.assertEqual(len({chunk["semantic_group_id"] for chunk in chunks}), 1)
        self.assertTrue(all(chunk["token_count"] <= 200 for chunk in chunks))

    def test_resume_semantic_chunking_groups_duplicate_skill_variants_as_secondary(self) -> None:
        resume = normalize_document(
            {
                "title": "Resume",
                "body": """Skills

Programming and Development

Python, TypeScript, React

AI and Data

RAG, PyTorch, MongoDB Vector Search

Programming: Python, TypeScript, React

AI: RAG, PyTorch, embeddings

Tools: Git, Docker, Vercel""",
                "metadata": {"file_type": "docx"},
            }
        )

        chunks = split_document(resume, ChunkConfig("resume_semantic", 320, 0, unit="tokens"))
        secondary = [chunk for chunk in chunks if chunk["retrieval_priority"] == "secondary"]

        self.assertTrue(secondary)
        combined = "\n".join(chunk["body"] for chunk in secondary)
        self.assertIn("Programming: Python", combined)
        self.assertIn("Tools: Git", combined)
        self.assertEqual(len({chunk["semantic_group_id"] for chunk in secondary}), 1)

    def test_recommends_markdown_and_short_json_chunking(self) -> None:
        markdown = normalize_document(
            {"title": "README", "body": "# Project\n" + "Evidence. " * 200, "metadata": {"file_type": "md"}}
        )
        short_json = normalize_document(
            {"title": "Summary", "body": "Short public summary.", "metadata": {"file_type": "json"}}
        )
        self.assertEqual(recommend_chunk_config(markdown), ChunkConfig("markdown", 800, 80, unit="tokens"))
        self.assertEqual(recommend_chunk_config(short_json), ChunkConfig("recursive", 800, 0, unit="tokens"))

    def test_csv_rows_never_add_chunk_overlap(self) -> None:
        document = normalize_document(
            {"title": "Experience rows", "body": "Structured row. " * 100, "metadata": {"file_type": "csv"}}
        )
        self.assertEqual(recommend_chunk_config(document), ChunkConfig("recursive", 800, 0, unit="tokens"))

    def test_chunk_metrics_flag_fragmented_content(self) -> None:
        metrics = chunk_metrics([{"body": "a" * 40}, {"body": "b" * 400}])
        self.assertEqual(metrics["count"], 2)
        self.assertEqual(metrics["min_length"], 40)
        self.assertEqual(metrics["max_length"], 400)
        self.assertEqual(metrics["too_short_ratio"], 0.5)
        self.assertTrue(metrics["warnings"])

    def test_detect_pii_finds_email_and_phone(self) -> None:
        findings = detect_pii("Email me at person@example.com or call 13776680803.")
        self.assertEqual({item["type"] for item in findings}, {"email", "phone"})

    def test_preview_retrieval_ranks_the_most_similar_chunk_first(self) -> None:
        class FakeModel:
            def encode_query(self, values):
                return np.array([[1.0, 0.0] for _ in values])

            def encode_document(self, values):
                return np.array([[1.0, 0.0] if "MongoDB" in value else [0.0, 1.0] for value in values])

        chunks = [{"body": "Frontend UI"}, {"body": "MongoDB vector search"}]
        results = rank_preview_chunks(chunks, "database experience", FakeModel(), top_k=2)
        self.assertEqual(results[0]["body"], "MongoDB vector search")
        self.assertEqual(results[0]["score"], 1.0)

    def test_preview_retrieval_diversifies_groups_and_prefers_primary_evidence(self) -> None:
        class FakeModel:
            def encode_query(self, values):
                return np.array([[1.0, 0.0] for _ in values])

            def encode_document(self, values):
                vectors = []
                for value in values:
                    if "summary duplicate" in value:
                        vectors.append([1.0, 0.0])
                    elif "project evidence" in value:
                        vectors.append([0.95, 0.05])
                    else:
                        vectors.append([0.0, 1.0])
                return np.array(vectors)

        chunks = [
            {
                "body": "summary duplicate one",
                "semantic_group_id": "summary",
                "retrieval_priority": "secondary",
            },
            {
                "body": "summary duplicate two",
                "semantic_group_id": "summary",
                "retrieval_priority": "secondary",
            },
            {
                "body": "project evidence",
                "semantic_group_id": "project-rag",
                "retrieval_priority": "primary",
            },
        ]

        results = rank_preview_chunks(chunks, "AI projects", FakeModel(), top_k=3)

        self.assertEqual(results[0]["body"], "project evidence")
        self.assertEqual(len([row for row in results if row["semantic_group_id"] == "summary"]), 1)

    def test_persist_and_parse_upload_keeps_a_stable_docx_result(self) -> None:
        document_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>Portfolio evidence from DOCX.</w:t></w:r></w:p></w:body>
        </w:document>'''
        with tempfile.TemporaryDirectory() as temp_dir:
            uploads_dir = Path(temp_dir)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            first = persist_and_parse_upload("resume.docx", buffer.getvalue(), uploads_dir)
            second = persist_and_parse_upload("resume.docx", buffer.getvalue(), uploads_dir)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["body"], "Portfolio evidence from DOCX.")

    def test_normalize_document_adds_stable_identity_and_public_visibility(self) -> None:
        raw = {
            "title": "RAG Assistant",
            "body": "A grounded portfolio assistant built with MongoDB Vector Search.",
            "metadata": {"category": "project", "language": "en"},
        }

        first = normalize_document(raw, default_visibility="public")
        second = normalize_document(raw, default_visibility="public")

        self.assertEqual(first["doc_id"], second["doc_id"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(first["visibility"], "public")
        self.assertEqual(first["metadata"]["visibility"], "public")

    def test_normalize_document_defaults_new_uploads_to_private(self) -> None:
        doc = normalize_document({"title": "Draft", "body": "Private draft body."})
        self.assertEqual(doc["visibility"], "private")

    def test_replace_document_body_preserves_identity_and_rebuilds_chunks(self) -> None:
        original = normalize_document(
            {
                "title": "Editable resume",
                "body": "Old MongoDB project evidence.",
                "metadata": {"file_type": "docx"},
            }
        )

        edited = replace_document_body(
            original,
            "<p>Updated RAG project evidence.</p>\n\n\nAvailable for interviews.",
        )
        chunks = split_document(edited, ChunkConfig(chunk_size=200, chunk_overlap=20))

        self.assertEqual(edited["doc_id"], original["doc_id"])
        self.assertNotEqual(edited["content_hash"], original["content_hash"])
        self.assertEqual(
            edited["body"],
            "Updated RAG project evidence.\n\nAvailable for interviews.",
        )
        self.assertIn("Updated RAG project evidence", chunks[0]["body"])
        self.assertNotIn("Old MongoDB project evidence", chunks[0]["body"])

    def test_chunk_config_rejects_excessive_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "25%"):
            ChunkConfig(strategy="recursive", chunk_size=400, chunk_overlap=120)

    def test_split_document_preserves_identity_and_adds_chunk_ids(self) -> None:
        doc = normalize_document(
            {
                "title": "Long project",
                "body": "First paragraph. " * 40 + "\n\n" + "Second paragraph. " * 40,
                "metadata": {"category": "project", "language": "en"},
            },
            default_visibility="public",
        )

        chunks = split_document(doc, ChunkConfig(chunk_size=200, chunk_overlap=40))

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["doc_id"], doc["doc_id"])
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertNotEqual(chunks[0]["chunk_id"], chunks[1]["chunk_id"])
        self.assertEqual(chunks[0]["visibility"], "public")
        self.assertEqual(chunks[0]["body"], chunks[0]["raw_body"])
        self.assertIn("Long project", chunks[0]["context_prefix"])
        self.assertTrue(chunks[0]["retrieval_text"].endswith(chunks[0]["raw_body"]))
        self.assertEqual(chunks[0]["chunk_unit"], "characters")

    def test_parse_json_and_csv_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "docs.json"
            json_path.write_text(
                json.dumps([{"title": "One", "body": "First body long enough for ingestion."}]),
                encoding="utf-8",
            )
            csv_path = root / "docs.csv"
            csv_path.write_text("title,body\nTwo,Second body long enough for ingestion.\n", encoding="utf-8")

            json_docs = parse_uploaded_file(json_path)
            csv_docs = parse_uploaded_file(csv_path)

        self.assertEqual(json_docs[0]["title"], "One")
        self.assertEqual(csv_docs[0]["title"], "Two")
        self.assertEqual(csv_docs[0]["visibility"], "private")


if __name__ == "__main__":
    unittest.main()
