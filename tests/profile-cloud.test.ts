import { describe, expect, it } from "vitest";
import { publicProfileContext } from "../lib/cloud-rag/profile";
import { planQuery, shouldRefuseWithoutRetrieval } from "../lib/cloud-rag/query-planning";

describe("profile facts and bounded query planning", () => {
  it("includes traceable public facts only", () => {
    expect(publicProfileContext()).toContain("source:");
    expect(publicProfileContext()).not.toContain("visibility=private");
  });

  it("keeps complex retrieval bounded", () => {
    const plan = planQuery("Compare Junyi's RAG and Owlswap projects");
    expect(plan.mode).toBe("complex");
    expect(plan.subqueries.length).toBeLessThanOrEqual(3);
    expect(plan.maxRounds).toBe(2);
  });

  it("refuses sensitive private requests before retrieval", () => {
    expect(shouldRefuseWithoutRetrieval("Junyi 的微信号是什么？")).toBe(true);
    expect(shouldRefuseWithoutRetrieval("What MongoDB experience does Junyi have?")).toBe(false);
  });
});
