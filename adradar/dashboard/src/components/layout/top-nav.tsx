"use client";

import { usePathname } from "next/navigation";
import { Play, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";

const ROUTE_NAMES: Record<string, string> = {
  "/": "Dashboard Overview",
  "/leads": "Live Leads Browser",
  "/pipeline": "Pipeline Analytics",
  "/outreach": "Email Sequence Studio",
  "/settings": "System Configuration",
};

export function TopNav() {
  const pathname = usePathname();
  const title = ROUTE_NAMES[pathname] || "Directory";

  return (
    <header className="h-16 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-30 flex items-center justify-between px-8">
      <h1 className="font-display text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">
        {title}
      </h1>
      
      <div className="flex items-center gap-6">
        <Button className="font-medium bg-primary hover:bg-primary/90 text-white shadow-[0_0_15px_rgba(124,58,237,0.3)] transition-all hover:shadow-[0_0_25px_rgba(124,58,237,0.5)]">
          <Play className="mr-2 h-4 w-4" fill="currentColor" />
          Run Pipeline Now
        </Button>
        
        <div className="flex items-center gap-4 border-l border-border/50 pl-6">
          <button className="relative text-muted-foreground hover:text-white transition-colors">
            <Bell className="h-5 w-5" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3 items-center justify-center rounded-full bg-hot text-[9px] font-bold text-white">
              3
            </span>
          </button>
          
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center text-sm font-bold shadow-lg">
              FR
            </div>
            <div className="flex flex-col text-sm">
              <span className="font-medium leading-none">Firestone Media</span>
              <span className="text-xs text-muted-foreground mt-0.5">Admin</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
