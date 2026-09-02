"use client";

import {
  AlertTriangle,
  Archive,
  Check,
  ChevronRight,
  Download,
  Eye,
  FileText,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { chunksForPreviewView, type PreviewView } from "../lib/cloud-publish/preview-view";
import type { KnowledgeSpace } from "./knowledge-space-selector";

type ProcessingProfile = {
  chunkMode: "standard" | "parent_child" | "resume_semantic";
  delimiter: string;
  childMaxTokens: number;
  childOverlapTokens: number;
  parentMaxTokens: number;
  normalizeWhitespace: boolean;
  removeUrls: boolean;
  removeEmails: boolean;
};

type PreviewChunk = {
  chunkId: string;
  parentChunkId: string;
  semanticGroupId: string;
  rawBody: string;
  parentBody: string;
  sectionType: string;
  sectionPath: string;
  entityTitle: string;
  tokenCount: number;
  charCount: number;
};

type Draft = {
  draftId: string;
  docId?: string;
  spaceId: string;
  title: string;
  summary: string;
  category: string;
  language: "zh" | "en";
  sourceUrl: string;
  fileName: string;
  fileType: string;
  sizeBytes: number;
  parsedBody: string;
  cleanedBody: string;
  processingProfile: ProcessingProfile;
  preview?: { parents: PreviewChunk[]; children: PreviewChunk[]; averageChildTokens: number };
  piiFindings: Array<{ kind: string; label: string }>;
  status: string;
  failureCode: string;
  publicationVersion: number;
  expiresAt: string;
};

type PublishedDocument = {
  docId: string;
  spaceId: string;
  spaceName: string;
  title: string;
  summary: string;
  category: string;
  language: "zh" | "en";
  updatedAt: string;
  sourceUrl?: string;
  status: string;
  publicationVersion: number;
};

type ResetPreview = {
  fingerprint: string;
  snapshot: {
    spaces: number;
    drafts: number;
    documents: number;
    chunks: number;
    metadata: number;
  };
};

const steps = ["Upload & parse", "Clean & inspect", "Chunk preview", "Publish"];

async function requestJson(url: string, init?: RequestInit) {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

export function PublishStudio() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [documents, setDocuments] = useState<PublishedDocument[]>([]);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [uploadSpaceId, setUploadSpaceId] = useState("portfolio");
  const [newSpaceName, setNewSpaceName] = useState("");
  const [newSpaceDescription, setNewSpaceDescription] = useState("");
  const [selected, setSelected] = useState<Draft | null>(null);
  const [tab, setTab] = useState<"drafts" | "published" | "archived">("drafts");
  const [step, setStep] = useState(0);
  const [previewView, setPreviewView] = useState<PreviewView>("children");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [resetPreview, setResetPreview] = useState<ResetPreview | null>(null);
  const [resetBackupFingerprint, setResetBackupFingerprint] = useState("");
  const [resetConfirmation, setResetConfirmation] = useState("");

  async function refresh() {
    setBusy("refresh");
    try {
      const payload = await requestJson("/api/admin/drafts", { cache: "no-store" });
      setDrafts(payload.drafts || []);
      setDocuments(payload.documents || []);
      setSpaces(payload.spaces || []);
      const activeSpaces = (payload.spaces || []).filter((space: KnowledgeSpace) => space.status === "active");
      if (activeSpaces.length && !activeSpaces.some((space: KnowledgeSpace) => space.spaceId === uploadSpaceId)) setUploadSpaceId(activeSpaces[0].spaceId);
      if (selected) {
        const updated = (payload.drafts || []).find((draft: Draft) => draft.draftId === selected.draftId);
        if (updated) setSelected(updated);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load Publish Studio.");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy("upload"); setError(""); setNotice("");
    try {
      const form = new FormData();
      form.append("spaceId", uploadSpaceId);
      Array.from(files).slice(0, 10).forEach((file) => form.append("files", file));
      const response = await fetch("/api/admin/drafts", { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok && response.status !== 207) throw new Error(payload.error || "Upload failed.");
      setNotice(`${payload.drafts?.length || 0} draft(s) created${payload.errors?.length ? `; ${payload.errors.length} file(s) need attention` : ""}.`);
      await refresh();
      if (payload.drafts?.[0]) { setSelected(payload.drafts[0]); setStep(0); setTab("drafts"); }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
      setBusy("");
    }
  }

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setSelected((current) => current ? { ...current, [key]: value } : current);
  }

  function updateProfile<K extends keyof ProcessingProfile>(key: K, value: ProcessingProfile[K]) {
    setSelected((current) => current ? { ...current, processingProfile: { ...current.processingProfile, [key]: value } } : current);
  }

  async function saveDraft(current = selected) {
    if (!current) throw new Error("Choose a draft first.");
    const payload = await requestJson(`/api/admin/drafts/${current.draftId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: current.title,
        summary: current.summary,
        category: current.category,
        language: current.language,
        sourceUrl: current.sourceUrl,
        spaceId: current.spaceId,
        cleanedBody: current.cleanedBody,
        processingProfile: current.processingProfile,
      }),
    });
    setSelected(payload.draft);
    return payload.draft as Draft;
  }

  async function previewDraft() {
    if (!selected) throw new Error("Choose a draft first.");
    setBusy("preview"); setError(""); setNotice("");
    try {
      const saved = await saveDraft(selected);
      const payload = await requestJson(`/api/admin/drafts/${saved.draftId}/preview`, { method: "POST" });
      setSelected(payload.draft);
      setDrafts((current) => current.map((draft) => draft.draftId === payload.draft.draftId ? payload.draft : draft));
      setNotice(payload.draft.piiFindings.length ? "Preview updated. Remove all detected PII before publishing." : "Preview is ready to publish.");
      return payload.draft as Draft;
    } finally {
      setBusy("");
    }
  }

  async function publish() {
    if (!selected) return;
    setBusy("publish"); setError(""); setNotice("");
    try {
      const ready = await previewDraft();
      if (ready.piiFindings.length) { setStep(1); return; }
      const payload = await requestJson(`/api/admin/drafts/${ready.draftId}/publish`, { method: "POST" });
      setNotice(`Published ${payload.chunkCount} searchable chunks.`);
      setSelected(null); setTab("published"); setStep(0);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Publishing failed. The draft was kept.");
    } finally {
      setBusy("");
    }
  }

  async function documentAction(action: "unpublish" | "revise" | "delete", document: PublishedDocument) {
    if (action === "delete" && !window.confirm(`Permanently delete “${document.title}”?`)) return;
    setBusy(`${action}:${document.docId}`); setError(""); setNotice("");
    try {
      if (action === "delete") await requestJson(`/api/admin/documents/${document.docId}`, { method: "DELETE" });
      else {
        const payload = await requestJson(`/api/admin/documents/${document.docId}/${action}`, { method: "POST" });
        if (action === "revise" && payload.draft) { setSelected(payload.draft); setTab("drafts"); setStep(1); }
      }
      setNotice(action === "unpublish" ? "Document removed from public retrieval." : action === "revise" ? "Revision draft created." : "Document permanently deleted.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The action failed.");
    } finally { setBusy(""); }
  }

  async function createSpace() {
    if (!newSpaceName.trim()) return;
    setBusy("space:create"); setError("");
    try {
      const payload = await requestJson("/api/admin/spaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newSpaceName, description: newSpaceDescription }),
      });
      setNewSpaceName(""); setNewSpaceDescription(""); setUploadSpaceId(payload.space.spaceId);
      setNotice(`Knowledge space “${payload.space.name}” created.`);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create the knowledge space.");
    } finally { setBusy(""); }
  }

  async function updateSpace(space: KnowledgeSpace, patch: { name?: string; status?: "active" | "archived" }) {
    setBusy(`space:${space.spaceId}`); setError("");
    try {
      await requestJson(`/api/admin/spaces/${space.spaceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      setNotice(patch.name ? "Knowledge space renamed." : patch.status === "archived" ? "Knowledge space archived and removed from public retrieval." : "Knowledge space restored.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update the knowledge space.");
    } finally { setBusy(""); }
  }

  async function moveDocument(document: PublishedDocument, spaceId: string) {
    setBusy(`move:${document.docId}`); setError("");
    try {
      await requestJson(`/api/admin/documents/${document.docId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spaceId }),
      });
      setNotice("Document moved without regenerating embeddings.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to move the document.");
    } finally { setBusy(""); }
  }

  async function previewReset() {
    setBusy("reset:preview"); setError(""); setNotice("");
    try {
      const payload = await requestJson("/api/admin/reset/preview", { method: "POST" });
      setResetPreview(payload);
      setResetBackupFingerprint("");
      setResetConfirmation("");
      setNotice("Reset scope inspected. Download a fresh backup before reset is enabled.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to inspect the reset scope.");
    } finally { setBusy(""); }
  }

  async function downloadResetBackup() {
    setBusy("reset:backup"); setError(""); setNotice("");
    try {
      const response = await fetch("/api/admin/export?scope=reset", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `Backup failed (${response.status})`);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `portfolio-reset-backup-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setResetPreview({ fingerprint: payload.fingerprint, snapshot: payload.snapshot });
      setResetBackupFingerprint(payload.fingerprint);
      setNotice("Backup downloaded. Verify the file is available locally before entering the confirmation phrase.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to download the reset backup.");
    } finally { setBusy(""); }
  }

  async function executeReset() {
    if (!resetPreview || resetBackupFingerprint !== resetPreview.fingerprint) return;
    setBusy("reset:execute"); setError(""); setNotice("");
    try {
      await requestJson("/api/admin/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmation: resetConfirmation,
          fingerprint: resetBackupFingerprint,
        }),
      });
      setSelected(null);
      setResetPreview(null);
      setResetBackupFingerprint("");
      setResetConfirmation("");
      setTab("drafts");
      setNotice("Public knowledge reset completed. Portfolio is now the only empty knowledge space.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Public knowledge reset failed.");
    } finally { setBusy(""); }
  }

  const visibleDocuments = documents.filter((document) => tab === "archived" ? document.status === "archived" : document.status === "published");
  const previewChunks = chunksForPreviewView(selected?.preview, previewView);
  const projectGroupCount = new Set(
    selected?.preview?.parents
      .filter((chunk) => chunk.sectionType === "project")
      .map((chunk) => chunk.semanticGroupId || chunk.parentChunkId) || [],
  ).size;

  return <div className="studioFrame">
    <header className="studioHeader"><div><span className="eyebrow">OWNER PUBLISHING</span><h1>Publish Studio</h1><p>Prepare public evidence without retaining the original uploaded file.</p></div><div className="studioHeaderActions"><a className="secondaryButton compactButton" href="/api/admin/export"><Download size={16}/>Export JSON</a><button className="iconButton" title="Refresh workspace" aria-label="Refresh workspace" onClick={() => void refresh()}><RefreshCw className={busy === "refresh" ? "spin" : ""} size={18}/></button></div></header>
    {notice ? <div className="successBanner"><Check size={17}/>{notice}</div> : null}
    {error ? <div className="errorBanner">{error}</div> : null}
    <div className="studioLayout">
      <aside className="studioSidebar">
        <input ref={inputRef} className="srOnly" type="file" multiple accept=".pdf,.docx,.md,.markdown,.txt,.csv" onChange={(event) => void uploadFiles(event.target.files)}/>
        <label className="fieldLabel sidebarSpaceSelect">Upload target
          <select value={uploadSpaceId} onChange={(event) => setUploadSpaceId(event.target.value)}>
            {spaces.filter((space) => space.status === "active").map((space) => <option value={space.spaceId} key={space.spaceId}>{space.name}</option>)}
          </select>
        </label>
        <button className="primaryButton uploadButton" onClick={() => inputRef.current?.click()} disabled={Boolean(busy)}>{busy === "upload" ? <LoaderCircle className="spin" size={17}/> : <Upload size={17}/>}Upload public candidates</button>
        <p className="uploadNote">PDF, DOCX, MD, TXT, CSV · 4 MB each<br/>Original files are discarded after parsing.</p>
        <details className="spaceManager">
          <summary>Manage knowledge spaces <span>{spaces.filter((space) => space.status === "active").length}</span></summary>
          <div className="spaceCreateForm"><input value={newSpaceName} onChange={(event) => setNewSpaceName(event.target.value)} placeholder="Space name" maxLength={80}/><input value={newSpaceDescription} onChange={(event) => setNewSpaceDescription(event.target.value)} placeholder="Short description" maxLength={300}/><button className="secondaryButton compactButton" disabled={!newSpaceName.trim() || Boolean(busy)} onClick={() => void createSpace()}><Plus size={15}/>Create</button></div>
          <div className="ownerSpaceList">{spaces.map((space) => <div key={space.spaceId} className="ownerSpaceItem"><span><strong>{space.name}</strong><small>{space.documentCount} documents · {space.status}</small></span><div><button title="Rename space" aria-label={`Rename ${space.name}`} onClick={() => { const name = window.prompt("Knowledge space name", space.name); if (name?.trim() && name.trim() !== space.name) void updateSpace(space, { name }); }}><Pencil size={14}/></button>{space.status === "active" ? <button title="Archive space" aria-label={`Archive ${space.name}`} disabled={space.spaceId === "portfolio"} onClick={() => void updateSpace(space, { status: "archived" })}><Archive size={14}/></button> : <button title="Restore space" aria-label={`Restore ${space.name}`} onClick={() => void updateSpace(space, { status: "active" })}><RotateCcw size={14}/></button>}</div></div>)}</div>
        </details>
        <div className="studioTabs" role="tablist">
          <button className={tab === "drafts" ? "selected" : ""} onClick={() => setTab("drafts")}>Drafts <span>{drafts.filter((item) => item.status !== "published").length}</span></button>
          <button className={tab === "published" ? "selected" : ""} onClick={() => setTab("published")}>Published <span>{documents.filter((item) => item.status === "published").length}</span></button>
          <button className={tab === "archived" ? "selected" : ""} onClick={() => setTab("archived")}>Archived <span>{documents.filter((item) => item.status === "archived").length}</span></button>
        </div>
        <div className="studioList">{tab === "drafts" ? drafts.filter((item) => item.status !== "published").map((draft) => <button key={draft.draftId} className={selected?.draftId === draft.draftId ? "studioListItem selected" : "studioListItem"} onClick={() => { setSelected(draft); setStep(0); }}><FileText size={17}/><span><strong>{draft.title}</strong><small>{spaces.find((space) => space.spaceId === draft.spaceId)?.name || draft.spaceId} · {draft.status} · {draft.fileType.toUpperCase()}</small></span><ChevronRight size={15}/></button>) : visibleDocuments.map((document) => <div className="publishedListItem" key={document.docId}><span><strong>{document.title}</strong><small>v{document.publicationVersion} · {document.status}</small><select aria-label={`Move ${document.title} to knowledge space`} value={document.spaceId} disabled={document.status !== "published" || busy === `move:${document.docId}`} onChange={(event) => void moveDocument(document, event.target.value)}>{spaces.filter((space) => space.status === "active").map((space) => <option key={space.spaceId} value={space.spaceId}>{space.name}</option>)}</select></span><div><button title="Create revision" aria-label="Create revision" onClick={() => void documentAction("revise", document)}><RotateCcw size={15}/></button>{document.status === "published" ? <button title="Unpublish" aria-label="Unpublish" onClick={() => void documentAction("unpublish", document)}><Archive size={15}/></button> : null}<button title="Permanently delete" aria-label="Permanently delete" onClick={() => void documentAction("delete", document)}><Trash2 size={15}/></button></div></div>)}</div>
      </aside>
      <section className="studioWorkspace">
        {!selected ? <div className="studioEmpty"><Upload size={26}/><h2>Select a draft or upload a document</h2><p>Every upload becomes an expiring draft. Nothing enters public retrieval until the final confirmation.</p></div> : <>
          <div className="stepper" aria-label="Publishing steps">{steps.map((label, index) => <button key={label} className={step === index ? "active" : step > index ? "complete" : ""} onClick={() => setStep(index)}><span>{step > index ? <Check size={14}/> : index + 1}</span>{label}</button>)}</div>
          {step === 0 ? <div className="studioPane"><div className="paneHeading"><div><span className="eyebrow">STEP 1</span><h2>Upload & parse</h2></div><span className="statusBadge">Parsed</span></div><dl className="fileFacts"><div><dt>File</dt><dd>{selected.fileName}</dd></div><div><dt>Type</dt><dd>{selected.fileType.toUpperCase()}</dd></div><div><dt>Size</dt><dd>{Math.max(1, Math.round(selected.sizeBytes / 1024))} KB</dd></div><div><dt>Retention</dt><dd>Text draft expires in 7 days</dd></div></dl><label className="fieldLabel">Parsed text<textarea value={selected.parsedBody} readOnly rows={16}/></label><div className="paneActions"><button className="primaryButton" onClick={() => setStep(1)}>Continue <ChevronRight size={16}/></button></div></div> : null}
          {step === 1 ? <div className="studioPane"><div className="paneHeading"><div><span className="eyebrow">STEP 2</span><h2>Clean & inspect</h2></div>{selected.piiFindings.length ? <span className="dangerBadge"><ShieldAlert size={14}/>{selected.piiFindings.length} PII finding(s)</span> : <span className="statusBadge"><Check size={14}/>PII clear</span>}</div><div className="fieldGrid"><label className="fieldLabel">Title<input value={selected.title} onChange={(event) => update("title", event.target.value)}/></label><label className="fieldLabel">Knowledge space<select value={selected.spaceId} onChange={(event) => update("spaceId", event.target.value)}>{spaces.filter((space) => space.status === "active").map((space) => <option key={space.spaceId} value={space.spaceId}>{space.name}</option>)}</select></label><label className="fieldLabel">Category<input value={selected.category} onChange={(event) => update("category", event.target.value)}/></label><label className="fieldLabel">Language<select value={selected.language} onChange={(event) => update("language", event.target.value as "zh" | "en")}><option value="zh">中文</option><option value="en">English</option></select></label><label className="fieldLabel wide">Summary<textarea rows={3} value={selected.summary} onChange={(event) => update("summary", event.target.value)}/></label><label className="fieldLabel">Public source URL<input type="url" value={selected.sourceUrl} onChange={(event) => update("sourceUrl", event.target.value)}/></label></div>{selected.piiFindings.length ? <div className="piiPanel"><ShieldAlert size={19}/><div><strong>Publishing is blocked</strong><p>Remove the detected {selected.piiFindings.map((item) => item.label).join(", ")} from the clean text, then run the check again. Detected values are not shown in errors or logs.</p></div></div> : null}<label className="fieldLabel">Clean public text<textarea rows={18} value={selected.cleanedBody} onChange={(event) => update("cleanedBody", event.target.value)}/></label><div className="paneActions"><button className="secondaryButton" onClick={() => void saveDraft().then(() => setNotice("Draft saved. Preview must be regenerated."))}>Save draft</button><button className="primaryButton" onClick={() => { void previewDraft().then(() => setStep(2)).catch((cause) => setError(cause instanceof Error ? cause.message : "Preview failed.")); }}>Run PII check & preview <Eye size={16}/></button></div></div> : null}
          {step === 2 ? <div className="studioPane"><div className="paneHeading"><div><span className="eyebrow">STEP 3</span><h2>Chunk configuration</h2></div><span className="statusBadge">{selected.preview?.children.length || 0} retrieval chunks</span></div><div className="profileGrid"><label className="fieldLabel">Mode<select value={selected.processingProfile.chunkMode} onChange={(event) => updateProfile("chunkMode", event.target.value as ProcessingProfile["chunkMode"])}><option value="standard">Standard</option><option value="parent_child">Parent-child</option><option value="resume_semantic">Resume semantic</option></select></label><label className="fieldLabel">Delimiter<input value={selected.processingProfile.delimiter.replace(/\n/g, "\\n")} onChange={(event) => updateProfile("delimiter", event.target.value.replace(/\\n/g, "\n"))}/></label><label className="fieldLabel">Child max tokens<input type="number" min={50} max={1000} value={selected.processingProfile.childMaxTokens} onChange={(event) => updateProfile("childMaxTokens", Number(event.target.value))}/></label><label className="fieldLabel">Child overlap<input type="number" min={0} max={Math.floor(selected.processingProfile.childMaxTokens * .25)} value={selected.processingProfile.childOverlapTokens} onChange={(event) => updateProfile("childOverlapTokens", Number(event.target.value))}/></label><label className="fieldLabel">Parent max tokens<input type="number" min={selected.processingProfile.childMaxTokens} max={2000} value={selected.processingProfile.parentMaxTokens} onChange={(event) => updateProfile("parentMaxTokens", Number(event.target.value))}/></label></div><div className="checkRow"><label><input type="checkbox" checked={selected.processingProfile.normalizeWhitespace} onChange={(event) => updateProfile("normalizeWhitespace", event.target.checked)}/>Normalize whitespace</label><label><input type="checkbox" checked={selected.processingProfile.removeUrls} onChange={(event) => updateProfile("removeUrls", event.target.checked)}/>Remove URLs</label><label><input type="checkbox" checked={selected.processingProfile.removeEmails} onChange={(event) => updateProfile("removeEmails", event.target.checked)}/>Remove emails</label></div><div className="previewMetrics"><div><strong>{selected.preview?.parents.length || 0}</strong><span>answer parents</span></div><div><strong>{projectGroupCount}</strong><span>project groups</span></div><div><strong>{selected.preview?.children.length || 0}</strong><span>retrieval children</span></div><div><strong>{selected.preview?.averageChildTokens || 0}</strong><span>avg. child tokens</span></div></div><div className="chunkPreviewToolbar"><div className="segmented" aria-label="Chunk preview type"><button className={previewView === "children" ? "selected" : ""} onClick={() => setPreviewView("children")}>Retrieval children</button><button className={previewView === "parents" ? "selected" : ""} onClick={() => setPreviewView("parents")}>Answer parents</button></div><span>Showing all {previewChunks.length} {previewView}</span></div><div className="chunkPreview">{previewChunks.map((chunk, index) => <details key={chunk.chunkId}><summary><span>#{index + 1}</span><strong>{chunk.sectionType} · {chunk.entityTitle || chunk.sectionPath}</strong><small>{chunk.tokenCount} tokens · {chunk.charCount} chars</small></summary><div>{previewView === "children" ? <><h3>Matched child</h3><p>{chunk.rawBody}</p><h3>Returned parent</h3><p>{chunk.parentBody}</p></> : <><h3>Answer parent</h3><p>{chunk.rawBody}</p></>}</div></details>)}</div><div className="paneActions"><button className="secondaryButton" onClick={() => void previewDraft().catch((cause) => setError(cause instanceof Error ? cause.message : "Preview failed."))}>{busy === "preview" ? <LoaderCircle className="spin" size={16}/> : <RefreshCw size={16}/>}Regenerate preview</button><button className="primaryButton" onClick={() => setStep(3)}>Review publication <ChevronRight size={16}/></button></div></div> : null}
          {step === 3 ? <div className="studioPane"><div className="paneHeading"><div><span className="eyebrow">STEP 4</span><h2>Publish confirmation</h2></div></div><div className="publishChecklist"><div className={selected.piiFindings.length ? "blocked" : "ok"}>{selected.piiFindings.length ? <ShieldAlert/> : <Check/>}<span><strong>PII gate</strong><small>{selected.piiFindings.length ? "Blocked until clean text is edited" : "No blocking PII detected"}</small></span></div><div className={selected.preview?.children.length ? "ok" : "blocked"}>{selected.preview?.children.length ? <Check/> : <ShieldAlert/>}<span><strong>Chunk preview</strong><small>{selected.preview?.children.length || 0} child chunks · {selected.preview?.parents.length || 0} parent contexts</small></span></div><div className="ok"><Check/><span><strong>Public boundary</strong><small>Only cleaned text and embeddings will be stored in public Atlas collections</small></span></div></div>{selected.failureCode === "free_quota_unavailable" ? <div className="quotaBanner">Embedding provider quota is currently unavailable. Your draft is intact; retry later without uploading again.</div> : null}<div className="publishSummary"><h3>{selected.title}</h3><p>{selected.summary || "No public summary yet."}</p><span>{spaces.find((space) => space.spaceId === selected.spaceId)?.name || selected.spaceId} · {selected.category} · {selected.language.toUpperCase()} · version {selected.publicationVersion}</span></div><div className="paneActions"><button className="secondaryButton" onClick={() => setStep(2)}>Back to preview</button><button className="primaryButton" disabled={Boolean(busy) || Boolean(selected.piiFindings.length) || !selected.preview?.children.length} onClick={() => void publish()}>{busy === "publish" ? <LoaderCircle className="spin" size={16}/> : <Send size={16}/>}Publish to public RAG</button></div></div> : null}
        </>}
      </section>
    </div>
    <section className="studioDangerZone" aria-labelledby="cloud-reset-heading">
      <div className="dangerZoneHeading"><AlertTriangle size={20}/><div><span className="eyebrow">OWNER ONLY</span><h2 id="cloud-reset-heading">Danger Zone</h2><p>Back up and remove all public drafts, documents, searchable chunks, and non-Portfolio spaces. Atlas, indexes, Clerk, Vercel, and environment variables are kept.</p></div></div>
      <div className="dangerZoneActions">
        <button className="secondaryButton" disabled={Boolean(busy)} onClick={() => void previewReset()}>{busy === "reset:preview" ? <LoaderCircle className="spin" size={16}/> : <Eye size={16}/>}Preview reset</button>
        <button className="secondaryButton" disabled={!resetPreview || Boolean(busy)} onClick={() => void downloadResetBackup()}>{busy === "reset:backup" ? <LoaderCircle className="spin" size={16}/> : <Download size={16}/>}Download reset backup</button>
      </div>
      {resetPreview ? <>
        <dl className="resetSnapshot"><div><dt>Spaces</dt><dd>{resetPreview.snapshot.spaces}</dd></div><div><dt>Drafts</dt><dd>{resetPreview.snapshot.drafts}</dd></div><div><dt>Documents</dt><dd>{resetPreview.snapshot.documents}</dd></div><div><dt>Chunks</dt><dd>{resetPreview.snapshot.chunks}</dd></div><div><dt>Metadata</dt><dd>{resetPreview.snapshot.metadata}</dd></div></dl>
        <label className="fieldLabel resetConfirmation">Type <code>RESET PORTFOLIO</code> after confirming the backup downloaded<input value={resetConfirmation} onChange={(event) => setResetConfirmation(event.target.value)} autoComplete="off"/></label>
        <button className="dangerButton" disabled={Boolean(busy) || resetBackupFingerprint !== resetPreview.fingerprint || resetConfirmation !== "RESET PORTFOLIO"} onClick={() => void executeReset()}>{busy === "reset:execute" ? <LoaderCircle className="spin" size={16}/> : <Trash2 size={16}/>}Reset public knowledge</button>
      </> : null}
    </section>
  </div>;
}
