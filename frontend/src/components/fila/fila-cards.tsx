import { FileQuestion, Hourglass } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { formatarScore, movimento, paciente, temDadosInsuficientes } from "@/lib/apresentacao"
import { useFlip } from "@/lib/use-flip"
import { cn } from "@/lib/utils"
import type { PropsFila } from "./fila-lista"
import { BarraClasse, ClasseBadge, Indicadores, MovimentoBadge, Prazo } from "./marcadores"

export function FilaCards({ itens, fichas, pendentes, data, hoje, primeiroDia, onAbrir }: PropsFila) {
  const flip = useFlip<HTMLDivElement>(itens)
  return (
    <div ref={flip} className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
      {itens.map((item) => {
        const f = fichas.get(item.solicitacaoId)?.data
        const p = f ? paciente(f) : null
        const mov = movimento(item, primeiroDia)
        const pendente = data === hoje && (pendentes.get(item.solicitacaoId) ?? []).some((s) => s.tipo !== "classificacao_inicial")
        const dadosInsuf = temDadosInsuficientes(f, data)
        return (
          <button
            key={item.solicitacaoId}
            data-flip={item.solicitacaoId}
            type="button"
            onClick={() => onAbrir(item)}
            className={cn(
              "relative flex min-h-48 flex-col gap-1 overflow-hidden rounded-xl bg-card p-3 pt-3.5 text-left text-card-foreground ring-1 ring-foreground/10 transition-shadow outline-none hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring",
              item.critico && "ring-2 ring-destructive/70",
              pendente && "ring-2 ring-swalis-b/60",
              dadosInsuf && "pb-8",
            )}
          >
            <BarraClasse classe={item.classe} className="absolute inset-x-0 top-0 h-[3px]" />
            <div className="flex items-center gap-1.5">
              <span className="text-xl leading-none font-semibold tracking-tight tabular-nums">
                {item.posicao}
                <small className="ml-0.5 text-[10px] font-normal text-muted-foreground">º</small>
              </span>
              <ClasseBadge classe={item.classe} />
              <span className="ml-auto">
                <MovimentoBadge mov={mov} />
              </span>
            </div>
            {p ? <p className="mt-0.5 truncate font-medium">{p.nome}</p> : <Skeleton className="mt-1 h-5 w-40" />}
            <Indicadores item={item} />
            {pendente && (
              <span className="inline-flex w-fit items-center gap-1 rounded-md bg-swalis-b/20 px-1.5 text-[10px] font-semibold">
                <Hourglass className="size-3" />
                aprovação pendente
              </span>
            )}
            {p ? (
              <p className="truncate text-xs text-muted-foreground">
                <span className="font-mono">{p.cid}</span> · {p.especialidade}
              </p>
            ) : (
              <Skeleton className="h-3.5 w-32" />
            )}
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-xs text-muted-foreground tabular-nums">
              <span className="text-foreground">{item.diasEmFila} d</span>·<span>prazo {item.prazo} d</span>·
              <Prazo item={item} />
            </p>
            <p className="mt-auto flex gap-3 pt-1 text-[11px] text-muted-foreground tabular-nums">
              <span>
                clínico <b className="text-foreground">{formatarScore(item.scoreClinico)}</b>
              </span>
              <span>
                risco <b className="text-foreground">{item.risco == null ? "–" : `${Math.round(item.risco * 100)}%`}</b>
              </span>
              <span className="ml-auto">
                final <b className="text-foreground">{formatarScore(item.score)}</b>
              </span>
            </p>
            {dadosInsuf && (
              <span className="absolute inset-x-0 bottom-0 flex items-center gap-1 bg-dados-insuf/15 px-3 py-1 text-[10px] font-medium text-dados-insuf">
                <FileQuestion className="size-3" />
                Dados insuficientes
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
