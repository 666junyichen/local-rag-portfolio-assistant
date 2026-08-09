import { OwnerAuthError, requireOwner } from "@/lib/cloud-publish/auth";
import { PublishStudio } from "@/components/publish-studio";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function StudioPage() {
  if (!process.env.CLERK_SECRET_KEY || !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return <div className="pageFrame"><div className="pageHeading"><span className="eyebrow">OWNER ONLY</span><h1>Publish Studio needs Clerk configuration</h1><p>Add the Clerk keys and OWNER_EMAILS in Vercel before opening this workspace.</p></div></div>;
  }
  try {
    await requireOwner();
  } catch (error) {
    if (error instanceof OwnerAuthError && error.status === 401) redirect("/sign-in?redirect_url=/studio");
    return <div className="pageFrame"><div className="errorBanner">This account is not authorized to publish documents.</div></div>;
  }
  return <PublishStudio/>;
}
