import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  api,
  type CatalogoResponse,
  type ManualPendienteItem,
  type SubsectorCobertura,
} from "@/lib/api";

function useRevisor(): [string, (v: string) => void] {
  const [revisor, setRevisor] = useState(() => localStorage.getItem("pt_revisor") ?? "");
  useEffect(() => {
    localStorage.setItem("pt_revisor", revisor);
  }, [revisor]);
  return [revisor, setRevisor];
}

function tiposDeSubsector(
  catalogo: CatalogoResponse | undefined,
  sector: string,
  subsector: string,
): { tipo_id: string; nombre: string }[] {
  if (!catalogo) return [];
  const sec = catalogo.sectores.find((s) => s.sector === sector);
  const sub = sec?.subsectores.find((s) => s.subsector === subsector);
  return sub?.tipos ?? [];
}

export function ManualPage() {
  const [revisor, setRevisor] = useRevisor();
  const [selected, setSelected] = useState<SubsectorCobertura | null>(null);

  const subsectores = useQuery({ queryKey: ["subsectores"], queryFn: api.subsectores });
  const catalogo = useQuery({ queryKey: ["catalogo"], queryFn: api.catalogo });

  // Selección inicial: primer subsector con pendientes.
  useEffect(() => {
    if (selected === null && subsectores.data) {
      const first = subsectores.data.items.find((s) => s.n_pendientes > 0);
      if (first) setSelected(first);
    }
  }, [subsectores.data, selected]);

  return (
    <div className="flex h-full flex-col">
      <header
        className="flex items-center gap-4 border-b px-6 py-3.5"
        style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}
      >
        <div>
          <h1 className="text-[15px] font-semibold">Clasificación manual</h1>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Asigna a mano el tipo de proyecto en subsectores sin cobertura.
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs" style={{ color: "var(--text-muted)" }}>
            Revisor
          </label>
          <input
            value={revisor}
            onChange={(e) => setRevisor(e.target.value)}
            placeholder="tu nombre"
            className="rounded-md border px-2.5 py-1.5 text-[13px] outline-none"
            style={{
              borderColor: revisor ? "var(--border-strong)" : "var(--danger)",
              background: "var(--bg-elevated)",
              color: "var(--text)",
            }}
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <SubsectorList
          items={subsectores.data?.items ?? []}
          loading={subsectores.isLoading}
          selected={selected}
          onSelect={setSelected}
        />
        <PendientesPane
          subsector={selected}
          revisor={revisor}
          tipos={
            selected ? tiposDeSubsector(catalogo.data, selected.sector, selected.subsector) : []
          }
        />
      </div>
    </div>
  );
}

