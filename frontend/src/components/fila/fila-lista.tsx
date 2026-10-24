import { Clock, MapPin } from "lucide-react"

import { SwalisBadge } from "@/components/dashboard/swalis"
import { justificar, sinais, solicitacoes, type ItemFila } from "@/lib/priorizacao"
import { FaixaBarra, FaixaTag, Movimento, Prazo } from "./marcadores"

type Props = {
  itens: ItemFila[]
  dia: number
  primeiroDia: boolean
  onAbrir: (item: ItemFila) => void
}

export function FilaLista({ itens, dia, primeiroDia, onAbrir }: Props) {
  return (
    <ul className="flex flex-col gap-2">
      {itens.map((item) => {
        const s = solicitacoes[item.idx]
        return (
          <li key={s.sid}>
            <button
              type="button"
              onClick={() => onAbrir(item)}
              className="relative grid w-full grid-cols-[3.5rem_minmax(0,1fr)] gap-x-4 gap-y-2 overflow-hidden rounded-xl bg-card py-3 pr-4 pl-5 text-left text-card-foreground ring-1 ring-foreground/10 transition-shadow outline-none hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring md:grid-cols-[3.5rem_minmax(0,1.3fr)_minmax(0,1.2fr)_8rem_5rem]"
            >
              <FaixaBarra faixa={item.faixa} className="absolute inset-y-0 left-0 w-1" />

              <div className="row-span-2 flex flex-col items-start gap-1 md:row-span-1">
                <span className="text-2xl leading-none font-semibold tracking-tight tabular-nums">
                  {item.posicao}
                  <small className="ml-0.5 text-[10px] font-normal text-muted-foreground">º</small>
                </span>
                <Movimento item={item} primeiroDia={primeiroDia} />
              </div>

              <div className="min-w-0">
                <p className="truncate font-medium">{s.nome}</p>
                <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span>
                    {s.idade} anos · {s.sexo}
                  </span>
                  <span className="inline-flex items-center gap-0.5">
                    <MapPin className="size-3" />
                    {s.municipio}
                  </span>
                  <span className="font-mono text-[10px]">{s.sid}</span>
                </p>
              </div>

              <div className="col-start-2 min-w-0 md:col-start-auto">
                <div className="flex items-center gap-2">
                  <SwalisBadge classe={item.classe} className="h-5 min-w-7 text-[11px]" />
                  <FaixaTag faixa={item.faixa} className="text-[10px]" />
                </div>
                <p className="mt-1 truncate text-xs text-muted-foreground">
                  <span className="font-mono text-foreground">{s.cidOriginal}</span> · {s.especialidade} · {s.procedimento}
                </p>
              </div>

              <div className="col-start-2 flex items-center gap-3 text-xs md:col-start-auto md:flex-col md:items-start md:gap-0.5">
                <span className="inline-flex items-center gap-1 text-muted-foreground tabular-nums">
                  <Clock className="size-3" />
                  {item.diasEmFila} d · prazo {item.prazo} d
                </span>
                <Prazo item={item} />
              </div>

              <div className="col-start-2 flex items-center gap-2 md:col-start-auto md:flex-col md:items-end md:gap-1">
                <span className="text-xs text-muted-foreground">
                  índice <b className="text-sm text-foreground tabular-nums">{item.score}</b>
                </span>
                <span className="block h-1 w-16 overflow-hidden rounded-full bg-muted">
                  <FaixaBarra faixa={item.faixa} className="block h-full" style={{ width: `${item.score}%` }} />
                </span>
              </div>

              <p className="col-start-2 line-clamp-2 text-xs leading-snug text-muted-foreground md:col-span-4">
                {justificar(s, item, sinais(s, dia))}
              </p>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
