// Aprovação das subidas de posição na fila.
// Sem backend, toda subida já nasce aprovada (APROVACAO_AUTOMATICA). Quando a API
// existir: troque a flag para false, carregue o status em `statusInicial` e
// implemente a chamada em `enviarAprovacao`.

import { useCallback, useState } from "react"

export type StatusAprovacao = "pendente" | "enviando" | "aprovado"

export const APROVACAO_AUTOMATICA = true

/** Identifica uma subida: a mesma solicitação pode subir em dias diferentes. */
export const chaveSubida = (data: string, sid: string) => `${data}:${sid}`

function statusInicial(): StatusAprovacao {
  return APROVACAO_AUTOMATICA ? "aprovado" : "pendente"
}

async function enviarAprovacao(chave: string): Promise<void> {
  // TODO(backend): POST /api/fila/subidas/{chave}/aprovar
  void chave
}

export function useAprovacoes() {
  const [status, setStatus] = useState<Record<string, StatusAprovacao>>({})

  const statusDe = useCallback((chave: string) => status[chave] ?? statusInicial(), [status])

  const aprovar = useCallback(async (chave: string) => {
    setStatus((s) => ({ ...s, [chave]: "enviando" }))
    try {
      await enviarAprovacao(chave)
      setStatus((s) => ({ ...s, [chave]: "aprovado" }))
    } catch {
      setStatus((s) => ({ ...s, [chave]: "pendente" }))
    }
  }, [])

  return { statusDe, aprovar }
}
