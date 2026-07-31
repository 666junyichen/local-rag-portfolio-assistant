import { ExternalLink, FileText } from "lucide-react";
import type { Source } from "@/lib/cloud-rag/types";

export function SourceList({ sources, compact = false }: { sources: Source[]; compact?: boolean }) {
  if (!sources.length) return <div className="emptyEvidence">No sources retrieved yet.</div>;
  return <div className="sourceList">{sources.map((source, index) => (
    <details className="sourceItem" key={source.chunkId || `${source.docId}-${index}`} open={!compact && index === 0}>
      <summary>
        <span className="sourceIndex">{index + 1}</span>
        <span className="sourceTitle"><strong>{source.title}</strong><small>{source.category} · {source.score.toFixed(3)}</small></span>
        <FileText size={16}/>
      </summary>
      <p>{source.snippet}</p>
      {source.url && <a href={source.url} target="_blank" rel="noreferrer">Open evidence <ExternalLink size={13}/></a>}
    </details>
  ))}</div>;
}
