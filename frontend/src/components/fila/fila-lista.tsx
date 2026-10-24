import type { UseQueryResult } from "@tanstack/react-query"
import { ArrowDown, ArrowUp, Clock, FileQuestion, LogOut, MapPin } from "lucide-react"

import type { FichaDTO, ItemFilaDTO, SugestaoDTO } from "@/api/tipos"
import { Skeleton } from "@/components/ui/skeleton"
import { formatarScore, movimento, paciente, rotuloAchado, temDadosInsuficientes, TIPO_SUGESTAO_LABEL } from "@/lib/apresentacao"
import { useFlip } from "@/lib/use-flip"
import { cn } from "@/lib/utils"
import { DecisaoSugestao } from "./decisao-sugestao"
import { BarraClasse, ClasseBadge, Indicadores, MovimentoBadge, Prazo } from "./marcadores"

export type PropsFila = {
  itens: ItemFilaDTO[]
  fichas: Map<string, UseQueryResult<FichaDTO>>
  /** Sugestões pendentes por solicitação (só fazem sentido na fila de hoje). */
  pendentes: Map<string, SugestaoDTO[]>
  data: string
  hoje: string | null
  primeiroDia: boolean
  onAbrir: (item: ItemFilaDTO) => void
}

function Score({ label, valor, sufixo, cor, titulo }: { label: string; valor: number | null; sufixo?: string; cor: string; titulo: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted/60 px-1.5 py-1" title={valor == null ? "Disponível só na fila de hoje" : titulo}>
      <p className="text-[9px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</p>
      <p className="text-sm leading-tight font-semibold tabular-nums">
        {formatarScore(valor)}
        {valor != null && sufixo}
      </p>
      <span className="mt-0.5 block h-0.5 overflow-hidden rounded-full bg-background">
        {valor != null && <span className={cn("block h-full", cor)} style={{ width: `${Math.min(valor, 100)}%` }} />}
      </span>
    </div>
  )
}

const ICONE_SUGESTAO = {
  subir: <ArrowUp className="size-3.5 text-success" />,
  descer: <ArrowDown className="size-3.5 text-destructive" />,
  remover: <LogOut className="size-3.5" />,
} as Record<string, React.ReactNode>

/** Sugestão pendente dentro do card: o regulador decide ali mesmo, lendo a justificativa. */
function BlocoAprovacao({ s, hoje }: { s: SugestaoDTO; hoje: string | null }) {
  return (
    <div className="flex flex-col gap-2 border-t border-dashed bg-swalis-b/5 py-2.5 pr-4 pl-5 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs font-medium">
          {ICONE_SUGESTAO[s.tipo]}
          {TIPO_SUGESTAO_LABEL[s.tipo]}
          {s.classeDe && s.classePara && s.classeDe !== s.classePara && (
            <span className="text-muted-foreground">
              classe {s.classeDe} → <b className="text-foreground">{s.classePara}</b>
            </span>
          )}
          {s.previa?.posicaoDe != null && s.previa.posicaoPara != null && (
            <span className="rounded-md bg-background px-1.5 tabular-nums ring-1 ring-foreground/10">
              se aprovada: {s.previa.posicaoDe}º → <b>{s.previa.posicaoPara}º</b>
            </span>
          )}
          {s.motivos.length > 0 && (
            <span className="text-muted-foreground">· {s.motivos.map((m) => rotuloAchado(m.codigo)).join(", ")}</span>
          )}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{s.justificativa}</p>
        {s.justificativaComparativa && (
          <p className="mt-1 text-xs leading-relaxed">
            {s.ultrapassados ? <b>Ultrapassa {s.ultrapassados} pacientes. </b> : null}
            {s.justificativaComparativa}
          </p>
        )}
      </div>
      <DecisaoSugestao sugestao={s} hoje={hoje} />
    </div>
  )
}

