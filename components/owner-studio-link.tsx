"use client";

import { Settings2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

type OwnerStudioLinkProps = {
  className?: string;
  href?: string;
  label?: string;
};

export function OwnerStudioLink({
  className = "ownerNavLink",
  href = "/studio",
  label = "Publish Studio",
}: OwnerStudioLinkProps) {
  const [owner, setOwner] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/admin/session", { cache: "no-store" })
      .then((response) => {
        if (active) setOwner(response.ok);
      })
      .catch(() => {
        if (active) setOwner(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (!owner) return null;

  return (
    <Link className={className} href={href}>
      <Settings2 size={16} />
      <span>{label}</span>
    </Link>
  );
}
