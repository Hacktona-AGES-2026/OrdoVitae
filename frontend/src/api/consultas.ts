import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { api, ErroApi } from "./cliente"

export const chaves = {
  simulacao: ["simulacao"] as const,
  datas: ["datas"] as const,
  pendentes: ["sugestoes", "pendente"] as const,
  decisao: (sid: string, hoje: string | null) => ["decisao", sid, hoje] as const,
  fila: (data: string, offset = 0, limite = 0) => ["fila", data, offset, limite] as const,
  ficha: (sid: string) => ["ficha", sid] as const,
  sugestoes: ["sugestoes"] as const,
  sugestoesDoDia: (data: string) => ["sugestoes", "dia", data] as const,
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

/** Uma página da fila de um dia. Foto de um dia passado não muda; a de hoje muda com aprovações e eventos. */
function opcoesFila(data: string, hoje: string | null, offset: number, limite: number) {
  const ehHoje = data === hoje
  return {
    queryKey: chaves.fila(data, offset, limite),
    queryFn: () => api.fila(ehHoje ? undefined : data, limite, offset),
    staleTime: ehHoje ? 30_000 : Infinity,
    retry: (n: number, e: Error) => !(e instanceof ErroApi && e.status === 404) && n < 2,
  }
}

export function useFilaDoDia(data: string | null, hoje: string | null, offset: number, limite: number) {
  return useQuery({
    ...opcoesFila(data ?? "", hoje, offset, limite),
    enabled: !!data,
    placeholderData: keepPreviousData,
  })
}

/** Carrega antes os próximos dias da timeline para o player não travar. */
export function preCarregarDias(qc: QueryClient, datas: string[], hoje: string | null, limite: number) {
  for (const d of datas) void qc.prefetchQuery(opcoesFila(d, hoje, 0, limite))
}

/** A primeira página do dia já respondeu (com fila ou com 404)? */
export function diaCarregado(qc: QueryClient, data: string, limite: number) {
  const status = qc.getQueryState(chaves.fila(data, 0, limite))?.status
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
    queryFn: () => api.sugestoes({ status: "pendente" }),
    staleTime: 15_000,
    select: (pagina) => {
      const porSid = new Map<string, typeof pagina.itens>()
      for (const s of pagina.itens) porSid.set(s.solicitacaoId, [...(porSid.get(s.solicitacaoId) ?? []), s])
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

/** Sugestões criadas num dia (o painel "o que mudou neste dia"). */
export function useSugestoesDoDia(data: string | null) {
  return useQuery({
    queryKey: chaves.sugestoesDoDia(data ?? ""),
    queryFn: () => api.sugestoes({ criadaEm: data! }),
    select: (pagina) => pagina.itens,
    enabled: !!data,
    staleTime: MINUTO,
  })
}

export function useAlertas(ativo: boolean) {
  return useQuery({ queryKey: chaves.alertas, queryFn: () => api.alertas(), select: (p) => p.itens, staleTime: MINUTO, enabled: ativo })
}

function invalidarDepoisDeDecidir(qc: QueryClient, sid: string, hoje: string | null) {
  void qc.invalidateQueries({ queryKey: chaves.sugestoes })
  void qc.invalidateQueries({ queryKey: chaves.alertas })
  void qc.invalidateQueries({ queryKey: chaves.ficha(sid) })
  // prefixo ["fila", hoje]: chaves.fila(hoje) completaria offset/limite com 0 e não casaria com nenhuma página
  if (hoje) void qc.invalidateQueries({ queryKey: ["fila", hoje] })
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
