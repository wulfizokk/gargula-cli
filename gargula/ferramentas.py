"""Ferramentas que a LLM pode usar: arquivos, terminal, busca, web, Meta Ads e WhatsApp.

Categorias de permissão:
  leitura  -> roda direto
  escrita  -> pede permissão (ou roda em modo --auto)
  sempre   -> pede permissão SEMPRE, mesmo em --auto (envio de WhatsApp)
"""

from __future__ import annotations

import fnmatch
import html
import ipaddress
import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from gargula import ads, contexto, zap
from gargula.llm import USER_AGENT

LIMITE_SAIDA = 20_000


class ErroFerramenta(Exception):
    pass


def _obj(props: dict, obrigatorios: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": obrigatorios}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}

DEFINICOES = [
    {"nome": "ler_arquivo", "categoria": "leitura",
     "descricao": "Lê um arquivo de texto com números de linha. Use 'inicio' e 'linhas' para arquivos grandes.",
     "parametros": _obj({"caminho": S, "inicio": I, "linhas": I}, ["caminho"])},
    {"nome": "listar", "categoria": "leitura",
     "descricao": "Lista arquivos e pastas. 'padrao' aceita glob, ex.: '*.md' ou '**/*.py'.",
     "parametros": _obj({"caminho": S, "padrao": S}, [])},
    {"nome": "buscar_texto", "categoria": "leitura",
     "descricao": "Procura uma expressão regular (sem diferenciar maiúsculas) dentro dos arquivos de uma pasta. "
                  "Devolve arquivo:linha: trecho.",
     "parametros": _obj({"padrao": S, "caminho": S, "arquivos": {"type": "string", "description": "glob do nome, ex.: *.md"}},
                        ["padrao"])},
    {"nome": "buscar_notas", "categoria": "leitura",
     "descricao": "Busca por palavras-chave nas notas da pasta base do usuário (vault/base de conhecimento) "
                  "e devolve as notas mais relevantes com trechos. Use antes de ler_arquivo quando não souber o caminho.",
     "parametros": _obj({"termo": S}, ["termo"])},
    {"nome": "ler_url", "categoria": "leitura",
     "descricao": "Baixa uma página da web (http/https) e devolve o texto limpo.",
     "parametros": _obj({"url": S}, ["url"])},
    {"nome": "meta_ads_insights", "categoria": "leitura",
     "descricao": "Métricas do Meta Ads (só leitura): gasto, CTR, CPC, CPM, compras, CPA, ROAS, leads e conversas. "
                  "periodo: today, yesterday, last_3d, last_7d, last_14d, last_30d, this_month, last_month. "
                  "nivel: campaign, adset ou ad.",
     "parametros": _obj({"periodo": S, "nivel": S, "conta": S}, [])},
    {"nome": "escrever_arquivo", "categoria": "escrita",
     "descricao": "Cria ou sobrescreve um arquivo com o conteúdo inteiro. Para mudar um trecho, prefira editar_arquivo.",
     "parametros": _obj({"caminho": S, "conteudo": S}, ["caminho", "conteudo"])},
    {"nome": "editar_arquivo", "categoria": "escrita",
     "descricao": "Troca um trecho exato de um arquivo. 'antigo' precisa aparecer uma única vez "
                  "(ou use todas=true). Leia o arquivo antes.",
     "parametros": _obj({"caminho": S, "antigo": S, "novo": S, "todas": B}, ["caminho", "antigo", "novo"])},
    {"nome": "executar", "categoria": "escrita",
     "descricao": "Roda um comando no terminal (PowerShell no Windows, bash no Linux/macOS) na pasta atual e devolve "
                  "a saída e o código de saída. Use para git, python, npm, scripts e inspeção do sistema.",
     "parametros": _obj({"comando": S, "timeout": I}, ["comando"])},
    {"nome": "whatsapp_enviar", "categoria": "sempre",
     "descricao": "Envia UMA mensagem de WhatsApp para UM número (Evolution ou Cloud API). Sempre pede confirmação "
                  "humana. Proibido usar para disparo em lote ou mensagem fria.",
     "parametros": _obj({"para": S, "texto": S, "via": {"type": "string", "enum": ["evolution", "cloud"]}},
                        ["para", "texto"])},
    {"nome": "obter_dna", "categoria": "leitura",
     "descricao": "Lê o DNA da marca, oferta, avatar ou filtro anti-slop da pasta de identidade. "
                  "categoria: avatar, oferta, marca ou anti_slop.",
     "parametros": _obj({"categoria": S}, ["categoria"])},
    {"nome": "reconciliar_checkout", "categoria": "leitura",
     "descricao": "Cruza métricas de anúncios com vendas reais de checkout (Kiwify, Hotmart, etc.) "
                  "para descobrir o ROAS Real e identificar boletos e Pix não pagos. "
                  "nivel opcional: campaign, adset ou ad.",
     "parametros": _obj({"arquivo_ads": S, "arquivo_checkout": S, "nivel": S}, ["arquivo_ads", "arquivo_checkout"])},
    {"nome": "crm_status", "categoria": "leitura",
     "descricao": "Inspeciona o status do CRM proprietário (Gárgula/Usetag CRM), módulos ativos e travas do agente.",
     "parametros": _obj({}, [])},
    {"nome": "crm_catalogo", "categoria": "leitura",
     "descricao": "Retorna o catálogo oficial de produtos, kits e preços cadastrados no CRM para evitar alucinações de valores.",
     "parametros": _obj({}, [])},
]
POR_NOME = {d["nome"]: d for d in DEFINICOES}


def definicoes_api() -> list[dict]:
    return [{k: d[k] for k in ("nome", "descricao", "parametros")} for d in DEFINICOES]


# ---------- utilidades ----------

def caminho(c: str) -> Path:
    if not c:
        raise ErroFerramenta("caminho vazio")
    p = Path(os.path.expanduser(c))
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    if contexto.bloqueado(p):
        raise ErroFerramenta("arquivo protegido (segredo ou pasta técnica): acesso negado")
    return p


def dentro_da_area(p: Path) -> bool:
    """Pasta atual ou pasta base configurada."""
    areas = [Path.cwd().resolve()]
    base = contexto.pasta_base()
    if base:
        areas.append(base.resolve())
    return any(p == a or a in p.parents for a in areas)


def _cortar(texto: str, limite: int = LIMITE_SAIDA) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite] + f"\n[… saída cortada: mais {len(texto) - limite} caracteres]"


