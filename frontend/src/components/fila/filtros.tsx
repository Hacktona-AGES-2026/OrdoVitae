import { SwalisBadge } from "@/components/dashboard/swalis"
import { cn } from "@/lib/utils"
import { CLASSES, FAIXA_NOME, PRAZO, type Classe, type Faixa } from "@/lib/priorizacao"
import { FaixaBarra } from "./marcadores"

export type FiltroPrazo = "todos" | "no_prazo" | "fora"

export type Filtros = {
  faixas: Faixa[]
  classes: Classe[]
  prazo: FiltroPrazo
}

const FAIXAS: Faixa[] = [1, 2, 3, 4, 5]

const chip =
  "inline-flex h-7 items-center gap-1.5 rounded-lg border px-2 text-xs transition-colors hover:bg-muted aria-pressed:border-foreground/40 aria-pressed:bg-muted"

function alternar<T>(lista: T[], v: T) {
  return lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v]
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={titulo}>
      <span className="w-12 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{titulo}</span>
      {children}
    </div>
  )
}

export function FiltrosFila({ valor, onChange }: { valor: Filtros; onChange: (f: Filtros) => void }) {
  const ativos = valor.faixas.length + valor.classes.length + (valor.prazo !== "todos" ? 1 : 0)
  const apagado = (lista: unknown[], ativo: boolean) => lista.length > 0 && !ativo && "opacity-55"

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-muted/30 p-3 ring-1 ring-foreground/5">
      <Grupo titulo="Faixa">
        {FAIXAS.map((f) => {
          const ativo = valor.faixas.includes(f)
          return (
            <button
              key={f}
              type="button"
              aria-pressed={ativo}
              title={FAIXA_NOME[f]}
              onClick={() => onChange({ ...valor, faixas: alternar(valor.faixas, f) })}
              className={cn(chip, apagado(valor.faixas, ativo))}
            >
              <FaixaBarra faixa={f} className="size-2 rounded-[2px]" />
              {f} · {FAIXA_NOME[f]}
            </button>
          )
        })}
      </Grupo>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <Grupo titulo="Classe">
          {CLASSES.map((c) => {
            const ativo = valor.classes.includes(c)
            return (
              <button
                key={c}
                type="button"
                aria-pressed={ativo}
                title={`Prazo ${PRAZO[c]} dias`}
                onClick={() => onChange({ ...valor, classes: alternar(valor.classes, c) })}
                className={cn(chip, "px-1", apagado(valor.classes, ativo))}
              >
                <SwalisBadge classe={c} className="h-5 min-w-7 text-[11px]" />
              </button>
            )
          })}
        </Grupo>
        <Grupo titulo="Prazo">
          {(
            [
              ["todos", "Todos"],
              ["fora", "Fora do prazo"],
              ["no_prazo", "No prazo"],
            ] as [FiltroPrazo, string][]
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={valor.prazo === v}
              onClick={() => onChange({ ...valor, prazo: v })}
              className={chip}
            >
              {label}
            </button>
          ))}
        </Grupo>
        {ativos > 0 && (
          <button
            type="button"
            onClick={() => onChange({ faixas: [], classes: [], prazo: "todos" })}
            className="text-xs text-muted-foreground underline-offset-4 hover:underline sm:ml-auto"
          >
            Limpar filtros ({ativos})
          </button>
        )}
      </div>
    </div>
  )
}
