import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@clerk/nextjs/server", () => ({ currentUser: vi.fn() }));

import { currentUser } from "@clerk/nextjs/server";
import { OwnerAuthError, isOwnerEmail, requireOwner } from "../lib/cloud-publish/auth";

const mockedCurrentUser = vi.mocked(currentUser);

afterEach(() => {
  vi.restoreAllMocks();
  delete process.env.CLERK_SECRET_KEY;
  delete process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  delete process.env.OWNER_EMAILS;
});

describe("owner authorization", () => {
  it("matches only verified allowlisted email addresses", () => {
    const allowlist = "owner@example.com, second@example.com";
    expect(isOwnerEmail("OWNER@example.com", true, allowlist)).toBe(true);
    expect(isOwnerEmail("owner@example.com", false, allowlist)).toBe(false);
    expect(isOwnerEmail("visitor@example.com", true, allowlist)).toBe(false);
    expect(isOwnerEmail(undefined, true, allowlist)).toBe(false);
  });

  it("fails closed when the owner allowlist is absent", () => {
    expect(isOwnerEmail("owner@example.com", true, "")).toBe(false);
  });

  it("returns 401 for a signed-out visitor", async () => {
    process.env.CLERK_SECRET_KEY = "secret";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "public";
    process.env.OWNER_EMAILS = "owner@example.com";
    mockedCurrentUser.mockResolvedValue(null);
    await expect(requireOwner()).rejects.toMatchObject<Partial<OwnerAuthError>>({ status: 401 });
  });

  it("returns 403 for a verified non-owner", async () => {
    process.env.CLERK_SECRET_KEY = "secret";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "public";
    process.env.OWNER_EMAILS = "owner@example.com";
    mockedCurrentUser.mockResolvedValue({
      id: "visitor",
      primaryEmailAddressId: "email-1",
      emailAddresses: [{ id: "email-1", emailAddress: "visitor@example.com", verification: { status: "verified" } }],
    } as never);
    await expect(requireOwner()).rejects.toMatchObject<Partial<OwnerAuthError>>({ status: 403 });
  });

  it("returns the owner identity only for a verified allowlisted account", async () => {
    process.env.CLERK_SECRET_KEY = "secret";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "public";
    process.env.OWNER_EMAILS = "owner@example.com";
    mockedCurrentUser.mockResolvedValue({
      id: "owner-id",
      primaryEmailAddressId: "email-1",
      emailAddresses: [{ id: "email-1", emailAddress: "OWNER@example.com", verification: { status: "verified" } }],
    } as never);
    await expect(requireOwner()).resolves.toEqual({ userId: "owner-id", email: "owner@example.com" });
  });
});
