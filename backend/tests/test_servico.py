"""Casos de uso do serviço contra os repositórios em memória (tests/fakes.py).

Cada teste cobre uma regra de negócio do contexto_servico_api.md (numeradas nos nomes).
"""
import csv
import io
import unittest
from datetime import date

from motor.modelos import TipoSugestao as T
from servico.casos_uso import ServicoFila
from servico.erros import ComentarioObrigatorio, NaoEncontrado, TransicaoInvalida
from servico.modelos import StatusSugestao as S
from tests.fakes import BancoMemoria, RedatorFake, RelogioMemoria, UnidadeDeTrabalhoMemoria

PROCS = {"PROC001": 1, "PROC002": 2, "PROC014": 4}


def solicitacao(sid, pid="PAC-1", proc="PROC002", cid="K40.9", entrada="2026-01-10", dor="2", lim="nenhuma", asa="2"):
    return {"solicitacao_id": sid, "paciente_id": pid, "procedimento_id": proc, "cid_principal": cid,
            "data_entrada_fila": entrada, "intensidade_dor_eva": dor, "limitacao_funcional": lim, "asa": asa,
            "comorbidades": "nenhuma", "justificativa_clinica": "Hernia inguinal redutivel, sem complicacoes ha meses."}


def evento(eid, sid, tipo, resultado, data, pid="PAC-1", valor="", descricao=""):
    return {"evento_id": eid, "solicitacao_id": sid, "paciente_id": pid, "data_evento": data, "tipo_evento": tipo,
            "resultado": resultado, "valor_numerico": valor, "descricao": descricao, "origem": "teste"}


class Base(unittest.TestCase):
    def setUp(self):
        self.banco = BancoMemoria()
        self.relogio = RelogioMemoria(self.banco)
        self.svc = ServicoFila(lambda: UnidadeDeTrabalhoMemoria(self.banco), self.relogio, RedatorFake(), PROCS)

    def tipos(self, registradas):
        return [r.sugestao.tipo for r in registradas]

    def aprovar_tudo(self):
        for r in self.svc.listar_sugestoes("pendente"):
            self.svc.aprovar_sugestao(r.id, se_pendente=True)


