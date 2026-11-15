"""Chat interativo no terminal."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from gargula import __version__, config, prompts, ui
from gargula.llm import ErroLLM, conversar

AJUDA = """Comandos:
  /modo <geral|copy|oferta|zap|ads|funil>   muda a especialidade
  /provedor <nome>                          troca a LLM (anthropic, openai, gemini, groq, ...)
  /modelo <nome>                            troca o modelo
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
        quem = "Você" if m["role"] == "user" else "Gárgula"
        partes.append(f"## {quem}\n\n{m['content']}\n")
    p.write_text("\n".join(partes), encoding="utf-8")
    return p


def rodar(provedor: str | None, modelo: str | None, modo: str = "geral") -> int:
    try:
        llm = config.resolver_llm(provedor, modelo)
    except ValueError as e:
        ui.erro(str(e))
        return 2
    print(ui.banner(__version__, llm["provedor"], llm["modelo"] or "?", modo))
    if not llm.get("chave") and llm["provedor"] not in ("ollama", "compativel"):
        ui.aviso(f"sem chave para {llm['provedor']}: defina {llm['env']} "
                 f"ou rode `gargula config set chave.{llm['provedor']} <chave>`")
    historico: list[dict] = []
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
                    modo = arg
                    ui.ok(f"modo: {modo}")
                else:
                    ui.erro(f"modos: {', '.join(prompts.MODOS)}")
            elif cmd == "provedor":
                try:
                    llm = config.resolver_llm(arg, None)
                    ui.ok(f"provedor: {llm['provedor']} · modelo: {llm['modelo']}")
                except ValueError as e:
                    ui.erro(str(e))
            elif cmd == "modelo":
                if arg:
                    llm["modelo"] = arg
                    ui.ok(f"modelo: {arg}")
                else:
                    print(llm["modelo"])
            elif cmd == "salvar":
                if not historico:
                    ui.aviso("nada para salvar ainda")
                else:
                    ui.ok(f"salvo em {salvar_conversa(historico, arg or None)}")
            else:
                ui.erro("comando desconhecido; digite /ajuda")
            continue

        historico.append({"role": "user", "content": texto})
        print()
        try:
            resposta = conversar(llm, prompts.sistema(modo), historico,
                                 ao_pedaco=lambda p: (sys.stdout.write(p), sys.stdout.flush()))
            print()
            historico.append({"role": "assistant", "content": resposta})
        except KeyboardInterrupt:
            print()
            ui.aviso("resposta interrompida")
            historico.pop()
        except ErroLLM as e:
            ui.erro(str(e))
            historico.pop()
