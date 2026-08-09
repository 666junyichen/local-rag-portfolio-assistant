import { OwnerAuthError } from "./auth";
import { PublishParseError } from "./parsers";
import { PublishConflictError, PublishQuotaUnavailableError } from "./publishing";

export function publishApiError(error: unknown): Response {
  if (error instanceof OwnerAuthError) return Response.json({ error: error.message }, { status: error.status });
  if (error instanceof PublishParseError) return Response.json({ error: error.message, code: error.code }, { status: 400 });
  if (error instanceof PublishQuotaUnavailableError) {
    return Response.json({ error: error.message, code: "free_quota_unavailable" }, { status: 503 });
  }
  if (error instanceof PublishConflictError) {
    return Response.json({ error: error.message, code: "publish_conflict" }, { status: 409 });
  }
  const message = error instanceof Error ? error.message : "";
  if (/not found/i.test(message)) return Response.json({ error: "Resource not found" }, { status: 404 });
  if (/invalid|must|empty|between|exceed|PII|ready/i.test(message)) return Response.json({ error: message }, { status: 400 });
  console.error("Publish API request failed");
  return Response.json({ error: "The publish service is temporarily unavailable." }, { status: 500 });
}