function SubsectorList({
  items,
  loading,
  selected,
  onSelect,
}: {
  items: SubsectorCobertura[];
  loading: boolean;
  selected: SubsectorCobertura | null;
  onSelect: (s: SubsectorCobertura) => void;
}) {
  return (
    <div
      className="w-80 shrink-0 overflow-y-auto border-r"
      style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}
    >
      <div
        className="sticky top-0 border-b px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide"
        style={{ borderColor: "var(--border)", background: "var(--bg-panel)", color: "var(--text-faint)" }}
      >
        Subsectores por cobertura
      </div>
      {loading && <div className="px-4 py-3 text-[13px]" style={{ color: "var(--text-muted)" }}>Cargando…</div>}
      {!loading && items.length === 0 && (
        <div className="px-4 py-3 text-[13px]" style={{ color: "var(--text-muted)" }}>
          Sin proyectos en el store. Carga CONSULTAS_EBI para empezar.
        </div>
      )}
      {items.map((s) => {
        const active = selected?.sector === s.sector && selected?.subsector === s.subsector;
        return (
          <button
            key={`${s.sector}/${s.subsector}`}
            type="button"
            onClick={() => onSelect(s)}
            className="block w-full border-b px-4 py-2.5 text-left transition-colors"
            style={{
              borderColor: "var(--border)",
              background: active ? "var(--accent-soft)" : "transparent",
            }}
          >
            <div
              className="truncate text-[13px] font-medium"
              style={{ color: active ? "var(--accent)" : "var(--text)" }}
            >
              {s.subsector}
            </div>
            <div className="truncate text-[11px]" style={{ color: "var(--text-faint)" }}>
              {s.sector}
            </div>
            <div className="mt-1 flex gap-1.5">
              <Badge tone="warning">{s.n_pendientes} pendientes</Badge>
              <Badge tone="success">{s.n_clasificados} clasif.</Badge>
              <Badge tone="muted">{s.n_tipos} tipos</Badge>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function PendientesPane({
  subsector,
  revisor,
  tipos,
}: {
  subsector: SubsectorCobertura | null;
  revisor: string;
  tipos: { tipo_id: string; nombre: string }[];
}) {
  const queryClient = useQueryClient();
  const key = subsector ? subsector.subsector : "";
  const pendientes = useQuery({
    queryKey: ["pendientes", key],
    queryFn: () => api.pendientes(key),
    enabled: Boolean(subsector),
  });

  const mutation = useMutation({
    mutationFn: (vars: { ebi: string; tipoId: string | null }) =>
      api.clasificar(vars.ebi, {
        veredicto: vars.tipoId ? "corregido" : "sin_tipo_aplicable",
        tipo_final_id: vars.tipoId,
        revisor,
      }),
    onSuccess: (rec) => {
      toast.success(
        rec.tipo_final_nombre
          ? `Clasificado como ${rec.tipo_final_nombre}`
          : "Marcado sin tipo aplicable",
      );
      void queryClient.invalidateQueries({ queryKey: ["pendientes", key] });
      void queryClient.invalidateQueries({ queryKey: ["subsectores"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (!subsector) {
    return (
      <div className="flex flex-1 items-center justify-center text-[13px]" style={{ color: "var(--text-muted)" }}>
        Elige un subsector de la izquierda.
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="px-6 py-4">
        <div className="text-[13px] font-medium">{subsector.subsector}</div>
        <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>
          {subsector.sector} · {pendientes.data?.total ?? 0} pendientes · {tipos.length} tipos disponibles
        </div>
      </div>
      {pendientes.isLoading && (
        <div className="px-6 text-[13px]" style={{ color: "var(--text-muted)" }}>Cargando…</div>
      )}
      {pendientes.data && pendientes.data.items.length === 0 && (
        <div className="px-6 text-[13px]" style={{ color: "var(--text-muted)" }}>
          No quedan pendientes en este subsector. 🎉
        </div>
      )}
      <div className="space-y-3 px-6 pb-8">
        {pendientes.data?.items.map((item) => (
          <PendienteCard
            key={item.ebi_codigo}
            item={item}
            tipos={tipos}
            disabled={!revisor || mutation.isPending}
            onClasificar={(tipoId) => mutation.mutate({ ebi: item.ebi_codigo, tipoId })}
          />
        ))}
      </div>
    </div>
  );
}

function PendienteCard({
  item,
  tipos,
  disabled,
  onClasificar,
}: {
  item: ManualPendienteItem;
  tipos: { tipo_id: string; nombre: string }[];
  disabled: boolean;
  onClasificar: (tipoId: string | null) => void;
}) {
  const [tipoId, setTipoId] = useState("");
  const descripcion = useMemo(
    () => [item.descripcion, item.justificacion].filter(Boolean).join(" · "),
    [item.descripcion, item.justificacion],
  );

  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-[13px] font-medium">{item.nombre || "(sin nombre)"}</span>
        <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
          BIP {item.ebi_codigo}
        </span>
      </div>
      {descripcion && (
        <p className="mt-1 line-clamp-2 text-[12px]" style={{ color: "var(--text-muted)" }}>
          {descripcion}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select
          value={tipoId}
          onChange={(e) => setTipoId(e.target.value)}
          className="min-w-56 rounded-md border px-2 py-1.5 text-[13px] outline-none"
          style={{ borderColor: "var(--border-strong)", background: "var(--bg-elevated)", color: "var(--text)" }}
        >
          <option value="">— elegir tipo —</option>
          {tipos.map((t) => (
            <option key={t.tipo_id} value={t.tipo_id}>
              {t.nombre}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={disabled || !tipoId}
          onClick={() => onClasificar(tipoId)}
          className="rounded-md px-3 py-1.5 text-[13px] font-medium text-white disabled:opacity-40"
          style={{ background: "var(--accent)" }}
        >
          Clasificar
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onClasificar(null)}
          className="rounded-md border px-3 py-1.5 text-[13px] disabled:opacity-40"
          style={{ borderColor: "var(--border-strong)", color: "var(--text-muted)" }}
        >
          Sin tipo aplicable
        </button>
      </div>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: "warning" | "success" | "muted" }) {
  const styles: Record<string, { bg: string; fg: string }> = {
    warning: { bg: "var(--warning-soft)", fg: "var(--warning)" },
    success: { bg: "var(--success-soft)", fg: "var(--success)" },
    muted: { bg: "var(--bg-elevated)", fg: "var(--text-faint)" },
  };
  const s = styles[tone];
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-medium"
      style={{ background: s.bg, color: s.fg }}
    >
      {children}
    </span>
  );
}
