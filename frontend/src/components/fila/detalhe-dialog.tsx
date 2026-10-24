import { Bot, FileText } from "lucide-react"
import { CartesianGrid, Line, LineChart, ReferenceDot, XAxis, YAxis } from "recharts"

import { useFicha, useFilaDoDia } from "@/api/consultas"
import type { AchadoDTO, FichaDTO, ItemFilaDTO } from "@/api/tipos"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import {
  achadoGrave,
  FONTE_LABEL,
  formatarData,
  formatarDataCurta,
  formatarScore,
  movimento,
  paciente,
  rotuloAchado,
  TIPO_SUGESTAO_LABEL,
} from "@/lib/apresentacao"
import { cn } from "@/lib/utils"
import { DecisaoCompartilhadaCard } from "./decisao-compartilhada"
import { DecisaoSugestao } from "./decisao-sugestao"
import { ClasseBadge, Indicadores, MovimentoBadge, Prazo } from "./marcadores"

type Props = {
  sid: string | null
  /** Item da fila no dia exibido (ausente se o paciente não está na fila desse dia). */
  item: ItemFilaDTO | null
  data: string
  hoje: string | null
  primeiroDia: boolean
  totalNaFila: number
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

function Campo({ k, v, largo }: { k: string; v: React.ReactNode; largo?: boolean }) {
  return (
    <div className={cn(largo && "sm:col-span-2")}>
      <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{k}</dt>
      <dd className="text-sm">{v || "–"}</dd>
    </div>
  )
}

export function DetalheDialog(props: Props) {
  return (
    <Dialog open={props.sid !== null} onOpenChange={(open) => !open && props.onClose()}>
      <DialogContent className="max-h-[calc(100vh-4rem)] gap-0 overflow-y-auto p-0 sm:max-w-3xl">
        {props.sid && <Conteudo {...props} sid={props.sid} />}
      </DialogContent>
    </Dialog>
  )
}

/** Linha do paciente na fila do dia quando ele não está na página aberta (ex.: aberto pelo painel do dia):
 *  sem isso o cabeçalho mostrava "fora da fila" para quem estava, por exemplo, em 65º. */
function useItemDoDia(sid: string, daPagina: ItemFilaDTO | null, ficha: FichaDTO | undefined, data: string, hoje: string | null) {
  const posicao =
    daPagina || !ficha ? null
    : data === hoje ? (ficha.ativa ? ficha.posicao : null)
    : (ficha.historico.find((h) => h.data === data)?.posicao ?? null)
  const q = useFilaDoDia(posicao ? data : null, hoje, (posicao ?? 1) - 1, 1)
  return daPagina ?? q.data?.ordem.find((i) => i.solicitacaoId === sid) ?? null
}

function Conteudo({ sid, item: daPagina, data, hoje, primeiroDia, totalNaFila }: Props & { sid: string }) {
  const { data: ficha, isPending, error } = useFicha(sid)
  const item = useItemDoDia(sid, daPagina, ficha, data, hoje)
  const p = ficha ? paciente(ficha) : null

  return (
    <>
      <DialogHeader className="gap-3 border-b bg-muted/40 p-5 pr-12">
        <div className="flex items-center gap-4">
          <div className="text-4xl leading-none font-semibold tracking-tight tabular-nums">
            {item ? item.posicao : "—"}
            <small className="ml-1 text-xs font-normal text-muted-foreground">
              {item ? `º de ${totalNaFila}` : "fora da fila"}
            </small>
          </div>
          <div className="min-w-0">
            <DialogTitle className="text-lg">{p ? p.nome : <Skeleton className="h-6 w-56" />}</DialogTitle>
            <DialogDescription className="flex flex-wrap gap-x-3 font-mono text-xs">
              <span>{sid}</span>
              {p?.pacienteId && <span>{p.pacienteId}</span>}
              <span className="font-sans">em {formatarData(data)}</span>
            </DialogDescription>
          </div>
        </div>
        {item && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-background px-2 py-0.5 ring-1 ring-foreground/10">
              <ClasseBadge classe={item.classe} /> prazo {item.prazo} d
            </span>
            <span className="rounded-full bg-background px-2 py-1 ring-1 ring-foreground/10">
              <Prazo item={item} /> {item.alemDoPrazo > 0 && "além do prazo"}
            </span>
            <span className="rounded-full bg-background px-2 py-1 tabular-nums ring-1 ring-foreground/10">
              {item.diasEmFila} dias de espera
            </span>
            <MovimentoBadge mov={movimento(item, primeiroDia)} />
            <Indicadores item={item} />
          </div>
        )}
      </DialogHeader>

      <div className="flex flex-col gap-6 p-5">
        <DecisaoCompartilhadaCard sid={sid} hoje={hoje} />
        {error && <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error.message}</p>}
        {isPending && <Carregando />}
        {ficha && p && (
          <>
            <Scores ficha={ficha} item={item} ehHoje={data === hoje} />
            <Historico ficha={ficha} data={data} posicaoHoje={data === hoje ? (item?.posicao ?? null) : null} />
            <Secao titulo={`Achados (${ficha.achados.length})`}>
              <Achados achados={ficha.achados} data={data} />
            </Secao>
            <Secao titulo="Paciente e procedimento">
              <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                <Campo k="Idade / sexo" v={`${p.idade ?? "–"} anos · ${p.sexo === "F" ? "feminino" : p.sexo === "M" ? "masculino" : p.sexo}`} />
                <Campo k="Município" v={`${p.municipio}${p.distanciaKm != null ? ` · ${p.distanciaKm} km` : ""}`} />
                <Campo k="Especialidade" v={p.especialidade} />
                <Campo k="CID principal" v={<><span className="font-mono">{p.cid}</span> · {p.cidDescricao}</>} />
                <Campo largo k="Procedimento" v={p.procedimento} />
                <Campo k="Dor (EVA)" v={p.dor == null ? "não informada" : `${p.dor} / 10`} />
                <Campo k="Limitação" v={p.limitacao || "não informada"} />
                <Campo k="ASA" v={p.asa || "sem ASA"} />
                <Campo k="Comorbidades" v={p.comorbidades} />
                <Campo k="Entrada na fila" v={p.dataEntrada && formatarData(p.dataEntrada)} />
                <Campo k="Prioridade manual" v={<>{p.prioridadeManual || "sem informação"} → <b>{ficha.classe}</b></>} />
              </dl>
            </Secao>
            <Secao titulo="Justificativa clínica">
              <Texto valor={p.justificativa} vazio="sem justificativa registrada" />
            </Secao>
            {p.observacoes && (
              <Secao titulo="Observações da regulação">
                <Texto valor={p.observacoes} vazio="" />
              </Secao>
            )}
            <Secao titulo={`Sugestões do motor (${ficha.sugestoes.length})`}>
              <ul className="flex flex-col gap-2">
                {[...ficha.sugestoes].reverse().map((s) => (
                  <li key={s.id} className={cn("flex flex-col gap-1.5 rounded-lg bg-muted/40 px-3 py-2", s.criadaEm > data && "opacity-45")}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium">
                          {TIPO_SUGESTAO_LABEL[s.tipo]}
                          {s.classePara && (
                            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                              {s.classeDe && s.classeDe !== s.classePara ? `${s.classeDe} → ` : ""}
                              {s.classePara}
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-muted-foreground tabular-nums">
                          {formatarData(s.criadaEm)}
                          {s.criadaEm > data && <b className="ml-1.5 font-medium">depois deste dia</b>}
                        </p>
                      </div>
                      <DecisaoSugestao sugestao={s} hoje={hoje} />
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">{(s.status === "pendente" && s.explicacao) || s.justificativa}</p>
                    {s.comentario && <p className="text-xs italic">“{s.comentario}”</p>}
                  </li>
                ))}
              </ul>
            </Secao>
          </>
        )}
      </div>
    </>
  )
}

function Carregando() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  )
}

