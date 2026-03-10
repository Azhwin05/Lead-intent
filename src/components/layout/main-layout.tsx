"use client";

import { Sidebar } from "@/components/layout/sidebar";
import { TopNav } from "@/components/layout/top-nav";

export function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen w-full bg-background relative selection:bg-primary/30">
      <Sidebar />
      <div className="flex-1 flex flex-col ml-[240px]">
        <TopNav />
        <main className="flex-1 p-8 overflow-y-auto w-full max-w-[1600px] mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
