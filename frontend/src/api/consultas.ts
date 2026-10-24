import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { api, ErroApi } from "./cliente"

export const chaves = {
  simulacao: ["simulacao"] as const,
  datas: ["datas"] as const,
  pendentes: ["sugestoes", "pendente"] as const,
  decisao: (sid: string, hoje: string | null) => ["decisao", sid, hoje] as const,
  fila: (data: string) => ["fila", data] as const,
  ficha: (sid: string) => ["ficha", sid] as const,
  sugestoes: ["sugestoes"] as const,
  alertas: ["alertas"] as const,
}

const MINUTO = 60_000

export function useSimulacao() {
  return useQuery({ queryKey: chaves.simulacao, queryFn: api.simulacao, staleTime: 30_000 })
}

export function useDatas() {
  return useQuery({ queryKey: chaves.datas, queryFn: api.datas, staleTime: 30_000 })
}

/** Tudo que muda quando o relógio da simulação anda ou uma sugestão é decidida. */
function invalidarSimulacao(qc: QueryClient) {
  for (const k of [chaves.simulacao, chaves.datas, chaves.sugestoes, chaves.alertas, ["fila"], ["ficha"], ["decisao"]])
    void qc.invalidateQueries({ queryKey: k })
}

/** Avança o relógio da simulação (o backend injeta as chegadas do dia e tira a foto). */
export function useAvancarDia() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (dias: number) => api.avancarDia(dias), onSuccess: () => invalidarSimulacao(qc) })
}

export function useConfigurarSimulacao() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (autoAprovar: boolean) => api.configurarSimulacao(autoAprovar),
    onSuccess: (sim) => qc.setQueryData(chaves.simulacao, sim),
  })
}

/** Foto de um dia passado não muda; a fila de hoje muda com aprovações e eventos. */
function opcoesFila(data: string, hoje: string | null) {
  const ehHoje = data === hoje
  return {
    queryKey: chaves.fila(data),
    queryFn: () => api.fila(ehHoje ? undefined : data),
    staleTime: ehHoje ? 30_000 : Infinity,
    retry: (n: number, e: Error) => !(e instanceof ErroApi && e.status === 404) && n < 2,
  }
}

export function useFilaDoDia(data: string | null, hoje: string | null) {
  return useQuery({
    ...opcoesFila(data ?? "", hoje),
    enabled: !!data,
    placeholderData: keepPreviousData,
  })
}

/** Carrega antes os próximos dias da timeline para o player não travar. */
export function preCarregarDias(qc: QueryClient, datas: string[], hoje: string | null) {
  for (const d of datas) void qc.prefetchQuery(opcoesFila(d, hoje))
}

/** O dia já respondeu (com fila ou com 404)? */
export function diaCarregado(qc: QueryClient, data: string) {
  const status = qc.getQueryState(chaves.fila(data))?.status
  return status === "success" || status === "error"
}

export function useFicha(sid: string | null) {
  return useQuery({
    queryKey: chaves.ficha(sid ?? ""),
    queryFn: () => api.ficha(sid!),
    enabled: !!sid,
    staleTime: 5 * MINUTO,
  })
}

/** Fichas só dos itens visíveis (a fila não traz nome/CID/procedimento). */
export function useFichas(sids: string[]) {
  return useQueries({
    queries: sids.map((sid) => ({
      queryKey: chaves.ficha(sid),
      queryFn: () => api.ficha(sid),
      staleTime: 5 * MINUTO,
    })),
    combine: (rs) => new Map(sids.map((sid, i) => [sid, rs[i]])),
  })
}

/** Pendentes de decisão, por solicitação (alimenta o bloco "aprovar" no card da fila). */
export function usePendentes() {
  return useQuery({
    queryKey: chaves.pendentes,
    queryFn: () => api.sugestoes("pendente"),
    staleTime: 15_000,
    select: (lista) => {
      const porSid = new Map<string, typeof lista>()
      for (const s of lista) porSid.set(s.solicitacaoId, [...(porSid.get(s.solicitacaoId) ?? []), s])
      return porSid
    },
  })
}

/** Motor secundário: calculado no backend com os dados recebidos até "hoje" da simulação. */
export function useDecisaoCompartilhada(sid: string | null, hoje: string | null) {
  return useQuery({
    queryKey: chaves.decisao(sid ?? "", hoje),
    queryFn: () => api.decisaoCompartilhada(sid!),
    enabled: !!sid,
    staleTime: 5 * MINUTO,
  })
}

export function useSugestoes() {
  return useQuery({ queryKey: chaves.sugestoes, queryFn: () => api.sugestoes(), staleTime: MINUTO })
}

export function useAlertas(ativo: boolean) {
  return useQuery({ queryKey: chaves.alertas, queryFn: api.alertas, staleTime: MINUTO, enabled: ativo })
}

function invalidarDepoisDeDecidir(qc: QueryClient, sid: string, hoje: string | null) {
  void qc.invalidateQueries({ queryKey: chaves.sugestoes })
  void qc.invalidateQueries({ queryKey: chaves.alertas })
  void qc.invalidateQueries({ queryKey: chaves.ficha(sid) })
  if (hoje) void qc.invalidateQueries({ queryKey: chaves.fila(hoje) })
}

export function useAprovarSugestao(hoje: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: number; sid: string }) => api.aprovar(id),
    onSuccess: (_, { sid }) => invalidarDepoisDeDecidir(qc, sid, hoje),
  })
}

export function useRejeitarSugestao(hoje: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, comentario }: { id: number; sid: string; comentario: string }) => api.rejeitar(id, comentario),
    onSuccess: (_, { sid }) => invalidarDepoisDeDecidir(qc, sid, hoje),
  })
}
