import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "RiftReview — Lịch Sử Đấu & Phân Tích LMHT",
  description:
    "Tra cứu hồ sơ Riot ID, đồng bộ lịch sử đấu Liên Minh Huyền Thoại và phân tích hậu trận Gold/XP Diff phong cách Coachless.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className="dark">
      <body className="font-sans min-h-screen flex flex-col bg-surface-950">
        <Navbar />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-slate-800/70 py-6 text-center text-xs text-slate-500">
          RiftReview &bull; Powered by Flask REST API v1, Riot Games API &amp; Data Dragon
        </footer>
      </body>
    </html>
  );
}
