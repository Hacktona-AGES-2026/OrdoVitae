import { LayoutGrid, List, Search } from "lucide-react"
import { useMemo, useState } from "react"

import { KpiRow, OverviewCharts } from "@/components/dashboard/overview"
import { QueueCard } from "@/components/dashboard/queue-card"
import { QueueList } from "@/components/dashboard/queue-list"
import { SwalisBadge } from "@/components/dashboard/swalis"
import { ThemeToggle } from "@/components/theme-toggle"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DESCRICAO_SWALIS, fila, PRAZO_SWALIS, type ClasseSwalis } from "@/data/mock-fila"
import { cn } from "@/lib/utils"

const CLASSES: ClasseSwalis[] = ["A1", "A2", "B", "C", "D"]

function App() {
  const [busca, setBusca] = useState("")
  const [classes, setClasses] = useState<ClasseSwalis[]>([])

  const itens = useMemo(() => {
    const termo = busca.trim().toLowerCase()
    return fila.filter(
      (s) =>
        (classes.length === 0 || classes.includes(s.swalis)) &&
        (!termo ||
          [s.nome, s.procedimento, s.cid, s.municipio, s.especialidade].some((v) =>
            v.toLowerCase().includes(termo),
          )),
    )
  }, [busca, classes])

  const alternarClasse = (c: ClasseSwalis) =>
    setClasses((atual) => (atual.includes(c) ? atual.filter((x) => x !== c) : [...atual, c]))

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4">
          <div className="flex items-baseline gap-3">
            <span className="font-heading text-lg font-semibold tracking-tight">OrdoVitae</span>
            <span className="hidden text-sm text-muted-foreground sm:inline">Fila cirúrgica eletiva</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Atualizado em 23/10/2026 · 06:00
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
        <KpiRow />
        <OverviewCharts />

        <section className="flex flex-col gap-4">
          <Tabs defaultValue="cards" className="gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="font-heading text-xl font-semibold tracking-tight">Fila de prioridade</h2>
                <p className="text-sm text-muted-foreground">
                  Ordenada pelo score clínico, recalculado diariamente a partir dos eventos de espera.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={busca}
                    onChange={(e) => setBusca(e.target.value)}
                    placeholder="Paciente, procedimento, CID…"
                    className="w-64 pl-8"
                  />
                </div>
                <TabsList>
                  <TabsTrigger value="cards" aria-label="Ver como cards">
                    <LayoutGrid />
                    Cards
                  </TabsTrigger>
                  <TabsTrigger value="lista" aria-label="Ver como lista">
                    <List />
                    Lista
                  </TabsTrigger>
                </TabsList>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filtrar por classe SWALIS">
              {CLASSES.map((c) => {
                const ativo = classes.includes(c)
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => alternarClasse(c)}
                    aria-pressed={ativo}
                    title={`${DESCRICAO_SWALIS[c]} · prazo ${PRAZO_SWALIS[c]} dias`}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors hover:bg-muted",
                      ativo ? "border-foreground/40 bg-muted" : "border-border",
                      classes.length > 0 && !ativo && "opacity-60",
                    )}
                  >
                    <SwalisBadge classe={c} className="h-5 min-w-7" />
                    <span className="text-muted-foreground">{PRAZO_SWALIS[c]} d</span>
                  </button>
                )
              })}
              {classes.length > 0 && (
                <button
                  type="button"
                  onClick={() => setClasses([])}
                  className="px-2 text-xs text-muted-foreground underline-offset-4 hover:underline"
                >
                  Limpar
                </button>
              )}
            </div>

            <TabsContent value="cards">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {itens.map((item) => (
                  <QueueCard key={item.solicitacaoId} item={item} />
                ))}
              </div>
            </TabsContent>
            <TabsContent value="lista">
              <QueueList itens={itens} />
            </TabsContent>
            {itens.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Nenhuma solicitação encontrada com esses filtros.
              </p>
            )}
          </Tabs>
        </section>
      </main>
    </div>
  )
}

export default App
