import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";


describe("safe reset UI contracts", () => {
  it("requires a reset preview, downloaded backup, fingerprint, and exact phrase", () => {
    const source = readFileSync("components/publish-studio.tsx", "utf8");

    expect(source).toContain("/api/admin/reset/preview");
    expect(source).toContain("/api/admin/export?scope=reset");
    expect(source).toContain("/api/admin/reset");
    expect(source).toContain("RESET PORTFOLIO");
    expect(source).toContain("resetBackupFingerprint");
  });

  it("hides cross-space controls until a second active space exists", () => {
    for (const file of ["components/chat-interface.tsx", "components/retrieval-lab.tsx"]) {
      const source = readFileSync(file, "utf8");
      expect(source).toContain("spaces.filter((space) => space.status === \"active\").length > 1");
    }
  });
});
