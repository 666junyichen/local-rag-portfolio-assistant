import { describe, expect, it } from "vitest";
import { chunksForPreviewView } from "../lib/cloud-publish/preview-view";

describe("Publish Studio chunk preview", () => {
  it("returns every retrieval child instead of truncating the preview", () => {
    const children = Array.from({ length: 48 }, (_, index) => ({ id: `child-${index + 1}` }));
    const parents = Array.from({ length: 35 }, (_, index) => ({ id: `parent-${index + 1}` }));

    expect(chunksForPreviewView({ children, parents }, "children")).toHaveLength(48);
    expect(chunksForPreviewView({ children, parents }, "parents")).toHaveLength(35);
  });

  it("returns an empty list before a preview exists", () => {
    expect(chunksForPreviewView(undefined, "children")).toEqual([]);
  });
});
