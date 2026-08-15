import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";


describe("Knowledge owner management entry", () => {
  it("renders the Knowledge management entry through the fail-closed owner component", () => {
    const catalog = readFileSync("components/knowledge-catalog.tsx", "utf8");

    expect(catalog).toContain('import { OwnerStudioLink } from "./owner-studio-link"');
    expect(catalog).toContain('label={"\\u4e0a\\u4f20\\u4e0e\\u7ba1\\u7406"}');
    expect(catalog).toContain('href="/studio"');
  });

  it("checks the owner session before rendering any Studio link", () => {
    const ownerLink = readFileSync("components/owner-studio-link.tsx", "utf8");

    expect(ownerLink).toContain('fetch("/api/admin/session"');
    expect(ownerLink).toContain("response.ok");
    expect(ownerLink).toContain("if (!owner) return null");
  });

  it("keeps the Studio page protected by server-side Owner authorization", () => {
    const studioPage = readFileSync("app/studio/page.tsx", "utf8");

    expect(studioPage).toContain("requireOwner()");
  });
});
