import { AlertTriangle, Handshake, Sparkles } from "lucide-react"

import { useDecisaoCompartilhada } from "@/api/consultas"
import type { NivelAtencao } from "@/api/tipos"
import { Skeleton } from "@/components/ui/skeleton"
import { formatarData } from "@/lib/apresentacao"
import { cn } from "@/lib/utils"

const STATUS_ADESAO: Record<string, string> = {
  quebra_adesao: "Quebra de adesão",
  alerta_manejo: "Alerta de manejo pré-operatório",
  reavaliar_indicacao: "Reavaliar indicação",
  conflito_decisao: "Conflito de decisão",
  barreira_social: "Barreira social / logística",
  adesao_positiva: "Adesão positiva",
  preferencia_valida: "Preferência do paciente válida",
  padrao: "Fluxo padrão",
}

const NIVEL: Record<NivelAtencao, { label: string; classe: string }> = {
  critico: { label: "atenção crítica", classe: "bg-destructive/15 text-destructive" },
  moderado: { label: "atenção moderada", classe: "bg-swalis-b/20 text-foreground" },
  informativo: { label: "informativo", classe: "bg-success/15 text-success" },
  nenhum: { label: "sem alerta", classe: "bg-muted text-muted-foreground" },
}

/**
 * Resumo da decisão compartilhada médico–paciente (motor secundário). Fica em roxo para não ser
 * confundido com a priorização: não mexe na fila, orienta a conversa do atendente com o paciente.
 */
export function DecisaoCompartilhadaCard({ sid, hoje }: { sid: string; hoje: string | null }) {
  const { data: d, isPending, error } = useDecisaoCompartilhada(sid, hoje)

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-decisao/30 bg-decisao/8 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <Handshake className="size-4 text-decisao" />
        <h3 className="text-sm font-semibold text-decisao">Decisão compartilhada · resumo para o atendente</h3>
        {d && (
          <span className={cn("rounded-md px-1.5 py-0.5 text-[11px] font-medium", NIVEL[d.nivelAtencaoMaximo].classe)}>
            {STATUS_ADESAO[d.statusAdesao] ?? d.statusAdesao} · {NIVEL[d.nivelAtencaoMaximo].label}
          </span>
        )}
      </header>

      {isPending && <Skeleton className="h-12 w-full bg-decisao/10" />}
      {error && <p className="text-sm text-destructive">{error.message}</p>}
      {d && (
        <>
          <p className="text-sm leading-relaxed">{d.resumoMedico}</p>

          {d.temConflitoClinico && (
            <p className="flex items-start gap-1.5 rounded-lg bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              Conflito clínico: a preferência ou conduta do paciente não é segura diante da gravidade do quadro.
            </p>
          )}

          {d.itens.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {d.itens.map((i) => (
                <li key={i.codigo} className="rounded-lg bg-background/70 px-3 py-2 ring-1 ring-decisao/15">
                  <p className="flex flex-wrap items-center gap-2 text-xs font-medium">
                    {i.titulo}
                    <span className={cn("rounded px-1 text-[10px]", NIVEL[i.nivelAtencao].classe)}>{NIVEL[i.nivelAtencao].label}</span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{i.recomendacaoConduta}</p>
                  {i.conflitoClinico && <p className="mt-1 text-xs text-destructive">{i.conflitoClinico}</p>}
                  {i.trechoEvidencia && <p className="mt-1 text-[11px] italic">“{i.trechoEvidencia}”</p>}
                </li>
              ))}
            </ul>
          )}

          <p className="flex items-start gap-1.5 border-t border-decisao/20 pt-2 text-[11px] text-muted-foreground">
            <Sparkles className="mt-0.5 size-3 shrink-0 text-decisao" />
            <span>
              Análise gerada com apoio de LLM e está sujeita a erros. Confirme as informações com o paciente e o médico antes de agir.
              {d.dataReferencia && ` Considera os dados recebidos até ${formatarData(d.dataReferencia)}.`}
            </span>
          </p>
        </>
      )}
    </section>
  )
}
