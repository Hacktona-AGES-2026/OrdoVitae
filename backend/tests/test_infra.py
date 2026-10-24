"""Teste de contrato das portas: a mesma bateria roda contra os fakes (tests/fakes.py) e contra o SQLite.

Se as duas passam, os fakes usados em test_servico.py se comportam como o banco real.
"""
import unittest
from datetime import date

from infra.conversores import (achado_de_dict, achado_de_linha, achado_para_dict, achado_para_linha, estado_de_linha,
                               estado_para_linha, sugestao_de_linha, sugestao_para_linha)
from infra.db import fabrica_para
from infra.redator import RedatorLLM, RedatorTemplate
from infra.relogio import RelogioSQL
from infra.unidade_de_trabalho import UnidadeDeTrabalhoSQL
from motor import EstadoAprovado, ItemFila, avaliar_risco
from motor.modelos import Achado, CodigoAchado as C, Dimensao as D, Evidencia, Origem, Sugestao, TipoSugestao as T
from servico.casos_uso import ServicoFila
from servico.modelos import StatusSugestao as S
from tests.fakes import BancoMemoria, RelogioMemoria, UnidadeDeTrabalhoMemoria

HOJE = date(2026, 1, 10)


def sol(sid, pid="PAC-1", proc="PROC002", entrada="2026-01-10"):
    return {"solicitacao_id": sid, "paciente_id": pid, "procedimento_id": proc, "data_entrada_fila": entrada,
            "cid_principal": "K40.9"}


def achado(codigo=C.PRONTO_SOCORRO, dim=D.DETERIORACAO, sid="SOL-1", ref="EVT-1", data=date(2026, 1, 5),
           origem=Origem.REGRA, trecho="Atendido no PS por dor."):
    return Achado(codigo, dim, sid, data, Evidencia("evento", ref, trecho), origem, 0.9)


def sugestao(sid="SOL-1"):
    return Sugestao(sid, T.SUBIR, "C", "B", [achado(sid=sid)], "C → B por PS recente.", urgente=False,
                    ordo_clinico_de=20.0, ordo_clinico_para=35.5)


