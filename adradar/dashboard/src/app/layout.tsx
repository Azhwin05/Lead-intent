import type { Metadata } from "next";
import { Inter, Syne, JetBrains_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { MainLayout } from "@/components/layout/main-layout";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const syne = Syne({ subsets: ["latin"], variable: "--font-syne" });
const jetBrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "AdRadar Dashboard",
  description: "AI-powered B2B Lead Generation Pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${syne.variable} ${jetBrainsMono.variable} font-sans antialiased text-white bg-background flex min-h-screen`}
      >
        <MainLayout>
          {children}
        </MainLayout>
        <Toaster theme="dark" position="top-right" />
      </body>
    </html>
  );
}

