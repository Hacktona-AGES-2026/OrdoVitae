import { cn } from "@/lib/utils"
import type { ClasseSwalis } from "@/data/mock-fila"

const estiloBadge: Record<ClasseSwalis, string> = {
  A1: "bg-swalis-a1/15 text-swalis-a1 ring-swalis-a1/30",
  A2: "bg-swalis-a2/15 text-swalis-a2 ring-swalis-a2/30",
  B: "bg-swalis-b/15 text-swalis-b ring-swalis-b/30",
  C: "bg-swalis-c/15 text-swalis-c ring-swalis-c/30",
  D: "bg-swalis-d/15 text-swalis-d ring-swalis-d/30",
}

export function SwalisBadge({ classe, className }: { classe: ClasseSwalis; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 min-w-9 items-center justify-center rounded-md px-1.5 text-xs font-semibold tabular-nums ring-1 ring-inset",
        estiloBadge[classe],
        className,
      )}
    >
      {classe}
    </span>
  )
}
