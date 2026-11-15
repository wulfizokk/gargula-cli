import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from gargula import ads, agente, checkout, cli, config, criativos, cro, dna, ferramentas, llm, ui, zap


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        limpo = {k: v for k, v in os.environ.items()
                 if not k.endswith("_API_KEY") and not k.startswith(("GARGULA", "EVOLUTION", "WHATSAPP", "META_"))}
        limpo["GARGULA_HOME"] = self.tmp.name
        self.env = mock.patch.dict(os.environ, limpo, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class TestMascote(unittest.TestCase):
    def test_sprite_retangular_e_linhas_pela_metade(self):
        self.assertEqual(len({len(l) for l in ui.MASCOTE}), 1)
        self.assertEqual(len(ui.desenhar(cor=False)), (len(ui.MASCOTE) + 1) // 2)

    def test_sem_cor_nao_tem_ansi_e_olhos_viram_buraco(self):
        txt = ui.banner("0.1.0", "openai", "x", "geral", cor=False)
        self.assertNotIn("\x1b", txt)
        self.assertIn("Gárgula CLI", txt)

    def test_com_cor_usa_roxo(self):
        self.assertIn("38;2;139;92;246", "".join(ui.desenhar(cor=True)))

    def test_markdown_fica_limpo_sem_cor(self):
        txt = ui.formatar_markdown("## Plano\n\n- **Meta Ads**: teste `CPA`\n> nota", cor=False)
        self.assertEqual(txt, "Plano\n\n• Meta Ads: teste CPA\n│ nota")
        self.assertNotIn("**", txt)

    def test_resposta_tem_identidade_e_recuo(self):
        with mock.patch("sys.stdout") as out:
            ui.resposta("Oi\n\n- item", cor=False)
        impresso = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertIn("● Gárgula", impresso)
        self.assertIn("  • item", impresso)


class TestConfig(Base):
    def test_padrao_e_anthropic(self):
        r = config.resolver_llm()
        self.assertEqual((r["provedor"], r["tipo"]), ("anthropic", "anthropic"))
        self.assertIsNone(r["chave"])

    def test_prioridade_env_sobre_arquivo(self):
        config.definir("chave.openai", "arquivo-1234")
        self.assertEqual(config.resolver_llm("openai")["chave"], "arquivo-1234")
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "env-5678"}):
            self.assertEqual(config.resolver_llm("openai")["chave"], "env-5678")

    def test_modelo_salvo_nao_vaza_para_outro_provedor(self):
        config.definir("provedor", "openai")
        config.definir("modelo", "gpt-x")
        self.assertEqual(config.resolver_llm()["modelo"], "gpt-x")
        self.assertEqual(config.resolver_llm("gemini")["modelo"], config.PROVEDORES["gemini"]["modelo"])

    def test_workspace_anthropic(self):
        self.assertIsNone(config.resolver_llm("anthropic")["workspace"])
        with mock.patch.dict(os.environ, {"ANTHROPIC_WORKSPACE_ID": "wrkspc_1"}):
            self.assertEqual(config.resolver_llm("anthropic")["workspace"], "wrkspc_1")
            self.assertIsNone(config.resolver_llm("openai")["workspace"])

    def test_carrega_env_sem_sobrescrever(self):
        cofre = Path(self.tmp.name) / "cofre.env"
        cofre.write_text('# chaves\nexport GEMINI_API_KEY="g-123"\nOPENAI_API_KEY=o-456\n', encoding="utf-8")
        config.definir("env_arquivos", str(cofre))
        os.environ["OPENAI_API_KEY"] = "ja-existia"
        self.assertEqual(config.carregar_envs(), [str(cofre)])
        self.assertEqual(os.environ["GEMINI_API_KEY"], "g-123")
        self.assertEqual(os.environ["OPENAI_API_KEY"], "ja-existia")

    def test_provedor_invalido(self):
        with self.assertRaises(ValueError):
            config.resolver_llm("nao-existe")

    def test_mascara(self):
        self.assertTrue(config.e_secreta("chave.openai"))
        self.assertTrue(config.e_secreta("meta.token"))
        self.assertFalse(config.e_secreta("modelo"))
        self.assertEqual(config.mascarar("sk-abcdefgh1234"), "••••1234")


