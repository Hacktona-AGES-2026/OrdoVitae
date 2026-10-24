import type {
  AlertaDTO,
  DecisaoCompartilhadaDTO,
  DiaFilaDTO,
  ErroDTO,
  FichaDTO,
  Pagina,
  SimulacaoDTO,
  StatusSugestao,
  SugestaoDTO,
} from "./tipos"

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000"

/** Erro HTTP da API, com o corpo `ErroDTO` quando o backend devolve um. */
export class ErroApi extends Error {
  readonly status: number
  readonly codigo: string

  constructor(status: number, corpo: Partial<ErroDTO> | null) {
    super(corpo?.detalhe || `Erro ${status} na API`)
    this.status = status
    this.codigo = corpo?.erro ?? "Desconhecido"
  }
}

async function req<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    // Content-Type só com corpo: num GET ele forçaria um preflight OPTIONS de CORS a cada chamada.
    resp = await fetch(`${API_URL}${caminho}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    })
  } catch {
    throw new ErroApi(0, { erro: "SemConexao", detalhe: `Não foi possível conectar à API em ${API_URL}.` })
  }
  if (!resp.ok) {
    const corpo = (await resp.json().catch(() => null)) as Partial<ErroDTO> | null
    throw new ErroApi(resp.status, corpo)
  }
  return resp.json() as Promise<T>
}

/** Máximo que a API devolve por página. */
export const LIMITE_MAX = 200

const query = (params: Record<string, string | number | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ""
}

export const api = {
  simulacao: () => req<SimulacaoDTO>("/simulacao"),

  /** Dias com foto da fila (os navegáveis na linha do tempo). */
  datas: () => req<string[]>("/simulacao/datas"),

  configurarSimulacao: (autoAprovar: boolean) =>
    req<SimulacaoDTO>("/simulacao", { method: "PATCH", body: JSON.stringify({ autoAprovar }) }),

  /** Com SIMULADOR=1 no backend, injeta as chegadas do dataset de cada dia e fotografa a fila. */
  avancarDia: (dias = 1) => req<SimulacaoDTO>("/simulacao", { method: "PATCH", body: JSON.stringify({ avancarDias: dias }) }),

  /** Avança até o próximo dia em que o motor cria uma sugestão (subir/descer/remover/alerta). */
  proximaSugestao: () => req<SimulacaoDTO>("/simulacao", { method: "PATCH", body: JSON.stringify({ proximaSugestao: true }) }),

  /** Uma página da fila. Sem `data`: fila viva de hoje; com data passada: a foto daquele dia (404 se não houver). */
  fila: (data: string | undefined, limite: number, offset: number) =>
    req<DiaFilaDTO>(`/fila${query({ data, limite, offset })}`),

  ficha: (sid: string) => req<FichaDTO>(`/solicitacoes/${encodeURIComponent(sid)}`),

  decisaoCompartilhada: (sid: string) =>
    req<DecisaoCompartilhadaDTO>(`/solicitacoes/${encodeURIComponent(sid)}/decisao-compartilhada`),

  sugestoes: (filtro: { status?: StatusSugestao; criadaEm?: string } = {}, limite = LIMITE_MAX, offset = 0) =>
    req<Pagina<SugestaoDTO>>(`/sugestoes${query({ ...filtro, limite, offset })}`),

  aprovar: (id: number) => req<SugestaoDTO>(`/sugestoes/${id}`, { method: "PATCH", body: JSON.stringify({ status: "aprovada" }) }),

  rejeitar: (id: number, comentario: string) =>
    req<SugestaoDTO>(`/sugestoes/${id}`, { method: "PATCH", body: JSON.stringify({ status: "rejeitada", comentario }) }),

  alertas: (limite = 50, offset = 0) => req<Pagina<AlertaDTO>>(`/alertas${query({ limite, offset })}`),

  exportarCsvUrl: () => `${API_URL}/fila.csv`,
}
