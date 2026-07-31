const chatForm = document.querySelector("[data-chat-form]");
const chatInput = document.querySelector("[data-chat-input]");
const chatLog = document.querySelector("[data-chat-log]");
const chatStatus = document.querySelector("[data-chat-status]");
const questionButtons = document.querySelectorAll("[data-question]");
const chatHistory = [];

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function appendMessage(role, content, sources = []) {
  if (!chatLog) return;
  const item = document.createElement("article");
  item.className = `chat-message ${role}`;
  const label = role === "assistant" ? "Assistant" : "You";
  const sourceMarkup = sources.length
    ? `<div class="source-list">${sources
        .slice(0, 3)
        .map((source) => `<span>${escapeHtml(source.title || "Portfolio source")}</span>`)
        .join("")}</div>`
    : "";
  item.innerHTML = `<strong>${label}</strong><p>${escapeHtml(content).replace(/\n/g, "<br>")}</p>${sourceMarkup}`;
  chatLog.appendChild(item);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function ask(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion) return;

  appendMessage("user", cleanQuestion);
  chatHistory.push({ role: "user", content: cleanQuestion });
  if (chatStatus) chatStatus.textContent = "Retrieving portfolio context and generating an answer...";
  if (chatInput) chatInput.value = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: cleanQuestion, history: chatHistory.slice(-6) }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "Request failed");

    appendMessage("assistant", payload.answer, payload.sources || []);
    chatHistory.push({ role: "assistant", content: payload.answer });
    if (chatStatus) chatStatus.textContent = "Online RAG answer generated from the portfolio knowledge base.";
  } catch (error) {
    appendMessage(
      "assistant",
      `The online assistant is not fully configured yet: ${error.message}. The screenshots and architecture above still show the implemented RAG workflow.`
    );
    if (chatStatus) chatStatus.textContent = "Cloud RAG configuration required.";
  }
}

if (chatForm) {
  chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(chatInput ? chatInput.value : "");
  });
}

questionButtons.forEach((button) => {
  button.addEventListener("click", () => ask(button.dataset.question || button.textContent));
});
