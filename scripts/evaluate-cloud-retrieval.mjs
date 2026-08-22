import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const ROOT = process.cwd();

function argValue(name, fallback = null) {
  const prefix = `--${name}=`;
  const match = process.argv.find((arg) => arg.startsWith(prefix));
  return match ? match.slice(prefix.length) : fallback;
}

function parseModes() {
  return String(argValue("modes", "vector,adaptive,hybrid"))
    .split(",")
    .map((mode) => mode.trim())
    .filter(Boolean);
}

export function rankMetrics(cases, rankings, latenciesMs) {
  let answerable = 0;
  let hit5 = 0;
  let recall5 = 0;
  let reciprocal = 0;
  let noAnswerTotal = 0;
  let noAnswerCorrect = 0;
  let privacyViolations = 0;

  for (const testCase of cases) {
    const ranked = rankings.get(testCase.case_id) || [];
    const expected = new Set(testCase.expected_doc_ids || []);
    if (testCase.should_answer === false) {
      noAnswerTotal += 1;
      if (!ranked.length) noAnswerCorrect += 1;
      if (/privacy|no_answer/.test(testCase.category) && ranked.length) privacyViolations += 1;
      continue;
    }
    answerable += 1;
    const top5 = ranked.slice(0, 5);
    const matched = top5.filter((docId) => expected.has(docId));
    if (matched.length) hit5 += 1;
    recall5 += expected.size ? matched.length / expected.size : 0;
    const firstHit = ranked.findIndex((docId) => expected.has(docId));
    if (firstHit >= 0) reciprocal += 1 / (firstHit + 1);
  }

  return {
    answerable,
    hit_at_5: answerable ? hit5 / answerable : 0,
    recall_at_5: answerable ? recall5 / answerable : 0,
    mrr: answerable ? reciprocal / answerable : 0,
    no_answer_accuracy: noAnswerTotal ? noAnswerCorrect / noAnswerTotal : 1,
    privacy_violations: privacyViolations,
    avg_latency_ms: latenciesMs.length
      ? latenciesMs.reduce((total, value) => total + value, 0) / latenciesMs.length
      : 0,
  };
}

async function retrieve(baseUrl, testCase, mode, topK) {
  const started = performance.now();
  let response;
  try {
    response = await fetch(new URL("/api/retrieve", baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: testCase.question,
        language: testCase.language || "zh",
        settings: {
          topK,
          scoreThreshold: null,
          spaceIds: ["portfolio"],
          retrievalMode: mode,
        },
      }),
    });
  } catch (error) {
    return {
      docIds: [],
      latencyMs: performance.now() - started,
      error: error instanceof Error ? error.message : String(error),
      retrieval: null,
    };
  }
  const latencyMs = performance.now() - started;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      docIds: [],
      latencyMs,
      error: payload.error || `HTTP ${response.status}`,
      retrieval: null,
    };
  }
  const sources = Array.isArray(payload.selectedContext) ? payload.selectedContext : [];
  return {
    docIds: sources.map((source) => String(source.docId || "")).filter(Boolean),
    latencyMs,
    error: null,
    retrieval: payload.retrieval || null,
  };
}

function strictlyImprovesBaseline(report, vector) {
  return report.metrics.hit_at_5 > 0
    && report.metrics.hit_at_5 >= vector.metrics.hit_at_5
    && report.metrics.mrr >= vector.metrics.mrr
    && (
      report.metrics.hit_at_5 > vector.metrics.hit_at_5
      || report.metrics.mrr > vector.metrics.mrr
      || report.metrics.recall_at_5 > vector.metrics.recall_at_5
    );
}

export function promotionGate(reports) {
  const vector = reports.vector;
  if (!vector) return "Run vector first; it is the promotion baseline.";
  const candidates = Object.entries(reports).filter(([mode]) => mode !== "vector");
  const winners = candidates.filter(([, report]) => (
    !report.degraded
    && report.metrics.privacy_violations === 0
    && report.metrics.no_answer_accuracy >= vector.metrics.no_answer_accuracy
    && strictlyImprovesBaseline(report, vector)
  ));
  if (!winners.length) return "Keep cloud default on vector; no candidate beat the baseline without regression.";
  return `Candidate default: ${winners[0][0]} met the benchmark gate.`;
}

export function isBoundaryRefusalFallback(item) {
  return /outside the public retrieval boundary/i.test(String(item.reason || ""));
}

export function isCapabilityFallback(item) {
  return item.requestedMode !== item.appliedMode && !isBoundaryRefusalFallback(item);
}

async function main() {
  const baseUrl = argValue("base-url", process.env.CLOUD_RAG_BASE_URL || process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000");
  const benchmarkPath = path.resolve(ROOT, argValue("benchmark", "evals/rag_benchmark.json"));
  const outputPath = path.resolve(ROOT, argValue("out", "evals/latest-cloud-retrieval.json"));
  const topK = Number(argValue("top-k", "5"));
  const limit = Number(argValue("limit", "0"));
  const cases = JSON.parse(await fs.readFile(benchmarkPath, "utf8"));
  const selectedCases = limit > 0 ? cases.slice(0, limit) : cases;
  const reports = {};

  for (const mode of parseModes()) {
    const rankings = new Map();
    const latencies = [];
    const fallbacks = [];
    const errors = [];
    for (const testCase of selectedCases) {
      const result = await retrieve(baseUrl, testCase, mode, topK);
      rankings.set(testCase.case_id, result.docIds);
      latencies.push(result.latencyMs);
      if (result.error) errors.push({ case_id: testCase.case_id, error: result.error });
      if (result.retrieval?.fallbackReason) {
        fallbacks.push({
          case_id: testCase.case_id,
          requestedMode: result.retrieval.requestedMode,
          appliedMode: result.retrieval.appliedMode,
          reason: result.retrieval.fallbackReason,
        });
      }
    }
    reports[mode] = {
      mode,
      cases: selectedCases.length,
      metrics: rankMetrics(selectedCases, rankings, latencies),
      degraded: fallbacks.some(isCapabilityFallback) || errors.length > 0,
      fallbacks,
      errors,
    };
    const metrics = reports[mode].metrics;
    console.log(`${mode}: Hit@5=${metrics.hit_at_5.toFixed(3)} MRR=${metrics.mrr.toFixed(3)} no-answer=${metrics.no_answer_accuracy.toFixed(3)} privacy=${metrics.privacy_violations} avg=${metrics.avg_latency_ms.toFixed(0)}ms`);
  }

  const report = {
    baseUrl,
    benchmark: path.relative(ROOT, benchmarkPath).replace(/\\/g, "/"),
    generatedAt: new Date().toISOString(),
    reports,
    defaultDecision: promotionGate(reports),
  };
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(`Wrote ${path.relative(ROOT, outputPath)}`);
  console.log(report.defaultDecision);
}

const entrypoint = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";
if (import.meta.url === entrypoint) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
}
