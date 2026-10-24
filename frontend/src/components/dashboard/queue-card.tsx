import {
  ArrowDown,
  ArrowUp,
  Check,
  Clock,
  MapPin,
  Minus,
  TriangleAlert,
  X,
} from "lucide-react"
import { Area, AreaChart, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import type { Solicitacao } from "@/data/mock-fila"
import { consumoPrazo, corSwalis, estiloAlerta, formatarData, rotuloEvento } from "./format"
import { SwalisBadge } from "./swalis"

export function Movimento({ atual, ontem }: { atual: number; ontem: number }) {
  const delta = ontem - atual
  if (delta === 0)
    return (
      <span className="inline-flex items-center text-xs text-muted-foreground">
        <Minus className="size-3" />
      </span>
    )
  const subiu = delta > 0
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        subiu ? "text-swalis-a1" : "text-success",
      )}
      title={subiu ? `Subiu ${delta} posições desde ontem` : `Desceu ${-delta} posições desde ontem`}
    >
      {subiu ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />}
      {Math.abs(delta)}
    </span>
  )
}

function ScoreSparkline({ item }: { item: Solicitacao }) {
  const config = { score: { label: "Score", color: corSwalis[item.swalis] } } satisfies ChartConfig
  const dados = item.historicoScore.map((score, i) => ({ dia: `D-${13 - i}`, score }))
  return (
    <ChartContainer config={config} className="aspect-auto h-16 w-full">
      <AreaChart data={dados} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`grad-${item.solicitacaoId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-score)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--color-score)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={[0, 100]} />
        <XAxis dataKey="dia" hide />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
        <Area
          dataKey="score"
          type="monotone"
          stroke="var(--color-score)"
          strokeWidth={2}
          fill={`url(#grad-${item.solicitacaoId})`}
          isAnimationActive={false}
        />
      </AreaChart>
    </ChartContainer>
  )
}

function Hba1cChart({ item }: { item: Solicitacao }) {
  const config = { valor: { label: "HbA1c %", color: "var(--chart-1)" } } satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto h-16 w-full">
      <LineChart data={item.hba1c} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
        <YAxis hide domain={[5, 11]} />
        <XAxis dataKey="data" hide />
        <ReferenceLine y={8.5} stroke="var(--destructive)" strokeDasharray="3 3" strokeOpacity={0.6} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
        <Line
          dataKey="valor"
          type="monotone"
          stroke="var(--color-valor)"
          strokeWidth={2}
          dot={{ r: 2.5, fill: "var(--color-valor)" }}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  )
}

function DorMeter({ item }: { item: Solicitacao }) {
  const dor = item.dorEva ?? 0
  return (
    <div className="flex h-16 flex-col justify-end gap-1.5">
      <div className="flex items-end gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className={cn("h-6 flex-1 rounded-sm", i < dor ? "bg-chart-2" : "bg-muted")}
            style={{ opacity: i < dor ? 0.45 + i * 0.055 : 1 }}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Limitação <span className="font-medium text-foreground">{item.limitacao ?? "—"}</span>
      </p>
    </div>
  )
}

function ItemPreOp({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-1.5">
      {ok ? <Check className="size-3.5 text-success" /> : <X className="size-3.5 text-destructive" />}
      <span className={cn(!ok && "text-foreground")}>{label}</span>
    </li>
  )
}

export function QueueCard({ item }: { item: Solicitacao }) {
  const prazo = consumoPrazo(item.swalis, item.diasEmFila)
  const ultimo = item.eventos[0]
  const temHba1c = item.hba1c.length > 0
  const ultimaHba1c = temHba1c ? item.hba1c[item.hba1c.length - 1].valor : null

  return (
    <Card className="relative">
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-1"
        style={{ background: corSwalis[item.swalis] }}
      />
      <CardHeader className="pl-5">
        <div className="flex items-start gap-3">
          <div className="flex w-9 shrink-0 flex-col items-center">
            <span className="text-2xl leading-none font-semibold tabular-nums">{item.posicao}</span>
            <Movimento atual={item.posicao} ontem={item.posicaoOntem} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate font-heading text-base font-medium">{item.nome}</h3>
                <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span>
                    {item.idade} anos · {item.sexo}
                  </span>
                  <span className="inline-flex items-center gap-0.5">
                    <MapPin className="size-3" />
                    {item.municipio}
                    {item.distanciaKm != null && ` · ${item.distanciaKm} km`}
                  </span>
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <SwalisBadge classe={item.swalis} />
                <span className="text-xs text-muted-foreground tabular-nums">
                  score <span className="font-semibold text-foreground">{item.score}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pl-5">
        <div>
          <p className="font-medium">{item.procedimento}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant="outline" className="font-mono">
              {item.cid}
            </Badge>
            <span className="truncate">{item.cidDescricao}</span>
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Clock className="size-3" />
              {item.diasEmFila} dias na fila · prazo {prazo.prazo} d
            </span>
            <span className={cn("font-medium tabular-nums", prazo.vencido && "text-destructive")}>
              {prazo.vencido ? `+${item.diasEmFila - prazo.prazo} d vencido` : `${prazo.pct}%`}
            </span>
          </div>
          <Progress
            value={Math.min(prazo.pct, 100)}
            className="[&_[data-slot=progress-indicator]]:bg-(--cor)"
            style={{ "--cor": prazo.vencido ? "var(--destructive)" : corSwalis[item.swalis] } as React.CSSProperties}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Score · 14 dias</p>
            <ScoreSparkline item={item} />
          </div>
          <div>
            {temHba1c ? (
              <>
                <p className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>HbA1c</span>
                  <span
                    className={cn(
                      "font-medium tabular-nums",
                      ultimaHba1c! > 8.5 ? "text-destructive" : "text-foreground",
                    )}
                  >
                    {ultimaHba1c!.toFixed(1).replace(".", ",")}%
                  </span>
                </p>
                <Hba1cChart item={item} />
              </>
            ) : (
              <>
                <p className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>Dor (EVA)</span>
                  <span className="font-medium text-foreground tabular-nums">{item.dorEva ?? "—"}/10</span>
                </p>
                <DorMeter item={item} />
              </>
            )}
          </div>
        </div>

        {item.alertas.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {item.alertas.map((a) => (
              <li
                key={a.label}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
                  estiloAlerta[a.severidade],
                )}
              >
                {a.severidade === "critico" && <TriangleAlert className="size-3" />}
                {a.label}
              </li>
            ))}
          </ul>
        )}

        <ul className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <ItemPreOp ok={item.preOp.avaliacaoAnestesica === "realizada"} label="Pré-anestésica" />
          <ItemPreOp ok={item.preOp.examesValidos} label="Exames" />
          <ItemPreOp ok={item.preOp.hba1cControlada !== false} label="Glicemia" />
        </ul>
      </CardContent>

      {ultimo && (
        <CardFooter className="mt-auto flex-col items-start gap-0.5 border-t bg-muted/40 py-3 pl-5 text-xs">
          <span className="text-muted-foreground">
            Último evento · {formatarData(ultimo.data)} · {rotuloEvento[ultimo.tipo]}
          </span>
          <span className="line-clamp-1">{ultimo.descricao}</span>
        </CardFooter>
      )}
    </Card>
  )
}
