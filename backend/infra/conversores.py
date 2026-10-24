"""Conversores puros: objetos do motor/serviço <-> linhas ORM (e JSON, para os motivos das sugestões).

Ida e volta sem perda: `achado_de_linha(achado_para_linha(a)) == a` (testado em test_infra.py).
As prévias de posição de `Sugestao` (ordo_de/para, posicao_de/para) não são persistidas: são calculadas na hora.
"""
from datetime import date

from motor import AvaliacaoRisco, EstadoAprovado
from motor.modelos import Achado, CodigoAchado, Dimensao, Evidencia, Origem, Sugestao, TipoSugestao
from servico.modelos import StatusSugestao, SugestaoRegistrada

from .orm import AchadoORM, EstadoORM, SugestaoORM


def achado_para_dict(a: Achado) -> dict:
    return {"codigo": a.codigo.value, "dimensao": a.dimensao.value, "solicitacao_id": a.solicitacao_id,
            "data_fato": a.data_fato.isoformat() if a.data_fato else None, "fonte": a.evidencia.fonte,
            "ref": a.evidencia.ref, "trecho": a.evidencia.trecho, "origem": a.origem.value, "confianca": a.confianca}


def achado_de_dict(d: dict) -> Achado:
    return Achado(CodigoAchado(d["codigo"]), Dimensao(d["dimensao"]), d["solicitacao_id"],
                  date.fromisoformat(d["data_fato"]) if d.get("data_fato") else None,
                  Evidencia(d["fonte"], d["ref"], d.get("trecho") or ""), Origem(d["origem"]), d.get("confianca", 1.0))


def achado_para_linha(a: Achado) -> AchadoORM:
    return AchadoORM(solicitacao_id=a.solicitacao_id, chave=a.id, codigo=a.codigo.value, dimensao=a.dimensao.value,
                     data_fato=a.data_fato, fonte=a.evidencia.fonte, ref=a.evidencia.ref, trecho=a.evidencia.trecho,
                     origem=a.origem.value, confianca=a.confianca)


def achado_de_linha(r: AchadoORM) -> Achado:
    return Achado(CodigoAchado(r.codigo), Dimensao(r.dimensao), r.solicitacao_id, r.data_fato,
                  Evidencia(r.fonte, r.ref, r.trecho or ""), Origem(r.origem), r.confianca)


def sugestao_para_linha(s: Sugestao, criada_em: date) -> SugestaoORM:
    return SugestaoORM(solicitacao_id=s.solicitacao_id, tipo=s.tipo.value, classe_de=s.classe_de,
                       classe_para=s.classe_para, ordo_clinico_de=s.ordo_clinico_de,
                       ordo_clinico_para=s.ordo_clinico_para, urgente=s.urgente, justificativa=s.justificativa,
                       motivos=[achado_para_dict(a) for a in s.motivos], status=StatusSugestao.PENDENTE.value,
                       criada_em=criada_em, decidida_por="", comentario="")


def sugestao_de_linha(r: SugestaoORM) -> SugestaoRegistrada:
    s = Sugestao(r.solicitacao_id, TipoSugestao(r.tipo), r.classe_de, r.classe_para,
                 [achado_de_dict(d) for d in r.motivos], r.justificativa, r.urgente,
                 ordo_clinico_de=r.ordo_clinico_de, ordo_clinico_para=r.ordo_clinico_para)
    return SugestaoRegistrada(r.id, s, StatusSugestao(r.status), r.criada_em, r.decidida_em,
                              r.decidida_por or "", r.comentario or "")


def estado_para_linha(sid: str, e: EstadoAprovado, risco: AvaliacaoRisco, provisorio: bool,
                      linha: EstadoORM | None = None) -> EstadoORM:
    linha = linha or EstadoORM(solicitacao_id=sid)
    linha.classe, linha.ordo_clinico, linha.provisorio = e.classe, e.ordo_clinico, provisorio
    linha.risco_valor, linha.asa, linha.asa_estimado = risco.valor, risco.asa, risco.asa_estimado
    linha.nivel_paciente, linha.nivel_procedimento = risco.nivel_paciente, risco.nivel_procedimento
    return linha


def estado_de_linha(r: EstadoORM) -> tuple[EstadoAprovado, AvaliacaoRisco]:
    return (EstadoAprovado(r.classe, r.ordo_clinico),
            AvaliacaoRisco(r.asa, r.asa_estimado, r.nivel_paciente, r.nivel_procedimento, r.risco_valor))