class TestLLM(unittest.TestCase):
    MSGS = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]

    def test_anthropic(self):
        url, h, c = llm.montar_requisicao("anthropic", "https://a/v1", "k", "m", "sis", self.MSGS)
        self.assertEqual(url, "https://a/v1/messages")
        self.assertEqual(h["x-api-key"], "k")
        self.assertEqual(c["system"][0]["text"], "sis")
        self.assertEqual(c["system"][0]["cache_control"], {"type": "ephemeral"})

    def test_openai_coloca_sistema_primeiro(self):
        url, h, c = llm.montar_requisicao("openai", "https://o/v1", "k", "m", "sis", self.MSGS)
        self.assertEqual(url, "https://o/v1/chat/completions")
        self.assertEqual(h["Authorization"], "Bearer k")
        self.assertEqual(c["messages"][0], {"role": "system", "content": "sis"})
        self.assertEqual(c["max_tokens"], llm.max_tokens())  # evita o 402 do OpenRouter

    def test_gemini_troca_assistant_por_model(self):
        url, h, c = llm.montar_requisicao("gemini", "https://g/v1beta", "k", "gm", "sis", self.MSGS)
        self.assertTrue(url.endswith("/models/gm:streamGenerateContent?alt=sse"))
        self.assertEqual([x["role"] for x in c["contents"]], ["user", "model"])

    def test_eventos_de_texto(self):
        for tipo, ev, esperado in (
            ("anthropic", {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "a"}}, "a"),
            ("openai", {"choices": [{"delta": {"content": "b"}}]}, "b"),
            ("gemini", {"candidates": [{"content": {"parts": [{"text": "c"}]}}]}, "c")):
            acc = llm.Acumulador(tipo)
            acc.evento(ev)
            self.assertEqual(acc.resultado()["texto"], esperado)

    def test_sse_ignora_done_e_lixo(self):
        linhas = [b"event: x\n", b"data: {\"a\": 1}\n", b"\n", b"data: [DONE]\n", b"data: {quebrado\n"]
        self.assertEqual(list(llm.ler_sse(linhas)), [{"a": 1}])

    def test_sem_chave_avisa_onde_configurar(self):
        r = {"provedor": "openai", "tipo": "openai", "base": "https://x", "modelo": "m",
             "chave": None, "env": "OPENAI_API_KEY"}
        with self.assertRaisesRegex(llm.ErroLLM, "OPENAI_API_KEY"):
            llm.conversar(r, "s", [{"role": "user", "content": "oi"}])


class _ServidorFalso(BaseHTTPRequestHandler):
    """Responde como uma API compatível com OpenAI em streaming."""
    recebido = {}

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _ServidorFalso.recebido = {"corpo": corpo, "auth": self.headers.get("Authorization")}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for pedaco in ("Olá, ", "empreendedor!"):
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": pedaco}}]}).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *a):
        pass


class TestStreamingPonta(unittest.TestCase):
    def test_conversa_completa_com_servidor_local(self):
        srv = HTTPServer(("127.0.0.1", 0), _ServidorFalso)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = {"provedor": "compativel", "tipo": "openai", "base": f"http://127.0.0.1:{srv.server_port}/v1",
                 "modelo": "teste", "chave": "k123", "env": None}
            pedacos = []
            texto = llm.conversar(r, "sis", [{"role": "user", "content": "oi"}], ao_pedaco=pedacos.append)["texto"]
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(texto, "Olá, empreendedor!")
        self.assertEqual(pedacos, ["Olá, ", "empreendedor!"])
        self.assertEqual(_ServidorFalso.recebido["auth"], "Bearer k123")
        self.assertTrue(_ServidorFalso.recebido["corpo"]["stream"])


