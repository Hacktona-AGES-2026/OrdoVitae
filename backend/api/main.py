"""API HTTP. Fina: cada rota chama um caso de uso e converte para DTO; regra de negócio fica no serviço.

Rodar (de dentro de backend/):  uvicorn api.main:app --reload
"""
import os
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from servico.casos_uso import ServicoFila

from .dependencias import obter_servico
from .dtos import (AlertaDTO, DiaFilaDTO, EntradaAvancarDia, EntradaIntegracao, EntradaRejeitar, EntradaSimulacao,
                   ErroDTO, FichaDTO, ItemFilaDTO, RecebimentoDTO, SimulacaoDTO, SugestaoDTO)
from .erros import registrar_handlers

app = FastAPI(title="OrdoVitae", description="Priorização da fila cirúrgica: integração, simulação e regulador.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("ORDO_CORS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
registrar_handlers(app)

Servico = Annotated[ServicoFila, Depends(obter_servico)]
ERROS = {404: {"model": ErroDTO}, 409: {"model": ErroDTO}, 422: {"model": ErroDTO}}


# --- integração (o simulador chama) ------------------------------------------------------

@app.post("/integracao/solicitacoes", response_model=RecebimentoDTO, tags=["integração"])
def receber_solicitacao(entrada: EntradaIntegracao, svc: Servico):
    return RecebimentoDTO(sugestoes=[SugestaoDTO.de(r) for r in svc.receber_solicitacao(entrada.dados, entrada.resposta_llm)])


@app.post("/integracao/eventos", response_model=RecebimentoDTO, tags=["integração"])
def receber_evento(entrada: EntradaIntegracao, svc: Servico):
    return RecebimentoDTO(sugestoes=[SugestaoDTO.de(r) for r in svc.receber_evento(entrada.dados, entrada.resposta_llm)])


# --- simulação ---------------------------------------------------------------------------

@app.post("/simulacao/avancar-dia", response_model=SimulacaoDTO, tags=["simulação"], responses=ERROS)
def avancar_dia(entrada: EntradaAvancarDia, svc: Servico):
    svc.avancar_dia(entrada.dias)
    return SimulacaoDTO.de(svc.consultar_simulacao())


@app.get("/simulacao", response_model=SimulacaoDTO, tags=["simulação"])
def consultar_simulacao(svc: Servico):
    return SimulacaoDTO.de(svc.consultar_simulacao())


@app.put("/simulacao", response_model=SimulacaoDTO, tags=["simulação"])
def configurar_simulacao(entrada: EntradaSimulacao, svc: Servico):
    return SimulacaoDTO.de(svc.configurar_simulacao(entrada.auto_aprovar))


# --- regulador (o front chama) -------------------------------------------------------------

@app.get("/fila", response_model=DiaFilaDTO, tags=["regulador"], responses=ERROS)
def consultar_fila(svc: Servico, data: date | None = None):
    """Sem `data` (ou com a data de hoje): fila viva. Com data passada: a foto daquele dia."""
    ordem = [ItemFilaDTO.de(l) for l in svc.consultar_fila(data)]
    return DiaFilaDTO(data=data or SimulacaoDTO.de(svc.consultar_simulacao()).hoje, ordem=ordem)


@app.get("/fila/exportar.csv", response_class=PlainTextResponse, tags=["regulador"])
def exportar_fila(svc: Servico):
    return PlainTextResponse(svc.exportar_fila_priorizada(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="fila_priorizada.csv"'})


@app.get("/solicitacoes/{sid}", response_model=FichaDTO, tags=["regulador"], responses=ERROS)
def consultar_paciente(sid: str, svc: Servico):
    return FichaDTO.de(svc.consultar_paciente(sid))


@app.get("/sugestoes", response_model=list[SugestaoDTO], tags=["regulador"])
def listar_sugestoes(svc: Servico, status: str | None = None):
    return [SugestaoDTO.de(r) for r in svc.listar_sugestoes(status)]


@app.post("/sugestoes/{id}/aprovar", response_model=SugestaoDTO, tags=["regulador"], responses=ERROS)
def aprovar(id: int, svc: Servico):
    return SugestaoDTO.de(svc.aprovar_sugestao(id))


@app.post("/sugestoes/{id}/rejeitar", response_model=SugestaoDTO, tags=["regulador"], responses=ERROS)
def rejeitar(id: int, entrada: EntradaRejeitar, svc: Servico):
    return SugestaoDTO.de(svc.rejeitar_sugestao(id, entrada.comentario))


@app.get("/alertas", response_model=list[AlertaDTO], tags=["regulador"])
def listar_alertas(svc: Servico):
    return [AlertaDTO.de(a) for a in svc.listar_alertas()]