def _env_sem_segredos() -> dict:
    """O terminal do agente não herda chaves de API carregadas pelo Gárgula."""
    marcadores = ("KEY", "TOKEN", "SECRET", "SENHA", "PASSWORD", "WORKSPACE_ID", "APIKEY")
    return {k: v for k, v in os.environ.items() if not any(m in k.upper() for m in marcadores)}


def _iterar(base: Path, glob_nome: str | None):
    for raiz, pastas, nomes in os.walk(base):
        pastas[:] = [d for d in pastas if d.lower() not in contexto.PASTAS_IGNORADAS and not d.startswith(".")]
        for n in nomes:
            if glob_nome and not fnmatch.fnmatch(n.lower(), glob_nome.lower()):
                continue
            p = Path(raiz) / n
            if not contexto.bloqueado(p):
                yield p


# ---------- implementações ----------

def ler_arquivo(caminho_: str, inicio: int = 1, linhas: int = 400) -> str:
    p = caminho(caminho_)
    if not p.is_file():
        raise ErroFerramenta(f"arquivo não existe: {p}")
    try:
        todas = p.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        raise ErroFerramenta("arquivo binário ou fora de UTF-8") from None
    inicio = max(1, int(inicio or 1))
    linhas = max(1, min(int(linhas or 400), 2000))
    trecho = todas[inicio - 1: inicio - 1 + linhas]
    corpo = "\n".join(f"{i:>5}\t{l}" for i, l in enumerate(trecho, start=inicio))
    fim = inicio + len(trecho) - 1
    rodape = f"\n[linhas {inicio}-{fim} de {len(todas)}]" if fim < len(todas) or inicio > 1 else ""
    return _cortar(corpo + rodape, 60_000)


def listar(caminho_: str = ".", padrao: str = "*") -> str:
    p = caminho(caminho_ or ".")
    if not p.is_dir():
        raise ErroFerramenta(f"não é pasta: {p}")
    itens = []
    for x in sorted(p.glob(padrao or "*")):
        rel = x.relative_to(p)
        if contexto.bloqueado(x) or any(part.lower() in contexto.PASTAS_IGNORADAS for part in rel.parts):
            continue
        itens.append(str(rel).replace("\\", "/") + ("/" if x.is_dir() else ""))
        if len(itens) >= 300:
            itens.append("[… mais itens; refine o padrão]")
            break
    return "\n".join(itens) or "(vazio)"


def buscar_texto(padrao: str, caminho_: str = ".", arquivos: str | None = None) -> str:
    base = caminho(caminho_ or ".")
    try:
        rx = re.compile(padrao, re.IGNORECASE)
    except re.error as e:
        raise ErroFerramenta(f"regex inválida: {e}") from None
    achados = []
    alvos = [base] if base.is_file() else _iterar(base, arquivos)
    for p in alvos:
        try:
            if p.stat().st_size > 2_000_000:
                continue
            texto = p.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            if rx.search(linha):
                rel = p.relative_to(base) if base.is_dir() else p.name
                achados.append(f"{str(rel).replace(chr(92), '/')}:{n}: {linha.strip()[:200]}")
                if len(achados) >= 100:
                    return "\n".join(achados) + "\n[… parou em 100 resultados; refine a busca]"
    return "\n".join(achados) or "nenhum resultado"


