import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { formatarData } from "@/lib/priorizacao"

const VELOCIDADES = [
  { label: "1×", ms: 1200 },
  { label: "2×", ms: 700 },
  { label: "4×", ms: 350 },
  { label: "8×", ms: 150 },
]

type Props = {
  frame: number
  total: number
  data: string
  primeiraData: string
  ultimaData: string
  tocando: boolean
  velocidade: number
  onFrame: (f: number) => void
  onTocar: () => void
  onVelocidade: (ms: number) => void
}

/** Player flutuante, fixo na base da tela e centralizado. */
export function Player(p: Props) {
  return (
    <div
      role="region"
      aria-label="Reprodução dos dias"
      className="fixed inset-x-0 bottom-4 z-30 mx-auto flex w-[calc(100%-2rem)] flex-col gap-2 rounded-2xl bg-popover/90 px-4 py-3 text-popover-foreground shadow-xl ring-1 ring-foreground/10 backdrop-blur-md md:w-1/2 md:min-w-[36rem]"
    >
      <div className="flex items-center gap-3">
        <div className="w-20 shrink-0">
          <p className="font-heading text-sm leading-tight font-semibold">Dia {p.frame + 1}</p>
          <p className="text-[11px] text-muted-foreground tabular-nums">{formatarData(p.data)}</p>
        </div>
        <div className="flex flex-1 items-center justify-center gap-1.5">
          <Button variant="ghost" size="icon" aria-label="Dia anterior" onClick={() => p.onFrame(p.frame - 1)}>
            <ChevronLeft />
          </Button>
          <Button size="icon-lg" className="rounded-full" aria-label={p.tocando ? "Pausar" : "Reproduzir"} onClick={p.onTocar}>
            {p.tocando ? <Pause /> : <Play />}
          </Button>
          <Button variant="ghost" size="icon" aria-label="Próximo dia" onClick={() => p.onFrame(p.frame + 1)}>
            <ChevronRight />
          </Button>
        </div>
        <div className="flex w-20 shrink-0 justify-end">
          <Select value={String(p.velocidade)} onValueChange={(v) => p.onVelocidade(Number(v))}>
            <SelectTrigger size="sm" className="w-16" aria-label="Velocidade">
              <SelectValue>{(v: string) => VELOCIDADES.find((x) => String(x.ms) === v)?.label}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {VELOCIDADES.map((v) => (
                <SelectItem key={v.ms} value={String(v.ms)}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
        <span>{formatarData(p.primeiraData).slice(0, 5)}</span>
        <Slider
          aria-label="Dia"
          min={0}
          max={p.total - 1}
          step={1}
          value={[p.frame]}
          onValueChange={(v) => p.onFrame(Array.isArray(v) ? v[0] : v)}
          className="flex-1"
        />
        <span>{formatarData(p.ultimaData).slice(0, 5)}</span>
      </div>
    </div>
  )
}
