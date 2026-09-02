"use client";

import { FormEvent, useState } from "react";
import { Bot, Languages, Send, SlidersHorizontal, UserRound } from "lucide-react";
import type { ChatTurn, Language, Source } from "@/lib/cloud-rag/types";
import { EvidenceRail } from "./evidence-rail";
import { KnowledgeSpaceSelector, usePublicKnowledgeSpaces } from "./knowledge-space-selector";

type Message = ChatTurn & { sources?: Source[] };

const copy = {
  zh: {
    kicker: "公开云端 RAG",
    title: "向 Junyi 的项目资料提问",
    description: "系统先从 MongoDB Atlas 召回公开证据，再由 OpenAI 基于证据回答。",
    placeholder: "例如：哪些项目体现了 Junyi 的 AI 应用能力？",
    empty: "你好，我可以根据公开的简历与项目资料，回答关于 Junyi 的技术能力、项目和经历。",
    questions: ["Junyi 最强的 AI 项目有哪些？", "他有哪些 MongoDB 经验？", "为什么适合全栈开发岗位？"],
  },
  en: {
    kicker: "PUBLIC CLOUD RAG",
    title: "Ask Junyi's portfolio evidence",
    description: "MongoDB Atlas retrieves public evidence first; OpenAI then answers from that evidence.",
    placeholder: "Ask about projects, skills, or technical experience",
    empty: "Hi. I answer questions about Junyi's public projects, skills, and experience with retrieved evidence.",
    questions: ["What are Junyi's strongest AI projects?", "What MongoDB experience does he have?", "Why is he a fit for full-stack roles?"],
  },
};

function parseSse(block: string) {
  const event = block.match(/^event: (.+)$/m)?.[1];
  const data = block.match(/^data: (.+)$/m)?.[1];
  return event && data ? { event, data: JSON.parse(data) } : null;
}

export function ChatInterface() {
  const [language, setLanguage] = useState<Language>("zh");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [spaceIds, setSpaceIds] = useState(["portfolio"]);
  const [crossSpace, setCrossSpace] = useState(false);
  const { spaces, error: spacesError } = usePublicKnowledgeSpaces();
  const hasMultipleSpaces = spaces.filter((space) => space.status === "active").length > 1;
  const text = copy[language];

  async function ask(value: string) {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    const history = messages.map(({ role, content }) => ({ role, content })).slice(-12);
    setMessages((current) => [...current, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);
    setQuestion(""); setSources([]); setBusy(true);
    try {
      const response = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: trimmed, language, history, settings: { topK, scoreThreshold: threshold, spaceIds } }) });
      if (!response.ok || !response.body) throw new Error((await response.json()).error || "Request failed");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { value: chunk, done } = await reader.read();
        buffer += decoder.decode(chunk || new Uint8Array(), { stream: !done });
        const blocks = buffer.split("\n\n"); buffer = blocks.pop() || "";
        for (const block of blocks) {
          const item = parseSse(block); if (!item) continue;
          if (item.event === "retrieval") setSources(item.data.sources);
          if (item.event === "token") setMessages((current) => current.map((message, index) => index === current.length - 1 ? { ...message, content: message.content + item.data.text } : message));
          if (item.event === "error") throw new Error(item.data.message);
        }
        if (done) break;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "The assistant is temporarily unavailable.";
      setMessages((current) => current.map((item, index) => index === current.length - 1 ? { ...item, content: `Error: ${message}` } : item));
    } finally { setBusy(false); }
  }

  function submit(event: FormEvent) { event.preventDefault(); void ask(question); }

  return <div className="workspace">
    <section className="chatWorkspace">
      <div className="workspaceHeader">
        <div><span className="eyebrow">{text.kicker}</span><h1>{text.title}</h1><p>{text.description}</p></div>
        <div className="headerActions">
          <button className="iconButton" title="Retrieval settings" aria-label="Retrieval settings" onClick={() => setSettingsOpen(!settingsOpen)}><SlidersHorizontal size={18}/></button>
          <div className="segmented" aria-label="Language"><Languages size={16}/>{(["zh", "en"] as Language[]).map((value) => <button key={value} className={language === value ? "selected" : ""} onClick={() => setLanguage(value)}>{value === "zh" ? "中文" : "EN"}</button>)}</div>
        </div>
      </div>
      <div className="spaceToolbar">
        <KnowledgeSpaceSelector spaces={spaces} value={spaceIds} onChange={setSpaceIds} multiple={crossSpace}/>
        {hasMultipleSpaces ? <label className="toggleLabel"><input type="checkbox" checked={crossSpace} onChange={(event) => { setCrossSpace(event.target.checked); if (!event.target.checked) setSpaceIds((current) => [current[0] || "portfolio"]); }}/>Cross-space query</label> : null}
        {spacesError ? <small className="inlineError">{spacesError}</small> : null}
      </div>
      {settingsOpen && <div className="settingsBar"><label>Top-K <input type="range" min="1" max="10" value={topK} onChange={(e) => setTopK(Number(e.target.value))}/><strong>{topK}</strong></label><label>Threshold <input type="number" min="0" max="1" step="0.05" placeholder="Off" value={threshold ?? ""} onChange={(e) => setThreshold(e.target.value === "" ? null : Number(e.target.value))}/></label></div>}
      <div className="chatLog" aria-live="polite">
        {!messages.length && <div className="welcomeMessage"><Bot size={20}/><p>{text.empty}</p></div>}
        {messages.map((message, index) => <div className={`message ${message.role}`} key={index}><span className="avatar">{message.role === "assistant" ? <Bot size={17}/> : <UserRound size={17}/>}</span><div>{message.content || (busy && index === messages.length - 1 ? <span className="typing">Retrieving evidence</span> : "")}</div></div>)}
      </div>
      <div className="suggestions">{text.questions.map((item) => <button key={item} onClick={() => void ask(item)}>{item}</button>)}</div>
      <form className="composer" onSubmit={submit}><textarea maxLength={500} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={text.placeholder} rows={2}/><button className="sendButton" aria-label="Send question" disabled={busy || !question.trim()}><Send size={18}/></button></form>
      <p className="privacyNote">Public demo · No chat text is persisted · {question.length}/500</p>
    </section>
    <EvidenceRail sources={sources}/>
  </div>;
}