def buscar_notas(termo: str) -> str:
    try:
        return contexto.formatar_busca(termo, contexto.buscar(termo, k=8))
    except contexto.ErroContexto as e:
        raise ErroFerramenta(str(e)) from None


def _validar_url_publica(url: str) -> None:
    """Impede SSRF para localhost, loopback, link-local e redes privadas."""
    if not re.match(r"^https?://", url or "", re.IGNORECASE):
        raise ErroFerramenta("só http(s)")
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        raise ErroFerramenta("URL sem host válido")
    if host.lower() in ("localhost", "ip6-localhost"):
        raise ErroFerramenta("acesso a endereço local bloqueado por segurança")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ErroFerramenta(f"não consegui resolver o host {host!r}: {e}") from None
    for info in infos:
        ip_str = info[4][0].split("%", 1)[0]
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise ErroFerramenta(f"acesso a endereço interno ({ip}) bloqueado por segurança")


class _RedirectSeguro(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validar_url_publica(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def ler_url(url: str) -> str:
    _validar_url_publica(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_RedirectSeguro())
    try:
        with opener.open(req, timeout=30) as r:
            bruto = r.read(3_000_000)
            tipo = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        raise ErroFerramenta(f"HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise ErroFerramenta(f"não consegui abrir: {e.reason}") from None
    texto = bruto.decode(tipo, "replace")
    if "<html" in texto[:2000].lower() or "<body" in texto.lower():
        texto = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", texto)
        texto = re.sub(r"(?i)<br\s*/?>|</(p|div|h\d|li|tr)>", "\n", texto)
        texto = html.unescape(re.sub(r"<[^>]+>", " ", texto))
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n\s*\n+", "\n\n", texto).strip()
    return _cortar(texto)


def meta_ads_insights(periodo: str = "last_7d", nivel: str = "campaign", conta: str | None = None) -> str:
    try:
        linhas = ads.buscar(conta, periodo or "last_7d", nivel or "campaign")
    except ads.ErroAds as e:
        raise ErroFerramenta(str(e)) from None
    return json.dumps([ads.resumir(l, nivel or "campaign") for l in linhas], ensure_ascii=False)


def escrever_arquivo(caminho_: str, conteudo: str) -> str:
    p = caminho(caminho_)
    existia = p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(conteudo, encoding="utf-8")
    return f"{'sobrescrito' if existia else 'criado'}: {p} ({len(conteudo.splitlines())} linhas)"


def editar_arquivo(caminho_: str, antigo: str, novo: str, todas: bool = False) -> str:
    p = caminho(caminho_)
    if not p.is_file():
        raise ErroFerramenta(f"arquivo não existe: {p}")
    texto = p.read_text(encoding="utf-8-sig")
    n = texto.count(antigo)
    if n == 0:
        raise ErroFerramenta("trecho 'antigo' não encontrado; leia o arquivo e copie o trecho exato")
    if n > 1 and not todas:
        raise ErroFerramenta(f"trecho aparece {n} vezes; inclua mais contexto ou use todas=true")
    p.write_text(texto.replace(antigo, novo) if todas else texto.replace(antigo, novo, 1), encoding="utf-8")
    return f"editado: {p} ({n if todas else 1} troca(s))"


def executar(comando: str, timeout: int = 120) -> str:
    timeout = max(1, min(int(timeout or 120), 600))
    kwargs = {}
    if os.name == "nt":
        args = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + comando]
        # Evita a chuva de janelas CMD/PowerShell piscando na tela no Windows
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        args = ["bash", "-lc", comando]
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, cwd=os.getcwd(),
                           env=_env_sem_segredos(), stdin=subprocess.DEVNULL, **kwargs)
    except subprocess.TimeoutExpired:
        raise ErroFerramenta(f"passou de {timeout}s e foi interrompido") from None
    except FileNotFoundError as e:
        raise ErroFerramenta(f"shell não encontrado: {e}") from None
    saida = (r.stdout + (b"\n" + r.stderr if r.stderr else b"")).decode("utf-8", "replace").strip()
    return _cortar(f"[código de saída {r.returncode}]\n{saida}")


def whatsapp_enviar(para: str, texto: str, via: str = "evolution") -> str:
    try:
        numero = zap.normalizar_numero(para)
        zap.enviar(via or "evolution", numero, texto)
    except zap.ErroZap as e:
        raise ErroFerramenta(str(e)) from None
    return f"enviado para {numero} via {via or 'evolution'}"


def obter_dna(categoria: str) -> str:
    from gargula import dna
    conteudo = dna.obter(categoria)
    return conteudo or f"DNA para '{categoria}' não configurado ainda."


def _inferir_nivel_ads(linhas: list[dict], nivel: str | None) -> str:
    if nivel in ("campaign", "adset", "ad"):
        return nivel
    if linhas:
        chaves = {ads._norm_chave(k) for k in linhas[0].keys()}
        if "ad_name" in chaves or "nome_do_anuncio" in chaves:
            return "ad"
        if "adset_name" in chaves or "nome_do_conjunto_de_anuncios" in chaves:
            return "adset"
    return "campaign"


def reconciliar_checkout(arquivo_ads: str, arquivo_checkout: str, nivel: str | None = None) -> str:
    from gargula import ads, checkout
    p_ads = caminho(arquivo_ads)
    p_check = caminho(arquivo_checkout)
    if not p_ads.is_file():
        raise ErroFerramenta(f"arquivo de ads não encontrado: {p_ads}")
    if not p_check.is_file():
        raise ErroFerramenta(f"arquivo de checkout não encontrado: {p_check}")
    brutas = ads.carregar_arquivo(str(p_ads))
    niv = _inferir_nivel_ads(brutas, nivel)
    resumos = [ads.resumir(l, niv) for l in brutas]
    vendas = checkout.carregar_vendas(str(p_check))
    res = checkout.reconciliar(resumos, vendas)
    return checkout.formatar_tabela(res)


def crm_status() -> str:
    from gargula import crm
    return crm.formatar_status()


def crm_catalogo() -> str:
    from gargula import crm
    return crm.formatar_tabela_catalogo()


IMPLEMENTACOES = {
    "ler_arquivo": lambda a: ler_arquivo(a.get("caminho", ""), a.get("inicio", 1), a.get("linhas", 400)),
    "listar": lambda a: listar(a.get("caminho", "."), a.get("padrao", "*")),
    "buscar_texto": lambda a: buscar_texto(a.get("padrao", ""), a.get("caminho", "."), a.get("arquivos")),
    "buscar_notas": lambda a: buscar_notas(a.get("termo", "")),
    "ler_url": lambda a: ler_url(a.get("url", "")),
    "meta_ads_insights": lambda a: meta_ads_insights(a.get("periodo"), a.get("nivel"), a.get("conta")),
    "escrever_arquivo": lambda a: escrever_arquivo(a.get("caminho", ""), a.get("conteudo", "")),
    "editar_arquivo": lambda a: editar_arquivo(a.get("caminho", ""), a.get("antigo", ""), a.get("novo", ""),
                                               bool(a.get("todas"))),
    "executar": lambda a: executar(a.get("comando", ""), a.get("timeout", 120)),
    "whatsapp_enviar": lambda a: whatsapp_enviar(a.get("para", ""), a.get("texto", ""), a.get("via", "evolution")),
    "obter_dna": lambda a: obter_dna(a.get("categoria", "")),
    "reconciliar_checkout": lambda a: reconciliar_checkout(
        a.get("arquivo_ads", ""), a.get("arquivo_checkout", ""), a.get("nivel")
    ),
    "crm_status": lambda a: crm_status(),
    "crm_catalogo": lambda a: crm_catalogo(),
}


def resumo_chamada(nome: str, args: dict) -> str:
    """Linha curta para mostrar ao usuário (sem despejar conteúdo gigante)."""
    principal = {
        "ler_arquivo": "caminho", "listar": "caminho", "buscar_texto": "padrao", "buscar_notas": "termo",
        "ler_url": "url", "meta_ads_insights": "periodo", "escrever_arquivo": "caminho",
        "editar_arquivo": "caminho", "executar": "comando", "whatsapp_enviar": "para",
        "obter_dna": "categoria", "reconciliar_checkout": "arquivo_checkout",
    }.get(nome)
    valor = str(args.get(principal, "")) if principal else ""
    valor = valor.replace("\n", " ")
    return f"{nome}({valor[:90] + ('…' if len(valor) > 90 else '')})"


def rodar(nome: str, args: dict) -> tuple[str, bool]:
    """Executa a ferramenta. Devolve (conteúdo, erro?)."""
    if nome not in IMPLEMENTACOES:
        return f"ferramenta desconhecida: {nome}", True
    if "_json_invalido" in args:
        return "argumentos em JSON inválido; tente de novo", True
    try:
        return IMPLEMENTACOES[nome](args), False
    except ErroFerramenta as e:
        return str(e), True
    except Exception as e:  # nunca derruba o agente
        return f"{type(e).__name__}: {e}", True
