"""API HTTP. Fina: cada rota chama um caso de uso e converte para DTO; regra de negócio fica no serviço.

Rodar (de dentro de backend/):  uvicorn api.main:app --reload
"""
import os
from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from servico.casos_uso import ServicoFila
from servico.erros import NaoEncontrado, TransicaoInvalida

from .dependencias import obter_servico, obter_simulador
from .dtos import (AlertaDTO, DecisaoCompartilhadaDTO, DiaFilaDTO, EntradaDecisao, EntradaIntegracao,
                   EntradaPatchSimulacao, ErroDTO, FichaDTO, ItemFilaDTO, PaginaDTO, RecebimentoDTO, ResumoFilaDTO,
                   SimulacaoDTO,
                   SugestaoDTO)
from .erros import registrar_handlers

app = FastAPI(title="OrdoVitae", description="Priorização da fila cirúrgica: integração, simulação e regulador.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("ORDO_CORS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
registrar_handlers(app)

Servico = Annotated[ServicoFila, Depends(obter_servico)]
SIMULADOR_ATIVO = os.environ.get("SIMULADOR") == "1"     # config de ambiente; desligado em produção
ERROS = {404: {"model": ErroDTO}, 409: {"model": ErroDTO}, 422: {"model": ErroDTO}}
# Paginação padrão de toda coleção: nenhuma rota devolve a coleção inteira.
Limite = Annotated[int, Query(ge=1, le=200, description="itens por página")]
Offset = Annotated[int, Query(ge=0, description="itens a pular")]
LIMITE_PADRAO = 50
MAX_DIAS_HISTORICO = 31


# --- integração (sistemas externos chamam) ------------------------------------------------

@app.post("/integracao/solicitacoes", response_model=RecebimentoDTO, status_code=status.HTTP_201_CREATED,
          tags=["integração"])
def receber_solicitacao(entrada: EntradaIntegracao, svc: Servico):
    return RecebimentoDTO(sugestoes=[SugestaoDTO.de(r) for r in svc.receber_solicitacao(entrada.dados, entrada.resposta_llm)])


@app.post("/integracao/eventos", response_model=RecebimentoDTO, status_code=status.HTTP_201_CREATED,
          tags=["integração"])
def receber_evento(entrada: EntradaIntegracao, svc: Servico):
    return RecebimentoDTO(sugestoes=[SugestaoDTO.de(r) for r in svc.receber_evento(entrada.dados, entrada.resposta_llm)])


# --- simulação (recurso único) ----------------------------------------------------------

@app.get("/simulacao/datas", response_model=list[date], tags=["simulação"])
def datas_com_foto(svc: Servico):
    """Dias com foto da fila, em ordem: são os dias navegáveis da linha do tempo do front."""
    return svc.datas_com_foto()


@app.get("/simulacao", response_model=SimulacaoDTO, tags=["simulação"])
def consultar_simulacao(svc: Servico):
    return SimulacaoDTO.de(svc.consultar_simulacao())


@app.patch("/simulacao", response_model=SimulacaoDTO, tags=["simulação"], responses=ERROS)
def alterar_simulacao(entrada: EntradaPatchSimulacao, svc: Servico):
    """`autoAprovar` liga/desliga a aprovação automática. `hoje` avança o relógio até a data:
    modo `passo` (dia a dia, com foto) ou `rapido` (aprovação automática, só a foto final).
    Com SIMULADOR=1, cada dia avançado recebe as chegadas do dataset."""
    if entrada.auto_aprovar is not None:
        svc.configurar_simulacao(entrada.auto_aprovar)
    if entrada.avancar_dias is not None:
        if SIMULADOR_ATIVO:
            obter_simulador(svc).avancar(entrada.avancar_dias)
        else:
            svc.avancar_dia(entrada.avancar_dias)
    elif entrada.hoje is not None:
        atual = svc.consultar_simulacao().hoje
        if SIMULADOR_ATIVO:
            sim = obter_simulador(svc)
            if entrada.modo == "rapido":
                sim.pular_ate(entrada.hoje)
            else:
                dias = (entrada.hoje - atual).days if atual != date.min else (entrada.hoje - sim.fonte.primeira_data()).days + 1
                if dias < 1:
                    raise TransicaoInvalida(f"a simulação já está em {atual}")
                sim.avancar(dias)
        else:
            if atual == date.min or entrada.hoje <= atual:
                raise TransicaoInvalida(f"não é possível ir de {atual} para {entrada.hoje}")
            svc.avancar_dia((entrada.hoje - atual).days)
    return SimulacaoDTO.de(svc.consultar_simulacao())


if SIMULADOR_ATIVO:
    from infra.db import zerar

    @app.delete("/simulacao", status_code=status.HTTP_204_NO_CONTENT, tags=["simulação"])
    def reiniciar_simulacao(svc: Servico):
        """Zera o banco do sistema; o próximo avanço começa no dia zero do dataset."""
        zerar(svc.uow().fabrica)
        svc.invalidar_cache()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- fila ---------------------------------------------------------------------------------

def _dia_fila(svc: ServicoFila, data: date | None, limite: int, offset: int) -> DiaFilaDTO:
    p = svc.consultar_fila(data, limite, offset)
    return DiaFilaDTO(data=data or SimulacaoDTO.de(svc.consultar_simulacao()).hoje, ordem=[ItemFilaDTO.de(l) for l in p],
                      total=p.total, limite=limite, offset=offset, resumo=ResumoFilaDTO(**p.resumo),
                      movimentos=[ItemFilaDTO.de(l) for l in p.movimentos])


@app.get("/fila", response_model=DiaFilaDTO, tags=["fila"], responses=ERROS)
def consultar_fila(svc: Servico, data: date | None = None, limite: Limite = LIMITE_PADRAO, offset: Offset = 0):
    """Fila viva (sem `data`) ou a foto de um dia passado. Paginada; posições são as da fila inteira."""
    return _dia_fila(svc, data, limite, offset)


@app.get("/fila/dias", response_model=list[DiaFilaDTO], tags=["fila"], responses=ERROS)
def historico_fila(svc: Servico, de: date, ate: date | None = None, limite: Limite = LIMITE_PADRAO):
    """Fotos da fila em vários dias (para o player): até 31 dias, `limite` primeiras posições de cada dia."""
    hoje = svc.consultar_simulacao().hoje
    ate = min(ate or hoje, hoje)
    if (ate - de).days >= MAX_DIAS_HISTORICO:
        raise TransicaoInvalida(f"intervalo máximo de {MAX_DIAS_HISTORICO} dias")
    dias = []
    for i in range((ate - de).days + 1):
        try:
            dias.append(_dia_fila(svc, de + timedelta(days=i), limite, 0))
        except NaoEncontrado:          # dia sem foto (avanço rápido)
            continue
    return dias


@app.get("/fila.csv", response_class=PlainTextResponse, tags=["fila"])
def exportar_fila(svc: Servico):
    """Representação CSV da fila inteira (entregável: solicitacao_id, posicao, justificativa)."""
    return PlainTextResponse(svc.exportar_fila_priorizada(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="fila_priorizada.csv"'})


# --- solicitações, sugestões, alertas ------------------------------------------------------

@app.get("/solicitacoes/{sid}", response_model=FichaDTO, tags=["regulador"], responses=ERROS)
def consultar_paciente(sid: str, svc: Servico):
    return FichaDTO.de(svc.consultar_paciente(sid))


@app.get("/solicitacoes/{sid}/decisao-compartilhada", response_model=DecisaoCompartilhadaDTO, tags=["regulador"],
         responses=ERROS)
def consultar_decisao_compartilhada(sid: str, svc: Servico):
    """Motor secundário: adesão, barreiras e preferências do paciente, com os dados recebidos até hoje."""
    av, usou_llm = svc.consultar_decisao_compartilhada(sid)
    return DecisaoCompartilhadaDTO.de(av, usou_llm, svc.consultar_simulacao().hoje)


@app.get("/sugestoes", response_model=PaginaDTO[SugestaoDTO], tags=["regulador"])
def listar_sugestoes(svc: Servico, status: str | None = Query(None, description="pendente|aprovada|rejeitada|substituida"),
                     criada_em: date | None = Query(None, alias="criadaEm", description="só as criadas neste dia"),
                     limite: Limite = LIMITE_PADRAO, offset: Offset = 0):
    """Paginada. As pendentes da página vêm com prévia de posição e justificativa comparativa."""
    return PaginaDTO[SugestaoDTO].de(svc.listar_sugestoes(status, limite, offset, criada_em), SugestaoDTO.de)


@app.get("/sugestoes/{id}", response_model=SugestaoDTO, tags=["regulador"], responses=ERROS)
def consultar_sugestao(id: int, svc: Servico):
    return SugestaoDTO.de(svc.consultar_sugestao(id))


@app.patch("/sugestoes/{id}", response_model=SugestaoDTO, tags=["regulador"], responses=ERROS)
def decidir_sugestao(id: int, entrada: EntradaDecisao, svc: Servico):
    """O regulador aprova ou rejeita (rejeitar exige comentário). Decidir duas vezes → 409."""
    if entrada.status == "aprovada":
        return SugestaoDTO.de(svc.aprovar_sugestao(id))
    return SugestaoDTO.de(svc.rejeitar_sugestao(id, entrada.comentario))


@app.get("/alertas", response_model=PaginaDTO[AlertaDTO], tags=["regulador"])
def listar_alertas(svc: Servico, tipo: str | None = Query(None, description="critico|prazo_estourado|sem_asa|perda_contato|…"),
                   limite: Limite = LIMITE_PADRAO, offset: Offset = 0):
    return PaginaDTO[AlertaDTO].de(svc.listar_alertas(tipo, limite, offset), AlertaDTO.de)
