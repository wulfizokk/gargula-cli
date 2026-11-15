# Gárgula CLI

```
              █▄              ▄█
               ▀█▄▄████████▄▄█▀
           █▄   ███▄▄████▄▄███   ▄█
           ███▄  ▀██████████▀  ▄███
            ▀████████████████████▀
              ▀█▀████████████▀█▀
                ▄▀█▀▄▀▀▀▀▄▀█▀▄
╭──────────────────────────────────────────────╮
│  Gárgula CLI                                 │
│  copiloto de marketing, vendas, WhatsApp e   │
│  Meta Ads, com a LLM que você quiser         │
╰──────────────────────────────────────────────╯
```

O Gárgula é um copiloto de terminal, open source, para quem vende pela internet: copy, oferta, funil, mensagens e envio de WhatsApp, e métricas do Meta Ads com diagnóstico. No terminal ele aparece roxo, sentado em cima do quadro.

- **Funciona com qualquer LLM**: Anthropic (Claude), OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Ollama (local) ou qualquer API compatível com OpenAI.
- **Não precisa de dependências**: usa só a biblioteca padrão do Python 3.9+.
- **Trava anti-ban no WhatsApp**: manda para 1 destinatário por vez, mostra uma prévia por padrão, pede confirmação e espera um intervalo mínimo entre envios. Ele não faz disparo em lote.
- **Meta Ads só em leitura**: lê métricas e recomenda escalar, manter, ajustar ou cortar. Nunca altera a sua conta.

## Instalação

```bash
pipx install git+https://github.com/wulfizokk/gargula-cli
# ou
pip install git+https://github.com/wulfizokk/gargula-cli
```

## Primeiros passos

```bash
# escolha a LLM: chave por variável de ambiente (recomendado) ou no config
export ANTHROPIC_API_KEY=...          # PowerShell: $env:ANTHROPIC_API_KEY="..."
gargula config set provedor anthropic

gargula                                # abre o chat interativo
gargula provedores                     # mostra as LLMs e quais estão com chave
```

Para trocar de LLM numa chamada, use `-p` e `-m`:

```bash
gargula -p groq chat "3 ganchos para reels de barbearia"
gargula -p ollama -m llama3.1 chat "ideia de isca digital para nutricionista"
gargula -p compativel chat "oi"        # com: gargula config set base_url.compativel http://localhost:1234/v1
```

## Comandos

| Comando | O que faz |
|---|---|
| `gargula` | chat interativo (`/modo copy`, `/provedor gemini`, `/salvar`, `/ajuda`) |
| `gargula chat "..."` | pergunta direta; aceita pipe: `cat pagina.txt \| gargula chat "melhore a headline"` |
| `gargula copy --produto ... --publico ...` | variações de copy (`--canal`, `--tom`, `--n`) |
| `gargula oferta --produto ... --preco ...` | promessa, mecanismo, bônus, garantia, escada de preço e objeções |
| `gargula funil --produto ... --canal ...` | funil por etapa com a métrica-chave e onde automatizar |
| `gargula zap msg --objetivo ...` | mensagens e fluxos de WhatsApp |
| `gargula zap enviar --para ... --texto ...` | prévia do envio; com `--enviar` manda 1 mensagem (Evolution ou Cloud API) |
| `gargula ads insights` | tabela de gasto, CTR, CPC, CPM, compras, CPA, ROAS, leads e conversas |
| `gargula ads diagnostico --meta "CPA até R$ 30"` | a tabela mais o veredito da IA por campanha |
| `gargula config mostrar\|set\|unset\|caminho` | configuração (os segredos aparecem mascarados) |

Os modos do chat são `geral`, `copy`, `oferta`, `zap`, `ads` e `funil`.

### WhatsApp

```bash
gargula config set evolution.url https://sua-evolution.com
gargula config set evolution.instancia minha-loja
gargula config set evolution.chave ...         # ou EVOLUTION_API_KEY

gargula zap enviar --para 5548999990000 --texto "Seu pedido saiu hoje!"            # só prévia
gargula zap enviar --para 5548999990000 --texto "Seu pedido saiu hoje!" --enviar   # envia
gargula zap enviar --via cloud ...             # WhatsApp Cloud API (cloud.token, cloud.phone_id)
```

As regras abaixo são intencionais e não dá para desligar por flag:

- Uma lista de números é recusada.
- Entre um envio e outro há no mínimo 60 s.
- Se a API responder 401/428 (número caído), o Gárgula avisa para não reenviar nem gerar QR em sequência.

Com API não oficial, use só para responder quem falou com você. Mensagem proativa vai pela Cloud API, com template aprovado.

### Meta Ads

```bash
export META_ACCESS_TOKEN=...         # token com permissão ads_read
gargula ads insights --conta act_123456789 --periodo last_7d
gargula ads insights --nivel adset --json > metricas.json
gargula ads diagnostico --arquivo metricas.csv --meta "ROAS 3" --ticket 97
```

Sem token, exporte as métricas do Gerenciador de Anúncios e passe com `--arquivo`. O CSV precisa das colunas `nome, gasto, impressoes, cliques, compras, receita` (e, se tiver, `leads` e `conversas`).

## Variáveis de ambiente

| Variável | Uso |
|---|---|
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `GARGULA_API_KEY` | chaves das LLMs |
| `ANTHROPIC_WORKSPACE_ID` | só para chave Anthropic sem workspace vinculado (erro 400 pedindo `anthropic-workspace-id`) |
| `GARGULA_PROVEDOR`, `GARGULA_MODELO`, `GARGULA_BASE_URL` | LLM padrão |
| `EVOLUTION_URL`, `EVOLUTION_INSTANCIA`, `EVOLUTION_API_KEY` | Evolution API |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` | WhatsApp Cloud API |
| `META_ACCESS_TOKEN`, `META_AD_ACCOUNT`, `META_GRAPH_VERSION` | Meta Ads (Graph API, padrão `v23.0`) |
| `GARGULA_HOME` | pasta de config (padrão `~/.gargula`) |
| `NO_COLOR` | desliga as cores |

**Arquivos .env:** ao iniciar, o Gárgula lê `~/.gargula/.env` e os arquivos listados em `env_arquivos`, por exemplo `gargula config set env_arquivos "C:\cofre\gemini.env;C:\cofre\anthropic.env"`. Ele nunca sobrescreve uma variável que já existe no ambiente.

Variável de ambiente vence o arquivo de config. O `config.json` guarda texto puro: em máquina compartilhada, prefira variáveis.

## Desenvolvimento

```bash
git clone https://github.com/wulfizokk/gargula-cli && cd gargula-cli
pip install -e .
python -m unittest discover -s tests -v
```

Para adicionar um provedor, basta uma entrada em `gargula/config.py` (`PROVEDORES`). Se ele não falar o formato da OpenAI, crie também o tipo em `gargula/llm.py`. Contribuições são bem-vindas: abra uma issue ou um PR.

## Licença

MIT
