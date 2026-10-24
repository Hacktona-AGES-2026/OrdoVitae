import { ArrowDown, ArrowUp, Equal, Plus } from "lucide-react"

import { cn } from "@/lib/utils"
import { FAIXA_NOME, type Faixa, type ItemFila } from "@/lib/priorizacao"

const corFaixaClasse: Record<Faixa, string> = {
  1: "bg-faixa-1",
  2: "bg-faixa-2",
  3: "bg-faixa-3",
  4: "bg-faixa-4",
  5: "bg-faixa-5",
}

const textoFaixaClasse: Record<Faixa, string> = {
  1: "text-faixa-1",
  2: "text-faixa-2",
  3: "text-faixa-3",
  4: "text-faixa-4",
  5: "text-faixa-5",
}

export function FaixaTag({ faixa, curta, className }: { faixa: Faixa; curta?: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[11px] font-semibold tracking-wide whitespace-nowrap uppercase",
        textoFaixaClasse[faixa],
        className,
      )}
    >
      <i className={cn("size-2 shrink-0 rounded-[2px]", corFaixaClasse[faixa])} />
      {faixa}
      {!curta && ` · ${FAIXA_NOME[faixa]}`}
    </span>
  )
}

export function FaixaBarra({
  faixa,
  className,
  style,
}: {
  faixa: Faixa
  className?: string
  style?: React.CSSProperties
}) {
  return <span aria-hidden className={cn(corFaixaClasse[faixa], className)} style={style} />
}

/** Variação de posição vs. dia anterior. Até 4 posições é "arrasto" da fila. */
export function Movimento({ item, primeiroDia }: { item: ItemFila; primeiroDia: boolean }) {
  if (primeiroDia) return null
  const base = "inline-flex h-5 items-center gap-0.5 rounded-full px-1.5 text-[11px] font-semibold tabular-nums"
  if (item.posicaoAnterior === null)
    return (
      <span className={cn(base, "bg-swalis-c/15 text-swalis-c")} title="Entrou na fila neste dia">
        <Plus className="size-3" />
        nova
      </span>
    )
  const d = item.posicaoAnterior - item.posicao
  if (d >= 5)
    return (
      <span className={cn(base, "bg-success/15 text-success")} title={`Subiu ${d} posições desde ontem`}>
        <ArrowUp className="size-3" />
        {d}
      </span>
    )
  if (d <= -5)
    return (
      <span className={cn(base, "bg-destructive/10 text-destructive")} title={`Desceu ${-d} posições desde ontem`}>
        <ArrowDown className="size-3" />
        {-d}
      </span>
    )
  return (
    <span className={cn(base, "bg-muted text-muted-foreground")} title="Estável: variação de até 4 posições">
      <Equal className="size-3" />
    </span>
  )
}

export function Prazo({ item, className }: { item: ItemFila; className?: string }) {
  return item.alemDoPrazo > 0 ? (
    <span className={cn("font-semibold text-destructive tabular-nums", className)}>+{item.alemDoPrazo} d</span>
  ) : (
    <span className={cn("font-semibold text-success", className)}>no prazo</span>
  )
}

