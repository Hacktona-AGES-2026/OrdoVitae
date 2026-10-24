import { CartesianGrid, Line, LineChart, ReferenceDot, XAxis, YAxis } from "recharts"

import { SwalisBadge } from "@/components/dashboard/swalis"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import {
  diasFila,
  formatarData,
  historicoPosicao,
  justificar,
  sinais,
  sinaisTexto,
  solicitacoes,
  TIPO_EVENTO_LABEL,
  type ItemFila,
} from "@/lib/priorizacao"
import { FaixaTag, Movimento, Prazo } from "./marcadores"

type Props = {
  item: ItemFila | null
  frame: number
  dia: number
  onClose: () => void
}

const configPosicao = { posicao: { label: "Posição", color: "var(--chart-3)" } } satisfies ChartConfig

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{titulo}</h3>
      {children}
    </section>
  )
}

function Barra({ label, valor, max, cor }: { label: string; valor: number; max: number; cor: string }) {
  return (
    <div className="grid grid-cols-[8rem_1fr_3.5rem] items-center gap-2 text-xs text-muted-foreground">
      <span>{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", cor)} style={{ width: `${(valor / max) * 100}%` }} />
      </div>
      <span className="text-right tabular-nums">
        {valor}/{max}
      </span>
    </div>
  )
}

function Campo({ k, v, largo }: { k: string; v: React.ReactNode; largo?: boolean }) {
  return (
    <div className={cn(largo && "sm:col-span-2")}>
      <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{k}</dt>
      <dd className="text-sm">{v}</dd>
    </div>
  )
}

export function DetalheDialog({ item, frame, dia, onClose }: Props) {
  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100vh-4rem)] gap-0 overflow-y-auto p-0 sm:max-w-3xl">
        {item && <Conteudo item={item} frame={frame} dia={dia} />}
      </DialogContent>
    </Dialog>
  )
}

