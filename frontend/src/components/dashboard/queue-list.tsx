import { TriangleAlert } from "lucide-react"

import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { Solicitacao } from "@/data/mock-fila"
import { cn } from "@/lib/utils"
import { Movimento } from "./queue-card"
import { consumoPrazo, corSwalis } from "./format"
import { SwalisBadge } from "./swalis"

export function QueueList({ itens }: { itens: Solicitacao[] }) {
  return (
    <Card className="gap-0 py-0">
      <div className="hidden grid-cols-[3rem_3rem_minmax(0,2fr)_minmax(0,2fr)_9rem_4rem_minmax(0,1.4fr)] gap-3 border-b px-4 py-2 text-xs font-medium text-muted-foreground md:grid">
        <span>#</span>
        <span>Classe</span>
        <span>Paciente</span>
        <span>Procedimento</span>
        <span>Prazo</span>
        <span className="text-right">Score</span>
        <span>Alerta principal</span>
      </div>
      <ol>
        {itens.map((item) => {
          const prazo = consumoPrazo(item.swalis, item.diasEmFila)
          const alerta = item.alertas[0]
          return (
            <li
              key={item.solicitacaoId}
              className="grid grid-cols-[3rem_1fr_auto] items-center gap-x-3 gap-y-1 border-b px-4 py-3 text-sm last:border-b-0 hover:bg-muted/40 md:grid-cols-[3rem_3rem_minmax(0,2fr)_minmax(0,2fr)_9rem_4rem_minmax(0,1.4fr)]"
            >
              <span className="flex items-center gap-1.5">
                <span className="font-semibold tabular-nums">{item.posicao}</span>
                <Movimento atual={item.posicao} ontem={item.posicaoOntem} />
              </span>
              <span className="hidden md:block">
                <SwalisBadge classe={item.swalis} />
              </span>
              <span className="min-w-0">
                <span className="block truncate font-medium">{item.nome}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {item.idade} a · {item.municipio}
                </span>
              </span>
              <span className="md:hidden">
                <SwalisBadge classe={item.swalis} />
              </span>
              <span className="col-span-3 min-w-0 md:col-span-1">
                <span className="block truncate">{item.procedimento}</span>
                <span className="block truncate font-mono text-xs text-muted-foreground">{item.cid}</span>
              </span>
              <span className="col-span-2 flex flex-col gap-1 md:col-span-1">
                <span className={cn("text-xs tabular-nums", prazo.vencido ? "text-destructive" : "text-muted-foreground")}>
                  {item.diasEmFila} / {prazo.prazo} d
                </span>
                <Progress
                  value={Math.min(prazo.pct, 100)}
                  className="[&_[data-slot=progress-indicator]]:bg-(--cor)"
                  style={{ "--cor": prazo.vencido ? "var(--destructive)" : corSwalis[item.swalis] } as React.CSSProperties}
                />
              </span>
              <span className="text-right font-semibold tabular-nums">{item.score}</span>
              <span className="col-span-3 min-w-0 text-xs md:col-span-1">
                {alerta ? (
                  <span
                    className={cn(
                      "inline-flex max-w-full items-center gap-1 truncate",
                      alerta.severidade === "critico" ? "text-destructive" : "text-muted-foreground",
                    )}
                  >
                    {alerta.severidade === "critico" && <TriangleAlert className="size-3 shrink-0" />}
                    <span className="truncate">{alerta.label}</span>
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </span>
            </li>
          )
        })}
      </ol>
    </Card>
  )
}
