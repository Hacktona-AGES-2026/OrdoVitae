import { ArrowDown, ArrowUp, Clock3, Equal, Plus, Ribbon, Siren } from "lucide-react"

import type { Classe, ItemFilaDTO } from "@/api/tipos"
import { DESCRICAO_CLASSE, PRAZO_CLASSE, type Movimento } from "@/lib/apresentacao"
import { cn } from "@/lib/utils"

const estiloClasse: Record<Classe, string> = {
  A1: "bg-swalis-a1/15 text-swalis-a1 ring-swalis-a1/30",
  A2: "bg-swalis-a2/15 text-swalis-a2 ring-swalis-a2/30",
  B: "bg-swalis-b/15 text-swalis-b ring-swalis-b/30",
  C: "bg-swalis-c/15 text-swalis-c ring-swalis-c/30",
  D: "bg-swalis-d/15 text-swalis-d ring-swalis-d/30",
}

const fundoClasse: Record<Classe, string> = {
  A1: "bg-swalis-a1",
  A2: "bg-swalis-a2",
  B: "bg-swalis-b",
  C: "bg-swalis-c",
  D: "bg-swalis-d",
}

export function ClasseBadge({ classe, className }: { classe: Classe; className?: string }) {
  return (
    <span
      title={`${DESCRICAO_CLASSE[classe]} · prazo ${PRAZO_CLASSE[classe]} dias`}
      className={cn(
        "inline-flex h-5 min-w-7 items-center justify-center rounded-md px-1.5 text-[11px] font-semibold tabular-nums ring-1 ring-inset",
        estiloClasse[classe],
        className,
      )}
    >
      {classe}
    </span>
  )
}

export function BarraClasse({
  classe,
  className,
  style,
}: {
  classe: Classe
  className?: string
  style?: React.CSSProperties
}) {
  return <span aria-hidden className={cn(fundoClasse[classe], className)} style={style} />
}

/** Variação de posição vs. dia anterior. */
export function MovimentoBadge({ mov }: { mov: Movimento }) {
  const base = "inline-flex h-5 items-center gap-0.5 rounded-full px-1.5 text-[11px] font-semibold tabular-nums"
  switch (mov.tipo) {
    case "primeiro":
      return null
    case "nova":
      return (
        <span className={cn(base, "bg-swalis-c/15 text-swalis-c")} title="Entrou na fila neste dia">
          <Plus className="size-3" />
          nova
        </span>
      )
    case "subiu":
      return (
        <span className={cn(base, "bg-success/15 text-success")} title={`Subiu ${mov.delta} posições desde o dia anterior`}>
          <ArrowUp className="size-3" />
          {mov.delta}
        </span>
      )
    case "desceu":
      return (
        <span className={cn(base, "bg-destructive/10 text-destructive")} title={`Desceu ${mov.delta} posições desde o dia anterior`}>
          <ArrowDown className="size-3" />
          {mov.delta}
        </span>
      )
    default:
      return (
        <span className={cn(base, "bg-muted text-muted-foreground")} title={`Estável (variação de ${mov.delta})`}>
          <Equal className="size-3" />
        </span>
      )
  }
}

export function Prazo({ item, className }: { item: Pick<ItemFilaDTO, "alemDoPrazo">; className?: string }) {
  return item.alemDoPrazo > 0 ? (
    <span className={cn("font-semibold text-destructive tabular-nums", className)}>+{item.alemDoPrazo} d</span>
  ) : (
    <span className={cn("font-semibold text-success", className)}>no prazo</span>
  )
}

/** Indicadores que só a fila de hoje traz (nas fotos antigas vêm null e não aparecem). */
export function Indicadores({ item, className }: { item: ItemFilaDTO; className?: string }) {
  const chip = "inline-flex h-5 items-center gap-1 rounded-md px-1.5 text-[10px] font-semibold"
  if (!item.critico && !item.oncologico && !item.provisorio) return null
  return (
    <span className={cn("inline-flex flex-wrap gap-1", className)}>
      {item.critico && (
        <span className={cn(chip, "bg-destructive text-white uppercase")} title="Grave, no topo e com prazo muito estourado">
          <Siren className="size-3" />
          crítico
        </span>
      )}
      {item.oncologico && (
        <span className={cn(chip, "bg-swalis-a2/15 text-swalis-a2")} title="CID C* ou biópsia positiva">
          <Ribbon className="size-3" />
          oncológico
        </span>
      )}
      {item.provisorio && (
        <span className={cn(chip, "bg-swalis-b/20 text-foreground")} title="Classificação inicial ainda não aprovada">
          <Clock3 className="size-3" />
          provisório
        </span>
      )}
    </span>
  )
}
