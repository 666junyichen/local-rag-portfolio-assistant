import { currentUser } from "@clerk/nextjs/server";

export class OwnerAuthError extends Error {
  constructor(message: string, public readonly status: 401 | 403 | 503) {
    super(message);
    this.name = "OwnerAuthError";
  }
}

function ownerEmails(value = process.env.OWNER_EMAILS || ""): Set<string> {
  return new Set(value.split(",").map((email) => email.trim().toLowerCase()).filter(Boolean));
}

export function isOwnerEmail(email: string | undefined, verified: boolean, allowlist = process.env.OWNER_EMAILS || ""): boolean {
  if (!email || !verified) return false;
  return ownerEmails(allowlist).has(email.trim().toLowerCase());
}

export type OwnerIdentity = { userId: string; email: string };

export async function requireOwner(): Promise<OwnerIdentity> {
  if (!process.env.CLERK_SECRET_KEY || !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    throw new OwnerAuthError("Owner authentication is not configured", 503);
  }
  const user = await currentUser();
  if (!user) throw new OwnerAuthError("Authentication required", 401);
  const primary = user.emailAddresses.find((item) => item.id === user.primaryEmailAddressId);
  const verified = primary?.verification?.status === "verified";
  if (!isOwnerEmail(primary?.emailAddress, verified, process.env.OWNER_EMAILS || "")) {
    throw new OwnerAuthError("Owner access required", 403);
  }
  return { userId: user.id, email: primary!.emailAddress.toLowerCase() };
}

export function ownerErrorResponse(error: unknown): Response | null {
  if (!(error instanceof OwnerAuthError)) return null;
  return Response.json({ error: error.message }, { status: error.status });
}
