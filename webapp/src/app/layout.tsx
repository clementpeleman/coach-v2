import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/sidebar";
import MobileNav from "@/components/mobile-nav";
import CoachChat from "@/components/coach-chat";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sports Hub",
  description: "Jouw persoonlijke sport coach en analyse platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="nl"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full bg-slate-50 text-slate-900">
        <Sidebar />
        <div className="flex flex-1 flex-col lg:pl-56">
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 pb-20 lg:pb-8">
            {children}
          </main>
        </div>
        <MobileNav />
        <CoachChat />
      </body>
    </html>
  );
}
