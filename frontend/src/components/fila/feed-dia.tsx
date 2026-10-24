import { ArrowDown, ArrowUp, Bell, LogOut, UserPlus } from "lucide-react"
import { useMemo } from "react"

import { useFichas } from "@/api/consultas"
import type { DiaFilaDTO, ItemFilaDTO, SugestaoDTO, TipoSugestao } from "@/api/tipos"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  CLASSES,
  DESCRICAO_CLASSE,
  formatarScore,
  LIMIAR_SALTO,
  paciente,
  rotuloAchado,
  sugestaoDeMudanca,
  TIPO_SUGESTAO_LABEL,
} from "@/lib/apresentacao"
import { cn } from "@/lib/utils"
import { DecisaoSugestao } from "./decisao-sugestao"
import { BarraClasse } from "./marcadores"

const ORDEM_TIPO: Record<TipoSugestao, number> = { subir: 0, remover: 1, descer: 2, alerta: 3, classificacao_inicial: 4 }

const ICONE: Partial<Record<TipoSugestao, React.ReactNode>> = {
  subir: <ArrowUp className="size-3.5 text-success" />,
  descer: <ArrowDown className="size-3.5 text-destructive" />,
  remover: <LogOut className="size-3.5 text-muted-foreground" />,
  alerta: <Bell className="size-3.5 text-swalis-b" />,
}

type Props = {
  data: string
  hoje: string | null
  dia: DiaFilaDTO | undefined
  primeiroDia: boolean
  sugestoes: SugestaoDTO[] | undefined
  carregandoSugestoes: boolean
  onAbrir: (sid: string) => void
}

function Secao({ titulo, extra, children }: { titulo: string; extra?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="flex items-center justify-between gap-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {titulo}
        {extra}
      </h3>
      {children}
    </section>
  )
}