function Texto({ valor, vazio }: { valor: string; vazio: string }) {
  return (
    <p className={cn("rounded-lg bg-muted/50 px-3 py-2 text-sm whitespace-pre-wrap", !valor && "text-muted-foreground italic")}>
      {valor || vazio}
    </p>
  )
}

function Barra({ label, valor, max, cor, sufixo }: { label: string; valor: number | null; max: number; cor: string; sufixo?: string }) {
  return (
    <div className="grid grid-cols-[9rem_1fr_4rem] items-center gap-2 text-xs text-muted-foreground">
      <span>{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        {valor != null && <div className={cn("h-full rounded-full", cor)} style={{ width: `${Math.min((valor / max) * 100, 100)}%` }} />}
      </div>
      <span className="text-right tabular-nums">
        {valor == null ? "–" : `${formatarScore(valor)}${sufixo ?? ""}`}
      </span>
    </div>
  )
}

/** Composição do score. Item de hoje traz tudo; foto antiga só o score final — o resto vem da ficha (estado atual). */
function Scores({ ficha, item, ehHoje }: { ficha: FichaDTO; item: ItemFilaDTO | null; ehHoje: boolean }) {
  return (
    <Secao titulo="Por que está nesta posição">
      <div className="flex flex-col gap-1.5">
        <Barra label="Score final" valor={item?.score ?? null} max={100} cor="bg-primary" />
        <Barra label="Score clínico" valor={item?.scoreClinico ?? null} max={100} cor="bg-chart-3" />
        <Barra label="OrdoScore clínico" valor={item?.ordoClinico ?? ficha.ordoClinico} max={100} cor="bg-chart-1" />
        <Barra label="Risco cirúrgico" valor={Math.round((item?.risco ?? ficha.risco) * 100)} max={100} cor="bg-destructive" sufixo="%" />
      </div>
      <p className="text-xs text-muted-foreground">
        {!ehHoje && "Neste dia o backend guarda só o score final; OrdoScore e risco são os valores atuais. "}
        Risco: {item?.riscoMotivo ?? ficha.riscoMotivo}
        {item?.asaEstimado && " (ASA estimado pelas comorbidades)"}. Quanto maior o risco, mais o score final é reduzido.
      </p>
    </Secao>
  )
}

/**
 * `historico` vem das fotos diárias. A foto de hoje é tirada quando o dia começa e não acompanha
 * aprovações feitas depois, então no dia de hoje o último ponto usa a posição ao vivo da fila.
 */
function Historico({ ficha, data, posicaoHoje }: { ficha: FichaDTO; data: string; posicaoHoje: number | null }) {
  if (ficha.historico.length === 0) return null
  const pontos = ficha.historico.map((h) => ({
    dia: formatarDataCurta(h.data),
    data: h.data,
    posicao: h.data === data && posicaoHoje != null ? posicaoHoje : h.posicao,
    score: h.score,
  }))
  const atual = pontos.find((h) => h.data === data)
  return (
    <Secao titulo={`Evolução da posição · ${pontos.length} dias`}>
      <ChartContainer config={configPosicao} className="aspect-auto h-32 w-full">
        <LineChart data={pontos} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="dia" tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} fontSize={10} />
          <YAxis reversed tickLine={false} axisLine={false} fontSize={10} domain={["dataMin", "dataMax"]} allowDecimals={false} />
          <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
          <Line dataKey="posicao" type="monotone" stroke="var(--color-posicao)" strokeWidth={2} dot={false} isAnimationActive={false} />
          {atual && <ReferenceDot x={atual.dia} y={atual.posicao} r={4} fill="var(--color-posicao)" stroke="var(--background)" strokeWidth={2} />}
        </LineChart>
      </ChartContainer>
    </Secao>
  )
}