class Contrato:
    """Bateria comum. Subclasses definem `criar()` → (uow, fábrica de relógio)."""

    def setUp(self):
        self.uow, self.novo_relogio = self.criar()

    def test_salvar_obter_e_ativas_exclui_quem_saiu(self):
        with self.uow as u:
            u.solicitacoes.salvar(sol("SOL-1"))
            u.solicitacoes.salvar(sol("SOL-2", pid="PAC-2"))
            u.saidas.registrar("SOL-2", "desistencia", "Pct desistiu.", HOJE)
            u.commit()
        with self.uow as u:
            self.assertEqual(u.solicitacoes.obter("SOL-1")["paciente_id"], "PAC-1")
            self.assertIsNone(u.solicitacoes.obter("SOL-X"))
            self.assertEqual([s["solicitacao_id"] for s in u.solicitacoes.ativas()], ["SOL-1"])
            self.assertEqual([u.solicitacoes.esta_ativa(s) for s in ("SOL-1", "SOL-2", "SOL-X")], [True, False, False])

    def test_ativa_do_paciente_encontra_duplicata(self):
        with self.uow as u:
            u.solicitacoes.salvar(sol("SOL-1"))
            u.commit()
        with self.uow as u:
            self.assertEqual(u.solicitacoes.ativa_do_paciente("PAC-1", "PROC002")["solicitacao_id"], "SOL-1")
            self.assertIsNone(u.solicitacoes.ativa_do_paciente("PAC-1", "PROC001"))

    def test_evento_repetido_e_achado_repetido_nao_duplica(self):
        with self.uow as u:
            u.eventos.salvar({"evento_id": "EVT-1", "solicitacao_id": "SOL-1", "data_evento": "2026-01-05"})
            u.achados.adicionar([achado(), achado()])
            u.commit()
        with self.uow as u:
            self.assertTrue(u.eventos.existe("EVT-1"))
            self.assertFalse(u.eventos.existe("EVT-2"))
            u.achados.adicionar([achado(), achado(C.INTERNACAO, ref="EVT-2")])
            u.commit()
        with self.uow as u:
            self.assertEqual([a.codigo for a in u.achados.da_solicitacao("SOL-1")], [C.PRONTO_SOCORRO, C.INTERNACAO])
            varias = u.achados.de_varias(["SOL-1", "SOL-2"])
            self.assertEqual(({k: len(v) for k, v in varias.items()}), {"SOL-1": 2, "SOL-2": 0})

    def test_ida_e_volta_pelos_repositorios(self):
        a = achado(origem=Origem.LLM, data=None)
        risco = avaliar_risco(None, 4, 5)
        with self.uow as u:
            u.achados.adicionar([a])
            u.estados.salvar("SOL-1", EstadoAprovado("B", 41.2), risco, provisorio=True)
            id = u.sugestoes.criar(sugestao(), HOJE)
            u.commit()
        with self.uow as u:
            self.assertEqual(u.achados.da_solicitacao("SOL-1"), [a])
            self.assertEqual(u.estados.obter("SOL-1"), (EstadoAprovado("B", 41.2), risco))
            self.assertEqual(u.estados.todos(), {"SOL-1": (EstadoAprovado("B", 41.2), risco)})
            r = u.sugestoes.obter(id)
            self.assertEqual((r.sugestao, r.status, r.criada_em), (sugestao(), S.PENDENTE, HOJE))

    def test_ciclo_da_sugestao_e_filtro_por_status(self):
        with self.uow as u:
            a, b = u.sugestoes.criar(sugestao(), HOJE), u.sugestoes.criar(sugestao(), HOJE)
            u.sugestoes.mudar_status(a, "rejeitada", "regulador", HOJE, "não concordo")
            u.commit()
        with self.uow as u:
            self.assertEqual([r.id for r in u.sugestoes.pendentes_de("SOL-1")], [b])
            self.assertEqual([r.id for r in u.sugestoes.listar("rejeitada")], [a])
            self.assertEqual(len(u.sugestoes.listar()), 2)
            r = u.sugestoes.obter(a)
            self.assertEqual((r.status, r.decidida_por, r.decidida_em, r.comentario),
                             (S.REJEITADA, "regulador", HOJE, "não concordo"))
            self.assertIsNone(u.sugestoes.obter(999))

    def test_rollback_em_excecao_e_sem_commit(self):
        with self.assertRaises(RuntimeError):
            with self.uow as u:
                u.solicitacoes.salvar(sol("SOL-1"))
                raise RuntimeError("falhou no meio")
        with self.uow as u:
            u.solicitacoes.salvar(sol("SOL-2"))      # sem commit
        with self.uow as u:
            self.assertEqual(u.solicitacoes.ativas(), [])

    def test_historico_foto_substitui_no_mesmo_dia(self):
        itens = [ItemFila("SOL-1", "B", 40, HOJE, False, False, posicao=1),
                 ItemFila("SOL-2", "D", 0, HOJE, False, True, posicao=2)]
        with self.uow as u:
            u.historico.salvar_foto(HOJE, itens)
            u.historico.salvar_foto(HOJE, itens[:1])
            u.commit()
        with self.uow as u:
            self.assertEqual([x["solicitacao_id"] for x in u.historico.foto(HOJE)], ["SOL-1"])
            self.assertEqual([(d, p) for d, p, _ in u.historico.posicoes("SOL-1")], [(HOJE, 1)])
            u.auditoria.registrar("aprovar", "SOL-1", "#1", "regulador", HOJE)
            u.commit()

    def test_relogio_dia_zero_e_persistencia_entre_sessoes(self):
        self.assertEqual(self.novo_relogio().hoje(), date.min)
        with self.uow as u:
            u.solicitacoes.salvar(sol("SOL-2", entrada="2026-03-01"))
            u.solicitacoes.salvar(sol("SOL-1", entrada="2026-01-10"))
            u.commit()
        r = self.novo_relogio()
        self.assertEqual(r.hoje(), date(2026, 1, 10))
        r.avancar(5)
        r.auto_aprovar = True
        outro = self.novo_relogio()
        self.assertEqual((outro.hoje(), outro.auto_aprovar), (date(2026, 1, 15), True))


