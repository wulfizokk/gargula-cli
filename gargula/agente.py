"""Ciclo do agente: a LLM pensa, chama ferramentas, recebe o resultado e continua até terminar."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime

from gargula import config, contexto, ferramentas, prompts, ui
from gargula.llm import ErroLLM, conversar

MAX_PASSOS_PADRAO = 200


def _max_passos() -> int:
    """Lê max_passos do config (0 = ilimitado). Padrão: 200."""
    v = config.carregar().get("max_passos")
    if v is not None:
        try:
            return int(v)
        except (ValueError, TypeError):
            pass
    return MAX_PASSOS_PADRAO


def _compactar_imagens_antigas(historico: list[dict], manter: int = 2) -> None:
    """Mantém base64 apenas nas últimas `manter` mensagens com imagens para poupar RAM e tokens."""
    com_img = [i for i, m in enumerate(historico) if m.get("imagens")]
    if len(com_img) <= manter:
        return
    for i in com_img[:-manter]:
        imgs = historico[i].pop("imagens", [])
        nomes = ", ".join(x.get("nome", "imagem") for x in imgs)
        if nomes:
            nota = f"\n[imagens enviadas anteriormente: {nomes}]"
            historico[i]["content"] = (historico[i].get("content") or "") + nota


class Agente:
    def __init__(self, llm: dict, modo: str = "geral", auto: bool = False, com_ferramentas: bool = True):
        self.llm = llm
        self.modo = modo
        self.auto = auto
        self.com_ferramentas = com_ferramentas
        self.historico: list[dict] = []
        self.liberadas: set[str] = set()   # ferramentas liberadas "para a sessão"
        self.cor = ui.usa_cor()
        self._inicio_turno: int | None = None

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
        # YOLO: tudo liberado exceto WhatsApp (que SEMPRE pede)
        if self.auto and cat != "sempre":
            if fora:
                ui.aviso(f"escrevendo fora da base: {args.get('caminho', '?')}")
            return True, ""
        if cat == "escrita" and not fora and nome in self.liberadas:
            return True, ""
        if not sys.stdin.isatty():
            return False, "sem permissão: rode no terminal interativo ou use --auto"
        # ── detalhes extras (só o que não aparece no resumo_chamada) ──
        detalhe = ""
        if nome == "executar":
            cmd = args.get("comando", "")
            if len(cmd) > 90 or "\n" in cmd:
                detalhe = cmd
        elif nome == "whatsapp_enviar":
            detalhe = f"para {args.get('para')}:\n{args.get('texto', '')}"
        elif nome == "editar_arquivo":
            detalhe = f"- {args.get('antigo', '')[:400]}\n+ {args.get('novo', '')[:400]}"
        elif nome == "escrever_arquivo":
            detalhe = f"{args.get('caminho')} ({len(str(args.get('conteudo', '')).splitlines())} linhas)"
        if fora:
            detalhe += "\n⚠ fora da pasta atual e da pasta base"
        if detalhe.strip():
            for l in detalhe.strip().splitlines()[:15]:
                if len(l) > 110:
                    l = l[:107] + "..."
                print(ui.pintar("    │ ", ui.PEDRA, cor=self.cor) + l)
        # ── tecla única: Enter/s = sim, n = não, t = todas ──
        hint = "enter" + ("/t" if cat == "escrita" and not fora else "") + "/n"
        sys.stdout.write(ui.pintar(f"    rodar? ", ui.LILAS, cor=self.cor)
                         + ui.pintar(f"({hint}) ", ui.PEDRA, cor=self.cor)
                         + ui.pintar("▸ ", ui.LILAS, negrito=True, cor=self.cor))
        sys.stdout.flush()
        try:
            ch = ui.ler_tecla()
        except KeyboardInterrupt:
            print(ui.pintar("cancelado", ui.VERMELHO, cor=self.cor))
            raise
        if ch in ("\r", "\n", "", "s", "y"):
            print(ui.pintar("sim", ui.VERDE, cor=self.cor))
            return True, ""
        if ch == "t" and cat == "escrita" and not fora:
            print(ui.pintar("todas ✔", ui.AMARELO, cor=self.cor))
            self.liberadas.add(nome)
            return True, ""
        if ch == "n":
            print(ui.pintar("não", ui.VERMELHO, cor=self.cor))
            try:
                motivo = input(ui.pintar("    instruções? › ", ui.CINZA, cor=self.cor)).strip()
            except (EOFError, KeyboardInterrupt):
                motivo = ""
            return False, "o usuário NEGOU esta ação." + (f" Instrução dele: {motivo}" if motivo else
                                                          " Pergunte como prefere seguir.")
        # qualquer outra tecla = sim (benefício da dúvida)
        print(ui.pintar("sim", ui.VERDE, cor=self.cor))
        return True, ""

    # ---------- turno ----------
    def turno(self, texto: str, imagens: list[dict] | None = None) -> str:
        self._inicio_turno = len(self.historico)
        msg_user: dict = {"role": "user", "content": texto}
        if imagens:
            msg_user["imagens"] = imagens
        self.historico.append(msg_user)
        _compactar_imagens_antigas(self.historico)
        defs = ferramentas.definicoes_api() if self.com_ferramentas else None
        sistema = self.sistema()
        final = ""
        limite = _max_passos()
        passo = 0
        while limite == 0 or passo < limite:
            passo += 1
            with ui.pensando(cor=self.cor):
                r = conversar(self.llm, sistema, self.historico, defs)
            self.historico.append({"role": "assistant", "content": r["texto"],
                                   "chamadas": r["chamadas"], "bruto": r.get("bruto")})
            if r["texto"].strip():
                ui.resposta(r["texto"], cor=self.cor)
                final = r["texto"]
            if not r["chamadas"]:
                if r.get("parada") in ("max_tokens", "length", "MAX_TOKENS"):
                    ui.aviso("a resposta bateu no limite de tokens (gargula config set max_tokens 8192)")
                self._inicio_turno = None
                return final
            resultados = []
            try:
                for c in r["chamadas"]:
                    print(ui.pintar("  ▸ ", ui.ROXO, negrito=True, cor=self.cor)
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
        ui.aviso(f"parei depois de {limite} passos; diga 'continue' para seguir")
        self._inicio_turno = None
        return final

    def desfazer_ultimo(self) -> None:
        """Após erro ou interrupção, remove todo o turno inacabado do histórico."""
        if self._inicio_turno is not None and self._inicio_turno <= len(self.historico):
            del self.historico[self._inicio_turno:]
            self._inicio_turno = None
            return
        if self.historico and self.historico[-1]["role"] == "user":
            self.historico.pop()


def rodar_unico(llm: dict, texto: str, modo: str = "geral", auto: bool = False,
                imagens: list[dict] | None = None) -> int:
    agente = Agente(llm, modo, auto)
    try:
        agente.turno(texto, imagens=imagens)
    except ErroLLM as e:
        ui.erro(str(e))
        return 1
    return 0
