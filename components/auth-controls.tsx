"use client";

import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import { LogIn, Settings2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

function OwnerStudioLink() {
  const [owner, setOwner] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/api/admin/session", { cache: "no-store" })
      .then((response) => { if (active) setOwner(response.ok); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  return owner ? <Link className="ownerNavLink" href="/studio"><Settings2 size={16}/><span>Publish Studio</span></Link> : null;
}

export function AuthControls() {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) return <div className="authControls" aria-label="Loading account" />;

  return (
    <div className="authControls">
      {isSignedIn ? (
        <>
          <OwnerStudioLink />
          <UserButton />
        </>
      ) : (
        <SignInButton mode="modal">
          <button className="ownerSignIn" type="button">
            <LogIn size={16} />
            <span>Owner</span>
          </button>
        </SignInButton>
      )}
    </div>
  );
}