export function FeedDia({ data, hoje, dia, primeiroDia, sugestoes, carregandoSugestoes, onAbrir }: Props) {
  const { doDia, entradas } = useMemo(() => {
    const doDiaTodas = (sugestoes ?? []).filter((s) => s.criadaEm === data)
    return {
      doDia: doDiaTodas
        .filter(sugestaoDeMudanca)
        .sort((a, b) => Number(b.status === "pendente") - Number(a.status === "pendente") || ORDEM_TIPO[a.tipo] - ORDEM_TIPO[b.tipo]),
      entradas: doDiaTodas.filter((s) => s.tipo === "classificacao_inicial").length,
    }
  }, [sugestoes, data])

  const movimentos = useMemo(() => {
    if (!dia || primeiroDia) return []
    // maiores saltos do dia, já filtrados e ordenados pelo backend
    return dia.movimentos
      .filter((i): i is ItemFilaDTO & { posicaoAnterior: number } => i.posicaoAnterior !== null)
      .map((i) => ({ item: i, delta: i.posicaoAnterior - i.posicao }))
  }, [dia, primeiroDia])

  const fichas = useFichas(useMemo(() => [...new Set([...doDia.map((s) => s.solicitacaoId), ...movimentos.map((m) => m.item.solicitacaoId)])], [doDia, movimentos]))
  const nome = (sid: string) => {
    const f = fichas.get(sid)?.data
    return f ? paciente(f).nome : sid
  }
  const pendentes = doDia.filter((s) => s.status === "pendente").length

  return (
    <Card className="lg:sticky lg:top-4 lg:h-[calc(100vh-9rem)]">
      <CardHeader>
        <CardTitle>O que mudou neste dia</CardTitle>
        <CardDescription>
          {doDia.length} sugestões · {movimentos.length} saltos na fila{entradas > 0 && ` · ${entradas} entradas`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        <ScrollArea className="h-96 min-h-0 lg:h-auto lg:flex-1">
          <div className="flex flex-col gap-5 pr-3">
            <Secao
              titulo="Sugestões do motor"
              extra={
                pendentes > 0 && (
                  <span className="rounded-full bg-swalis-b/20 px-2 text-foreground normal-case">{pendentes} {pendentes === 1 ? "pendente" : "pendentes"}</span>
                )
              }
            >
              {carregandoSugestoes && <p className="text-xs text-muted-foreground">Carregando sugestões…</p>}
              {!carregandoSugestoes && doDia.length === 0 && (
                <p className="text-xs text-muted-foreground italic">Nenhuma sugestão criada neste dia.</p>
              )}
              <ul className="flex flex-col gap-1.5">
                {doDia.map((s) => (
                  <li key={s.id} className="flex flex-col gap-1.5 rounded-lg bg-muted/40 px-2.5 py-2">
                    <div className="flex items-start gap-2">
                      <span className="mt-0.5">{ICONE[s.tipo]}</span>
                      <button type="button" onClick={() => onAbrir(s.solicitacaoId)} className="min-w-0 flex-1 text-left">
                        <p className="truncate text-xs font-medium hover:underline">{nome(s.solicitacaoId)}</p>
                        <p className="text-[11px] text-muted-foreground tabular-nums">
                          {TIPO_SUGESTAO_LABEL[s.tipo]}
                          {s.classeDe && s.classePara && s.classeDe !== s.classePara && ` · ${s.classeDe} → ${s.classePara}`}
                          {s.ordoClinicoDe != null && s.ordoClinicoPara != null &&
                            ` · score ${formatarScore(s.ordoClinicoDe)} → ${formatarScore(s.ordoClinicoPara)}`}
                        </p>
                        {s.motivos.length > 0 && (
                          <p className="truncate text-[11px] text-muted-foreground">
                            {s.motivos.map((m) => rotuloAchado(m.codigo)).join(" · ")}
                          </p>
                        )}
                        {s.previa?.posicaoDe != null && s.previa.posicaoPara != null && (
                          <p className="text-[11px] font-medium tabular-nums">
                            se aprovada: {s.previa.posicaoDe}º → {s.previa.posicaoPara}º
                          </p>
                        )}
                      </button>
                      <DecisaoSugestao sugestao={s} hoje={hoje} compacto />
                    </div>
                    {/* por que o motor sugere: o regulador lê antes de aprovar */}
                    {s.status === "pendente" && (s.explicacao || s.justificativa) && (
                      <p className="border-t border-dashed border-foreground/10 pt-1.5 text-[11px] leading-relaxed">
                        {s.explicacao || s.justificativa}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </Secao>

            <Secao titulo={`Saltos na fila (≥${LIMIAR_SALTO} posições)`}>
              {primeiroDia ? (
                <p className="text-xs text-muted-foreground italic">Primeiro dia da timeline: sem dia anterior para comparar.</p>
              ) : movimentos.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">Ninguém saltou posições — a fila só envelheceu.</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {movimentos.map(({ item, delta }) => (
                    <li key={item.solicitacaoId}>
                      <button
                        type="button"
                        onClick={() => onAbrir(item.solicitacaoId)}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left hover:bg-muted/60"
                      >
                        <span
                          className={cn(
                            "inline-flex w-12 shrink-0 items-center gap-0.5 text-xs font-semibold tabular-nums",
                            delta > 0 ? "text-success" : "text-destructive",
                          )}
                        >
                          {delta > 0 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />}
                          {Math.abs(delta)}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-xs">{nome(item.solicitacaoId)}</span>
                        <span className="text-[11px] text-muted-foreground tabular-nums">
                          {item.posicaoAnterior}º → {item.posicao}º
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Secao>

            {entradas > 0 && (
              <p className="flex items-center gap-2 text-xs text-muted-foreground">
                <UserPlus className="size-3.5" />
                {entradas} solicitações entraram na fila neste dia.
              </p>
            )}
          </div>
        </ScrollArea>
        <Separator />
        <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-1">
          {CLASSES.map((c) => (
            <li key={c} className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <BarraClasse classe={c} className="size-2 shrink-0 rounded-[2px]" />
              <b className="w-5 text-foreground">{c}</b>
              <span className="truncate">{DESCRICAO_CLASSE[c]}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
