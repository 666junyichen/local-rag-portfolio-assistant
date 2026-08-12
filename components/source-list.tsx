import { ExternalLink, FileText } from "lucide-react";
import type { Source } from "@/lib/cloud-rag/types";

export function SourceList({
  sources,
  compact = false,
  showMatchedSnippet = false,
}: {
  sources: Source[];
  compact?: boolean;
  showMatchedSnippet?: boolean;
}) {
  if (!sources.length) return <div className="emptyEvidence">No sources retrieved yet.</div>;
  return <div className="sourceList">{sources.map((source, index) => (
    <details className="sourceItem" key={source.chunkId || `${source.docId}-${index}`} open={!compact && index === 0}>
      <summary>
        <span className="sourceIndex">{index + 1}</span>
        <span className="sourceTitle">
          <strong>{source.entityTitle || source.title}</strong>
          <small><span className="spaceBadge">{source.spaceName}</span>{source.sectionType || source.category} · {source.score.toFixed(3)}</small>
        </span>
        <FileText size={16}/>
      </summary>
      <p>{showMatchedSnippet ? source.matchedSnippet || source.snippet : source.snippet}</p>
      {source.retrievalChannels?.length ? <small>
        Channels: {source.retrievalChannels.join(" + ")}
        {source.vectorRank ? ` · vector #${source.vectorRank}` : ""}
        {source.bm25Rank ? ` · BM25 #${source.bm25Rank}` : ""}
      </small> : null}
      {source.url && <a href={source.url} target="_blank" rel="noreferrer">Open evidence <ExternalLink size={13}/></a>}
    </details>
  ))}</div>;
}
