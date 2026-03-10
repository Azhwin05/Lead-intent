"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar, Target, Flame, BarChart3, Mail, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/", icon: Target },
  { name: "Live Leads", href: "/leads", icon: Flame },
  { name: "Pipeline", href: "/pipeline", icon: BarChart3 },
  { name: "Outreach", href: "/outreach", icon: Mail },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-[240px] border-r bg-background flex flex-col justify-between overflow-y-auto">
      <div>
        <div className="h-16 flex items-center px-6 border-b border-border/50">
          <Radar className="h-6 w-6 text-primary mr-3" />
          <span className="font-display font-bold text-lg tracking-wide text-white">AdRadar</span>
        </div>

        <nav className="p-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-all group",
                  isActive
                    ? "bg-primary/10 text-primary glow-primary"
                    : "text-muted-foreground hover:bg-surface-2 hover:text-white"
                )}
              >
                <Icon
                  className={cn(
                    "mr-3 h-4 w-4 transition-colors",
                    isActive ? "text-primary flex-shrink-0" : "text-muted-foreground group-hover:text-white flex-shrink-0"
                  )}
                />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-border/50 bg-surface">
        <div className="flex items-center mb-3">
          <div className="h-2 w-2 rounded-full bg-green mr-2 animate-pulse" />
          <span className="text-sm font-medium text-white">Pipeline Running</span>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground flex justify-between">
            <span>Next run:</span>
            <span className="text-white">Today 06:00 AM</span>
          </div>
          <div className="text-xs text-muted-foreground flex justify-between gap-2 overflow-hidden whitespace-nowrap text-ellipsis">
            <span>Last run:</span>
            <span className="text-white">Yesterday 06:02 AM — 34 leads</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
