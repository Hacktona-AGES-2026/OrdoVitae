"""Casos de uso: recebem dados de integração, chamam extração + motor e persistem pelas portas.

Fluxo de referência: spikes/replay.py. Este módulo depende só de `motor`, `extracao` e das portas.
"""
import csv
import io
from collections.abc import Callable, Mapping
from datetime import date, timedelta

from extracao import extrair_evento, extrair_solicitacao
from motor import AvaliacaoRisco, EstadoAprovado, ItemFila, avaliar, avaliar_risco, critico, decidir, ordenar, prever_posicoes
from motor.modelos import Avaliacao, Dimensao, Sugestao, TipoSugestao as T

from . import regras
from .erros import ComentarioObrigatorio, NaoEncontrado, TransicaoInvalida
from .modelos import Alerta, FichaPaciente, LinhaFila, Simulacao, StatusSugestao, SugestaoRegistrada
from .portas import Redator, Relogio, UnidadeDeTrabalho

REGULADOR = "regulador"
SIMULACAO = "simulacao"            # autor das aprovações automáticas
MUDANCA_DE_CLASSE = {T.CLASSIFICACAO_INICIAL, T.SUBIR, T.DESCER}


class ServicoFila:
    def __init__(self, uow: Callable[[], UnidadeDeTrabalho], relogio: Relogio, redator: Redator,
                 risco_procedimento: Mapping[str, int]):
        """`uow`: fábrica de unidades de trabalho; `risco_procedimento`: procedimento_id → risco 1–5."""
        self.uow = uow
        self.relogio = relogio
        self.redator = redator
        self.risco_procedimento = risco_procedimento

    # --- integração ------------------------------------------------------------------

    def receber_solicitacao(self, dados: dict, resposta_llm: list[dict] | None = None) -> list[SugestaoRegistrada]:
        sid = dados["solicitacao_id"]
        entrada = regras.data(dados["data_entrada_fila"])
        hoje = max(self.relogio.hoje(), entrada)
        with self.uow() as uow:
            if uow.solicitacoes.obter(sid):
                return []                                   # reenvio: idempotente
            duplicata = uow.solicitacoes.ativa_do_paciente(dados.get("paciente_id"), dados.get("procedimento_id"))
            uow.solicitacoes.salvar(dados)
            novos = extrair_solicitacao(dados, resposta_llm)
            uow.achados.adicionar(novos)
            av = avaliar(sid, uow.achados.da_solicitacao(sid), hoje, entrada)
            uow.estados.salvar(sid, EstadoAprovado(av.classe, av.ordo_clinico), self._risco(dados), provisorio=True)

            sugestoes = decidir(av, None, novos)
            if duplicata:
                sugestoes.append(Sugestao(
                    sid, T.REMOVER, av.classe, None, [],
                    justificativa=f"Duplicata de {duplicata['solicitacao_id']} (mesmo paciente e procedimento já ativos)."))
            ids = self._registrar(uow, sugestoes, av, hoje)
            uow.auditoria.registrar("solicitacao_recebida", sid, f"classe provisória {av.classe}", SIMULACAO, hoje)
            uow.commit()
        return self._depois_de_registrar(ids)

    def receber_evento(self, dados: dict, resposta_llm: list[dict] | None = None) -> list[SugestaoRegistrada]:
        eid, sid = dados["evento_id"], dados["solicitacao_id"]
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            if uow.eventos.existe(eid):
                return []                                   # evento repetido
            uow.eventos.salvar(dados)
            sol = uow.solicitacoes.obter(sid)
            if sol is None or not uow.solicitacoes.esta_ativa(sid):
                motivo = "desconhecida" if sol is None else "fora da fila"
                uow.auditoria.registrar("evento_ignorado", sid, f"{eid}: solicitação {motivo}", SIMULACAO,
                                        max(hoje, regras.data(dados["data_evento"])))
                uow.commit()
                return []

            entrada = regras.data(sol["data_entrada_fila"])
            hoje = max(hoje, entrada, regras.data(dados["data_evento"]))
            novos = extrair_evento(dados, resposta_llm)
            uow.achados.adicionar(novos)
            av = avaliar(sid, uow.achados.da_solicitacao(sid), hoje, entrada)

            pendentes = uow.sugestoes.pendentes_de(sid)
            estado, risco = uow.estados.obter(sid)
            if any(r.sugestao.tipo == T.CLASSIFICACAO_INICIAL for r in pendentes):
                # classe ainda provisória: o motor reclassifica do zero, mas só vale se houve achado clínico
                # novo e o resultado mudou (regra 2: alerta ou tempo passando não mexem na classe)
                clinico_novo = any(a.dimensao != Dimensao.ALERTA for a in novos)
                mudou = (av.classe, av.ordo_clinico) != (estado.classe, estado.ordo_clinico)
                sugestoes = [s for s in decidir(av, None, novos)
                             if s.tipo != T.CLASSIFICACAO_INICIAL or (clinico_novo and mudou)]
            else:
                sugestoes = decidir(av, estado, novos)

            if any(s.tipo in MUDANCA_DE_CLASSE for s in sugestoes):
                for r in pendentes:
                    if r.sugestao.tipo in MUDANCA_DE_CLASSE:
                        uow.sugestoes.mudar_status(r.id, StatusSugestao.SUBSTITUIDA.value, SIMULACAO, hoje,
                                                   f"substituída pelo evento {eid}")
            for s in sugestoes:
                if s.tipo == T.CLASSIFICACAO_INICIAL:   # a fila usa a proposta mais recente enquanto não há aprovação
                    uow.estados.salvar(sid, EstadoAprovado(s.classe_para, s.ordo_clinico_para), risco, provisorio=True)
            ids = self._registrar(uow, sugestoes, av, hoje)
            uow.commit()
        return self._depois_de_registrar(ids)

    # --- regulador --------------------------------------------------------------------

    def aprovar_sugestao(self, id: int, por: str = REGULADOR, se_pendente: bool = False) -> SugestaoRegistrada:
        """Aplica a sugestão. `se_pendente`: usado pela aprovação automática, ignora o que já foi decidido."""
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            r = self._obter_pendente(uow, id, se_pendente)
            if r is None:
                return uow.sugestoes.obter(id)
            s, sid = r.sugestao, r.solicitacao_id
            if s.tipo == T.REMOVER:
                uow.saidas.registrar(sid, regras.motivo_saida(s).value, s.justificativa, hoje)
                for outra in uow.sugestoes.pendentes_de(sid):
                    if outra.id != id:
                        uow.sugestoes.mudar_status(outra.id, StatusSugestao.SUBSTITUIDA.value, por, hoje,
                                                   "paciente saiu da fila")
            elif s.tipo in MUDANCA_DE_CLASSE:
                _, risco = uow.estados.obter(sid)
                uow.estados.salvar(sid, EstadoAprovado(s.classe_para, s.ordo_clinico_para), risco, provisorio=False)
            # ALERTA: aprovar = regulador ciente; não mexe na ordem
            uow.sugestoes.mudar_status(id, StatusSugestao.APROVADA.value, por, hoje)
            uow.auditoria.registrar("aprovar", sid, f"#{id} {s.tipo.value}", por, hoje)
            uow.commit()
            return uow.sugestoes.obter(id)

    def rejeitar_sugestao(self, id: int, comentario: str, por: str = REGULADOR) -> SugestaoRegistrada:
        if not (comentario or "").strip():
            raise ComentarioObrigatorio("rejeitar uma sugestão exige comentário")
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            r = self._obter_pendente(uow, id, se_pendente=False)
            uow.sugestoes.mudar_status(id, StatusSugestao.REJEITADA.value, por, hoje, comentario.strip())
            uow.auditoria.registrar("rejeitar", r.solicitacao_id, f"#{id} {r.sugestao.tipo.value}: {comentario.strip()}",
                                    por, hoje)
            uow.commit()
            return uow.sugestoes.obter(id)

    # --- simulação ---------------------------------------------------------------------

    def avancar_dia(self, dias: int = 1) -> date:
        """Avança o relógio dia a dia, guardando uma foto da fila em cada dia."""
        if dias < 1:
            raise TransicaoInvalida("dias deve ser >= 1")
        for _ in range(dias):
            hoje = self.relogio.avancar(1)
            self.fotografar_fila()
        return hoje

    def fotografar_fila(self) -> None:
        """Guarda a foto da fila oficial de hoje (alimenta posição anterior e a navegação por dia)."""
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            uow.historico.salvar_foto(hoje, self._fila(uow, hoje))
            uow.commit()

    def consultar_simulacao(self) -> Simulacao:
        return Simulacao(self.relogio.hoje(), self.relogio.auto_aprovar)

    def configurar_simulacao(self, auto_aprovar: bool) -> Simulacao:
        self.relogio.auto_aprovar = auto_aprovar
        return self.consultar_simulacao()

    # --- consultas -------------------------------------------------------------------

    def consultar_fila(self, data: date | None = None) -> list[LinhaFila]:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            anterior = {x["solicitacao_id"]: x["posicao"] for x in uow.historico.foto((data or hoje) - timedelta(days=1))}
            if data is not None and data != hoje:
                foto = uow.historico.foto(data)
                if not foto:
                    raise NaoEncontrado(f"sem foto da fila em {data.isoformat()}")
                entradas = {sid: regras.data(uow.solicitacoes.obter(sid)["data_entrada_fila"])
                            for sid in (x["solicitacao_id"] for x in foto)}
                return [LinhaFila(x["solicitacao_id"], x["posicao"], anterior.get(x["solicitacao_id"]), x["classe"],
                                  x["score"], (data - entradas[x["solicitacao_id"]]).days) for x in foto]

            estados = uow.estados.todos()
            provisorios = self._provisorios(uow)
            linhas = []
            for i in self._fila(uow, hoje):
                _, risco = estados[i.solicitacao_id]
                linhas.append(LinhaFila(
                    i.solicitacao_id, i.posicao, anterior.get(i.solicitacao_id), i.classe, i.score(hoje),
                    (hoje - i.data_entrada).days, i.score_clinico(hoje), i.ordo_clinico, risco.valor, risco.motivo,
                    risco.asa_estimado, i.oncologico, i.solicitacao_id in provisorios, critico(i, hoje)))
            return linhas

    def consultar_paciente(self, sid: str) -> FichaPaciente:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            dados = uow.solicitacoes.obter(sid)
            if dados is None:
                raise NaoEncontrado(f"solicitação {sid}")
            estado, risco = uow.estados.obter(sid)
            posicao = next((i.posicao for i in self._fila(uow, hoje) if i.solicitacao_id == sid), None)
            return FichaPaciente(
                sid, dados, ativa=posicao is not None, classe=estado.classe, ordo_clinico=estado.ordo_clinico,
                provisorio=sid in self._provisorios(uow), risco=risco.valor, risco_motivo=risco.motivo,
                posicao=posicao, achados=uow.achados.da_solicitacao(sid), historico=uow.historico.posicoes(sid),
                sugestoes=[r for r in uow.sugestoes.listar() if r.solicitacao_id == sid])

    def listar_sugestoes(self, status: str | None = None) -> list[SugestaoRegistrada]:
        """Pendentes vêm com a prévia de posição (de/para), calculada na hora sobre a fila atual."""
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            registradas = uow.sugestoes.listar(status)
            pendentes = [r.sugestao for r in registradas if r.status == StatusSugestao.PENDENTE]
            if pendentes:
                prever_posicoes(self._fila(uow, hoje), pendentes, hoje)
            return registradas

    def listar_alertas(self) -> list[Alerta]:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            alertas = [Alerta(",".join(sorted({a.codigo.value.lower() for a in r.sugestao.motivos})),
                              r.solicitacao_id, r.sugestao.justificativa, r.id)
                       for r in uow.sugestoes.listar(StatusSugestao.PENDENTE.value) if r.sugestao.tipo == T.ALERTA]
            estados = uow.estados.todos()
            for i in self._fila(uow, hoje):
                _, risco = estados[i.solicitacao_id]
                if risco.asa_estimado:
                    alertas.append(Alerta("sem_asa", i.solicitacao_id, f"Sem ASA no cadastro: {risco.motivo}."))
                if critico(i, hoje):
                    alertas.append(Alerta("critico", i.solicitacao_id,
                                          f"Classe {i.classe}, {i.razao_prazo(hoje):.1f}x o prazo, score {i.score(hoje)}."))
                elif i.razao_prazo(hoje) > 1:
                    alertas.append(Alerta("prazo_estourado", i.solicitacao_id,
                                          f"{(hoje - i.data_entrada).days} dias na fila, {i.razao_prazo(hoje):.1f}x o prazo da classe {i.classe}."))
            return alertas

    def exportar_fila_priorizada(self) -> str:
        """CSV do entregável comum: solicitacao_id, posicao, justificativa."""
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            ultima = {}
            for r in sorted(uow.sugestoes.listar(), key=lambda r: r.id):
                if r.sugestao.tipo in MUDANCA_DE_CLASSE and r.status in (StatusSugestao.APROVADA, StatusSugestao.PENDENTE):
                    ultima[r.solicitacao_id] = r
            estados = uow.estados.todos()
            saida = io.StringIO()
            w = csv.writer(saida, lineterminator="\n")
            w.writerow(["solicitacao_id", "posicao", "justificativa"])
            for i in self._fila(uow, hoje):
                _, risco = estados[i.solicitacao_id]
                r = ultima.get(i.solicitacao_id)
                origem = "" if r is None else ("" if r.status == StatusSugestao.APROVADA else " (provisória)")
                motivo = r.sugestao.justificativa if r else f"Classe {i.classe}."
                w.writerow([i.solicitacao_id, i.posicao,
                            f"Score {i.score(hoje)}; risco {risco.motivo}{origem}. {motivo}"])
            return saida.getvalue()

    # --- internos --------------------------------------------------------------------

    def _obter_pendente(self, uow: UnidadeDeTrabalho, id: int, se_pendente: bool) -> SugestaoRegistrada | None:
        r = uow.sugestoes.obter(id)
        if r is None:
            raise NaoEncontrado(f"sugestão {id}")
        if r.status != StatusSugestao.PENDENTE:
            if se_pendente:
                return None
            raise TransicaoInvalida(f"sugestão {id} já está {r.status.value}")
        return r

    def _provisorios(self, uow: UnidadeDeTrabalho) -> set[str]:
        """Classe ainda não aprovada = há CLASSIFICACAO_INICIAL pendente."""
        return {r.solicitacao_id for r in uow.sugestoes.listar(StatusSugestao.PENDENTE.value)
                if r.sugestao.tipo == T.CLASSIFICACAO_INICIAL}

    def _fila(self, uow: UnidadeDeTrabalho, hoje: date) -> list[ItemFila]:
        """Fila oficial: solicitações ativas com estado (aprovado ou provisório), ordenadas pelo motor."""
        estados = uow.estados.todos()
        ativas = [s for s in uow.solicitacoes.ativas() if s["solicitacao_id"] in estados]
        por_sid = uow.achados.de_varias([s["solicitacao_id"] for s in ativas])
        itens = []
        for sol in ativas:
            sid = sol["solicitacao_id"]
            estado, risco = estados[sid]
            achados = [a for a in por_sid[sid] if a.data_fato is None or a.data_fato <= hoje]
            itens.append(ItemFila(sid, estado.classe, estado.ordo_clinico, regras.data(sol["data_entrada_fila"]),
                                  regras.oncologico(sol), regras.sem_urgencia(sol, achados), risco.valor))
        return ordenar(itens, hoje)

    def _risco(self, dados: dict) -> AvaliacaoRisco:
        proc = self.risco_procedimento.get(dados.get("procedimento_id"), regras.RISCO_PROCEDIMENTO_PADRAO)
        return avaliar_risco(regras.asa(dados), regras.n_comorbidades(dados), proc)

    def _registrar(self, uow: UnidadeDeTrabalho, sugestoes: list[Sugestao], av: Avaliacao, hoje: date) -> list[int]:
        ids = []
        for s in sugestoes:
            s.justificativa = self.redator.justificar(s, av)
            ids.append(uow.sugestoes.criar(s, hoje))
            uow.auditoria.registrar("sugestao_criada", s.solicitacao_id, f"{s.tipo.value}: {s.justificativa}",
                                    SIMULACAO, hoje)
        return ids

    def _depois_de_registrar(self, ids: list[int]) -> list[SugestaoRegistrada]:
        """Aprovação automática (flag da simulação) e devolução das sugestões já com o status final."""
        if self.relogio.auto_aprovar:
            for id in ids:
                self.aprovar_sugestao(id, por=SIMULACAO, se_pendente=True)
        with self.uow() as uow:
            return [uow.sugestoes.obter(id) for id in ids]