class TestZap(Base):
    def test_normaliza_numero_brasileiro(self):
        self.assertEqual(zap.normalizar_numero("(48) 99999-0000"), "5548999990000")
        self.assertEqual(zap.normalizar_numero("+55 48 99999-0000"), "5548999990000")

    def test_recusa_lote(self):
        for lote in ("5548999990000,5548988887777", "5548999990000;5548988887777",
                     "5548999990000\n5548988887777", "5548999990000 5548988887777"):
            with self.assertRaises(zap.ErroZap):
                zap.normalizar_numero(lote)

    def test_intervalo_minimo(self):
        self.assertEqual(zap.segundos_para_liberar(), 0)
        zap.registrar_envio("5548999990000", "evolution", agora=1000)
        self.assertEqual(zap.segundos_para_liberar(agora=1010), 50)
        self.assertEqual(zap.segundos_para_liberar(agora=1061), 0)
        log = json.loads((Path(self.tmp.name) / "zap_envios.json").read_text())
        self.assertEqual(log["historico"][0]["para"], "…0000")  # número inteiro não fica salvo

    def test_evolution_sem_config(self):
        with self.assertRaisesRegex(zap.ErroZap, "evolution.url"):
            zap.montar_envio("evolution", "5548999990000", "oi")

    def test_cloud_monta_corpo(self):
        config.definir("cloud.token", "t")
        config.definir("cloud.phone_id", "123")
        url, h, c = zap.montar_envio("cloud", "5548999990000", "oi")
        self.assertIn("/123/messages", url)
        self.assertEqual(c["text"]["body"], "oi")

    def test_enviar_sem_flag_e_so_previa(self):
        with mock.patch.object(zap, "enviar") as env:
            self.assertEqual(cli.main(["zap", "enviar", "--para", "48999990000", "--texto", "oi"]), 0)
            env.assert_not_called()


class TestAds(Base):
    LINHA = {"campaign_name": "Black", "spend": "100", "impressions": "10000", "clicks": "200",
             "ctr": "2", "cpc": "0.5", "cpm": "10",
             "actions": [{"action_type": "omni_purchase", "value": "4"},
                         {"action_type": "purchase", "value": "4"}],
             "action_values": [{"action_type": "omni_purchase", "value": "400"}]}

    def test_resumo_nao_conta_compra_duas_vezes(self):
        r = ads.resumir(self.LINHA)
        self.assertEqual((r["compras"], r["cpa"], r["roas"]), (4, 25.0, 4.0))

    def test_csv_e_tabela(self):
        p = Path(self.tmp.name) / "m.csv"
        p.write_text("nome,gasto,impressoes,cliques,compras,receita\nTopo,50,5000,100,0,0\n", encoding="utf-8")
        r = [ads.resumir(l) for l in ads.carregar_arquivo(str(p))]
        self.assertEqual((r[0]["nome"], r[0]["ctr"], r[0]["cpa"]), ("Topo", 2.0, None))
        self.assertIn("R$ 50,00", ads.tabela(r))

    def test_sem_token(self):
        with self.assertRaisesRegex(ads.ErroAds, "meta.token"):
            ads.buscar("act_1")


class TestCLI(Base):
    def test_versao(self):
        with self.assertRaises(SystemExit) as s:
            cli.main(["--version"])
        self.assertEqual(s.exception.code, 0)

    def test_config_set_e_mostrar_mascara(self):
        cli.main(["config", "set", "chave.openai", "sk-segredo-9999"])
        with mock.patch("sys.stdout") as out:
            cli.main(["config", "mostrar"])
        impresso = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertIn("••••9999", impresso)
        self.assertNotIn("segredo", impresso)


