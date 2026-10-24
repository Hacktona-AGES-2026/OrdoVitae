"""Redatores das justificativas que o regulador lê.

- `justificar`: texto gravado quando a sugestão é criada. Sempre o template determinístico do motor
  (a simulação cria milhares de sugestões; chamar o LLM aqui seria lento e caro).
- `explicar`: o texto mostrado ao lado do botão Aprovar, gerado quando a sugestão pendente é exibida.
  Junta "por que mudou" + "por que fica nessa posição". O LLM só REDIGE a partir dos fatos estruturados;
  qualquer falha (sem chave, timeout, referência inventada) cai no template curto.
"""
import os
import re
from collections.abc import Callable

from motor.modelos import Avaliacao, Sugestao, TipoSugestao as T

REFERENCIA = re.compile(r"\b(?:SOL|EVT|PAC|OBS)-[\w-]+")
NOMES = {"estado": "estado clínico", "classe": "classe SWALIS", "espera": "tempo de espera", "risco": "risco"}
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODELO_PADRAO = "deepseek-flash"


TIPO = {"subir": "subir na fila", "descer": "descer na fila", "classificacao_inicial": "classificação inicial",
        "remover": "remover da fila", "alerta": "alerta"}


def _rotulo(codigo: str) -> str:
    return codigo.lower().replace("_", " ").replace("hba1c", "HbA1c").replace("cid", "CID")


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _fatos(s: Sugestao) -> list[str]:
    """Fatos estruturados da sugestão, em linhas curtas (entrada do LLM e base do template)."""
    fatos = [f"Sugestão: {TIPO[s.tipo.value]} ({s.solicitacao_id})."]
    if s.classe_de and s.classe_para and s.classe_de != s.classe_para:
        fatos.append(f"Classe SWALIS: {s.classe_de} → {s.classe_para}.")
    if s.ordo_clinico_de is not None and s.ordo_clinico_para is not None:
        fatos.append(f"Estado clínico: {_num(s.ordo_clinico_de)} → {_num(s.ordo_clinico_para)}.")
    if s.posicao_de is not None and s.posicao_para is not None:
        fatos.append(f"Posição na fila: {s.posicao_de}º → {s.posicao_para}º "
                     f"(score {_num(s.ordo_de or 0)} → {_num(s.ordo_para or 0)}).")
    for a in s.motivos[:4]:
        data = a.data_fato.strftime("%d/%m/%Y") if a.data_fato else "sem data"
        trecho = f' — "{a.evidencia.trecho[:120]}"' if a.evidencia.trecho else ""
        fatos.append(f"Achado: {_rotulo(a.codigo.value)} em {data} ({a.evidencia.ref}){trecho}.")
    if s.comparacao and s.componentes_para:
        viz = s.comparacao[0]
        subiu = (s.posicao_para or 0) < (s.posicao_de or 10**9)
        dif = {k: s.componentes_para[k] - viz.componentes[k] for k in viz.componentes}
        decisivo = max(dif, key=dif.get) if subiu else min(dif, key=dif.get)
        motivo = {"estado": "estado clínico mais grave", "classe": "classe SWALIS mais urgente",
                  "espera": "mais tempo de espera", "risco": "menor risco cirúrgico"}[decisivo]
        if not subiu:
            motivo = {"estado": "estado clínico menos grave", "classe": "classe SWALIS menos urgente",
                      "espera": "menos tempo de espera", "risco": "maior risco cirúrgico"}[decisivo]
        fatos.append(f"{'Ultrapassa' if subiu else 'Fica atrás de'} {s.ultrapassados} paciente(s). "
                     f"Este paciente fica {'à frente' if subiu else 'atrás'} de quem está "
                     f"{'logo abaixo' if subiu else 'logo acima'} (classe {viz.classe}) porque ESTE paciente tem "
                     f"{motivo} ({_num(abs(dif[decisivo]))} pontos de diferença no score).")
    return fatos


