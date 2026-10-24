"""Erros do serviço. A API traduz cada um num status HTTP (404, 409, 422) num handler único."""


class ErroServico(Exception):
    """Base: tudo que o serviço recusa por regra de negócio."""


class NaoEncontrado(ErroServico):
    """Solicitação ou sugestão inexistente → 404."""


class TransicaoInvalida(ErroServico):
    """Ex.: aprovar sugestão que não está pendente → 409."""


class ComentarioObrigatorio(ErroServico):
    """Rejeitar sem comentário → 422."""
