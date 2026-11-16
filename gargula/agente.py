"""Ciclo do agente: a LLM pensa, chama ferramentas, recebe o resultado e continua até terminar."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime

from gargula import contexto, ferramentas, prompts, ui
from gargula.llm import ErroLLM, conversar

MAX_PASSOS = 40


class Agente:
    def __init__(self, llm: dict, modo: str = "geral", auto: bool = False, com_ferramentas: bool = True):
        self.llm = llm
        self.modo = modo
        self.auto = auto
        self.com_ferramentas = com_ferramentas
        self.historico: list[dict] = []
        self.liberadas: set[str] = set()   # ferramentas liberadas "para a sessão"
        self.cor = ui.usa_cor()

    # ---------- prompt ----------
    def sistema(self) -> str:
        base = contexto.pasta_base()
        partes = [prompts.sistema(self.modo)]
        if self.com_ferramentas:
            partes.append(prompts.AGENTE.format(
                cwd=os.getcwd(), so=f"{platform.system()} {platform.release()}",
                shell="PowerShell" if os.name == "nt" else "bash",
                data=datetime.now().strftime("%d/%m/%Y %H:%M"),
                base=str(base) if base else "(não configurada)"))
        partes.append(contexto.texto_fixo())
        return "\n".join(p for p in partes if p)

    # ---------- permissão ----------
    def permitido(self, nome: str, args: dict) -> tuple[bool, str]:
        cat = ferramentas.POR_NOME.get(nome, {}).get("categoria", "escrita")
        if cat == "leitura":
            return True, ""
        fora = False
        if nome in ("escrever_arquivo", "editar_arquivo"):
            try:
                fora = not ferramentas.dentro_da_area(ferramentas.caminho(args.get("caminho", "")))
            except ferramentas.ErroFerramenta as e:
                return False, str(e)
        if cat == "escrita" and not fora and (self.auto or nome in self.liberadas):
            return True, ""
        if not sys.stdin.isatty():
            return False, "sem permissão: rode no terminal interativo ou use --auto"
        detalhe = ""
        if nome == "executar":
            detalhe = args.get("comando", "")
        elif nome == "whatsapp_enviar":
            detalhe = f"para {args.get('para')}:\n{args.get('texto', '')}"
        elif nome == "editar_arquivo":
            detalhe = f"{args.get('caminho')}\n- {args.get('antigo', '')[:400]}\n+ {args.get('novo', '')[:400]}"
        elif nome == "escrever_arquivo":
            detalhe = f"{args.get('caminho')} ({len(str(args.get('conteudo', '')).splitlines())} linhas)"
        if fora:
            detalhe += "\n(fora da pasta atual e da pasta base)"
        print(ui.pintar("  ┌ permissão: ", ui.LILAS, negrito=True, cor=self.cor) + nome)
        for l in detalhe.splitlines()[:30]:
            print(ui.pintar("  │ ", ui.ROXO, cor=self.cor) + l)
        opcoes = "[s]im / [n]ão" + (" / [t]odas desta sessão" if cat == "escrita" and not fora else "")
        try:
            r = input(ui.pintar(f"  └ permitir? {opcoes}: ", ui.LILAS, cor=self.cor)).strip().lower()
        except EOFError:
            r = "n"
        if r in ("t", "todas", "todos") and cat == "escrita" and not fora:
            self.liberadas.add(nome)
            return True, ""
        if r in ("s", "sim", "y", "yes"):
            return True, ""
        motivo = input(ui.pintar("  └ quer dizer o que fazer em vez disso? (enter pula): ", ui.CINZA, cor=self.cor)).strip() \
            if sys.stdin.isatty() else ""
        return False, "o usuário NEGOU esta ação." + (f" Instrução dele: {motivo}" if motivo else
                                                      " Pergunte como prefere seguir.")

    # ---------- turno ----------
    def turno(self, texto: str, imagens: list[dict] | None = None) -> str:
        msg_user: dict = {"role": "user", "content": texto}
        if imagens:
            msg_user["imagens"] = imagens
        self.historico.append(msg_user)
        defs = ferramentas.definicoes_api() if self.com_ferramentas else None
        final = ""
        for _ in range(MAX_PASSOS):
            with ui.pensando(cor=self.cor):
                r = conversar(self.llm, self.sistema(), self.historico, defs)
            self.historico.append({"role": "assistant", "content": r["texto"],
                                   "chamadas": r["chamadas"], "bruto": r.get("bruto")})
            if r["texto"].strip():
                ui.resposta(r["texto"], cor=self.cor)
                final = r["texto"]
            if not r["chamadas"]:
                if r.get("parada") in ("max_tokens", "length", "MAX_TOKENS"):
                    ui.aviso("a resposta bateu no limite de tokens (gargula config set max_tokens 8192)")
                return final
            resultados = []
            try:
                for c in r["chamadas"]:
                    print(ui.pintar("  ⏺ ", ui.ROXO, negrito=True, cor=self.cor)
                          + ui.pintar(ferramentas.resumo_chamada(c["nome"], c["args"]), ui.LILAS, cor=self.cor))
                    ok, motivo = self.permitido(c["nome"], c["args"])
                    if ok:
                        conteudo, erro = ferramentas.rodar(c["nome"], c["args"])
                    else:
                        conteudo, erro = motivo, True
                    primeira = (conteudo.strip().splitlines() or [""])[0][:110]
                    n = len(conteudo.splitlines())
                    marca = ui.pintar("    ⎿ ", ui.CINZA, cor=self.cor)
                    print(marca + ui.pintar(("✖ " if erro else "") + primeira + (f"  (+{n - 1} linhas)" if n > 1 else ""),
                                            (248, 113, 113) if erro else ui.CINZA, cor=self.cor))
                    resultados.append({"id": c["id"], "nome": c["nome"], "conteudo": conteudo or "(vazio)", "erro": erro})
            except KeyboardInterrupt:
                feitos = {x["id"] for x in resultados}
                resultados += [{"id": c["id"], "nome": c["nome"], "conteudo": "interrompido pelo usuário", "erro": True}
                               for c in r["chamadas"] if c["id"] not in feitos]
                self.historico.append({"role": "ferramenta", "resultados": resultados})
                raise
            self.historico.append({"role": "ferramenta", "resultados": resultados})
        ui.aviso(f"parei depois de {MAX_PASSOS} passos; diga 'continue' para seguir")
        return final

    def desfazer_ultimo(self) -> None:
        """Após erro na primeira chamada, tira o pedido sem resposta do histórico."""
        if self.historico and self.historico[-1]["role"] == "user":
            self.historico.pop()


def rodar_unico(llm: dict, texto: str, modo: str = "geral", auto: bool = False) -> int:
    agente = Agente(llm, modo, auto)
    try:
        agente.turno(texto)
    except ErroLLM as e:
        ui.erro(str(e))
        return 1
    return 0
