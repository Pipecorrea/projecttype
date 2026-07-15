// Cliente tipado de la API HITL (PT-19). Los tipos reflejan los DTOs Pydantic.

export type Origen = "l1" | "l2" | "l3" | "residual" | "manual";
export type Veredicto = "aceptado" | "corregido" | "sin_tipo_aplicable" | "no_evaluable";

export const VEREDICTO_LABELS: Record<Veredicto, string> = {
  aceptado: "Aceptado",
  corregido: "Corregido",
  sin_tipo_aplicable: "Sin tipo aplicable",
  no_evaluable: "No evaluable",
};

export interface HealthResponse {
  status: string;
  version: string;
  snapshot_loaded: boolean;
  total_clasificados: number;
  revisados: number;
  taxonomy_hash: string;
}

export interface ReviewSummary {
  total_clasificados: number;
  revisados: number;
  pendientes: number;
  por_origen: Record<string, number>;
  por_veredicto: Record<string, number>;
  taxonomy_hash: string;
  prompt_version: string;
  store_writer: string | null;
  store_actualizado: string | null;
}

export interface SubsectorCobertura {
  sector: string;
  subsector: string;
  n_tipos: number;
  n_clasificados: number;
  n_pendientes: number;
}

export interface SubsectoresResponse {
  items: SubsectorCobertura[];
  total: number;
}

export interface ManualPendienteItem {
  ebi_codigo: string;
  nombre: string;
  sector: string;
  subsector: string;
  descripcion: string;
  justificacion: string;
}

export interface ManualPendientesResponse {
  items: ManualPendienteItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface CatalogoTipo {
  tipo_id: string;
  nombre: string;
  definicion: string;
}

export interface CatalogoSubsector {
  subsector: string;
  tipos: CatalogoTipo[];
}

export interface CatalogoSector {
  sector: string;
  subsectores: CatalogoSubsector[];
}

export interface CatalogoResponse {
  sectores: CatalogoSector[];
  n_tipos: number;
  n_subsectores: number;
  taxonomy_hash: string;
}

export interface SaveVerdictRequest {
  veredicto: Veredicto;
  tipo_final_id?: string | null;
  notas?: string;
  revisor: string;
}

export interface RevisionTipoRecord {
  ebi_codigo: string;
  veredicto: Veredicto;
  tipo_final_id: string | null;
  tipo_final_nombre: string | null;
  revisor: string;
  revisado_en: string;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail ?? data);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    cache: "no-store",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  summary: () => request<ReviewSummary>("/api/review/summary"),
  subsectores: () => request<SubsectoresResponse>("/api/manual/subsectores"),
  pendientes: (subsector: string, offset = 0, limit = 50) =>
    request<ManualPendientesResponse>(
      `/api/manual/pendientes?subsector=${encodeURIComponent(subsector)}&offset=${offset}&limit=${limit}`,
    ),
  catalogo: () => request<CatalogoResponse>("/api/catalogo/arbol"),
  clasificar: (ebi: string, body: SaveVerdictRequest) =>
    request<RevisionTipoRecord>(`/api/manual/clasificar/${encodeURIComponent(ebi)}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
