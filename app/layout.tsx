import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { SiteShell } from "@/components/site-shell";

export const metadata: Metadata = {
  title: "Junyi Chen · Portfolio RAG Assistant",
  description: "A dual-mode local and cloud portfolio RAG assistant with verifiable sources.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const authConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY);
  const shell = <SiteShell authConfigured={authConfigured}>{children}</SiteShell>;
  return (
    <html lang="zh-CN">
      <body>{authConfigured ? <ClerkProvider>{shell}</ClerkProvider> : shell}</body>
    </html>
  );
}
