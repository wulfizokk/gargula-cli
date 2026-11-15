"""Ponto de entrada: `gargula`."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gargula import __version__, ads, config, prompts, ui, zap
from gargula.llm import ErroLLM, responder


def _llm(args):
    return config.resolver_llm(args.provedor, args.modelo)


def _perguntar(args, modo: str, pedido: str) -> int:
    """Uma pergunta à LLM com saída em streaming (boa para pipe: `gargula copy ... > copy.md`)."""
    llm = _llm(args)
    responder(llm, prompts.sistema(modo), [{"role": "user", "content": pedido}],
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
        return repl.rodar(args.provedor, args.modelo, args.modo, args.auto)
    from gargula import agente
    return agente.rodar_unico(_llm(args), texto, args.modo, args.auto)


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


def cmd_zap_objetar(args) -> int:
    objecao = args.objecao
    if not objecao and not sys.stdin.isatty():
        objecao = sys.stdin.read().strip()
    if not objecao:
        raise ValueError("informe a objeção do cliente (ex.: gargula zap objetar 'achei caro')")
    pedido = ("Quebre esta objeção de venda no WhatsApp apresentando 3 abordagens táticas:\n"
              f"Objeção do cliente: \"{objecao}\"\n"
              + _campos(contexto=args.contexto, produto=args.produto, preco=args.preco))
    return _perguntar(args, "objetar", pedido)


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


def cmd_ads_reconciliar(args) -> int:
    from gargula import checkout
    resumos = _linhas_ads(args)
    if not resumos:
        ui.aviso("nenhuma métrica de anúncio encontrada")
        return 1
    vendas = checkout.carregar_vendas(args.checkout)
    if not vendas:
        ui.aviso("nenhuma venda encontrada no arquivo de checkout")
        return 1
    resultado = checkout.reconciliar(resumos, vendas)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(checkout.formatar_tabela(resultado))
    return 0


def cmd_cro(args) -> int:
    from gargula import cro
    entrada = sys.stdin.read().strip() if not sys.stdin.isatty() else None
    texto = cro.extrair_conteudo(args.url, args.arquivo, entrada or (" ".join(args.texto) if args.texto else None))
    llm = _llm(args)
    cro.auditar(llm, texto)
    print()
    return 0


def cmd_criativos_ganchos(args) -> int:
    from gargula import criativos
    criativos.gerar_ganchos(_llm(args), args.produto, args.publico, args.extra)
    print()
    return 0


def cmd_criativos_roteiro(args) -> int:
    from gargula import criativos
    criativos.gerar_roteiro(_llm(args), args.produto, args.publico, args.formato, args.extra)
    print()
    return 0


def cmd_criativos_pacote(args) -> int:
    from gargula import criativos
    criativos.gerar_pacote(_llm(args), args.produto, args.publico, args.preco, args.extra)
    print()
    return 0


def cmd_dna(args) -> int:
    from gargula import dna
    if args.acao == "inicializar":
        dna.inicializar_templates()
        ui.ok(f"templates criados em {dna.pasta_dna()}")
    elif args.acao == "pasta":
        print(dna.pasta_dna())
    elif args.acao == "mostrar":
        if getattr(args, "categoria", None):
            print(dna.obter(args.categoria))
        else:
            for cat, txt in dna.listar().items():
                print(ui.pintar(f"=== {cat.upper()} ===", ui.ROXO, negrito=True))
                print(txt or "(vazio)")
                print()
    elif args.acao == "set":
        if not args.categoria or args.valor is None:
            raise ValueError("uso: gargula dna set <avatar|oferta|marca|anti_slop> <texto_ou_arquivo>")
        val = args.valor
        p = Path(val)
        if p.is_file():
            val = p.read_text(encoding="utf-8-sig")
        dna.salvar(args.categoria, val)
        ui.ok(f"DNA {args.categoria} atualizado em {dna.arquivo(args.categoria)}")
    elif args.acao == "reset":
        if not sys.stdin.isatty() or input("Tem certeza que deseja resetar os arquivos de DNA? Digite 'sim': ").strip().lower() == "sim":
            for cat in dna.CATEGORIAS:
                f = dna.arquivo(cat)
                if f.is_file():
                    f.unlink()
            ui.ok("DNA resetado")
        else:
            ui.aviso("cancelado")
    return 0


def cmd_crm(args) -> int:
    from gargula import crm
    if args.acao == "status":
        print(crm.formatar_status())
    elif args.acao == "catalogo":
        print(crm.formatar_tabela_catalogo())
    elif args.acao == "config":
        if getattr(args, "chave", None) and getattr(args, "valor", None):
            config.definir(f"crm.{args.chave}", args.valor)
            ui.ok(f"crm.{args.chave} salvo")
        else:
            print(f"crm.url   = {crm.url_crm()}")
            print(f"crm.pasta = {crm.pasta_crm() or '(não configurada)'}")
    return 0


def cmd_inicio(args) -> int:
    from gargula import dna
    print(ui.banner(__version__, "gargula", "", "geral", cor=ui.usa_cor()))
    print(ui.pintar("\nBem-vindo ao Assistente do Gárgula CLI!", ui.ROXO, negrito=True))
    print("Vamos conferir seus provedores de IA e seu ecossistema de vendas.\n")

    print(ui.pintar("1. Status das LLMs:", ui.AMARELO, negrito=True))
    cmd_provedores(args)
    print()

    if sys.stdin.isatty():
        prov_atual = config.obter("provedor", "anthropic")
        prov = input(f"Provedor padrão atual é '{prov_atual}'. Deseja trocar? (Enter para manter ou digite o nome): ").strip().lower()
        if prov and prov in config.PROVEDORES:
            config.definir("provedor", prov)
            ui.ok(f"provedor padrão alterado para: {prov}")

        print()
        print(ui.pintar("2. Base de Conhecimento / Vault do Obsidian:", ui.AMARELO, negrito=True))
        base_atual = config.obter("pasta_base", "")
        nova_base = input(f"Caminho da sua pasta de notas/vault [{base_atual or 'nenhuma'}]: ").strip()
        if nova_base:
            p = Path(os.path.expanduser(nova_base))
            if p.is_dir():
                config.definir("pasta_base", str(p.resolve()))
                ui.ok(f"pasta base salva: {p.resolve()}")
            else:
                config.definir("pasta_base", nova_base)
                ui.aviso(f"pasta salva: {nova_base}")

        print()
        print(ui.pintar("3. Brand & Offer DNA (Filtro Anti-Slop):", ui.AMARELO, negrito=True))
        dna.inicializar_templates()
        ui.ok(f"templates de identidade prontos em {dna.pasta_dna()}")

    print()
    ui.ok("Tudo pronto! Comandos revolucionários para você testar:")
    print("  • gargula copy --produto 'Seu Produto' --publico 'Seu Nicho'")
    print("  • gargula cro --url 'https://seusite.com' (ou passe --arquivo)")
    print("  • gargula criativos ganchos --produto 'Seu Produto'")
    print("  • gargula zap objetar 'achei caro, vou ver com meu sócio'")
    print("  • gargula ads reconciliar --ads metricas.csv --checkout kiwify.csv")
    print("  • gargula dna mostrar")
    print("  • gargula (abre o chat interativo com o agente autônomo)\n")
    return 0


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
        description="Gárgula: agente de terminal para marketing digital, vendas online, WhatsApp e Meta Ads.",
        epilog="Sem subcomando abre o chat interativo. Ex.: gargula copy --produto 'placa NFC' --publico 'barbearias'",
    )
    p.add_argument("--version", action="version", version=f"gargula {__version__}")
    p.add_argument("-p", "--provedor", help=f"LLM: {', '.join(config.PROVEDORES)}")
    p.add_argument("-m", "--modelo", help="modelo do provedor (ex.: gpt-4o-mini)")
    p.add_argument("-y", "--auto", action="store_true",
                   help="aprova escrita de arquivos e comandos sem perguntar (WhatsApp sempre pergunta)")
    sub = p.add_subparsers(dest="comando")

    c = sub.add_parser("chat", help="tarefa para o agente ou chat interativo (aceita texto por pipe)")
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

    # WhatsApp
    z = sub.add_parser("zap", help="WhatsApp: gerar mensagens, enviar e quebrar objeções").add_subparsers(dest="acao", required=True)
    c = z.add_parser("msg", help="gera mensagens/fluxos de WhatsApp com IA")
    c.add_argument("--objetivo", required=True, help="ex.: 'recuperar carrinho de quem pediu o Pix'")
    c.add_argument("--contexto")
    c.add_argument("--tom")
    c.add_argument("--n", type=int, default=3)
    c.set_defaults(func=cmd_zap_msg)

    c = z.add_parser("objetar", help="gera 3 abordagens cirúrgicas para quebrar objeções no 1 a 1")
    c.add_argument("objecao", nargs="?", help="a frase ou objeção do cliente (ex.: 'achei caro')")
    c.add_argument("--contexto", help="histórico ou perfil do cliente")
    c.add_argument("--produto", help="produto ofertado")
    c.add_argument("--preco", help="preço e condições")
    c.set_defaults(func=cmd_zap_objetar)

    c = z.add_parser("enviar", help="envia UMA mensagem (prévia por padrão)")
    c.add_argument("--para", required=True, help="um número com DDI, ex.: 5548999990000")
    c.add_argument("--texto", required=True, help="texto ou '-' para ler do stdin")
    c.add_argument("--via", default="evolution", choices=["evolution", "cloud"])
    c.add_argument("--enviar", action="store_true", help="envia de verdade (sem isso é só prévia)")
    c.add_argument("--sim", action="store_true", help="pula a confirmação interativa")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_zap_enviar)

    # Meta Ads
    a = sub.add_parser("ads", help="Meta Ads: métricas, diagnóstico e reconciliação").add_subparsers(dest="acao", required=True)
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

    c = a.add_parser("reconciliar", help="cruza gasto de ads com vendas reais de checkout para achar o ROAS Real")
    c.add_argument("--checkout", required=True, help="arquivo CSV do checkout (Kiwify, Hotmart, Eduzz, etc.)")
    c.add_argument("--arquivo", help="arquivo CSV/JSON com métricas do Meta Ads (ou busca via API se omitido)")
    c.add_argument("--conta", help="act_123... (ou meta.conta)")
    c.add_argument("--periodo", default="last_7d", choices=ads.PERIODOS)
    c.add_argument("--nivel", default="campaign", choices=["campaign", "adset", "ad"])
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_ads_reconciliar)

    # CRO & War Room
    c = sub.add_parser("cro", help="War Room: stress-test de CRO de página de vendas / oferta")
    c.add_argument("texto", nargs="*", help="texto ou conteúdo da oferta")
    c.add_argument("--url", help="URL da página de vendas")
    c.add_argument("--arquivo", help="arquivo local com HTML ou Markdown da página")
    c.set_defaults(func=cmd_cro)

    # Fábrica de Criativos
    cr = sub.add_parser("criativos", help="Fábrica de Criativos: ganchos virais, roteiros e pacotes para anúncios").add_subparsers(dest="acao", required=True)
    c = cr.add_parser("ganchos", help="gera 10 ganchos de 3s divididos em 5 arquétipos")
    c.add_argument("--produto", required=True)
    c.add_argument("--publico")
    c.add_argument("--extra")
    c.set_defaults(func=cmd_criativos_ganchos)

    c = cr.add_parser("roteiro", help="gera roteiro completo de anúncio em vídeo com indicações de cena e B-Roll")
    c.add_argument("--produto", required=True)
    c.add_argument("--publico")
    c.add_argument("--formato", default="reels", help="reels, tiktok, shorts ou vsl")
    c.add_argument("--extra")
    c.set_defaults(func=cmd_criativos_roteiro)

    c = cr.add_parser("pacote", help="gera pacote pronto para subir no Meta Ads (3 copys, 5 títulos, descrições e UTMs)")
    c.add_argument("--produto", required=True)
    c.add_argument("--publico")
    c.add_argument("--preco")
    c.add_argument("--extra")
    c.set_defaults(func=cmd_criativos_pacote)

    # Brand & Offer DNA
    d = sub.add_parser("dna", help="Brand & Offer DNA: gerencia a identidade da marca, oferta e filtro anti-slop").add_subparsers(dest="acao", required=True)
    c = d.add_parser("mostrar", help="exibe os dados atuais de DNA")
    c.add_argument("categoria", nargs="?", choices=["avatar", "oferta", "marca", "anti_slop"])
    c.set_defaults(func=cmd_dna)

    c = d.add_parser("set", help="define ou atualiza um arquivo de DNA")
    c.add_argument("categoria", choices=["avatar", "oferta", "marca", "anti_slop"])
    c.add_argument("valor", help="texto ou caminho de arquivo")
    c.set_defaults(func=cmd_dna)

    c = d.add_parser("pasta", help="mostra o caminho da pasta de DNA")
    c.set_defaults(func=cmd_dna)

    c = d.add_parser("inicializar", help="cria os templates padrão de DNA em ~/.gargula/dna")
    c.set_defaults(func=cmd_dna)

    c = d.add_parser("reset", help="remove os arquivos de DNA")
    c.set_defaults(func=cmd_dna)

    # CRM Proprietário
    crm_p = sub.add_parser("crm", help="Gárgula CRM: integração com a central de atendimento e vendas").add_subparsers(dest="acao", required=True)
    c = crm_p.add_parser("status", help="mostra status do CRM, módulos ativos e travas do agente")
    c.set_defaults(func=cmd_crm)

    c = crm_p.add_parser("catalogo", help="exibe a tabela oficial de kits e preços cadastrados no CRM")
    c.set_defaults(func=cmd_crm)

    c = crm_p.add_parser("config", help="configura ou exibe url e pasta do CRM")
    c.add_argument("chave", nargs="?", choices=["url", "pasta", "token"])
    c.add_argument("valor", nargs="?")
    c.set_defaults(func=cmd_crm)

    # Início Rápido / Wizard
    for nome in ("inicio", "wizard"):
        c = sub.add_parser(nome, help="assistente interativo de configuração inicial no terminal")
        c.set_defaults(func=cmd_inicio)

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
            return repl.rodar(args.provedor, args.modelo, "geral", args.auto)
        return args.func(args)
    except (ErroLLM, zap.ErroZap, ads.ErroAds, ValueError, FileNotFoundError) as e:
        ui.erro(str(e))
        return 1
    except KeyboardInterrupt:
        print()
        return 130
