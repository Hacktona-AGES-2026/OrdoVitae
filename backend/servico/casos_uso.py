"""Casos de uso: recebem dados de integração, chamam extração + motor e persistem pelas portas.

Fluxo de referência: spikes/replay.py. Este módulo depende só de `motor`, `extracao` e das portas.
"""
import csv
import functools
import io
from concurrent.futures import ThreadPoolExecutor, wait
from collections.abc import Callable, Mapping
from datetime import date, timedelta

from extracao import extrair_evento, extrair_solicitacao
from motor import config
from motor import AvaliacaoRisco, EstadoAprovado, ItemFila, avaliar, avaliar_risco, critico, decidir, ordenar, prever_posicoes
from motor.modelos import Avaliacao, Dimensao, Origem, Sugestao, TipoSugestao as T
from motor_secundario import AvaliacaoDecisaoCompartilhada, avaliar_decisao_compartilhada

from . import regras
from .erros import ComentarioObrigatorio, NaoEncontrado, TransicaoInvalida
from .modelos import Alerta, FichaPaciente, LinhaFila, Pagina, Simulacao, StatusSugestao, SugestaoRegistrada
from .portas import Redator, Relogio, UnidadeDeTrabalho

REGULADOR = "regulador"
SIMULACAO = "simulacao"            # autor das aprovações automáticas
MUDANCA_DE_CLASSE = {T.CLASSIFICACAO_INICIAL, T.SUBIR, T.DESCER}
_POOL_REDATOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="redator")   # sobrevive à requisição


def _escrita(metodo):
    """Invalida o cache da fila antes E depois da escrita: uma leitura concorrente (threadpool da API)
    que montasse a fila antes do commit deixaria em cache a fila velha com a versão nova."""
    @functools.wraps(metodo)
    def envolvido(self, *args, **kwargs):
        self.invalidar_cache()
        try:
            return metodo(self, *args, **kwargs)
        finally:
            self.invalidar_cache()
    return envolvido


