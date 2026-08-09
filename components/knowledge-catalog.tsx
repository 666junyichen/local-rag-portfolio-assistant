"use client";

import { BookOpenText, ExternalLink, Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { KnowledgeSpaceSelector, usePublicKnowledgeSpaces } from "./knowledge-space-selector";

type PublicDocument = {
  docId: string;
  title: string;
  summary: string;
  category: string;
  language: "zh" | "en";
  updatedAt: string;
  sourceUrl?: string;
  spaceId: string;
  spaceName: string;
};

export function KnowledgeCatalog() {
  const [documents, setDocuments] = useState<PublicDocument[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [spaceIds, setSpaceIds] = useState(["portfolio"]);
  const { spaces } = usePublicKnowledgeSpaces();

  async function load(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (category) params.set("category", category);
      spaceIds.forEach((spaceId) => params.append("spaceId", spaceId));
      const response = await fetch(`/api/knowledge?${params}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to load the catalog.");
      setDocuments(payload.documents || []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load the catalog.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  const categories = [...new Set(documents.map((document) => document.category).filter(Boolean))].sort();

  return <div className="pageFrame knowledgePage">
    <div className="pageHeading"><span className="eyebrow">PUBLIC KNOWLEDGE</span><h1>Published evidence catalog</h1><p>Browse the curated public documents available to Ask AI. Full text, chunks, embeddings, and owner metadata are never exposed here.</p></div>
    <div className="catalogSpaceFilter"><KnowledgeSpaceSelector spaces={spaces} value={spaceIds} onChange={setSpaceIds}/></div>
    <form className="catalogToolbar" onSubmit={load}>
      <label className="searchField"><Search size={17}/><span className="srOnly">Search documents</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search titles and summaries" maxLength={100}/></label>
      <select aria-label="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
      <button className="primaryButton" type="submit">Search</button>
    </form>
    {error ? <div className="errorBanner">{error}</div> : null}
    <div className="catalogSummary"><strong>{loading ? "Loading" : documents.length}</strong><span>public documents</span></div>
    {!loading && !documents.length ? <div className="emptyCatalog"><BookOpenText size={23}/><strong>No public documents matched.</strong><span>Try a broader search or seed the public catalog.</span></div> : null}
    <div className="documentGrid">{documents.map((document) => <article className="documentCard" key={document.docId}>
      <div className="documentMeta"><span>{document.spaceName}</span><span>{document.category}</span><span>{document.language.toUpperCase()}</span></div>
      <h2>{document.title}</h2>
      <p>{document.summary || "Public source available for grounded answers."}</p>
      <footer><time dateTime={document.updatedAt}>{document.updatedAt ? new Date(document.updatedAt).toLocaleDateString() : "Date unavailable"}</time>{document.sourceUrl ? <a href={document.sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink size={14}/></a> : <span>Curated source</span>}</footer>
    </article>)}</div>
  </div>;
}
