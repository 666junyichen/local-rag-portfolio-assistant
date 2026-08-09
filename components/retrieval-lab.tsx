"use client";

import { FormEvent, useState } from "react";
import { RotateCcw, Search } from "lucide-react";
import type { Source } from "@/lib/cloud-rag/types";
import { SourceList } from "./source-list";
import { KnowledgeSpaceSelector, usePublicKnowledgeSpaces } from "./knowledge-space-selector";

export function RetrievalLab() {
  const [question, setQuestion] = useState("Junyi 有哪些 RAG 和 MongoDB 项目经验？");
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState<number | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [spaceIds, setSpaceIds] = useState(["portfolio"]);
  const [crossSpace, setCrossSpace] = useState(false);
  const { spaces } = usePublicKnowledgeSpaces();

  async function run(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch("/api/retrieve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, language: "zh", settings: { topK, scoreThreshold: threshold, spaceIds } }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Retrieval failed");
      setSources(result.selectedContext);
    } catch (problem) { setError(problem instanceof Error ? problem.message : "Retrieval failed"); }
    finally { setBusy(false); }
  }

  return <div className="pageFrame">
    <div className="pageHeading"><span className="eyebrow">READ-ONLY PUBLIC INDEX</span><h1>Retrieval Lab</h1><p>检查问题实际召回了哪些公开片段，并观察 Top-K 和相关度阈值如何改变上下文。</p></div>
    <div className="spaceToolbar labSpaceToolbar"><KnowledgeSpaceSelector spaces={spaces} value={spaceIds} onChange={setSpaceIds} multiple={crossSpace}/><label className="toggleLabel"><input type="checkbox" checked={crossSpace} onChange={(event) => { setCrossSpace(event.target.checked); if (!event.target.checked) setSpaceIds((current) => [current[0] || "portfolio"]); }}/>Cross-space query</label></div>
    <form className="labPanel" onSubmit={run}>
      <div className="labQuery"><label htmlFor="lab-question">测试问题</label><textarea id="lab-question" value={question} maxLength={500} onChange={(event) => setQuestion(event.target.value)} rows={3}/></div>
      <div className="labControls">
        <label>Top-K <input type="range" min="1" max="10" value={topK} onChange={(event) => setTopK(Number(event.target.value))}/><strong>{topK}</strong></label>
        <label>Score threshold <input type="number" min="0" max="1" step="0.05" placeholder="Disabled" value={threshold ?? ""} onChange={(event) => setThreshold(event.target.value ? Number(event.target.value) : null)}/></label>
        <button type="button" className="secondaryButton" onClick={() => { setTopK(5); setThreshold(null); }}><RotateCcw size={16}/> Reset</button>
        <button className="primaryButton" disabled={busy}><Search size={16}/> {busy ? "Retrieving…" : "Run retrieval"}</button>
      </div>
    </form>
    {error && <div className="errorBanner">{error}</div>}
    <div className="resultsHeader"><h2>Selected context</h2><span>{sources.length} chunks · {spaceIds.length} space(s) · public only</span></div>
    <SourceList sources={sources}/>
  </div>;
}
