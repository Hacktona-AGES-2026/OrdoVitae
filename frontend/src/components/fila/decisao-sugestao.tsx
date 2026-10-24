import { Check, Loader2, X } from "lucide-react"
import { useState } from "react"

import { useAprovarSugestao, useRejeitarSugestao } from "@/api/consultas"
import type { StatusSugestao, SugestaoDTO } from "@/api/tipos"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const STATUS: Record<StatusSugestao, { label: string; classe: string }> = {
  pendente: { label: "Pendente", classe: "bg-swalis-b/20 text-foreground" },
  aprovada: { label: "Aprovada", classe: "bg-success/15 text-success" },
  rejeitada: { label: "Rejeitada", classe: "bg-destructive/10 text-destructive" },
  substituida: { label: "Substituída", classe: "bg-muted text-muted-foreground" },
}

export function StatusChip({ s }: { s: SugestaoDTO }) {
  const st = STATUS[s.status]
  const por = s.decididaPor === "simulacao" ? "automática" : s.decididaPor
  return (
    <span
      title={s.decididaEm ? `${st.label} em ${s.decididaEm}${por ? ` (${por})` : ""}` : undefined}
      className={cn("inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-[11px] font-medium", st.classe)}
    >
      {s.status === "aprovada" && <Check className="size-3" />}
      {st.label}
      {s.status === "aprovada" && por === "automática" && <span className="font-normal opacity-75">· auto</span>}
    </span>
  )
}

/** Aprovar/rejeitar uma sugestão pendente. Rejeitar exige comentário (422 no backend). */
export function DecisaoSugestao({ sugestao, hoje, compacto }: { sugestao: SugestaoDTO; hoje: string | null; compacto?: boolean }) {
  const aprovar = useAprovarSugestao(hoje)
  const rejeitar = useRejeitarSugestao(hoje)
  const [rejeitando, setRejeitando] = useState(false)
  const [comentario, setComentario] = useState("")

  if (sugestao.status !== "pendente") return <StatusChip s={sugestao} />

  // já decidida aqui: segura o botão até a lista recarregar (senão um 2º clique dá 409)
  const decidida = [aprovar, rejeitar].some((m) => m.isSuccess && m.variables?.id === sugestao.id)
  const ocupado = aprovar.isPending || rejeitar.isPending || decidida
  const erro = aprovar.error ?? rejeitar.error

  if (rejeitando)
    return (
      <form
        className="flex w-full flex-col gap-1.5"
        onSubmit={(e) => {
          e.preventDefault()
          rejeitar.mutate({ id: sugestao.id, sid: sugestao.solicitacaoId, comentario })
        }}
      >
        <Textarea
          autoFocus
          value={comentario}
          onChange={(e) => setComentario(e.target.value)}
          placeholder="Motivo da rejeição (obrigatório)"
          className="min-h-14 text-xs"
        />
        <div className="flex justify-end gap-1.5">
          <Button type="button" size="xs" variant="ghost" onClick={() => setRejeitando(false)}>
            Cancelar
          </Button>
          <Button type="submit" size="xs" variant="destructive" disabled={!comentario.trim() || ocupado}>
            {rejeitar.isPending && <Loader2 className="animate-spin" />}
            Rejeitar
          </Button>
        </div>
        {erro && <p className="text-[11px] text-destructive">{erro.message}</p>}
      </form>
    )

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <div className="flex gap-1">
        {!compacto && (
          <Button size="xs" variant="ghost" disabled={ocupado} onClick={() => setRejeitando(true)}>
            <X />
            Rejeitar
          </Button>
        )}
        <Button size="xs" disabled={ocupado} onClick={() => aprovar.mutate({ id: sugestao.id, sid: sugestao.solicitacaoId })}>
          {aprovar.isPending ? <Loader2 className="animate-spin" /> : <Check />}
          Aprovar
        </Button>
      </div>
      {erro && <p className="text-[11px] text-destructive">{erro.message}</p>}
    </div>
  )
}
