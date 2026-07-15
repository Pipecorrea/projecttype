import { Link, Outlet } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FolderTree, ListChecks, PencilRuler, Tags } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/manual", label: "Clasificación manual", icon: Tags, enabled: true },
  { to: "/revision", label: "Revisión", icon: ListChecks, enabled: false },
  { to: "/config", label: "Editor de prompts", icon: PencilRuler, enabled: false },
  { to: "/catalogo", label: "Catálogo", icon: FolderTree, enabled: false },
] as const;

export function Shell() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className="flex w-64 shrink-0 flex-col border-r"
        style={{ background: "var(--bg-panel)", borderColor: "var(--border)" }}
      >
        <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="text-[15px] font-semibold">ProjectType</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            Revisión HITL
          </div>
        </div>
        <nav className="flex-1 px-3 py-3 space-y-1">
          {NAV.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
        <div
          className="px-5 py-3 border-t text-[11px] leading-relaxed"
          style={{ borderColor: "var(--border)", color: "var(--text-faint)" }}
        >
          {health.data ? (
            <>
              <div>v{health.data.version}</div>
              <div title="hash de la taxonomía activa">
                taxonomy {health.data.taxonomy_hash.slice(0, 8)}
              </div>
            </>
          ) : (
            <div>conectando…</div>
          )}
        </div>
      </aside>
      <main className="min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({
  to,
  label,
  icon: Icon,
  enabled,
}: {
  to: string;
  label: string;
  icon: typeof Tags;
  enabled: boolean;
}) {
  if (!enabled) {
    return (
      <div
        className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] cursor-not-allowed opacity-45"
        title="Próximamente"
      >
        <Icon size={16} />
        <span>{label}</span>
        <span className="ml-auto text-[10px] uppercase tracking-wide">pronto</span>
      </div>
    );
  }
  return (
    <Link
      to={to}
      className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors"
      activeProps={{
        style: { background: "var(--accent-soft)", color: "var(--accent)", fontWeight: 600 },
      }}
      inactiveProps={{ style: { color: "var(--text-muted)" } }}
    >
      {({ isActive }) => (
        <>
          <Icon size={16} className={cn(isActive && "opacity-100")} />
          <span>{label}</span>
        </>
      )}
    </Link>
  );
}
