"""Ponto de entrada: `gargula`."""

from __future__ import annotations

import argparse
import json
import sys

from gargula import __version__, ads, config, prompts, ui, zap
from gargula.llm import ErroLLM, conversar


def _llm(args):
    return config.resolver_llm(args.provedor, args.modelo)


def _perguntar(args, modo: str, pedido: str) -> int:
    """Uma pergunta à LLM com saída em streaming (boa para pipe: `gargula copy ... > copy.md`)."""
    llm = _llm(args)
    conversar(llm, prompts.sistema(modo), [{"role": "user", "content": pedido}],
              ao_pedaco=lambda p: (sys.stdout.write(p), sys.stdout.flush()))
    print()
    return 0


def _campos(**kv) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in kv.items() if v)


# ---------- comandos ----------

def cmd_chat(args) -> int:
    texto = " ".join(args.texto).strip()
    if not sys.stdin.isatty():
        entrada = sys.stdin.read().strip()
        texto = f"{texto}\n\n{entrada}".strip() if entrada else texto
    if not texto:
        from gargula import repl
        return repl.rodar(args.provedor, args.modelo, args.modo)
    return _perguntar(args, args.modo, texto)


def cmd_copy(args) -> int:
    pedido = (f"Escreva {args.n} variações de copy para {args.canal}.\n"
              + _campos(produto=args.produto, publico=args.publico, preco=args.preco,
                        tom=args.tom, extra=args.extra))
    return _perguntar(args, "copy", pedido)


def cmd_oferta(args) -> int:
    pedido = "Monte a oferta completa.\n" + _campos(
        produto=args.produto, publico=args.publico, preco=args.preco, extra=args.extra)
    return _perguntar(args, "oferta", pedido)


def cmd_funil(args) -> int:
    pedido = "Desenhe o funil de vendas.\n" + _campos(
        produto=args.produto, canal=args.canal, ticket=args.ticket, extra=args.extra)
    return _perguntar(args, "funil", pedido)


def cmd_zap_msg(args) -> int:
    pedido = (f"Escreva {args.n} versões de mensagem de WhatsApp.\n"
              + _campos(objetivo=args.objetivo, contexto=args.contexto, tom=args.tom))
    return _perguntar(args, "zap", pedido)


def cmd_zap_enviar(args) -> int:
    numero = zap.normalizar_numero(args.para)
    texto = args.texto if args.texto != "-" else sys.stdin.read().strip()
    if not texto:
        raise zap.ErroZap("texto vazio")
    print(ui.pintar("Prévia do envio", ui.ROXO, negrito=True))
    print(f"  via:  {args.via}\n  para: {numero}\n  ---\n" + "\n".join("  " + l for l in texto.splitlines()))
    if args.via == "cloud":
        ui.aviso("Cloud API: texto livre só dentro da janela de 24 h após a última mensagem do cliente")
    if not args.enviar:
        ui.aviso("nada foi enviado. Repita com --enviar para enviar de verdade.")
        return 0
    if not args.sim:
        if not sys.stdin.isatty():
            raise zap.ErroZap("confirmação necessária: rode no terminal ou use --sim")
        if input(f"Enviar para {numero}? Digite 'sim': ").strip().lower() != "sim":
            ui.aviso("cancelado")
            return 1
    resp = zap.enviar(args.via, numero, texto)
    ui.ok("enviado")
    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    return 0


def _linhas_ads(args) -> list[dict]:
    brutas = ads.carregar_arquivo(args.arquivo) if args.arquivo else ads.buscar(
        args.conta, args.periodo, args.nivel)
    return [ads.resumir(l, args.nivel) for l in brutas]


def cmd_ads_insights(args) -> int:
    resumos = _linhas_ads(args)
    if args.json:
        print(json.dumps(resumos, ensure_ascii=False, indent=2))
    elif not resumos:
        ui.aviso("nenhuma métrica no período")
    else:
        print(ads.tabela(resumos))
    return 0


def cmd_ads_diagnostico(args) -> int:
    resumos = _linhas_ads(args)
    if not resumos:
        ui.aviso("nenhuma métrica no período")
        return 0
    print(ads.tabela(resumos) + "\n")
    pedido = ("Diagnostique estas campanhas do Meta Ads. Moeda: BRL. "
              + (f"Meta: {args.meta}. " if args.meta else "")
              + (f"Ticket médio: R$ {args.ticket}. " if args.ticket else "")
              + "\n\nMétricas (JSON):\n" + json.dumps(resumos, ensure_ascii=False))
    return _perguntar(args, "ads", pedido)


def cmd_provedores(args) -> int:
    atual = config.resolver_llm(args.provedor, args.modelo)["provedor"]
    for nome, p in config.PROVEDORES.items():
        llm = config.resolver_llm(nome, None)
        tem = "ok" if llm["chave"] else {"ollama": "não precisa", "compativel": "opcional"}.get(nome, "sem chave")
        marca = "●" if nome == atual else " "
        print(f"{marca} {nome:<11} {str(llm['modelo']):<26} chave: {tem:<11} {p['env'] or ''}")
    return 0


def cmd_config(args) -> int:
    if args.acao == "caminho":
        print(config.arquivo())
    elif args.acao == "mostrar":
        cfg = config.carregar()
        if not cfg:
            print(f"(vazio) {config.arquivo()}")
        for k, v in sorted(cfg.items()):
            print(f"{k} = {config.mascarar(v) if config.e_secreta(k) else v}")
    elif args.acao == "set":
        if not args.chave or args.valor is None:
            raise ValueError("uso: gargula config set <chave> <valor>")
        if args.chave == "provedor" and args.valor not in config.PROVEDORES:
            raise ValueError(f"provedores: {', '.join(config.PROVEDORES)}")
        config.definir(args.chave, args.valor)
        ui.ok(f"{args.chave} salvo" + (" (texto puro em " + str(config.arquivo()) + "; prefira variável de ambiente em máquina compartilhada)"
                                       if config.e_secreta(args.chave) else ""))
    elif args.acao == "unset":
        ui.ok("removido") if config.remover(args.chave or "") else ui.aviso("chave não existia")
    return 0