class ServicoFila:
    def __init__(self, uow: Callable[[], UnidadeDeTrabalho], relogio: Relogio, redator: Redator,
                 risco_procedimento: Mapping[str, int]):
        """`uow`: fábrica de unidades de trabalho; `risco_procedimento`: procedimento_id → risco 1–5."""
        self.uow = uow
        self.relogio = relogio
        self.redator = redator
        self.risco_procedimento = risco_procedimento
        self._versao = 0                                    # muda a cada escrita: invalida o cache da fila
        self._cache_fila: tuple[tuple, list[ItemFila]] | None = None

    def invalidar_cache(self) -> None:
        """Chamado por toda escrita (e pela rota que zera o banco da simulação)."""
        self._versao += 1

    # --- integração ------------------------------------------------------------------

    @_escrita
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

    @_escrita
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

    @_escrita
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

    @_escrita
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

    @_escrita
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

    def datas_com_foto(self) -> list[date]:
        """Dias navegáveis na linha do tempo (os que têm foto da fila)."""
        with self.uow() as uow:
            return uow.historico.datas()

    def consultar_simulacao(self) -> Simulacao:
        return Simulacao(self.relogio.hoje(), self.relogio.auto_aprovar)

    def configurar_simulacao(self, auto_aprovar: bool) -> Simulacao:
        self.relogio.auto_aprovar = auto_aprovar
        return self.consultar_simulacao()

    # --- consultas -------------------------------------------------------------------

    LIMIAR_SALTO = 5            # mudança de posição que conta como "salto" no resumo do dia
    MAX_MOVIMENTOS = 12

    def consultar_fila(self, data: date | None = None, limite: int | None = None, offset: int = 0) -> Pagina:
        """Fila oficial (viva ou foto de `data`), paginada. Posições são sempre as da fila inteira.

        A página traz também o resumo do dia inteiro (`resumo`) e os maiores saltos (`movimentos`),
        para o front não precisar da fila completa."""
        linhas = self._linhas_fila(data)
        pagina = Pagina.de(linhas, limite, offset)
        saltos = sorted((l for l in linhas if l.posicao_anterior is not None
                         and abs(l.posicao_anterior - l.posicao) >= self.LIMIAR_SALTO),
                        key=lambda l: -abs(l.posicao_anterior - l.posicao))
        pagina.movimentos = saltos[:self.MAX_MOVIMENTOS]
        pagina.resumo = {"na_fila": len(linhas), "saltos": len(saltos),
                         "fora_do_prazo": sum(l.dias_em_fila > config.PRAZO_DIAS[l.classe] for l in linhas),
                         "criticos": sum(bool(l.critico) for l in linhas)}
        return pagina

    def _linhas_fila(self, data: date | None) -> list[LinhaFila]:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            anterior = {x["solicitacao_id"]: x["posicao"] for x in uow.historico.foto((data or hoje) - timedelta(days=1))}
            if data is not None and data != hoje:
                foto = uow.historico.foto(data)
                if not foto:
                    raise NaoEncontrado(f"sem foto da fila em {data.isoformat()}")
                entradas = uow.solicitacoes.datas_entrada([x["solicitacao_id"] for x in foto])
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

    def consultar_decisao_compartilhada(self, sid: str) -> tuple[AvaliacaoDecisaoCompartilhada, bool]:
        """Motor secundário só com o que o sistema já recebeu até hoje (não vaza informação do futuro).

        As observações chegam como eventos `observacao` (regra 11) e são remontadas no campo
        `observacoes`; achados de origem LLM entram como `achados_llm`. Devolve (avaliação, usou_llm).
        """
        with self.uow() as uow:
            dados = uow.solicitacoes.obter(sid)
            if dados is None:
                raise NaoEncontrado(f"solicitação {sid}")
            eventos = uow.eventos.da_solicitacao(sid)
            achados_llm = [{"codigo": a.codigo.value, "trecho_literal": a.evidencia.trecho}
                           for a in uow.achados.da_solicitacao(sid) if a.origem == Origem.LLM]
        observacoes = [e.get("descricao", "") for e in eventos if e.get("tipo_evento") == "observacao"]
        solicitacao = dict(dados, observacoes=" ".join([dados.get("observacoes") or "", *observacoes]).strip())
        clinicos = [e for e in eventos if e.get("tipo_evento") != "observacao"]
        return avaliar_decisao_compartilhada(solicitacao, clinicos, achados_llm), bool(achados_llm)

    def consultar_paciente(self, sid: str) -> FichaPaciente:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            dados = uow.solicitacoes.obter(sid)
            if dados is None:
                raise NaoEncontrado(f"solicitação {sid}")
            estado, risco = uow.estados.obter(sid)
            posicao = next((i.posicao for i in self._fila(uow, hoje) if i.solicitacao_id == sid), None)
            sugestoes = uow.sugestoes.da_solicitacao(sid)
            pendentes = [r.sugestao for r in sugestoes if r.status == StatusSugestao.PENDENTE]
            provisorio = any(s.tipo == T.CLASSIFICACAO_INICIAL for s in pendentes)   # mesmo critério de _provisorios
            if pendentes:                       # a ficha mostra o mesmo texto redigido da lista, não o template cru
                prever_posicoes(self._fila(uow, hoje), pendentes, hoje)
                self._explicar(pendentes)
            return FichaPaciente(
                sid, dados, ativa=posicao is not None, classe=estado.classe, ordo_clinico=estado.ordo_clinico,
                provisorio=provisorio, risco=risco.valor, risco_motivo=risco.motivo,
                posicao=posicao, achados=uow.achados.da_solicitacao(sid), historico=uow.historico.posicoes(sid),
                sugestoes=sugestoes)

    def consultar_sugestao(self, id: int) -> SugestaoRegistrada:
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            r = uow.sugestoes.obter(id)
            if r is None:
                raise NaoEncontrado(f"sugestão {id}")
            if r.status == StatusSugestao.PENDENTE:
                prever_posicoes(self._fila(uow, hoje), [r.sugestao], hoje)
                self._explicar([r.sugestao])
            return r

    def listar_sugestoes(self, status: str | None = None, limite: int | None = None, offset: int = 0,
                         criada_em: date | None = None) -> Pagina:
        """Paginada; `criada_em` filtra pelo dia. As pendentes DA PÁGINA vêm com a prévia de posição."""
        hoje = self.relogio.hoje()
        with self.uow() as uow:
            todas = uow.sugestoes.listar(status)
            if criada_em is not None:
                todas = [r for r in todas if r.criada_em == criada_em]
            pagina = Pagina.de(todas, limite, offset)
            pendentes = [r.sugestao for r in pagina if r.status == StatusSugestao.PENDENTE]
            if pendentes:
                prever_posicoes(self._fila(uow, hoje), pendentes, hoje)
                self._explicar(pendentes)
            return pagina

    def listar_alertas(self, tipo: str | None = None, limite: int | None = None, offset: int = 0) -> Pagina:
        """Paginada; `tipo` filtra (ex.: critico, prazo_estourado, sem_asa, perda_contato…)."""
        alertas = self._alertas()
        if tipo:
            alertas = [a for a in alertas if tipo in a.tipo.split(",")]
        return Pagina.de(alertas, limite, offset)

    def _alertas(self) -> list[Alerta]:
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
        """Fila oficial, em cache até a próxima escrita ou mudança de dia (todas as leituras precisam dela)."""
        chave = (hoje, self._versao)
        if self._cache_fila is None or self._cache_fila[0] != chave:
            self._cache_fila = (chave, self._montar_fila(uow, hoje))
        return self._cache_fila[1]

    def _montar_fila(self, uow: UnidadeDeTrabalho, hoje: date) -> list[ItemFila]:
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

    MAX_EXPLICACOES = 24        # por consulta: as primeiras pendentes da página (3 rodadas do pool)
    PRAZO_EXPLICACAO = 4.0      # segundos para a consulta inteira, não por chamada

    def _explicar(self, sugestoes: list[Sugestao]) -> None:
        """Texto final de cada sugestão pendente (LLM em paralelo; o redator cai no template se falhar).

        Com prazo total: rede lenta (ou 200 pendentes) não trava a tela. O que passar do limite ou não
        ficar pronto vai com o template e termina em segundo plano, enchendo o cache do redator."""
        # subir/descer primeiro: são as que o regulador decide; classificação inicial fica por último
        prioridade = sorted(sugestoes, key=lambda s: s.tipo not in (T.SUBIR, T.DESCER))[:self.MAX_EXPLICACOES]
        futuros = {id(s): _POOL_REDATOR.submit(self.redator.explicar, s) for s in prioridade}
        wait(futuros.values(), timeout=self.PRAZO_EXPLICACAO)
        for s in sugestoes:
            f = futuros.get(id(s))
            pronto = f is not None and f.done() and f.exception() is None
            s.explicacao = f.result() if pronto else self.redator.explicar_sem_llm(s)

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
