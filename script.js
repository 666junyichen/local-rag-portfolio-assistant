const translations = {
  en: {
    brandSubtitle: "Junyi Chen project showcase",
    navArchitecture: "Architecture",
    navDemo: "Demo",
    navRun: "Run locally",
    heroEyebrow: "Fully local RAG portfolio demo",
    heroTitle: "A private AI assistant that answers questions about my portfolio.",
    heroLede:
      "This project turns a Google and MongoDB local RAG workshop into a recruiter-friendly portfolio assistant. It retrieves curated resume and project facts from MongoDB Vector Search, then answers with a local Ollama-hosted Gemma model.",
    viewGithub: "View GitHub repo",
    viewDemo: "View screenshots",
    metricLocal: "local runtime",
    metricDocs: "curated knowledge entries",
    metricStack: "core RAG components",
    architectureEyebrow: "How it works",
    architectureTitle: "Local RAG architecture with a public showcase layer.",
    stepOneTitle: "Curated portfolio data",
    stepOneText: "Resume-safe facts live in data/portfolio_docs.json, not in private folders or certificates.",
    stepTwoTitle: "Local embeddings",
    stepTwoText: "voyage-4-nano embeddings are generated locally through SentenceTransformers.",
    stepThreeTitle: "MongoDB Vector Search",
    stepThreeText: "MongoDB Local Atlas stores chunks and retrieves the most relevant portfolio context.",
    stepFourTitle: "Ollama Gemma answer",
    stepFourText: "A local Gemma model generates a grounded answer for the Streamlit chat UI.",
    demoEyebrow: "Demo preview",
    demoTitle: "The deployed page explains the project; the AI assistant runs locally.",
    demoText:
      "Vercel hosts this bilingual showcase. The private RAG assistant stays local because it depends on Docker, MongoDB Local Atlas, and Ollama.",
    homeCaption: "Home screen with example recruiter questions.",
    answerCaption: "Generated answer grounded in the portfolio knowledge base.",
    runEyebrow: "Run locally",
    runTitle: "Reproduce the RAG assistant on your machine.",
    resumeTitle: "Resume-ready impact",
    resumeText:
      "Built a fully local RAG portfolio assistant using MongoDB Atlas Vector Search, local embeddings, Ollama-hosted Gemma, ingestion scripts, smoke tests, and a Streamlit chat UI.",
    footerText: "Built as a local-first AI portfolio project by Junyi Chen.",
  },
  zh: {
    brandSubtitle: "Junyi Chen 项目展示页",
    navArchitecture: "架构",
    navDemo: "演示",
    navRun: "本地运行",
    heroEyebrow: "全本地 RAG 简历项目",
    heroTitle: "一个可以回答我项目经历的私有 AI assistant。",
    heroLede:
      "这个项目把 Google 和 MongoDB 的本地 RAG workshop 改造成一个适合招聘展示的 portfolio assistant。它从 MongoDB Vector Search 检索精选简历和项目事实，再用本地 Ollama Gemma 模型生成回答。",
    viewGithub: "查看 GitHub 仓库",
    viewDemo: "查看截图",
    metricLocal: "本地运行",
    metricDocs: "精选知识条目",
    metricStack: "核心 RAG 组件",
    architectureEyebrow: "工作方式",
    architectureTitle: "本地 RAG 架构，加一个可公开部署的展示层。",
    stepOneTitle: "精选 portfolio 数据",
    stepOneText: "适合公开展示的简历事实放在 data/portfolio_docs.json，不上传私人文件、证书或敏感材料。",
    stepTwoTitle: "本地 embedding",
    stepTwoText: "通过 SentenceTransformers 在本地生成 voyage-4-nano embeddings。",
    stepThreeTitle: "MongoDB Vector Search",
    stepThreeText: "MongoDB Local Atlas 保存文本 chunks，并检索最相关的 portfolio 上下文。",
    stepFourTitle: "Ollama Gemma 回答",
    stepFourText: "本地 Gemma 模型基于检索结果生成回答，并在 Streamlit chat UI 中展示。",
    demoEyebrow: "演示预览",
    demoTitle: "Vercel 页面负责展示项目；真正的 AI assistant 保持本地运行。",
    demoText:
      "Vercel 部署的是这个中英文展示页。私有 RAG assistant 仍然在本地运行，因为它依赖 Docker、MongoDB Local Atlas 和 Ollama。",
    homeCaption: "首页展示适合 recruiter 提问的示例问题。",
    answerCaption: "回答基于 portfolio knowledge base 检索生成。",
    runEyebrow: "本地运行",
    runTitle: "在你的电脑上复现这个 RAG assistant。",
    resumeTitle: "可以写进简历的项目价值",
    resumeText:
      "构建了一个全本地 RAG portfolio assistant，使用 MongoDB Atlas Vector Search、本地 embeddings、Ollama Gemma、数据导入脚本、smoke test 和 Streamlit chat UI。",
    footerText: "Junyi Chen 构建的 local-first AI portfolio 项目。",
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
      node.textContent = dictionary[key];
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
