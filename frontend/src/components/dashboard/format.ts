import { PRAZO_SWALIS, type ClasseSwalis, type Severidade, type TipoEvento } from "@/data/mock-fila"

export function formatarData(iso: string) {
  const [a, m, d] = iso.split("-")
  return `${d}/${m}/${a}`
}

export const rotuloEvento: Record<TipoEvento, string> = {
  biopsia: "Biópsia",
  hba1c: "HbA1c",
  pronto_socorro: "Pronto-socorro",
  internacao: "Internação",
  exame_imagem: "Imagem",
  consulta_reavaliacao: "Reavaliação",
  contato_telefonico: "Contato telefônico",
  falta: "Falta",
}

export const corSwalis: Record<ClasseSwalis, string> = {
  A1: "var(--swalis-a1)",
  A2: "var(--swalis-a2)",
  B: "var(--swalis-b)",
  C: "var(--swalis-c)",
  D: "var(--swalis-d)",
}

export const estiloAlerta: Record<Severidade, string> = {
  critico: "bg-destructive/10 text-destructive",
  atencao: "bg-swalis-b/15 text-foreground",
  info: "bg-muted text-muted-foreground",
}

/** Quanto do prazo SWALIS já foi consumido (pode passar de 100%). */
export function consumoPrazo(classe: ClasseSwalis, diasEmFila: number) {
  const prazo = PRAZO_SWALIS[classe]
  return { prazo, pct: Math.round((diasEmFila / prazo) * 100), vencido: diasEmFila > prazo }
}