class TestContratoFakes(Contrato, unittest.TestCase):
    def criar(self):
        banco = BancoMemoria()
        return UnidadeDeTrabalhoMemoria(banco), lambda: RelogioMemoria(banco)


class TestContratoSQL(Contrato, unittest.TestCase):
    def criar(self):
        fabrica = fabrica_para("sqlite://")
        self.addCleanup(fabrica.kw["bind"].dispose)
        return UnidadeDeTrabalhoSQL(fabrica), lambda: RelogioSQL(fabrica)


class TestConversores(unittest.TestCase):
    def test_ida_e_volta(self):
        for a in (achado(), achado(origem=Origem.LLM, data=None, trecho="")):
            self.assertEqual(achado_de_linha(achado_para_linha(a)), a)
            self.assertEqual(achado_de_dict(achado_para_dict(a)), a)
        linha = sugestao_para_linha(sugestao(), HOJE)
        linha.id = 7
        r = sugestao_de_linha(linha)
        self.assertEqual((r.id, r.sugestao, r.status), (7, sugestao(), S.PENDENTE))
        risco = avaliar_risco(3, 2, 4)
        self.assertEqual(estado_de_linha(estado_para_linha("SOL-1", EstadoAprovado("A2", 60.0), risco, False)),
                         (EstadoAprovado("A2", 60.0), risco))


class ClienteFalso:
    def __init__(self, texto=None, erro=None):
        self.texto, self.erro = texto, erro
        self.models = self

    def generate_content(self, **_):
        if self.erro:
            raise self.erro
        return type("Resposta", (), {"text": self.texto})()


class TestRedator(unittest.TestCase):
    def test_llm_cai_no_template_quando_inventa_referencia_ou_falha(self):
        s, base = sugestao(), sugestao().justificativa
        self.assertEqual(RedatorTemplate().justificar(s, None), base)
        ok = "Paciente subiu de C para B após ida ao PS (EVT-1)."
        self.assertEqual(RedatorLLM(cliente=ClienteFalso(ok)).justificar(s, None), ok)
        self.assertEqual(RedatorLLM(cliente=ClienteFalso("Biópsia EVT-999 positiva.")).justificar(s, None), base)
        self.assertEqual(RedatorLLM(cliente=ClienteFalso(erro=TimeoutError())).justificar(s, None), base)
        self.assertEqual(RedatorLLM(chave="").justificar(s, None), base)


class TestServicoSobreSQL(unittest.TestCase):
    """O serviço roda com UnidadeDeTrabalhoSQL sem mudar uma linha dele."""

    def test_fluxo_completo(self):
        fabrica = fabrica_para("sqlite://")
        self.addCleanup(fabrica.kw["bind"].dispose)
        uow = UnidadeDeTrabalhoSQL(fabrica)
        svc = ServicoFila(lambda: uow, RelogioSQL(fabrica), RedatorTemplate(), {"PROC002": 2, "PROC014": 4})
        svc.receber_solicitacao(sol("SOL-1"))
        svc.receber_solicitacao(dict(sol("SOL-2", pid="PAC-2", proc="PROC014"), cid_principal="C50.9"))
        for r in svc.listar_sugestoes("pendente"):
            svc.aprovar_sugestao(r.id)
        svc.receber_evento({"evento_id": "EVT-1", "solicitacao_id": "SOL-1", "data_evento": "2026-01-12",
                            "tipo_evento": "contato_telefonico", "resultado": "desistiu",
                            "descricao": "Pct informa que nao deseja mais realizar a cirurgia."})
        [remover] = svc.listar_sugestoes("pendente")
        svc.aprovar_sugestao(remover.id)
        svc.avancar_dia(2)
        self.assertEqual([l.solicitacao_id for l in svc.consultar_fila()], ["SOL-2"])
        self.assertEqual(svc.consultar_paciente("SOL-1").ativa, False)
        self.assertIn("SOL-2,1,", svc.exportar_fila_priorizada())


if __name__ == "__main__":
    unittest.main()