class TestChamadasDeFerramenta(unittest.TestCase):
    def test_anthropic_monta_json_em_pedacos(self):
        acc = llm.Acumulador("anthropic")
        for ev in ({"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
                   {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Vou ler."}},
                   {"type": "content_block_start", "index": 1,
                    "content_block": {"type": "tool_use", "id": "tu1", "name": "ler_arquivo", "input": {}}},
                   {"type": "content_block_delta", "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": '{"cami'}},
                   {"type": "content_block_delta", "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": 'nho": "a.md"}'}},
                   {"type": "message_delta", "delta": {"stop_reason": "tool_use"}}):
            acc.evento(ev)
        r = acc.resultado()
        self.assertEqual(r["texto"], "Vou ler.")
        self.assertEqual(r["chamadas"], [{"id": "tu1", "nome": "ler_arquivo", "args": {"caminho": "a.md"}}])
        self.assertEqual(r["parada"], "tool_use")

    def test_openai_junta_argumentos_por_indice(self):
        acc = llm.Acumulador("openai")
        acc.evento({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "listar", "arguments": '{"cam'}}]}}]})
        acc.evento({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": 'inho": "."}'}}]}, "finish_reason": "tool_calls"}]})
        self.assertEqual(acc.resultado()["chamadas"], [{"id": "c1", "nome": "listar", "args": {"caminho": "."}}])

    def test_gemini_guarda_partes_brutas(self):
        acc = llm.Acumulador("gemini")
        parte = {"functionCall": {"name": "buscar_notas", "args": {"termo": "usetag"}}, "thoughtSignature": "xyz"}
        acc.evento({"candidates": [{"content": {"parts": [parte]}}]})
        r = acc.resultado()
        self.assertEqual(r["chamadas"][0]["args"], {"termo": "usetag"})
        self.assertEqual(r["bruto"], [parte])  # thoughtSignature volta intacto na próxima rodada

    def test_historico_convertido_para_cada_api(self):
        hist = [{"role": "user", "content": "lê"},
                {"role": "assistant", "content": "", "chamadas": [{"id": "x1", "nome": "listar", "args": {}}]},
                {"role": "ferramenta", "resultados": [{"id": "x1", "nome": "listar", "conteudo": "a.md", "erro": False}]}]
        defs = ferramentas.definicoes_api()
        _, _, a = llm.montar_requisicao("anthropic", "u", "k", "m", "s", hist, ferramentas=defs)
        self.assertEqual(a["messages"][1]["content"][0]["type"], "tool_use")
        self.assertEqual(a["messages"][2]["content"][0]["tool_use_id"], "x1")
        self.assertIn("input_schema", a["tools"][0])
        _, _, o = llm.montar_requisicao("openai", "u", "k", "m", "s", hist, ferramentas=defs)
        self.assertEqual(o["messages"][2]["tool_calls"][0]["function"]["name"], "listar")
        self.assertEqual(o["messages"][3], {"role": "tool", "tool_call_id": "x1", "content": "a.md"})
        _, _, g = llm.montar_requisicao("gemini", "u", "k", "m", "s", hist, ferramentas=defs)
        self.assertEqual(g["contents"][1]["parts"][0]["functionCall"]["name"], "listar")
        self.assertIn("functionResponse", g["contents"][2]["parts"][0])
        self.assertIn("functionDeclarations", g["tools"][0])


class TestFerramentas(Base):
    def setUp(self):
        super().setUp()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        Path("notas").mkdir()
        Path("notas/usetag.md").write_text("# USETAG\nplaca NFC de avaliação\npreço kit\n", encoding="utf-8")
        Path("notas/.secrets").mkdir()
        Path("notas/.secrets/chaves.env").write_text("API=segredo", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        super().tearDown()

    def test_ler_listar_buscar(self):
        self.assertIn("2\tplaca NFC", ferramentas.ler_arquivo("notas/usetag.md"))
        self.assertEqual(ferramentas.listar("notas"), "usetag.md")  # .secrets some da lista
        self.assertIn("usetag.md:2:", ferramentas.buscar_texto("nfc", "notas"))
        self.assertNotIn("segredo", ferramentas.buscar_texto("segredo", "."))

    def test_segredo_bloqueado(self):
        conteudo, erro = ferramentas.rodar("ler_arquivo", {"caminho": "notas/.secrets/chaves.env"})
        self.assertTrue(erro)
        self.assertIn("protegido", conteudo)

    def test_editar_exige_trecho_unico(self):
        Path("x.txt").write_text("a\na\nb\n", encoding="utf-8")
        self.assertTrue(ferramentas.rodar("editar_arquivo", {"caminho": "x.txt", "antigo": "a", "novo": "z"})[1])
        ferramentas.rodar("editar_arquivo", {"caminho": "x.txt", "antigo": "b", "novo": "c"})
        self.assertEqual(Path("x.txt").read_text(encoding="utf-8"), "a\na\nc\n")

    def test_buscar_notas_na_pasta_base(self):
        config.definir("pasta_base", str(Path(self.tmp.name) / "notas"))
        self.assertIn("usetag.md", ferramentas.buscar_notas("placa avaliação"))

    def test_terminal_nao_herda_chaves(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-x", "META_ACCESS_TOKEN": "t", "PATH_X": "ok"}):
            env = ferramentas._env_sem_segredos()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("META_ACCESS_TOKEN", env)
        self.assertEqual(env["PATH_X"], "ok")

    def test_executar(self):
        saida = ferramentas.executar("echo gargula")
        self.assertIn("[código de saída 0]", saida)
        self.assertIn("gargula", saida)


class TestAgente(Base):
    LLM = {"provedor": "openai", "tipo": "openai", "base": "u", "modelo": "m", "chave": "k", "env": "X"}

    def _respostas(self, *rs):
        fila = list(rs)
        return mock.patch.object(agente, "conversar", side_effect=lambda *a, **k: fila.pop(0))

    def test_ciclo_ferramenta_e_resposta_final(self):
        Path(self.tmp.name, "nota.md").write_text("ticket médio R$ 97", encoding="utf-8")
        caminho = str(Path(self.tmp.name, "nota.md"))
        r1 = {"texto": "", "chamadas": [{"id": "1", "nome": "ler_arquivo", "args": {"caminho": caminho}}],
              "parada": "tool_calls"}
        r2 = {"texto": "O ticket é R$ 97.", "chamadas": [], "parada": "stop"}
        a = agente.Agente(self.LLM)
        with self._respostas(r1, r2), mock.patch("sys.stdout"):
            final = a.turno("qual o ticket?")
        self.assertEqual(final, "O ticket é R$ 97.")
        resultado = a.historico[2]["resultados"][0]
        self.assertIn("R$ 97", resultado["conteudo"])
        self.assertFalse(resultado["erro"])

    def test_escrita_sem_terminal_e_sem_auto_e_negada(self):
        r1 = {"texto": "", "chamadas": [{"id": "1", "nome": "executar", "args": {"comando": "echo oi"}}],
              "parada": "tool_calls"}
        r2 = {"texto": "ok", "chamadas": [], "parada": "stop"}
        a = agente.Agente(self.LLM)
        with self._respostas(r1, r2), mock.patch("sys.stdout"), mock.patch("sys.stdin") as stdin:
            stdin.isatty.return_value = False
            a.turno("roda")
        self.assertTrue(a.historico[2]["resultados"][0]["erro"])
        self.assertIn("sem permissão", a.historico[2]["resultados"][0]["conteudo"])

    def test_auto_libera_comando_mas_nao_whatsapp(self):
        a = agente.Agente(self.LLM, auto=True)
        with mock.patch("sys.stdin") as stdin:
            stdin.isatty.return_value = False
            self.assertTrue(a.permitido("executar", {"comando": "dir"})[0])
            self.assertFalse(a.permitido("whatsapp_enviar", {"para": "1", "texto": "oi"})[0])

    def test_contexto_carrega_agents_md(self):
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            Path("AGENTS.md").write_text("regra: responder curto", encoding="utf-8")
            self.assertIn("responder curto", agente.Agente(self.LLM).sistema())
        finally:
            os.chdir(cwd)


class TestDNA(Base):
    def test_salvar_e_obter_dna(self):
        dna.salvar("avatar", "Dor: CPA caro demais")
        self.assertEqual(dna.obter("avatar"), "Dor: CPA caro demais")
        self.assertIn("avatar.md", str(dna.arquivo("avatar")))

    def test_anti_slop_padrao(self):
        txt = dna.obter("anti_slop")
        self.assertIn("Filtro Anti-Slop", txt)
        self.assertIn("no mundo acelerado de hoje", txt)

    def test_formatar_contexto(self):
        dna.salvar("oferta", "Promessa: Dobrar faturamento")
        ctx = dna.formatar_contexto()
        self.assertIn("Offer DNA", ctx)
        self.assertIn("Dobrar faturamento", ctx)
        self.assertIn("Regras Anti-Slop", ctx)

    def test_ferramenta_obter_dna(self):
        dna.salvar("marca", "Tom: Sem papas na língua")
        saida, erro = ferramentas.rodar("obter_dna", {"categoria": "marca"})
        self.assertFalse(erro)
        self.assertEqual(saida, "Tom: Sem papas na língua")


class TestCheckout(Base):
    def test_identificar_transacao_formatos(self):
        # formato estilo Kiwify / BR
        l1 = {"Status": "Aprovada", "Valor Líquido": "R$ 197,50", "utm_campaign": "natal_promo"}
        t1 = checkout.identificar_transacao(l1)
        self.assertEqual(t1["status"], "pago")
        self.assertEqual(t1["valor"], 197.5)
        self.assertEqual(t1["campanha"], "natal_promo")

        # formato com status pendente (boleto)
        l2 = {"status": "aguardando pagamento", "valor": "97,00", "campanha": "natal_promo"}
        t2 = checkout.identificar_transacao(l2)
        self.assertEqual(t2["status"], "pendente")
        self.assertEqual(t2["valor"], 97.0)

        # formato estornado
        l3 = {"status": "reembolsado", "valor": "97.00"}
        t3 = checkout.identificar_transacao(l3)
        self.assertEqual(t3["status"], "cancelado")

    def test_reconciliacao_e_alerta_boleto(self):
        ads_res = [{
            "nome": "campanha_natal",
            "gasto": 300.0,
            "compras": 6,
            "receita": 600.0,
            "roas": 2.0
        }]
        checkout_linhas = [
            {"status": "aprovado", "valor": "100,00", "campanha": "campanha_natal"},
            {"status": "aguardando", "valor": "100,00", "campanha": "campanha_natal"},
            {"status": "aguardando", "valor": "100,00", "campanha": "campanha_natal"},
        ]
        res = checkout.reconciliar(ads_res, checkout_linhas)
        camp = res["campanhas"][0]
        self.assertEqual(camp["real_pagas"], 1)
        self.assertEqual(camp["real_pendentes"], 2)
        self.assertEqual(camp["real_receita"], 100.0)
        self.assertEqual(camp["real_roas"], 0.33)
        self.assertEqual(camp["veredito"], "ALERTA (BOLETO/PIX FANTASMA)")
        self.assertEqual(res["totais"]["lucro_real_total"], -200.0)

        tabela_str = checkout.formatar_tabela(res)
        self.assertIn("Gasto Meta", tabela_str)
        self.assertIn("BOLETO/PIX FANTASMA", tabela_str)


class TestCRO(Base):
    def test_extrair_conteudo_direto_e_arquivo(self):
        self.assertEqual(cro.extrair_conteudo(texto_direto="conteudo direto"), "conteudo direto")
        f = Path(self.tmp.name) / "lp.html"
        f.write_text("<h1>Oferta de Natal</h1>", encoding="utf-8")
        self.assertEqual(cro.extrair_conteudo(arquivo=str(f)), "<h1>Oferta de Natal</h1>")


class TestCriativos(Base):
    def test_gerar_ganchos_e_roteiro(self):
        with mock.patch("gargula.criativos.responder") as resp:
            criativos.gerar_ganchos({"provedor": "openai"}, "Curso de Inglês", "Adultos", "sem gramática")
            self.assertTrue(resp.called)
            pedido = resp.call_args[0][2][0]["content"]
            self.assertIn("Curso de Inglês", pedido)
            self.assertIn("QUEBRA DE PADRÃO", pedido)

        with mock.patch("gargula.criativos.responder") as resp:
            criativos.gerar_roteiro({"provedor": "openai"}, "Placa NFC", "Barbearias", "reels")
            self.assertTrue(resp.called)
            pedido = resp.call_args[0][2][0]["content"]
            self.assertIn("Placa NFC", pedido)
            self.assertIn("GANCHO VISUAL", pedido)


if __name__ == "__main__":
    unittest.main()