function Achados({ achados, data }: { achados: AchadoDTO[]; data: string }) {
  if (achados.length === 0) return <p className="text-sm text-muted-foreground">Nenhum achado registrado.</p>
  return (
    <ul className="flex flex-col gap-1.5">
      {[...achados]
        .sort((a, b) => (b.dataFato ?? "").localeCompare(a.dataFato ?? ""))
        .map((a, i) => (
          <li
            key={`${a.ref}-${a.codigo}-${i}`}
            className={cn(
              "grid grid-cols-[auto_1fr] gap-x-2.5 gap-y-0.5 rounded-lg bg-muted/40 px-3 py-2",
              a.dataFato && a.dataFato > data && "opacity-45",
            )}
          >
            <span
              className={cn(
                "row-span-2 mt-0.5 h-fit rounded-md px-1.5 py-0.5 text-[11px] font-medium",
                achadoGrave(a) ? "bg-destructive/10 text-destructive" : a.codigo === "MELHORA" ? "bg-success/15 text-success" : "bg-swalis-b/20",
              )}
            >
              {rotuloAchado(a.codigo)}
            </span>
            <p className="text-xs text-muted-foreground">
              {a.dataFato ? formatarData(a.dataFato) : "sem data"} · {FONTE_LABEL[a.fonte] ?? a.fonte} · {a.dimensao}
              {a.dataFato && a.dataFato > data && <b className="ml-1.5 font-medium">depois deste dia</b>}
              <span className="ml-1.5 inline-flex items-center gap-0.5" title={`Extraído por ${a.origem}, confiança ${Math.round(a.confianca * 100)}%`}>
                {a.origem === "llm" ? <Bot className="size-3" /> : <FileText className="size-3" />}
                {a.origem}
                {a.confianca < 1 && ` ${Math.round(a.confianca * 100)}%`}
              </span>
            </p>
            <p className="text-xs">“{a.trecho}”</p>
          </li>
        ))}
    </ul>
  )
}
