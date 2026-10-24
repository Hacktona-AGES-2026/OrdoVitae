import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { distribuicaoSwalis, movimentoFila } from "@/data/mock-fila"
import { cn } from "@/lib/utils"
import { corSwalis } from "./format"

const kpis = [
  { label: "Solicitações na fila", valor: "941", detalhe: "+2 vs. ontem" },
  { label: "Classe A com prazo vencido", valor: "61", detalhe: "54% da classe A", alerta: true },
  { label: "Espera mediana", valor: "214 d", detalhe: "−3 d em 30 dias" },
  { label: "Prontos para operar", valor: "412", detalhe: "pré-op completo" },
]

export function KpiRow() {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {kpis.map((k) => (
        <Card key={k.label} size="sm">
          <CardHeader>
            <CardDescription>{k.label}</CardDescription>
            <p
              className={cn(
                "font-heading text-3xl font-semibold tracking-tight tabular-nums",
                k.alerta && "text-destructive",
              )}
            >
              {k.valor}
            </p>
            <p className="text-xs text-muted-foreground">{k.detalhe}</p>
          </CardHeader>
        </Card>
      ))}
    </div>
  )
}

const configDistribuicao = {
  total: { label: "No prazo" },
  vencidos: { label: "Vencidos", color: "var(--destructive)" },
} satisfies ChartConfig

const configMovimento = {
  entradas: { label: "Entradas", color: "var(--chart-3)" },
  saidas: { label: "Cirurgias / saídas", color: "var(--chart-1)" },
} satisfies ChartConfig

export function OverviewCharts() {
  const distribuicao = distribuicaoSwalis.map((d) => ({ ...d, noPrazo: d.total - d.vencidos }))

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Fila por classe SWALIS</CardTitle>
          <CardDescription>Solicitações no prazo e com prazo vencido</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={configDistribuicao} className="aspect-auto h-44 w-full">
            <BarChart data={distribuicao} layout="vertical" margin={{ left: 0, right: 8 }}>
              <CartesianGrid horizontal={false} />
              <YAxis dataKey="classe" type="category" tickLine={false} axisLine={false} width={28} />
              <XAxis type="number" hide />
              <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
              <Bar dataKey="noPrazo" name="total" stackId="a" radius={[4, 0, 0, 4]} isAnimationActive={false}>
                {distribuicao.map((d) => (
                  <Cell key={d.classe} fill={corSwalis[d.classe]} fillOpacity={0.85} />
                ))}
              </Bar>
              <Bar
                dataKey="vencidos"
                stackId="a"
                fill="var(--color-vencidos)"
                fillOpacity={0.25}
                stroke="var(--color-vencidos)"
                strokeOpacity={0.6}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Movimento diário</CardTitle>
          <CardDescription>Entradas e saídas da fila · últimos 14 dias</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={configMovimento} className="aspect-auto h-44 w-full">
            <BarChart data={movimentoFila} margin={{ left: -20, right: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="dia" tickLine={false} axisLine={false} interval={1} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} fontSize={11} />
              <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar dataKey="entradas" fill="var(--color-entradas)" radius={3} isAnimationActive={false} />
              <Bar dataKey="saidas" fill="var(--color-saidas)" radius={3} isAnimationActive={false} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  )
}
