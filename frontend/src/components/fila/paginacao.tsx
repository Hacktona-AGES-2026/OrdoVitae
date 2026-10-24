import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"

function paginas(atual: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const set = new Set([1, total, atual - 1, atual, atual + 1].filter((p) => p >= 1 && p <= total))
  const ord = [...set].sort((a, b) => a - b)
  const out: (number | "…")[] = []
  ord.forEach((p, i) => {
    if (i > 0 && p - ord[i - 1] > 1) out.push("…")
    out.push(p)
  })
  return out
}

type Props = {
  pagina: number
  totalPaginas: number
  totalItens: number
  porPagina: number
  onPagina: (p: number) => void
}

export function Paginacao({ pagina, totalPaginas, totalItens, porPagina, onPagina }: Props) {
  if (totalItens === 0) return null
  const ini = (pagina - 1) * porPagina + 1
  const fim = Math.min(pagina * porPagina, totalItens)

  return (
    <nav aria-label="Paginação" className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-xs text-muted-foreground tabular-nums">
        {ini}–{fim} de {totalItens}
      </p>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)}>
          <ChevronLeft />
          Anterior
        </Button>
        {paginas(pagina, totalPaginas).map((p, i) =>
          p === "…" ? (
            <span key={`e${i}`} className="px-1 text-xs text-muted-foreground">
              …
            </span>
          ) : (
            <Button
              key={p}
              variant={p === pagina ? "outline" : "ghost"}
              size="icon-sm"
              aria-current={p === pagina ? "page" : undefined}
              onClick={() => onPagina(p)}
              className="tabular-nums"
            >
              {p}
            </Button>
          ),
        )}
        <Button variant="ghost" size="sm" disabled={pagina >= totalPaginas} onClick={() => onPagina(pagina + 1)}>
          Próxima
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