# ---------- parser ----------

def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gargula",
        description="Gárgula: copiloto de terminal para marketing digital, vendas online, WhatsApp e Meta Ads.",
        epilog="Sem subcomando abre o chat interativo. Ex.: gargula copy --produto 'placa NFC' --publico 'barbearias'",
    )
    p.add_argument("--version", action="version", version=f"gargula {__version__}")
    p.add_argument("-p", "--provedor", help=f"LLM: {', '.join(config.PROVEDORES)}")
    p.add_argument("-m", "--modelo", help="modelo do provedor (ex.: gpt-4o-mini)")
    sub = p.add_subparsers(dest="comando")

    c = sub.add_parser("chat", help="pergunta direta ou chat interativo (aceita texto por pipe)")
    c.add_argument("texto", nargs="*")
    c.add_argument("--modo", default="geral", choices=list(prompts.MODOS))
    c.set_defaults(func=cmd_chat)

    c = sub.add_parser("copy", help="gera variações de copy")
    c.add_argument("--produto", required=True)
    c.add_argument("--publico")
    c.add_argument("--preco")
    c.add_argument("--canal", default="anúncio no Meta Ads",
                   help="ex.: 'anúncio no Meta Ads', 'legenda de Instagram', 'WhatsApp', 'e-mail'")
    c.add_argument("--tom")
    c.add_argument("--n", type=int, default=3)
    c.add_argument("--extra", help="qualquer detalhe a mais")
    c.set_defaults(func=cmd_copy)

    c = sub.add_parser("oferta", help="estrutura uma oferta (promessa, bônus, escada de preço)")
    c.add_argument("--produto", required=True)
    c.add_argument("--publico")
    c.add_argument("--preco")
    c.add_argument("--extra")
    c.set_defaults(func=cmd_oferta)

    c = sub.add_parser("funil", help="desenha um funil de vendas com métricas por etapa")
    c.add_argument("--produto", required=True)
    c.add_argument("--canal", help="ex.: Instagram + WhatsApp")
    c.add_argument("--ticket")
    c.add_argument("--extra")
    c.set_defaults(func=cmd_funil)

    z = sub.add_parser("zap", help="WhatsApp: gerar mensagens e enviar 1 por vez").add_subparsers(dest="acao", required=True)
    c = z.add_parser("msg", help="gera mensagens/fluxos de WhatsApp com IA")
    c.add_argument("--objetivo", required=True, help="ex.: 'recuperar carrinho de quem pediu o Pix'")
    c.add_argument("--contexto")
    c.add_argument("--tom")
    c.add_argument("--n", type=int, default=3)
    c.set_defaults(func=cmd_zap_msg)
    c = z.add_parser("enviar", help="envia UMA mensagem (prévia por padrão)")
    c.add_argument("--para", required=True, help="um número com DDI, ex.: 5548999990000")
    c.add_argument("--texto", required=True, help="texto ou '-' para ler do stdin")
    c.add_argument("--via", default="evolution", choices=["evolution", "cloud"])
    c.add_argument("--enviar", action="store_true", help="envia de verdade (sem isso é só prévia)")
    c.add_argument("--sim", action="store_true", help="pula a confirmação interativa")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_zap_enviar)

    a = sub.add_parser("ads", help="Meta Ads: métricas e diagnóstico (só leitura)").add_subparsers(dest="acao", required=True)
    for nome, fn, ajuda in (("insights", cmd_ads_insights, "tabela de métricas"),
                            ("diagnostico", cmd_ads_diagnostico, "escalar/manter/ajustar/cortar com IA")):
        c = a.add_parser(nome, help=ajuda)
        c.add_argument("--conta", help="act_123... (ou meta.conta)")
        c.add_argument("--periodo", default="last_7d", choices=ads.PERIODOS)
        c.add_argument("--nivel", default="campaign", choices=["campaign", "adset", "ad"])
        c.add_argument("--arquivo", help="usar métricas de um .json/.csv em vez da API")
        c.add_argument("--json", action="store_true") if nome == "insights" else None
        if nome == "diagnostico":
            c.add_argument("--meta", help="ex.: 'CPA até R$ 30' ou 'ROAS 3'")
            c.add_argument("--ticket", help="ticket médio em R$")
        c.set_defaults(func=fn)

    c = sub.add_parser("provedores", help="lista as LLMs suportadas e se a chave está configurada")
    c.set_defaults(func=cmd_provedores)

    c = sub.add_parser("config", help="configuração em ~/.gargula/config.json")
    c.add_argument("acao", choices=["mostrar", "set", "unset", "caminho"])
    c.add_argument("chave", nargs="?")
    c.add_argument("valor", nargs="?")
    c.set_defaults(func=cmd_config)
    return p


def main(argv=None) -> int:
    ui.preparar_terminal()
    config.carregar_envs()
    args = montar_parser().parse_args(argv)
    try:
        if not getattr(args, "func", None):
            from gargula import repl
            return repl.rodar(args.provedor, args.modelo)
        return args.func(args)
    except (ErroLLM, zap.ErroZap, ads.ErroAds, ValueError, FileNotFoundError) as e:
        ui.erro(str(e))
        return 1
    except KeyboardInterrupt:
        print()
        return 130