function Conteudo({ item, frame, dia }: { item: ItemFila; frame: number; dia: number }) {
  const s = solicitacoes[item.idx]
  const z = sinais(s, dia)
  const total = diasFila[frame].ordem.length
  const espera = Math.max(0, item.score - item.gravidade)
  const lista = sinaisTexto(s, z)
  const eventos = s.eventos.filter((e) => e.dia <= dia).reverse()
  const futuros = s.eventos.length - eventos.length
  const hist = historicoPosicao(item.idx).map((posicao, k) => ({
    dia: formatarData(diasFila[k].data).slice(0, 5),
    posicao,
  }))
  const hba = z.hba1c ?? s.hba1cCadastro

  return (
    <>
      <DialogHeader className="gap-3 border-b bg-muted/40 p-5 pr-12">
        <div className="flex items-center gap-4">
          <div className="text-4xl leading-none font-semibold tracking-tight tabular-nums">
            {item.posicao}
            <small className="ml-1 text-xs font-normal text-muted-foreground">º de {total}</small>
          </div>
          <div className="min-w-0">
            <DialogTitle className="text-lg">{s.nome}</DialogTitle>
            <DialogDescription className="flex gap-3 font-mono text-xs">
              <span>{s.sid}</span>
              <span>{s.pid}</span>
            </DialogDescription>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <FaixaTag faixa={item.faixa} className="rounded-full bg-background px-2 py-1 ring-1 ring-foreground/10" />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-background px-2 py-0.5 ring-1 ring-foreground/10">
            <SwalisBadge classe={item.classe} className="h-5 min-w-7 text-[11px]" /> prazo {item.prazo} d
          </span>
          <span className="rounded-full bg-background px-2 py-1 ring-1 ring-foreground/10">
            <Prazo item={item} /> {item.alemDoPrazo > 0 && "além do prazo"}
          </span>
          <span className="rounded-full bg-background px-2 py-1 tabular-nums ring-1 ring-foreground/10">
            {item.diasEmFila} dias de espera
          </span>
          <Movimento item={item} primeiroDia={frame === 0} />
        </div>
      </DialogHeader>

      <div className="flex flex-col gap-6 p-5">
        <Secao titulo="Por que está nesta posição">
          <p className="rounded-r-lg border-l-2 border-primary bg-muted/50 px-3 py-2 text-sm leading-relaxed">
            {justificar(s, item, z)}
          </p>
          <div className="flex flex-col gap-1.5">
            <Barra label="Gravidade clínica" valor={item.gravidade} max={60} cor="bg-faixa-1" />
            <Barra label="Tempo e atraso" valor={espera} max={40} cor="bg-chart-1" />
            <Barra label="Índice total" valor={item.score} max={100} cor="bg-primary" />
          </div>
        </Secao>

        <Secao titulo="Evolução da posição · 30 dias">
          <ChartContainer config={configPosicao} className="aspect-auto h-32 w-full">
            <LineChart data={hist} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="dia" tickLine={false} axisLine={false} interval={6} fontSize={10} />
              <YAxis reversed tickLine={false} axisLine={false} fontSize={10} domain={["dataMin", "dataMax"]} allowDecimals={false} />
              <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
              <Line
                dataKey="posicao"
                type="monotone"
                stroke="var(--color-posicao)"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              {hist[frame].posicao != null && (
                <ReferenceDot
                  x={hist[frame].dia}
                  y={hist[frame].posicao!}
                  r={4}
                  fill="var(--color-posicao)"
                  stroke="var(--background)"
                  strokeWidth={2}
                />
              )}
            </LineChart>
          </ChartContainer>
        </Secao>

        <Secao titulo="Paciente e procedimento">
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <Campo k="Idade / sexo" v={`${s.idade} anos · ${s.sexo === "F" ? "feminino" : "masculino"}`} />
            <Campo k="Município" v={s.municipio} />
            <Campo k="Especialidade" v={s.especialidade} />
            <Campo
              k="CID principal"
              v={
                <>
                  <span className="font-mono">{s.cidOriginal}</span> · {s.cidDescricao}
                </>
              }
            />
            <Campo
              largo
              k="Procedimento"
              v={
                <>
                  {s.procedimento}{" "}
                  <span className="text-muted-foreground">
                    · risco {s.risco ?? "–"} · porte {s.porte || "–"} · UTI {s.uti || "–"}
                  </span>
                </>
              }
            />
            <Campo k="Dor (EVA)" v={s.dor == null ? "não informada" : `${s.dor} / 10`} />
            <Campo k="Limitação" v={s.limitacao || "não informada"} />
            <Campo k="ASA" v={s.asa ?? "n/d"} />
            <Campo
              k="HbA1c"
              v={
                hba == null
                  ? "–"
                  : `${hba.toLocaleString("pt-BR", { minimumFractionDigits: 1 })}%${z.hba1c == null ? " (cadastro)" : ""}`
              }
            />
            <Campo k="Entrada na fila" v={formatarData(s.dataEntrada)} />
            <Campo
              k="Prioridade manual"
              v={
                <>
                  {s.prioridadeManual || "sem informação"} → <b>{item.classe}</b>
                </>
              }
            />
          </dl>
        </Secao>

        <Secao titulo="Sinais considerados">
          <ul className="flex flex-wrap gap-1.5">
            {lista.length === 0 && (
              <li className="rounded-md bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
                sem sinal de gravidade
              </li>
            )}
            {lista.map((x) => (
              <li
                key={x}
                className={cn(
                  "rounded-md px-2 py-0.5 text-xs font-medium",
                  /bióp|interna|pronto|piora/i.test(x)
                    ? "bg-destructive/10 text-destructive"
                    : "bg-swalis-b/15 text-foreground",
                )}
              >
                {x}
              </li>
            ))}
          </ul>
        </Secao>

        <Secao titulo="Justificativa clínica">
          <p className={cn("rounded-lg bg-muted/50 px-3 py-2 text-sm whitespace-pre-wrap", !s.justificativa && "text-muted-foreground italic")}>
            {s.justificativa || "sem justificativa registrada"}
          </p>
        </Secao>

        <Secao titulo="Observações da regulação">
          <p className={cn("rounded-lg bg-muted/50 px-3 py-2 text-sm whitespace-pre-wrap", !s.observacoes && "text-muted-foreground italic")}>
            {s.observacoes || "sem observações"}
          </p>
        </Secao>

        <Secao titulo={`Eventos até este dia (${eventos.length})${futuros ? ` · ${futuros} depois` : ""}`}>
          <ul className="flex flex-col gap-1.5">
            {eventos.length === 0 && <li className="text-sm text-muted-foreground">Nenhum evento até este dia.</li>}
            {eventos.slice(0, 14).map((e, k) => (
              <li
                key={k}
                className="grid grid-cols-[5.5rem_1fr_auto] items-baseline gap-2 rounded-lg bg-muted/40 px-2.5 py-1.5 text-sm"
              >
                <span className="text-xs text-muted-foreground tabular-nums">{formatarData(e.data)}</span>
                <span>
                  <span className="font-medium">{TIPO_EVENTO_LABEL[e.tipo]}</span>
                  {e.valor != null && e.tipo === "hba1c" && ` · ${e.valor.toLocaleString("pt-BR")}%`}
                  {e.valor != null && e.tipo === "internacao" && ` · ${e.valor} dias`}
                </span>
                <span className="text-xs font-medium text-muted-foreground">{e.resultado.replace(/_/g, " ")}</span>
              </li>
            ))}
          </ul>
        </Secao>
      </div>
    </>
  )
}
