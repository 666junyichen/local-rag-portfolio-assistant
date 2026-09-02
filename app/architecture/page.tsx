import Image from "next/image";
import { ArrowRight, CheckCircle2, Cloud, Database, HardDrive, LockKeyhole } from "lucide-react";

export default function ArchitecturePage() {
  return <div className="pageFrame">
    <div className="pageHeading"><span className="eyebrow">ARCHITECTURE & EVIDENCE</span><h1>One repository, two privacy boundaries</h1><p>本地模式处理完整私有资料；云端 Demo 只检索人工确认的公开 portfolio 摘要。</p></div>
    <div className="modeGrid">
      <section className="modePanel"><div className="modeIcon local"><HardDrive size={20}/></div><h2>Local private mode</h2><p>Streamlit 与本地服务组成完整 Knowledge Studio、Retrieval Lab 和 Chat。</p><div className="flow"><span>Private files</span><ArrowRight/><span>SentenceTransformers</span><ArrowRight/><span>MongoDB Local Atlas</span><ArrowRight/><span>Ollama</span></div><ul><li><CheckCircle2/>Upload and chunk preview</li><li><CheckCircle2/>Public + private retrieval</li><li><LockKeyhole/>Data stays on the machine</li></ul></section>
      <section className="modePanel"><div className="modeIcon cloud"><Cloud size={20}/></div><h2>Cloud public mode</h2><p>Next.js 和 Vercel Functions 为招聘者提供可分享、可验证的公开问答。</p><div className="flow"><span>Curated JSON</span><ArrowRight/><span>OpenAI embeddings</span><ArrowRight/><span>Atlas Vector + BM25</span><ArrowRight/><span>OpenAI Luna</span></div><ul><li><CheckCircle2/>Streaming chat and citations</li><li><CheckCircle2/>Read-only Retrieval Lab</li><li><Database/>Public collection is isolated</li></ul></section>
    </div>
    <section className="privacyBand"><LockKeyhole size={22}/><div><h2>Privacy boundary</h2><p><code>portfolio_knowledge_local</code> and <code>portfolio_knowledge_public</code> are separate collections with separate embedding models and indexes. Private uploads are Git ignored and rejected by the cloud seed script.</p></div></section>
    <div className="evidenceShots"><figure><Image src="/streamlit-home.png" alt="Local Streamlit portfolio chat" width={1400} height={800}/><figcaption>Local bilingual Chat with retrieved sources</figcaption></figure><figure><Image src="/streamlit-answer.png" alt="Local RAG answer and evidence" width={1400} height={800}/><figcaption>Verified local answer flow</figcaption></figure></div>
  </div>;
}
