import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from gargula import ads, cli, config, llm, ui, zap


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
        self.assertEqual(c["system"], "sis")

    def test_openai_coloca_sistema_primeiro(self):
        url, h, c = llm.montar_requisicao("openai", "https://o/v1", "k", "m", "sis", self.MSGS)
        self.assertEqual(url, "https://o/v1/chat/completions")
        self.assertEqual(h["Authorization"], "Bearer k")
        self.assertEqual(c["messages"][0], {"role": "system", "content": "sis"})
        self.assertEqual(c["max_tokens"], llm.MAX_TOKENS)  # evita o 402 do OpenRouter

    def test_gemini_troca_assistant_por_model(self):
        url, h, c = llm.montar_requisicao("gemini", "https://g/v1beta", "k", "gm", "sis", self.MSGS)
        self.assertTrue(url.endswith("/models/gm:streamGenerateContent?alt=sse"))
        self.assertEqual([x["role"] for x in c["contents"]], ["user", "model"])

    def test_eventos(self):
        self.assertEqual(llm.texto_do_evento("anthropic", {"type": "content_block_delta",
                         "delta": {"type": "text_delta", "text": "a"}}), "a")
        self.assertEqual(llm.texto_do_evento("openai", {"choices": [{"delta": {"content": "b"}}]}), "b")
        self.assertEqual(llm.texto_do_evento("gemini", {"candidates": [{"content": {"parts": [{"text": "c"}]}}]}), "c")

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
            texto = llm.conversar(r, "sis", [{"role": "user", "content": "oi"}], ao_pedaco=pedacos.append)
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


if __name__ == "__main__":
    unittest.main()
