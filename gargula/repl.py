"""Chat interativo no terminal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from gargula import __version__, config, contexto, prompts, ui
from gargula.agente import Agente
from gargula.imagens import extrair_imagens
from gargula.llm import ErroLLM

AJUDA = """Comandos:
  /modo <geral|copy|oferta|zap|ads|funil>   muda a especialidade
  /provedor <nome>                          troca a LLM (drael, anthropic, openai, gemini, groq, ...)
  /modelo <nome>                            troca o modelo
  /yolo                                     liga/desliga modo YOLO (aprovação automática)
  /auto                                     sinônimo de /yolo
  /contexto                                 mostra os arquivos de instrução carregados (GARGULA.md, AGENTS.md...)
  /limpar                                   apaga o histórico da conversa
  /salvar [arquivo.md]                      salva a conversa em Markdown
  /resume                                   salva sessão para retomar depois (ou carrega a última)
  /sair                                     encerra (ou Ctrl+D)
Termine a linha com \\ para continuar escrevendo na linha de baixo. Ctrl+C interrompe a resposta."""


def _ler_entrada(prompt: str) -> str:
    linhas = []
    while True:
        linha = input(prompt if not linhas else "  ")
        if linha.endswith("\\"):
            linhas.append(linha[:-1])
            continue
        linhas.append(linha)
        return "\n".join(linhas)


def salvar_conversa(historico: list[dict], destino: str | None) -> Path:
    p = Path(destino or f"gargula-{datetime.now():%Y%m%d-%H%M}.md")
    partes = ["# Conversa com o Gárgula\n"]
    for m in historico:
        role = m.get("role")
        if role == "user":
            texto = m.get("content", "")
            imgs = m.get("imagens") or []
            if imgs:
                nomes = ", ".join(x.get("nome", "imagem") for x in imgs)
                texto = f"{texto}\n\n_(imagens anexadas: {nomes})_".strip()
            partes.append(f"## Você\n\n{texto}\n")
        elif role == "assistant":
            texto = (m.get("content") or "").strip()
            chamadas = m.get("chamadas") or []
            if chamadas:
                nomes_tools = ", ".join(c.get("nome", "?") for c in chamadas)
                bloco_tools = f"_Ferramentas usadas: {nomes_tools}_"
                texto = f"{texto}\n\n{bloco_tools}".strip()
            if texto:
                partes.append(f"## Gárgula\n\n{texto}\n")
        elif role == "ferramenta":
            linhas = []
            for r in m.get("resultados") or []:
                status = "erro" if r.get("erro") else "ok"
                previa = (r.get("conteudo") or "").strip().splitlines()
                resumo = previa[0][:120] if previa else "(vazio)"
                linhas.append(f"- `{r.get('nome', '?')}` ({status}): {resumo}")
            if linhas:
                partes.append("### Retorno das ferramentas\n\n" + "\n".join(linhas) + "\n")
    p.write_text("\n".join(partes), encoding="utf-8")
    return p


def _pasta_sessoes() -> Path:
    return config.pasta() / "sessoes"


def _serializar_msg(m: dict) -> dict:
    """Versão serializável de uma mensagem do histórico (remove base64 pesado)."""
    s: dict = {"role": m.get("role", ""), "content": m.get("content", "")}
    if m.get("chamadas"):
        s["chamadas"] = [{"id": c.get("id"), "nome": c.get("nome"), "args": c.get("args")}
                         for c in m["chamadas"]]
    if m.get("resultados"):
        s["resultados"] = [{"id": r.get("id"), "nome": r.get("nome"),
                            "conteudo": r.get("conteudo", "")[:2000], "erro": r.get("erro", False)}
                           for r in m["resultados"]]
    # imagens: só guarda nome, não base64
    if m.get("imagens"):
        s["imagens_ref"] = [i.get("nome", "?") for i in m["imagens"]]
    return s


def salvar_sessao(historico: list[dict], modo: str, destino: str | None = None) -> Path:
    """Salva sessão em JSON para /resume posterior."""
    pasta = _pasta_sessoes()
    pasta.mkdir(parents=True, exist_ok=True)
    if destino:
        p = Path(destino)
    else:
        p = pasta / f"sessao-{datetime.now():%Y%m%d-%H%M}.json"
    dados = {
        "versao": 1,
        "modo": modo,
        "data": datetime.now().isoformat(),
        "historico": [_serializar_msg(m) for m in historico],
    }
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    # symlink/cópia para 'ultima.json' para fácil retomada
    ultima = pasta / "ultima.json"
    try:
        if ultima.exists():
            ultima.unlink()
        ultima.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return p


def carregar_sessao(origem: str | None = None) -> tuple[list[dict], str] | None:
    """Carrega sessão salva. Retorna (historico, modo) ou None."""
    if origem:
        p = Path(origem)
    else:
        p = _pasta_sessoes() / "ultima.json"
    if not p.is_file():
        return None
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
        return dados.get("historico", []), dados.get("modo", "geral")
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def rodar(provedor: str | None, modelo: str | None, modo: str = "geral", auto: bool = False) -> int:
    try:
        llm = config.resolver_llm(provedor, modelo)
    except ValueError as e:
        ui.erro(str(e))
        return 2
    ui.exibir_banner_inicial(__version__, llm["provedor"], llm["modelo"] or "?", modo, auto=auto)
    if not llm.get("chave") and llm["provedor"] not in ("ollama", "compativel"):
        if llm["provedor"] == "drael":
            ui.aviso("sem chave para drael: rode `drael login`, defina DRAEL_KEY (ou DRAEL_API_KEY) "
                     "ou rode `gargula config set chave.drael <chave>`")
        else:
            ui.aviso(f"sem chave para {llm['provedor']}: defina {llm['env']} "
                     f"ou rode `gargula config set chave.{llm['provedor']} <chave>`")
    agente = Agente(llm, modo, auto)
    historico = agente.historico
    fixos = contexto.arquivos_fixos()
    if fixos:
        print(ui.pintar("  contexto: " + ", ".join(p.name for p in fixos), ui.CINZA))
    if auto:
        ui.ok("modo YOLO ativado: escrita e comandos liberados (WhatsApp sempre pergunta)")
    cor = ui.usa_cor()
    seta = ui.pintar("❯ ", ui.ROXO, negrito=True, cor=cor)

    while True:
        print()
        try:
            texto = _ler_entrada(seta).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            if historico:
                salvar_sessao(historico, agente.modo)
                ui.ok("sessão salva automaticamente (/resume para retomar)")
            return 0
        if not texto:
            continue
        if texto.startswith("/"):
            cmd, _, arg = texto[1:].partition(" ")
            arg = arg.strip()
            if cmd in ("sair", "exit", "quit"):
                if historico:
                    salvar_sessao(historico, agente.modo)
                    ui.ok("sessão salva (/resume para retomar)")
                return 0
            if cmd in ("ajuda", "help", "?"):
                print(AJUDA)
            elif cmd == "limpar":
                historico.clear()
                ui.ok("histórico apagado")
            elif cmd == "modo":
                if arg in prompts.MODOS:
                    modo = agente.modo = arg
                    ui.ok(f"modo: {modo}")
                else:
                    ui.erro(f"modos: {', '.join(prompts.MODOS)}")
            elif cmd == "provedor":
                try:
                    llm = agente.llm = config.resolver_llm(arg, None)
                    ui.ok(f"provedor: {llm['provedor']} · modelo: {llm['modelo']}")
                except ValueError as e:
                    ui.erro(str(e))
            elif cmd == "modelo":
                if arg:
                    llm["modelo"] = arg
                    ui.ok(f"modelo: {arg}")
                else:
                    print(llm["modelo"])
            elif cmd in ("auto", "yolo"):
                agente.auto = not agente.auto
                ui.ok("modo YOLO ativado (escrita e comandos liberados)" if agente.auto else "modo seguro ativado: pede permissão")
            elif cmd == "contexto":
                for p in contexto.arquivos_fixos() or []:
                    print(f"  {p}")
                print(f"  pasta base: {contexto.pasta_base() or '(não configurada)'}")
            elif cmd == "salvar":
                if not historico:
                    ui.aviso("nada para salvar ainda")
                else:
                    ui.ok(f"salvo em {salvar_conversa(historico, arg or None)}")
            elif cmd == "resume":
                if arg == "carregar" or (not arg and not historico):
                    # /resume sem arg e sem histórico = carregar última
                    sessao = carregar_sessao(arg if arg and arg != "carregar" else None)
                    if sessao:
                        hist_carregado, modo_carregado = sessao
                        historico.clear()
                        historico.extend(hist_carregado)
                        agente.modo = modo_carregado
                        ui.ok(f"sessão carregada ({len(historico)} mensagens, modo: {modo_carregado})")
                    else:
                        ui.aviso("nenhuma sessão salva encontrada")
                else:
                    # /resume = salvar sessão atual
                    if not historico:
                        ui.aviso("nada para salvar ainda")
                    else:
                        p = salvar_sessao(historico, agente.modo, arg or None)
                        ui.ok(f"sessão salva em {p}")
            else:
                ui.erro("comando desconhecido; digite /ajuda")
            continue

        print()
        try:
            avisos_img: list[str] = []
            texto_limpo, imgs = extrair_imagens(texto, avisos=avisos_img)
            for av in avisos_img:
                ui.aviso(av)
            if imgs:
                nomes = ", ".join(f"{i['nome']} ({i['kb']} KB)" for i in imgs)
                ui.ok(f"{len(imgs)} imagem(ns): {nomes}")
            agente.turno(texto_limpo, imagens=imgs if imgs else None)
        except KeyboardInterrupt:
            print()
            ui.aviso("interrompido")
            agente.desfazer_ultimo()
        except ErroLLM as e:
            ui.erro(str(e))
            agente.desfazer_ultimo()
