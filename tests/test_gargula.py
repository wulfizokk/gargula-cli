import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from gargula import ads, agente, checkout, cli, config, criativos, crm, cro, dna, ferramentas, imagens, llm, repl, ui, zap


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        limpo = {k: v for k, v in os.environ.items()
                 if not k.endswith("_API_KEY") and not k.startswith(("GARGULA", "EVOLUTION", "WHATSAPP", "META_", "DRAEL"))}
        limpo["GARGULA_HOME"] = self.tmp.name
        limpo["XDG_CONFIG_HOME"] = self.tmp.name
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
    def test_padrao_e_drael_core(self):
        r = config.resolver_llm()
        self.assertEqual((r["provedor"], r["tipo"], r["modelo"]), ("drael", "openai", "drael-v1"))
        self.assertEqual(r["base"], "https://drael.sh/v1")
        self.assertIsNone(r["chave"])

    def test_drael_login_credencial_host_e_fallback_env(self):
        drael_dir = Path(self.tmp.name) / "drael"
        drael_dir.mkdir(parents=True)
        (drael_dir / "credential").write_text("drael-login-tok\n", encoding="utf-8")
        (drael_dir / "config.json").write_text('{"host": "https://custom.drael.sh/"}', encoding="utf-8")

        r = config.resolver_llm()
        self.assertEqual(r["chave"], "drael-login-tok")
        self.assertEqual(r["base"], "https://custom.drael.sh/v1")

        with mock.patch.dict(os.environ, {"DRAEL_API_KEY": "alt-123"}):
            self.assertEqual(config.resolver_llm()["chave"], "alt-123")
        with mock.patch.dict(os.environ, {"DRAEL_KEY": "main-456", "DRAEL_API_KEY": "alt-123", "DRAEL_HOST": "https://h.drael.sh"}):
            r2 = config.resolver_llm()
            self.assertEqual(r2["chave"], "main-456")
            self.assertEqual(r2["base"], "https://h.drael.sh/v1")

    def test_max_tokens_drael_e_padrao(self):
        self.assertEqual(llm.max_tokens("drael-v1"), 32768)
        self.assertEqual(llm.max_tokens("gpt-4o-mini"), 4096)
        _, _, body = llm.montar_requisicao("openai", "https://drael.sh/v1", "k", "drael-v1", "s", [{"role": "user", "content": "oi"}])
        self.assertEqual(body["max_tokens"], 32768)

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
        with mock.patch.dict(os.environ, {"DRAEL_KEY": "dr-x", "ANTHROPIC_API_KEY": "sk-x", "META_ACCESS_TOKEN": "t", "PATH_X": "ok"}):
            env = ferramentas._env_sem_segredos()
        self.assertNotIn("DRAEL_KEY", env)
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


class TestCRM(Base):
    def test_crm_catalogo(self):
        cat = crm.obter_catalogo()
        self.assertIsInstance(cat, list)
        self.assertTrue(any("kit-10" in item.get("id", "") for item in cat))
        tabela = crm.formatar_tabela_catalogo()
        self.assertIn("Kit 10", tabela)
        self.assertIn("Preço à Vista", tabela)

    def test_crm_status(self):
        st_txt = crm.formatar_status()
        self.assertIn("STATUS DO GÁRGULA CRM", st_txt)

    def test_ferramentas_crm(self):
        s1, e1 = ferramentas.rodar("crm_status", {})
        self.assertFalse(e1)
        self.assertIn("STATUS DO GÁRGULA CRM", s1)

        s2, e2 = ferramentas.rodar("crm_catalogo", {})
        self.assertFalse(e2)
        self.assertIn("Kit 10", s2)


class TestUIExtras(unittest.TestCase):
    def test_amarelo_definido(self):
        self.assertIsNotNone(getattr(ui, "AMARELO", None))
        self.assertEqual(ui.AMARELO, (251, 191, 36))

    def test_banner_com_yolo_alinhado(self):
        txt = ui.banner("0.3.0", "anthropic", "claude-sonnet-5-5", "geral", cor=False, auto=True)
        self.assertIn("[YOLO]", txt)
        bordas = [l for l in txt.splitlines() if l.startswith(("╭", "│", "╰"))]
        self.assertEqual(len({len(l) for l in bordas}), 1)


