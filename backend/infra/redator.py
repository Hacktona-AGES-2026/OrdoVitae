"""Redatores da justificativa. O template é o padrão; o LLM só reescreve, e cai no template em qualquer falha."""
import os
import re

from motor.modelos import Avaliacao, Sugestao

REFERENCIA = re.compile(r"\b(?:SOL|EVT|PAC)-[\w-]+")
MODELO_PADRAO = "gemini-2.5-flash"


class RedatorTemplate:
    """Usa a justificativa determinística montada pelo motor (motor.decisor._justificar)."""

    def justificar(self, s: Sugestao, av: Avaliacao) -> str:
        return s.justificativa


class RedatorLLM:
    """Reescreve a justificativa em linguagem do regulador, sem acrescentar fatos.

    Guarda: toda referência citada (SOL-…, EVT-…) tem que estar nos achados recebidos; senão, template.
    """

    def __init__(self, chave: str | None = None, modelo: str | None = None, cliente=None):
        self.chave = chave or os.environ.get("GEMINI_KEY")
        self.modelo = modelo or os.environ.get("ORDO_MODELO_LLM", MODELO_PADRAO)
        self.cliente = cliente
        self.template = RedatorTemplate()

    def justificar(self, s: Sugestao, av: Avaliacao) -> str:
        base = self.template.justificar(s, av)
        if self.cliente is None and not self.chave:
            return base
        try:
            texto = self._chamar(self._prompt(s, base)).strip()
        except Exception:
            return base
        permitidas = set(REFERENCIA.findall(base)) | {a.evidencia.ref for a in s.motivos} | {s.solicitacao_id}
        if not texto or any(r not in permitidas for r in REFERENCIA.findall(texto)):
            return base
        return texto

    def _prompt(self, s: Sugestao, base: str) -> str:
        return ("Reescreva a justificativa abaixo para um médico regulador, em português, em no máximo 3 frases. "
                "Use SOMENTE os fatos presentes nela; não acrescente diagnósticos, datas, números ou referências. "
                "Mantenha as referências (SOL-…, EVT-…) exatamente como estão.\n\n"
                f"Sugestão: {s.tipo.value} ({s.classe_de} → {s.classe_para})\nJustificativa: {base}")

    def _chamar(self, prompt: str) -> str:
        if self.cliente is None:
            from google import genai
            self.cliente = genai.Client(api_key=self.chave)
        resposta = self.cliente.models.generate_content(model=self.modelo, contents=prompt,
                                                        config={"temperature": 0})
        return resposta.text or ""
