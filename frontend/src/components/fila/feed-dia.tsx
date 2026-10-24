import { ArrowUp, Check, Loader2 } from "lucide-react"
import { useMemo } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { chaveSubida, type StatusAprovacao } from "@/lib/aprovacoes"
import { cn } from "@/lib/utils"
import {
  diaNumero,
  diasFila,
  FAIXA_NOME,
  solicitacoes,
  TIPO_EVENTO_LABEL,
  type Faixa,
  type ItemFila,
} from "@/lib/priorizacao"
import { FaixaBarra } from "./marcadores"

type Linha = { chave: string; rotulo: string; titulo: string; detalhe: string }
type Subida = { chave: string; item: ItemFila; nome: string; motivo: string }

function resumoDoDia(f: number) {
  const atual = diasFila[f]
  const ant = f > 0 ? diasFila[f - 1] : null
  const dia = diaNumero(atual.data)
  const posAtual = new Set(atual.ordem.map((i) => i.idx))

  const subidas: Subida[] = []
  const entradas: Linha[] = []
  const eventos: Linha[] = []
  const saidas: Linha[] = []

  for (const s of solicitacoes) {
    for (const e of s.eventos) {
      if (e.dia === dia)
        eventos.push({
          chave: `ev-${s.idx}-${eventos.length}`,
          rotulo: "evento",
          titulo: `${TIPO_EVENTO_LABEL[e.tipo]} · ${e.resultado.replace(/_/g, " ")}`,
          detalhe: s.nome,
        })
    }
  }

  if (ant) {
    for (const item of atual.ordem) {
      const s = solicitacoes[item.idx]
      if (item.posicaoAnterior === null) {
        if (diaNumero(s.dataEntrada) === dia)
          entradas.push({ chave: `in-${item.idx}`, rotulo: "nova", titulo: "Entrou na fila", detalhe: `${s.nome} · posição ${item.posicao}` })
      } else if (item.posicaoAnterior - item.posicao >= 5) {
        const ev = s.eventos.find((e) => e.dia === dia)
        subidas.push({
          chave: chaveSubida(atual.data, s.sid),
          item,
          nome: s.nome,
          motivo: ev ? `${TIPO_EVENTO_LABEL[ev.tipo]} · ${ev.resultado.replace(/_/g, " ")}` : "recálculo de prazo e espera",
        })
      }
    }
    for (const item of ant.ordem) {
      const s = solicitacoes[item.idx]
      if (!posAtual.has(item.idx) && s.dataSaida && diaNumero(s.dataSaida) <= dia)
        saidas.push({ chave: `out-${item.idx}`, rotulo: "saída", titulo: "Saiu da fila", detalhe: s.nome })
    }
  }

  subidas.sort((a, b) => b.item.posicaoAnterior! - b.item.posicao - (a.item.posicaoAnterior! - a.item.posicao))
  return { subidas, outros: [...entradas, ...eventos, ...saidas] }
}

function BotaoAprovar({ status, onAprovar }: { status: StatusAprovacao; onAprovar: () => void }) {
  if (status === "aprovado")
    return (
      <span className="inline-flex h-6 items-center gap-1 rounded-md bg-success/15 px-2 text-[11px] font-medium text-success">
        <Check className="size-3" />
        Aprovado
      </span>
    )
  return (
    <Button size="xs" onClick={onAprovar} disabled={status === "enviando"}>
      {status === "enviando" ? <Loader2 className="animate-spin" /> : <Check />}
      Aprovar
    </Button>
  )
}

type Props = {
  frame: number
  statusDe: (chave: string) => StatusAprovacao
  onAprovar: (chave: string) => void
  onAbrir: (item: ItemFila) => void
}

export function FeedDia({ frame, statusDe, onAprovar, onAbrir }: Props) {
  const { subidas, outros } = useMemo(() => resumoDoDia(frame), [frame])
  const pendentes = subidas.filter((s) => statusDe(s.chave) !== "aprovado").length

  return (
    <Card className="lg:sticky lg:top-4 lg:h-[calc(100vh-9rem)]">
      <CardHeader>
        <CardTitle>O que mudou neste dia</CardTitle>
        <CardDescription>
          {subidas.length + outros.length === 0
            ? "Nada mudou — a fila só envelheceu"
            : `${subidas.length} subidas · ${outros.length} outras movimentações`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        <ScrollArea className="h-96 min-h-0 lg:h-auto lg:flex-1">
          <div className="flex flex-col gap-4 pr-3">
            <section className="flex flex-col gap-1.5">
              <h3 className="flex items-center justify-between text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                Subidas na fila
                {pendentes > 0 && (
                  <span className="rounded-full bg-swalis-b/20 px-2 text-foreground normal-case">
                    {pendentes} pendentes
                  </span>
                )}
              </h3>
              {subidas.length === 0 && <p className="text-xs text-muted-foreground italic">Nenhuma subida neste dia.</p>}
              <ul className="flex flex-col gap-1.5">
                {subidas.map((s) => (
                  <li key={s.chave} className="flex items-center gap-2 rounded-lg bg-muted/40 px-2.5 py-2">
                    <span className="inline-flex w-10 shrink-0 items-center gap-0.5 text-xs font-semibold text-success tabular-nums">
                      <ArrowUp className="size-3" />
                      {s.item.posicaoAnterior! - s.item.posicao}
                    </span>
                    <button type="button" onClick={() => onAbrir(s.item)} className="min-w-0 flex-1 text-left hover:underline">
                      <p className="truncate text-xs font-medium">{s.nome}</p>
                      <p className="truncate text-[11px] text-muted-foreground tabular-nums">
                        {s.item.posicaoAnterior}º → {s.item.posicao}º · {s.motivo}
                      </p>
                    </button>
                    <BotaoAprovar status={statusDe(s.chave)} onAprovar={() => onAprovar(s.chave)} />
                  </li>
                ))}
              </ul>
            </section>

            <section className="flex flex-col gap-1.5">
              <h3 className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                Eventos, entradas e saídas
              </h3>
              {outros.length === 0 && <p className="text-xs text-muted-foreground italic">Nenhum evento neste dia.</p>}
              <ul className="flex flex-col gap-1.5">
                {outros.map((it) => (
                  <li key={it.chave} className="grid grid-cols-[3rem_1fr] gap-2 rounded-lg bg-muted/40 px-2.5 py-1.5">
                    <span className={cn("pt-px text-[10px] text-muted-foreground", it.rotulo === "nova" && "text-swalis-c")}>
                      {it.rotulo}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs leading-tight font-medium">{it.titulo}</p>
                      <p className="truncate text-[11px] text-muted-foreground">{it.detalhe}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </ScrollArea>
        <Separator />
        <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          {([1, 2, 3, 4, 5] as Faixa[]).map((f) => (
            <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
              <FaixaBarra faixa={f} className="size-2 shrink-0 rounded-[2px]" />
              {f} · {FAIXA_NOME[f]}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