class TestRecebimento(Base):
    def test_r1_paciente_novo_entra_provisorio_com_classificacao_inicial(self):
        regs = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.assertEqual(self.tipos(regs), [T.CLASSIFICACAO_INICIAL])
        self.assertEqual(regs[0].status, S.PENDENTE)
        self.assertTrue(self.banco.estados["SOL-1"][2])
        [linha] = self.svc.consultar_fila()
        self.assertTrue(linha.provisorio)

    def test_relogio_comeca_na_entrada_mais_antiga(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1", entrada="2026-01-10"))
        self.assertEqual(self.relogio.hoje(), date(2026, 1, 10))

    def test_reenvio_da_mesma_solicitacao_e_ignorado(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.assertEqual(self.svc.receber_solicitacao(solicitacao("SOL-1")), [])

    def test_r2_evento_sem_achado_clinico_nao_gera_mudanca(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.aprovar_tudo()
        regs = self.svc.receber_evento(evento("EVT-1", "SOL-1", "biopsia", "negativo", "2026-01-20"))
        self.assertEqual(regs, [])

    def test_r2_evento_de_piora_gera_subir(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.aprovar_tudo()
        regs = self.svc.receber_evento(evento("EVT-1", "SOL-1", "biopsia", "positivo", "2026-01-20"))
        self.assertEqual(self.tipos(regs), [T.SUBIR])
        self.assertEqual(regs[0].sugestao.classe_para, "A2")

    def test_r3_pendente_de_classe_e_substituida_por_evento_novo(self):
        [inicial] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        [nova] = self.svc.receber_evento(evento("EVT-1", "SOL-1", "pronto_socorro", "observacao", "2026-01-15"))
        self.assertEqual(self.banco.sugestoes[inicial.id].status, S.SUBSTITUIDA)
        self.assertEqual(nova.sugestao.tipo, T.CLASSIFICACAO_INICIAL)
        estado, _, provisorio = self.banco.estados["SOL-1"]
        self.assertEqual((estado.ordo_clinico, provisorio), (nova.sugestao.ordo_clinico_para, True))

    def test_r3_alerta_novo_nao_substitui_mudanca_pendente(self):
        [inicial] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.receber_evento(evento("EVT-1", "SOL-1", "falta", "consulta", "2026-01-15"))
        self.assertEqual(self.banco.sugestoes[inicial.id].status, S.PENDENTE)

    def test_r4_evento_repetido_e_ignorado(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        ev = evento("EVT-1", "SOL-1", "pronto_socorro", "observacao", "2026-01-15")
        self.assertTrue(self.svc.receber_evento(ev))
        self.assertEqual(self.svc.receber_evento(ev), [])

    def test_r4_evento_de_quem_saiu_ou_desconhecido_e_ignorado_com_auditoria(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        [saida] = self.svc.receber_evento(evento("EVT-1", "SOL-1", "contato_telefonico", "desistiu", "2026-01-15",
                                                 descricao="Pct informa que nao deseja mais realizar a cirurgia."))
        self.svc.aprovar_sugestao(saida.id)
        self.assertEqual(self.svc.receber_evento(evento("EVT-2", "SOL-1", "pronto_socorro", "observacao", "2026-01-16")), [])
        self.assertEqual(self.svc.receber_evento(evento("EVT-3", "SOL-X", "pronto_socorro", "observacao", "2026-01-16")), [])
        self.assertEqual([a["acao"] for a in self.banco.auditoria[-2:]], ["evento_ignorado", "evento_ignorado"])


class TestSaidas(Base):
    def test_r5_desistencia_aprovada_registra_saida_com_motivo(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        [saida] = self.svc.receber_evento(evento("EVT-1", "SOL-1", "contato_telefonico", "desistiu", "2026-01-15",
                                                 descricao="Pct informa que nao deseja mais realizar a cirurgia."))
        self.assertEqual(saida.sugestao.tipo, T.REMOVER)
        self.svc.aprovar_sugestao(saida.id)
        self.assertEqual(self.banco.saidas["SOL-1"]["motivo"], "desistencia")
        self.assertEqual(self.svc.consultar_fila(), [])
        pendentes = [r for r in self.banco.sugestoes.values() if r.status == S.PENDENTE]
        self.assertEqual(pendentes, [], "as outras pendentes do paciente que saiu são fechadas")

    def test_r5_outro_servico(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        [saida] = self.svc.receber_evento(evento(
            "EVT-1", "SOL-1", "contato_telefonico", "informou_cirurgia_outro_servico", "2026-01-15",
            descricao="Pct informa que ja realizou o procedimento em outro servico."))
        self.svc.aprovar_sugestao(saida.id)
        self.assertEqual(self.banco.saidas["SOL-1"]["motivo"], "outro_servico")

    def test_r5_motivo_pelo_texto_da_evidencia(self):
        from motor.modelos import Achado, CodigoAchado, Dimensao, Evidencia, Sugestao
        from servico.regras import motivo_saida

        def remover(trecho):
            a = Achado(CodigoAchado.SAIU_DA_FILA, Dimensao.ALERTA, "SOL-1", None, Evidencia("observacao", "SOL-1:observacoes", trecho))
            return motivo_saida(Sugestao("SOL-1", T.REMOVER, "C", None, [a], ""))
        self.assertEqual(remover("Familiar informa que paciente operou pelo convenio.").value, "outro_servico")
        self.assertEqual(remover("Pct informa que ja realizou o procedimento em outro servico.").value, "outro_servico")
        self.assertEqual(remover('Paciente refere que nao deseja mais operar no momento.').value, "desistencia")
        self.assertEqual(remover("PCT DESISTIU DO PROCEDIMENTO. SOLICITA RETIRADA DA FILA.").value, "desistencia")

    def test_r6_duplicata_sugere_remover_a_nova(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        regs = self.svc.receber_solicitacao(solicitacao("SOL-2"))
        remover = next(r for r in regs if r.sugestao.tipo == T.REMOVER)
        self.assertIn("SOL-1", remover.sugestao.justificativa)
        self.svc.aprovar_sugestao(remover.id)
        self.assertEqual(self.banco.saidas["SOL-2"]["motivo"], "duplicata")

    def test_r6_mesmo_paciente_outro_procedimento_nao_e_duplicata(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        regs = self.svc.receber_solicitacao(solicitacao("SOL-2", proc="PROC001"))
        self.assertNotIn(T.REMOVER, self.tipos(regs))


class TestRegulador(Base):
    def test_aprovar_aplica_estado_e_tira_provisorio(self):
        [r] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.aprovar_sugestao(r.id)
        self.assertFalse(self.banco.estados["SOL-1"][2])
        self.assertFalse(self.svc.consultar_fila()[0].provisorio)

    def test_r7_rejeitar_exige_comentario_e_audita(self):
        [r] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        with self.assertRaises(ComentarioObrigatorio):
            self.svc.rejeitar_sugestao(r.id, "  ")
        self.svc.rejeitar_sugestao(r.id, "classe não condiz com o exame físico")
        self.assertEqual(self.banco.sugestoes[r.id].status, S.REJEITADA)
        self.assertEqual(self.banco.auditoria[-1]["acao"], "rejeitar")
        self.assertEqual(self.banco.auditoria[-1]["por"], "regulador")

    def test_transicoes_invalidas(self):
        [r] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.aprovar_sugestao(r.id)
        with self.assertRaises(TransicaoInvalida):
            self.svc.aprovar_sugestao(r.id)
        with self.assertRaises(TransicaoInvalida):
            self.svc.rejeitar_sugestao(r.id, "tarde demais")
        with self.assertRaises(NaoEncontrado):
            self.svc.aprovar_sugestao(999)

    def test_r8_aprovacao_automatica(self):
        self.svc.configurar_simulacao(auto_aprovar=True)
        [r] = self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.assertEqual(r.status, S.APROVADA)
        self.assertEqual(r.decidida_por, "simulacao")
        self.assertFalse(self.banco.estados["SOL-1"][2])

    def test_r8_aprovacao_automatica_de_duplicata_remove(self):
        self.svc.configurar_simulacao(auto_aprovar=True)
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.receber_solicitacao(solicitacao("SOL-2"))
        self.assertEqual([l.solicitacao_id for l in self.svc.consultar_fila()], ["SOL-1"])


class TestConsultas(Base):
    def test_r9_alertas_nao_mexem_na_ordem(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1", asa=""))
        self.svc.receber_solicitacao(solicitacao("SOL-2", pid="PAC-2"))
        self.aprovar_tudo()
        antes = [l.solicitacao_id for l in self.svc.consultar_fila()]
        self.svc.receber_evento(evento("EVT-1", "SOL-2", "hba1c", "resultado", "2026-01-15", pid="PAC-2", valor="10.2"))
        tipos = {a.tipo for a in self.svc.listar_alertas()}
        self.assertIn("hba1c_descontrolada", tipos)
        self.assertIn("sem_asa", tipos)
        self.assertEqual([l.solicitacao_id for l in self.svc.consultar_fila()], antes)

    def test_r10_avancar_dia_tira_foto_por_dia_e_guarda_posicao_anterior(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.aprovar_tudo()
        hoje = self.svc.avancar_dia(3)
        self.assertEqual(hoje, date(2026, 1, 13))
        self.assertEqual(len(self.svc.consultar_paciente("SOL-1").historico), 3)
        [antiga] = self.svc.consultar_fila(date(2026, 1, 12))
        self.assertEqual((antiga.posicao, antiga.posicao_anterior, antiga.dias_em_fila), (1, 1, 2))
        with self.assertRaises(NaoEncontrado):
            self.svc.consultar_fila(date(2025, 1, 1))

    def test_oncologico_passa_na_frente_e_ficha_tem_evidencia(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.receber_solicitacao(solicitacao("SOL-2", pid="PAC-2", cid="C50.9", proc="PROC014"))
        self.aprovar_tudo()
        self.assertEqual(self.svc.consultar_fila()[0].solicitacao_id, "SOL-2")
        ficha = self.svc.consultar_paciente("SOL-2")
        self.assertEqual((ficha.classe, ficha.posicao, ficha.ativa), ("A2", 1, True))
        self.assertTrue(any(a.evidencia.ref == "SOL-2:cid_principal" for a in ficha.achados))
        with self.assertRaises(NaoEncontrado):
            self.svc.consultar_paciente("SOL-X")

    def test_sugestoes_pendentes_vem_com_previa_de_posicao(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.receber_solicitacao(solicitacao("SOL-2", pid="PAC-2"))
        self.aprovar_tudo()
        self.svc.receber_evento(evento("EVT-1", "SOL-2", "biopsia", "positivo", "2026-01-20", pid="PAC-2"))
        [s] = self.svc.listar_sugestoes("pendente")
        self.assertEqual((s.sugestao.posicao_de, s.sugestao.posicao_para), (2, 1))

    def test_exportar_csv_tem_todas_as_ativas_com_justificativa(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        self.svc.receber_solicitacao(solicitacao("SOL-2", pid="PAC-2", cid="C50.9"))
        linhas = list(csv.DictReader(io.StringIO(self.svc.exportar_fila_priorizada())))
        self.assertEqual([l["solicitacao_id"] for l in linhas], ["SOL-2", "SOL-1"])
        self.assertEqual([l["posicao"] for l in linhas], ["1", "2"])
        self.assertTrue(all("provisória" in l["justificativa"] for l in linhas))


if __name__ == "__main__":
    unittest.main()


class TestDecisaoCompartilhada(Base):
    def test_usa_so_o_que_chegou_e_remonta_observacoes(self):
        self.svc.receber_solicitacao(solicitacao("SOL-1"))
        av, usou_llm = self.svc.consultar_decisao_compartilhada("SOL-1")
        self.assertFalse(av.elegivel_decisao_compartilhada)
        self.assertFalse(usou_llm)

        # regra 11: observação chega como evento "observacao" e volta para o campo observacoes
        self.svc.receber_evento(evento("OBS-SOL-1", "SOL-1", "observacao", "", "2026-01-10",
                                       descricao="Necessita TFD para deslocamento. Dificuldade de transporte."))
        av, _ = self.svc.consultar_decisao_compartilhada("SOL-1")
        self.assertTrue(av.elegivel_decisao_compartilhada)
        self.assertEqual(av.status_adesao.value, "barreira_social")
        self.assertIn("transporte", av.itens[0].trecho_evidencia.lower())

    def test_solicitacao_inexistente(self):
        with self.assertRaises(NaoEncontrado):
            self.svc.consultar_decisao_compartilhada("SOL-X")


class RedatorLento(RedatorFake):
    def explicar(self, s):
        import time
        time.sleep(2)
        return "texto do LLM"

    def explicar_sem_llm(self, s):
        return "template"


class TestPrazoDaExplicacao(Base):
    def test_llm_lento_nao_trava_a_listagem_e_cai_no_template(self):
        import time
        self.svc.redator = RedatorLento()
        self.svc.PRAZO_EXPLICACAO = 0.2
        for i in range(3):
            self.svc.receber_solicitacao(solicitacao(f"SOL-{i}", pid=f"PAC-{i}"))
        t0 = time.perf_counter()
        pendentes = self.svc.listar_sugestoes("pendente")
        self.assertLess(time.perf_counter() - t0, 1.5)
        self.assertEqual({r.sugestao.explicacao for r in pendentes}, {"template"})