class TestYoloEImagens(Base):
    def test_yolo_via_config(self):
        config.definir("yolo", "true")
        parser = cli.montar_parser()
        args = parser.parse_args([])
        self.assertTrue(cli._modo_auto(args))

    def test_yolo_via_flag_antes_ou_depois_de_chat(self):
        parser = cli.montar_parser()
        for argv in (["--yolo"], ["--yolo", "chat", "oi"], ["chat", "--yolo", "oi"]):
            args = parser.parse_args(argv)
            self.assertTrue(args.auto)
            self.assertTrue(cli._modo_auto(args))

    def test_extrair_imagens_dedup_limite_e_bloqueio(self):
        img = Path(self.tmp.name) / "criativo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
        pasta_sec = Path(self.tmp.name) / ".secrets"
        pasta_sec.mkdir()
        img_sec = pasta_sec / "token.png"
        img_sec.write_bytes(b"png")

        avisos = []
        txt, imgs = imagens.extrair_imagens(f'analise "{img}" e {img} e "{img_sec}"', avisos=avisos)
        self.assertIn("analise", txt)
        self.assertEqual(len(imgs), 1)
        self.assertEqual(imgs[0]["nome"], "criativo.png")
        self.assertTrue(any("bloqueada" in a for a in avisos))

        with mock.patch.object(imagens, "LIMITE_BYTES", 50):
            avisos_tam = []
            _, imgs_tam = imagens.extrair_imagens(str(img), avisos=avisos_tam)
            self.assertEqual(imgs_tam, [])
            self.assertTrue(any("excede" in a for a in avisos_tam))

    def test_compactar_imagens_antigas(self):
        hist = [
            {"role": "user", "content": "um", "imagens": [{"nome": "1.png", "base64": "A"}]},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "dois", "imagens": [{"nome": "2.png", "base64": "B"}]},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "tres", "imagens": [{"nome": "3.png", "base64": "C"}]},
        ]
        agente._compactar_imagens_antigas(hist, manter=2)
        self.assertNotIn("imagens", hist[0])
        self.assertIn("1.png", hist[0]["content"])
        self.assertIn("imagens", hist[2])
        self.assertIn("imagens", hist[4])

    def test_multimodal_formatos_api(self):
        imgs = [{"caminho": "x.png", "nome": "x.png", "mime": "image/png", "base64": "QUJD", "kb": 1}]
        msgs = [{"role": "user", "content": "analisa isso", "imagens": imgs}]

        ant = llm._msgs_anthropic(msgs)
        self.assertEqual(ant[0]["role"], "user")
        self.assertEqual(len(ant[0]["content"]), 2)
        self.assertEqual(ant[0]["content"][0]["type"], "image")
        self.assertEqual(ant[0]["content"][0]["source"]["data"], "QUJD")

        oai = llm._msgs_openai(msgs)
        self.assertEqual(oai[0]["role"], "user")
        self.assertEqual(len(oai[0]["content"]), 2)
        self.assertIn("data:image/png;base64,QUJD", oai[0]["content"][0]["image_url"]["url"])

        gem = llm._msgs_gemini(msgs)
        self.assertEqual(gem[0]["role"], "user")
        self.assertEqual(gem[0]["parts"][0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(gem[0]["parts"][0]["inline_data"]["data"], "QUJD")


class TestAuditoriaFixes(Base):
    def test_salvar_conversa_com_ferramentas_e_imagens(self):
        hist = [
            {"role": "user", "content": "veja o caixa", "imagens": [{"nome": "print.png", "base64": "AAA"}]},
            {"role": "assistant", "content": "", "chamadas": [{"id": "c1", "nome": "crm_status", "args": {}}]},
            {"role": "ferramenta", "resultados": [{"id": "c1", "nome": "crm_status", "conteudo": "OK ativo", "erro": False}]},
            {"role": "assistant", "content": "Tudo certo.", "chamadas": []},
        ]
        destino = Path(self.tmp.name) / "chat.md"
        salvo = repl.salvar_conversa(hist, str(destino))
        conteudo = salvo.read_text(encoding="utf-8")
        self.assertIn("print.png", conteudo)
        self.assertIn("`crm_status` (ok): OK ativo", conteudo)
        self.assertIn("Tudo certo.", conteudo)
        self.assertNotIn("AAA", conteudo)

    def test_checkout_sem_dupla_contagem_e_sem_espacos(self):
        ads_res = [
            {"nome": "Black", "gasto": 100.0, "compras": 1, "receita": 100.0, "roas": 1.0},
            {"nome": "Black - Remarketing", "gasto": 100.0, "compras": 2, "receita": 200.0, "roas": 2.0},
        ]
        linhas = [
            {"status": "aprovado", "Valor Líquido": "R$ 200,00", "valor_desconto": "50,00", "utm_campaign": "Black - Remarketing"},
            {"status": "aprovado", "valor": "100,00", "utm_campaign": "   "},  # sem UTM válida
        ]
        res = checkout.reconciliar(ads_res, linhas)
        self.assertEqual(res["campanhas"][0]["real_pagas"], 0)
        self.assertEqual(res["campanhas"][1]["real_pagas"], 1)
        self.assertEqual(res["campanhas"][1]["real_receita"], 200.0)
        self.assertEqual(res["totais"]["receita_real_total"], 200.0)

    def test_ads_csv_ptbr_e_ponto_e_virgula(self):
        p = Path(self.tmp.name) / "meta_pt.csv"
        p.write_text(
            "Nome da campanha;Valor usado (BRL);Impressões;Cliques no link;Compras;Valor de conversão da compra\n"
            "Escala Natal;1.250,50;50000;1000;10;R$ 3.751,50\n",
            encoding="utf-8",
        )
        linhas = ads.carregar_arquivo(str(p))
        r = ads.resumir(linhas[0])
        self.assertEqual(r["nome"], "Escala Natal")
        self.assertEqual(r["gasto"], 1250.5)
        self.assertEqual(r["compras"], 10)
        self.assertEqual(r["receita"], 3751.5)
        self.assertEqual(r["roas"], 3.0)

    def test_crm_pasta_detecta_so_worker_sem_painel(self):
        proj = Path(self.tmp.name) / "Projetos" / "crm-usetag"
        (proj / "worker").mkdir(parents=True)
        with mock.patch("pathlib.Path.home", return_value=Path(self.tmp.name)):
            self.assertEqual(crm.pasta_crm(), proj)

    def test_ler_url_bloqueia_ssrf_local_e_privado(self):
        for url in ("http://localhost:8080/", "http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data/"):
            with self.assertRaisesRegex(ferramentas.ErroFerramenta, "bloqueado"):
                ferramentas.ler_url(url)

    def test_cli_reconciliar_aceita_flag_ads_e_arquivo(self):
        parser = cli.montar_parser()
        a1 = parser.parse_args(["ads", "reconciliar", "--arquivo", "a.csv", "--checkout", "b.csv"])
        a2 = parser.parse_args(["ads", "reconciliar", "--ads", "a.csv", "--checkout", "b.csv"])
        self.assertEqual(a1.arquivo, "a.csv")
        self.assertEqual(a2.arquivo, "a.csv")

    def test_agente_desfaz_turno_multipasso_em_erro(self):
        llm_fake = {"provedor": "openai", "tipo": "openai", "base": "u", "modelo": "m", "chave": "k", "env": "X"}
        Path(self.tmp.name, "n.md").write_text("dado", encoding="utf-8")
        r1 = {"texto": "", "chamadas": [{"id": "1", "nome": "ler_arquivo", "args": {"caminho": str(Path(self.tmp.name, "n.md"))}}],
              "parada": "tool_calls"}
        a = agente.Agente(llm_fake, auto=True)
        a.historico.append({"role": "user", "content": "prev"})
        a.historico.append({"role": "assistant", "content": "ok prev"})
        chamadas = [r1, llm.ErroLLM("HTTP 429")]

        def fake_conv(*_args, **_kwargs):
            v = chamadas.pop(0)
            if isinstance(v, Exception):
                raise v
            return v

        with mock.patch.object(agente, "conversar", side_effect=fake_conv), mock.patch("sys.stdout"):
            with self.assertRaises(llm.ErroLLM):
                a.turno("novo pedido")
        a.desfazer_ultimo()
        self.assertEqual(len(a.historico), 2)
        self.assertEqual(a.historico[-1]["content"], "ok prev")

    def test_llm_retry_em_429(self):
        tentativas = {"n": 0}

        class HandlerRetry(BaseHTTPRequestHandler):
            def do_POST(self):
                _ = self.rfile.read(int(self.headers["Content-Length"]))
                tentativas["n"] += 1
                if tentativas["n"] == 1:
                    self.send_response(429)
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "rate limit"}}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": "recuperado"}}]}).encode())

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), HandlerRetry)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = {"provedor": "compativel", "tipo": "openai", "base": f"http://127.0.0.1:{srv.server_port}/v1",
                 "modelo": "m", "chave": "k", "env": None}
            with mock.patch("time.sleep"):
                res = llm.conversar(r, "s", [{"role": "user", "content": "oi"}], stream=False)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(tentativas["n"], 2)
        self.assertEqual(res["texto"], "recuperado")

    def test_llm_nao_retenta_apos_emitir_chunk_em_streaming(self):
        import socket as _socket

        class RespParcial:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def __iter__(self):
                yield b'data: {"choices": [{"delta": {"content": "parte1"}}]}\n'
                raise _socket.timeout("caiu no meio")

        pedacos = []
        r = {"provedor": "compativel", "tipo": "openai", "base": "https://x/v1",
             "modelo": "m", "chave": "k", "env": None}
        with mock.patch("urllib.request.urlopen", return_value=RespParcial()) as uo, mock.patch("time.sleep"):
            with self.assertRaisesRegex(llm.ErroLLM, "demorou"):
                llm.conversar(r, "s", [{"role": "user", "content": "oi"}], ao_pedaco=pedacos.append)
        self.assertEqual(uo.call_count, 1)
        self.assertEqual(pedacos, ["parte1"])

    def test_cmd_chat_envia_imagens_no_modo_direto(self):
        img = Path(self.tmp.name) / "ad.png"
        img.write_bytes(b"pngbytes")
        with mock.patch("sys.stdin") as stdin, mock.patch("gargula.agente.rodar_unico", return_value=0) as rodar_mock:
            stdin.isatty.return_value = True
            cli.main(["--yolo", "chat", "analisa", str(img)])
        self.assertTrue(rodar_mock.called)
        kwargs = rodar_mock.call_args.kwargs
        self.assertEqual(len(kwargs["imagens"]), 1)
        self.assertEqual(kwargs["imagens"][0]["nome"], "ad.png")

    def test_cmd_inicio_executa_sem_erro(self):
        with mock.patch("sys.stdin") as stdin, mock.patch("sys.stdout"):
            stdin.isatty.return_value = False
            self.assertEqual(cli.main(["inicio"]), 0)


if __name__ == "__main__":
    unittest.main()
