"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  BarChart3,
  ShieldCheck,
  Building2,
  FileText,
  GitCompare,
  Play,
  ClipboardList,
  Workflow,
  BookOpen,
} from "lucide-react";

const NAV = [
  { href: "/p3", label: "P3 Crypto", icon: ShieldCheck },
  { href: "/p1", label: "P1 Equity", icon: BarChart3 },
  { href: "/p2", label: "P2 SEC", icon: Building2 },
  { href: "/committee", label: "Committee", icon: GitCompare },
  { href: "/comparison", label: "Comparison", icon: FileText },
  { href: "/control", label: "Pipeline", icon: Play },
  { href: "/audit", label: "Audit Trail", icon: ClipboardList },
  { href: "/workflow", label: "Workflow", icon: Workflow },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-[hsl(var(--sidebar))] text-foreground">
      <div className="flex h-14 items-center border-b border-border px-4">
        <Link
          href="/p3"
          className="text-lg font-bold tracking-tight text-foreground hover:text-primary"
        >
          Surveillance
        </Link>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              "hover:bg-accent hover:text-accent-foreground",
              pathname.startsWith(href)
                ? "bg-[hsl(var(--sidebar-active))] text-[hsl(var(--sidebar-active-fg))] font-semibold shadow-sm"
                : "text-muted-foreground"
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>
      <div className="space-y-3 border-t border-border px-4 py-3">
        <ThemeToggle />
        <p className="text-xs text-muted-foreground">BITS Hackathon 2026</p>
      </div>
    </aside>
  );
}