class RedatorTemplate:
    def justificar(self, s: Sugestao, av: Avaliacao | None) -> str:
        return s.justificativa

    def explicar(self, s: Sugestao) -> str:
        """Template curto: o achado principal + a posição. Usado sem LLM ou quando o LLM falha."""
        if s.tipo in (T.REMOVER, T.ALERTA):
            return s.justificativa
        partes = []
        if s.motivos:
            a = s.motivos[0]
            data = f" em {a.data_fato.strftime('%d/%m')}" if a.data_fato else ""
            partes.append(f"{_rotulo(a.codigo.value).capitalize()}{data} ({a.evidencia.ref}).")
        if s.posicao_de is not None and s.posicao_para is not None:
            partes.append(f"Se aprovada, vai de {s.posicao_de}º para {s.posicao_para}º.")
        if s.comparacao:
            viz = s.comparacao[0]
            partes.append(f"{'Passa à frente de' if s.posicao_para < (s.posicao_de or 10**9) else 'Fica atrás de'} "
                          f"{s.ultrapassados} paciente(s); o mais próximo é {viz.solicitacao_id} (classe {viz.classe}).")
        return " ".join(partes) or s.justificativa

    def explicar_sem_llm(self, s: Sugestao) -> str:
        return RedatorTemplate.explicar(self, s)


class RedatorLLM(RedatorTemplate):
    """DeepSeek (API compatível com OpenAI). `cliente`: função prompt → texto (os testes injetam uma falsa)."""

    def __init__(self, chave: str | None = None, modelo: str | None = None,
                 cliente: Callable[[str], str] | None = None, timeout: float = 15):
        self.chave = chave if chave is not None else os.environ.get("DEEPSEEK_API_KEY", "")
        self.modelo = modelo or os.environ.get("ORDO_MODELO_LLM", MODELO_PADRAO)
        self.cliente = cliente
        self.timeout = timeout
        self._cache: dict[tuple, str] = {}

    def explicar(self, s: Sugestao) -> str:
        base = super().explicar(s)
        if s.tipo in (T.REMOVER, T.ALERTA) or (self.cliente is None and not self.chave):
            return base
        fatos = _fatos(s)
        chave_cache = (s.solicitacao_id, s.tipo, s.classe_para, s.ordo_clinico_para, s.posicao_de, s.posicao_para)
        if chave_cache in self._cache:
            return self._cache[chave_cache]
        try:
            texto = (self.cliente or self._chamar_deepseek)(self._prompt(fatos)).strip()
        except Exception:
            return base
        texto = re.sub(r"<think>[\s\S]*?</think>", "", texto).strip()
        permitidas = set(REFERENCIA.findall(" ".join(fatos)))
        if not texto or any(r not in permitidas for r in REFERENCIA.findall(texto)):
            return base
        self._cache[chave_cache] = texto
        return texto

    def _prompt(self, fatos: list[str]) -> str:
        return ("Você escreve para um médico regulador da fila cirúrgica do SUS, que precisa decidir em segundos. "
                "Em português, em NO MÁXIMO 2 frases e 45 palavras, diga: (1) o fato clínico que motivou a sugestão "
                "e (2) para onde o paciente vai na fila e o que o separa de quem fica logo abaixo/acima. "
                "Use SOMENTE os fatos abaixo, em linguagem clínica natural: não invente nada, não use códigos "
                "internos em maiúsculas, não repita o identificador do próprio paciente, cite no máximo uma "
                "referência de evento (EVT-…) exatamente como aparece, e omita scores que não mudam a decisão. "
                "Se os fatos não trouxerem comparação com outro paciente, não comente isso."
                "\n\nFatos:\n- " + "\n- ".join(fatos))

    def _chamar_deepseek(self, prompt: str) -> str:
        import httpx
        r = httpx.post(DEEPSEEK_URL, timeout=self.timeout,
                       headers={"Authorization": f"Bearer {self.chave}"},
                       json={"model": self.modelo, "temperature": 0,
                             # só redige a partir de fatos prontos: raciocínio não ajuda e custa ~1s por chamada
                             "thinking": {"type": "disabled"},
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
