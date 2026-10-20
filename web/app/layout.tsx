import type { Metadata } from "next";
import { Jost } from "next/font/google";
import "./globals.css";
import { TopNav } from "@/components/TopNav";
import { Footer } from "@/components/Footer";

const jost = Jost({
  subsets: ["latin"],
  variable: "--font-jost",
  display: "swap",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "NextRole. — AI-powered job search",
  description: "Tailor your resume with AI, track applications, and understand what the job search agent looks for.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={jost.variable}>
      <body className="min-h-screen bg-paper text-ink flex flex-col">
        <TopNav />
        <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-10">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
