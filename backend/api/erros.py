"""Handler único: erros do serviço → status HTTP."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from servico.erros import ComentarioObrigatorio, ErroServico, NaoEncontrado, TransicaoInvalida

STATUS = {NaoEncontrado: 404, TransicaoInvalida: 409, ComentarioObrigatorio: 422}


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroServico)
    async def erro_servico(_: Request, e: ErroServico) -> JSONResponse:
        return JSONResponse(status_code=STATUS.get(type(e), 400), content={"erro": type(e).__name__, "detalhe": str(e)})
