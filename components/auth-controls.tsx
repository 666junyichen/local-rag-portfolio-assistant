"use client";

import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import { LogIn } from "lucide-react";
import { OwnerStudioLink } from "./owner-studio-link";

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
