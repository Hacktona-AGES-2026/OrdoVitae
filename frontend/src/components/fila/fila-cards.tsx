import { SwalisBadge } from "@/components/dashboard/swalis"
import { cn } from "@/lib/utils"
import { justificar, sinais, solicitacoes, type ItemFila } from "@/lib/priorizacao"
import { FaixaBarra, FaixaTag, Movimento, Prazo } from "./marcadores"

type Props = {
  itens: ItemFila[]
  dia: number
  primeiroDia: boolean
  onAbrir: (item: ItemFila) => void
}

export function FilaCards({ itens, dia, primeiroDia, onAbrir }: Props) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
      {itens.map((item) => {
        const s = solicitacoes[item.idx]
        const mudou =
          !primeiroDia &&
          (item.posicaoAnterior === null || Math.abs(item.posicaoAnterior - item.posicao) >= 5)
        return (
          <button
            key={s.sid}
            type="button"
            onClick={() => onAbrir(item)}
            className={cn(
              "group/cell relative flex min-h-48 flex-col gap-1 overflow-hidden rounded-xl bg-card p-3 pt-3.5 text-left text-card-foreground ring-1 ring-foreground/10 transition-[box-shadow,translate] outline-none hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring",
              mudou && "animate-[destaque_1.1s_ease-out]",
            )}
          >
            <FaixaBarra faixa={item.faixa} className="absolute inset-x-0 top-0 h-[3px]" />
            <div className="flex items-center gap-1.5">
              <span className="text-xl leading-none font-semibold tracking-tight tabular-nums">
                {item.posicao}
                <small className="ml-0.5 text-[10px] font-normal text-muted-foreground">º</small>
              </span>
              <SwalisBadge classe={item.classe} className="h-5 min-w-7 text-[11px]" />
              <span className="ml-auto">
                <Movimento item={item} primeiroDia={primeiroDia} />
              </span>
            </div>
            <p className="mt-0.5 truncate font-medium">{s.nome}</p>
            <FaixaTag faixa={item.faixa} className="text-[10px]" />
            <p className="truncate text-xs text-muted-foreground">
              <span className="font-mono">{s.cidOriginal}</span> · {s.especialidade}
            </p>
            <p className="font-mono text-[10px] text-muted-foreground">{s.sid}</p>
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-xs text-muted-foreground tabular-nums">
              <span className="text-foreground">{item.diasEmFila} d</span>·<span>prazo {item.prazo} d</span>·
              <Prazo item={item} />
            </p>
            <p className="mt-0.5 line-clamp-3 text-[11px] leading-snug text-muted-foreground">
              {justificar(s, item, sinais(s, dia))}
            </p>
            <div className="mt-auto h-[3px] overflow-hidden rounded-full bg-muted" title={`Índice ${item.score}/100`}>
              <FaixaBarra faixa={item.faixa} className="block h-full opacity-75" style={{ width: `${item.score}%` }} />
            </div>
          </button>
        )
      })}
    </div>
  )
}
