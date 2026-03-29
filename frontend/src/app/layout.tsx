import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sumi.web - Voice AI Agent",
  description: "Real-time voice conversation with AI agents",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body className="antialiased min-h-screen">{children}</body>
    </html>
  );
}
