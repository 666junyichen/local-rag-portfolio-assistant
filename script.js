const translations = {
  en: {
    brandSubtitle: "Junyi Chen AI portfolio project",
    navArchitecture: "Architecture",
    navChat: "Ask AI",
    navDemo: "Evidence",
    navRun: "Implementation",
    heroEyebrow: "Local-first RAG assistant / Portfolio Q&A",
    heroTitle: "A local RAG assistant that answers recruiter questions from a curated portfolio knowledge base.",
    heroLede:
      "This project adapts a Google and MongoDB local RAG workshop into a portfolio-focused AI assistant. It ingests structured resume and project facts, retrieves relevant context with MongoDB Vector Search, and generates grounded answers through a local Ollama-hosted LLM.",
    viewGithub: "View GitHub repo",
    viewDemo: "View evidence screenshots",
    metricLocal: "local-first runtime",
    metricDocs: "portfolio knowledge entries",
    metricStack: "RAG pipeline stages",
    architectureEyebrow: "System design",
    architectureTitle: "A recruiter-facing showcase for a private local RAG system.",
    stepOneTitle: "Curated knowledge base",
    stepOneText: "27 resume-safe project, internship, skill, and portfolio facts are stored in data/portfolio_docs.json.",
    stepTwoTitle: "Embedding generation",
    stepTwoText: "SentenceTransformer creates local embeddings for each chunk before indexing.",
    stepThreeTitle: "MongoDB Vector Search",
    stepThreeText: "MongoDB Local Atlas stores embedded chunks and retrieves the most relevant portfolio context for each question.",
    stepFourTitle: "Grounded LLM answer",
    stepFourText: "An Ollama-hosted local model answers from retrieved context and displays the response in a Streamlit chat UI.",
    chatEyebrow: "Online RAG demo",
    chatTitle: "Ask the portfolio assistant a recruiter-style question.",
    chatText:
      "This chat panel is designed for the cloud version: Vercel calls a serverless API, retrieves context from MongoDB Atlas Vector Search, and uses a cloud LLM to answer from Junyi's curated portfolio knowledge base.",
    sampleQuestionOne: "Strongest AI/data projects?",
    sampleQuestionTwo: "MongoDB and RAG experience?",
    sampleQuestionThree: "Chinese role-fit summary",
    chatWelcome: "Ask about Junyi's projects, AI/RAG experience, MongoDB work, internships, or portfolio evidence.",
    chatPlaceholder: "Ask a recruiter-style question about Junyi's portfolio...",
    chatSubmit: "Ask",
    chatStatus: "Cloud RAG needs MongoDB Atlas and a cloud LLM key to answer online.",
    demoEyebrow: "Evidence preview",
    demoTitle: "The public page shows the system, screenshots, and workflow; the interactive assistant runs locally.",
    demoText:
      "The deployed Vercel page is a stable portfolio showcase. The live RAG chat is intentionally local because the current version depends on local MongoDB, local embeddings, and Ollama rather than a cloud LLM service.",
    homeCaption: "Streamlit entry screen with recruiter-style example questions.",
    answerCaption: "Generated answer grounded in the curated portfolio knowledge base.",
    runEyebrow: "Implementation proof",
    runTitle: "The project includes reproducible setup, ingestion, smoke test, and Streamlit chat commands.",
    resumeTitle: "Project value for reviewers",
    resumeText:
      "This project demonstrates an end-to-end RAG workflow: document curation, chunking, embedding generation, vector indexing, semantic retrieval, prompt assembly, local LLM response generation, chat history storage, smoke testing, and a bilingual Streamlit UI.",
    footerText: "Local-first RAG portfolio assistant by Junyi Chen.",
  },
  zh: {
    brandSubtitle: "Junyi Chen AI 作品集项目",
    navArchitecture: "系统架构",
    navChat: "在线问答",
    navDemo: "项目证据",
    navRun: "实现方式",
    heroEyebrow: "本地优先 RAG assistant / 作品集问答",
    heroTitle: "一个基于作品集知识库回答招聘方问题的本地 RAG assistant。",
    heroLede:
      "该项目将 Google 与 MongoDB 的本地 RAG workshop 改造成面向作品集展示的 AI assistant。系统读取结构化简历与项目事实，使用 MongoDB Vector Search 检索相关上下文，并通过本地 Ollama LLM 生成有依据的回答。",
    viewGithub: "查看 GitHub 仓库",
    viewDemo: "查看项目截图",
    metricLocal: "本地优先运行",
    metricDocs: "作品集知识条目",
    metricStack: "RAG 流程阶段",
    architectureEyebrow: "系统设计",
    architectureTitle: "面向招聘方展示的私有本地 RAG 系统。",
    stepOneTitle: "结构化知识库",
    stepOneText: "整理 27 条可公开展示的项目、实习、技能和作品集事实，存储在 data/portfolio_docs.json。",
    stepTwoTitle: "Embedding 生成",
    stepTwoText: "使用 SentenceTransformer 为文本 chunks 生成本地 embeddings，并用于后续索引。",
    stepThreeTitle: "MongoDB Vector Search",
    stepThreeText: "MongoDB Local Atlas 存储向量化 chunks，并根据用户问题检索最相关的作品集上下文。",
    stepFourTitle: "基于上下文的 LLM 回答",
    stepFourText: "本地 Ollama 模型基于检索结果生成回答，并通过 Streamlit chat UI 展示。",
    chatEyebrow: "在线 RAG Demo",
    chatTitle: "向作品集 assistant 提一个招聘方会问的问题。",
    chatText:
      "这个聊天区是为云端版本设计的：Vercel 调用 serverless API，从 MongoDB Atlas Vector Search 检索上下文，并使用云端 LLM 基于 Junyi 的作品集知识库生成回答。",
    sampleQuestionOne: "最强 AI/数据项目？",
    sampleQuestionTwo: "MongoDB 和 RAG 经验？",
    sampleQuestionThree: "中文总结岗位匹配度",
    chatWelcome: "可以询问 Junyi 的项目、AI/RAG 经验、MongoDB 实践、实习经历或作品集证据。",
    chatPlaceholder: "请输入一个招聘方视角的问题...",
    chatSubmit: "提问",
    chatStatus: "云端 RAG 需要配置 MongoDB Atlas 和云端 LLM key 后才能在线回答。",
    demoEyebrow: "项目证据预览",
    demoTitle: "公开页面展示系统、截图和流程；真正的交互式 assistant 当前在本地运行。",
    demoText:
      "Vercel 页面用于稳定展示项目成果。当前版本的 RAG chat 依赖本地 MongoDB、本地 embeddings 和 Ollama，因此没有直接把私有本地服务暴露到公网。",
    homeCaption: "Streamlit 首页展示适合招聘方提问的示例问题。",
    answerCaption: "回答基于作品集知识库检索结果生成。",
    runEyebrow: "实现证据",
    runTitle: "项目包含可复现的环境配置、数据导入、smoke test 和 Streamlit chat 运行命令。",
    resumeTitle: "给评审者看的项目价值",
    resumeText:
      "该项目展示了完整 RAG 链路能力：文档整理、文本切分、embedding 生成、向量索引、语义检索、Prompt 组装、本地 LLM 回答生成、chat history 存储、smoke test 与中英文 Streamlit UI。",
    footerText: "Junyi Chen 构建的本地优先 RAG 作品集助手。",
  },
};

const languageButtons = document.querySelectorAll(".lang-button");
const translatableNodes = document.querySelectorAll("[data-i18n]");

function setLanguage(language) {
  const dictionary = translations[language] || translations.en;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";

  translatableNodes.forEach((node) => {
    const key = node.dataset.i18n;
    if (dictionary[key]) {
      if (node.dataset.i18nPlaceholder !== undefined) {
        node.setAttribute("placeholder", dictionary[key]);
      } else {
        node.textContent = dictionary[key];
      }
    }
  });

  languageButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.lang === language);
  });

  localStorage.setItem("preferred-language", language);
}

languageButtons.forEach((button) => {
  button.addEventListener("click", () => setLanguage(button.dataset.lang));
});

const savedLanguage = localStorage.getItem("preferred-language");
const requestedLanguage = new URLSearchParams(window.location.search).get("lang");
setLanguage(requestedLanguage === "zh" || requestedLanguage === "en" ? requestedLanguage : savedLanguage || "en");