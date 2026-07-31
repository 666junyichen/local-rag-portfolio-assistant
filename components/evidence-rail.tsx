import { CheckCircle2, Cloud, Database, LockKeyhole } from "lucide-react";
import type { Source } from "@/lib/cloud-rag/types";
import { SourceList } from "./source-list";

export function EvidenceRail({ sources }: { sources: Source[] }) {
  return <aside className="evidenceRail">
    <section className="railSection">
      <div className="sectionLabel"><CheckCircle2 size={16}/> Answer evidence</div>
      <SourceList sources={sources} compact/>
    </section>
    <section className="railSection runtimeFacts">
      <div className="sectionLabel"><Cloud size={16}/> Cloud runtime</div>
      <p><Database size={15}/> MongoDB Atlas Vector Search</p>
      <p><span className="geminiDot"/> Gemini embedding + generation</p>
      <p><LockKeyhole size={15}/> Public portfolio documents only</p>
    </section>
  </aside>;
}
