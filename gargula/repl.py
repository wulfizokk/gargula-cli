"""Chat interativo no terminal."""

from __future__ import annotations

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
            return 0
        if not texto:
            continue
        if texto.startswith("/"):
            cmd, _, arg = texto[1:].partition(" ")
            arg = arg.strip()
            if cmd in ("sair", "exit", "quit"):
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
