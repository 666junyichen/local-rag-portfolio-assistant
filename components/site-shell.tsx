"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenText, Braces, Github, MessageSquareText, Microscope } from "lucide-react";
import { AuthControls } from "./auth-controls";

const links = [
  { href: "/", label: "Ask AI", icon: MessageSquareText },
  { href: "/knowledge", label: "Knowledge", icon: BookOpenText },
  { href: "/lab", label: "Retrieval Lab", icon: Microscope },
  { href: "/architecture", label: "Architecture", icon: Braces },
];

export function SiteShell({ children, authConfigured }: { children: React.ReactNode; authConfigured: boolean }) {
  const pathname = usePathname();
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand"><span className="brandMark">R</span><span>Portfolio RAG</span></Link>
        <nav aria-label="Primary navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={pathname === href ? "navLink active" : "navLink"}><Icon size={17}/><span>{label}</span></Link>
          ))}
        </nav>
        {authConfigured ? <AuthControls/> : null}
        <a className="iconButton" aria-label="View GitHub repository" title="GitHub repository" href="https://github.com/666junyichen/local-rag-portfolio-assistant" target="_blank" rel="noreferrer"><Github size={19}/></a>
      </header>
      <main>{children}</main>
    </>
  );
}