export function FilaLista({ itens, fichas, pendentes, data, hoje, primeiroDia, onAbrir }: PropsFila) {
  const flip = useFlip<HTMLUListElement>(itens)
  const ehHoje = data === hoje

  return (
    <ul ref={flip} className="flex flex-col gap-2">
      {itens.map((item) => {
        const f = fichas.get(item.solicitacaoId)?.data
        const p = f ? paciente(f) : null
        const sugestoes = ehHoje ? (pendentes.get(item.solicitacaoId) ?? []).filter((s) => s.tipo !== "classificacao_inicial") : []
        const dadosInsuf = temDadosInsuficientes(f, data)
        return (
          <li key={item.solicitacaoId} data-flip={item.solicitacaoId}>
            <article
              className={cn(
                "relative overflow-hidden rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 transition-shadow hover:shadow-md",
                item.critico && "ring-2 ring-destructive/70",
                sugestoes.length > 0 && "ring-2 ring-swalis-b/60",
              )}
            >
              <BarraClasse classe={item.classe} className="absolute inset-y-0 left-0 w-1" />
              <button
                type="button"
                onClick={() => onAbrir(item)}
                className="grid w-full grid-cols-[8.5rem_minmax(0,1fr)] gap-x-4 gap-y-2 py-3 pr-4 pl-5 text-left outline-none focus-visible:bg-muted/40 md:grid-cols-[8.5rem_minmax(0,1.3fr)_minmax(0,1.2fr)_8rem_4.5rem]"
              >
                {/* esquerda: posição + scores clínico e de risco lado a lado */}
                <div className="row-span-3 flex flex-col gap-2 md:row-span-2">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl leading-none font-semibold tracking-tight tabular-nums">
                      {item.posicao}
                      <small className="ml-0.5 text-[10px] font-normal text-muted-foreground">º</small>
                    </span>
                    <MovimentoBadge mov={movimento(item, primeiroDia)} />
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    <Score label="Clínico" valor={item.scoreClinico} cor="bg-chart-3" titulo="Score clínico (0–100): estado do paciente, classe e espera" />
                    <Score
                      label="Risco"
                      valor={item.risco == null ? null : Math.round(item.risco * 100)}
                      sufixo="%"
                      cor="bg-destructive"
                      titulo={`Risco cirúrgico: ${item.riscoMotivo ?? ""}`}
                    />
                  </div>
                </div>

                <div className="min-w-0">
                  {p ? (
                    <>
                      <p className="truncate font-medium">{p.nome}</p>
                      <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                        <span>
                          {p.idade ?? "–"} anos · {p.sexo}
                        </span>
                        <span className="inline-flex items-center gap-0.5">
                          <MapPin className="size-3" />
                          {p.municipio}
                        </span>
                        <span className="font-mono text-[10px]">{item.solicitacaoId}</span>
                      </p>
                    </>
                  ) : (
                    <>
                      <Skeleton className="h-5 w-48" />
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">{item.solicitacaoId}</p>
                    </>
                  )}
                </div>

                <div className="col-start-2 min-w-0 md:col-start-auto">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <ClasseBadge classe={item.classe} />
                    <Indicadores item={item} />
                  </div>
                  {p ? (
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      <span className="font-mono text-foreground">{p.cid}</span> · {p.especialidade} · {p.procedimento}
                    </p>
                  ) : (
                    <Skeleton className="mt-1.5 h-3.5 w-56" />
                  )}
                </div>

                <div className="col-start-2 flex items-center gap-3 text-xs md:col-start-auto md:flex-col md:items-start md:gap-0.5">
                  <span className="inline-flex items-center gap-1 text-muted-foreground tabular-nums">
                    <Clock className="size-3" />
                    {item.diasEmFila} d · prazo {item.prazo} d
                  </span>
                  <Prazo item={item} />
                </div>

                <div className="col-start-2 flex items-center gap-2 md:col-start-auto md:flex-col md:items-end md:gap-0.5">
                  <span className="text-[10px] tracking-wider text-muted-foreground uppercase">Final</span>
                  <b className="text-sm tabular-nums">{formatarScore(item.score)}</b>
                </div>

                {p ? (
                  <p className="col-start-2 line-clamp-2 text-xs leading-snug text-muted-foreground md:col-span-4">
                    {p.justificativa || "Sem justificativa clínica registrada."}
                  </p>
                ) : (
                  <Skeleton className="col-start-2 h-3.5 w-full md:col-span-4" />
                )}
              </button>

              {sugestoes.map((s) => (
                <BlocoAprovacao key={s.id} s={s} hoje={hoje} />
              ))}

              {dadosInsuf && (
                <div className="flex items-center gap-1.5 bg-dados-insuf/15 py-1.5 pr-4 pl-5 text-[11px] font-medium text-dados-insuf">
                  <FileQuestion className="size-3.5" />
                  Dados insuficientes — justificativa clínica pobre; a classificação pode estar subestimada.
                </div>
              )}
            </article>
          </li>
        )
      })}
    </ul>
  )
}
