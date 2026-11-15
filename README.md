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

O Gárgula é um agente de terminal open source para quem vende pela internet, no estilo do Claude Code, mas feito para marketing digital, vendas, WhatsApp e Meta Ads. No terminal ele aparece roxo, sentado em cima do quadro.

- **É um agente de verdade**: lê e edita arquivos, roda comandos, busca nas suas notas (vault do Obsidian, base de conhecimento), lê páginas da web e consulta o Meta Ads sozinho, em ciclo, até terminar a tarefa.
- **Filtro Anti-Slop & Brand DNA**: elimina clichês vazios de IA ("transforme sua jornada", "mergulhe fundo") e escreve com o vocabulário, dores reais e mecanismo único da sua marca.
- **ROAS Real (Reconciliação com Checkout)**: cruza o gasto de anúncios com vendas pagas reais (Kiwify, Hotmart, Eduzz, etc.) para caçar anúncios que parecem lucrativos mas só geram boletos abandonados.
- **War Room & Auditor de CRO**: submete a sua Landing Page a um stress-test com 3 personas impiedosas (o cético, o impaciente e o racional) antes de você colocar dinheiro em tráfego.
- **Sniper de WhatsApp**: quebra objeções duras no 1 a 1 com táticas de isolamento, custo de inação e reversão de risco, com proteção anti-ban rigorosa.
- **Pede permissão**: leitura roda direto; escrever arquivo e rodar comando pedem `[s]im / [n]ão / [t]odas`. Com `--auto` (ou `/auto`) ele aprova sozinho, exceto o envio de WhatsApp, que sempre pergunta.
- **Protege segredos**: não lê `.env`, `.secrets`, chaves nem tokens, e o terminal do agente não herda as chaves de API.
- **Lê instruções do projeto**: carrega `GARGULA.md`, `AGENTS.md` e `CLAUDE.md` da pasta atual e da pasta base.
- **Funciona com qualquer LLM**: Anthropic (Claude), OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Ollama (local) ou qualquer API compatível com OpenAI.
- **Zero dependências externas**: roda 100% com a biblioteca padrão do Python 3.9+.

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

## Agente

```bash
gargula config set pasta_base "C:\Users\voce\minhas-notas"   # vault/base que ele pode pesquisar
gargula                                      # chat com ferramentas
gargula chat "leia minhas notas de preço e monte 3 ofertas para a Black Friday"
gargula --auto chat "rode os testes e corrija o que falhar"
```

| Ferramenta | Permissão |
|---|---|
| `ler_arquivo`, `listar`, `buscar_texto`, `buscar_notas`, `ler_url`, `meta_ads_insights`, `obter_dna`, `reconciliar_checkout` | roda direto |
| `escrever_arquivo`, `editar_arquivo`, `executar` (PowerShell/bash) | pergunta (ou `--auto`); fora da pasta atual sempre pergunta |
| `whatsapp_enviar` | sempre pergunta, um número por vez |

Para trabalho de agente, os melhores resultados vêm de Claude (Anthropic). Modelos menores funcionam, mas desistem mais cedo.

## Comandos

| Comando | O que faz |
|---|---|
| `gargula inicio` (ou `wizard`) | assistente interativo de boas-vindas e configuração no terminal |
| `gargula` | chat interativo (`/modo copy`, `/modo cro`, `/provedor gemini`, `/salvar`, `/ajuda`) |
| `gargula chat "..."` | pergunta direta ao agente; aceita pipe: `cat pagina.txt \| gargula chat "melhore a headline"` |
| `gargula cro --url ... \| --arquivo ...` | War Room: stress-test de CRO de página com 3 personas implacáveis e score 0-100 |
| `gargula criativos ganchos` | 10 ganchos de 3s divididos em 5 arquétipos de alta conversão |
| `gargula criativos roteiro` | roteiro de vídeo de anúncio com indicações de corte e B-Roll |
| `gargula criativos pacote` | pacote pronto para subir no Meta Ads (3 copys, 5 headlines, descrições e UTMs) |
| `gargula copy --produto ... --publico ...` | variações de copy (`--canal`, `--tom`, `--n`) |
| `gargula oferta --produto ... --preco ...` | promessa, mecanismo, bônus, garantia, escada de preço e objeções |
| `gargula funil --produto ... --canal ...` | funil por etapa com a métrica-chave e onde automatizar |
| `gargula zap msg --objetivo ...` | mensagens e fluxos de WhatsApp |
| `gargula zap objetar "achei caro"` | Sniper: 3 abordagens táticas de quebra de objeção no 1 a 1 |
| `gargula zap enviar --para ... --texto ...` | prévia do envio; com `--enviar` manda 1 mensagem (Evolution ou Cloud API) |
| `gargula ads insights` | tabela de gasto, CTR, CPC, CPM, compras, CPA, ROAS, leads e conversas |
| `gargula ads diagnostico --meta "CPA até R$ 30"` | a tabela mais o veredito da IA por campanha |
| `gargula ads reconciliar --checkout ...` | cruza gasto de ads com vendas reais de checkout para achar o ROAS Real |
| `gargula dna mostrar\|set\|inicializar` | gerencia o Brand & Offer DNA e o filtro anti-slop |
| `gargula config mostrar\|set\|unset\|caminho` | configuração (os segredos aparecem mascarados) |

Os modos do chat são `geral`, `copy`, `oferta`, `zap`, `objetar`, `ads`, `reconciliar`, `cro`, `criativos` e `funil`.

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

### Reconciliação de Checkout (ROAS Real)

Cruza os relatórios do Meta Ads com os dados reais do seu checkout (Kiwify, Hotmart, Eduzz, Braip, Yampi, Shopify, etc.):

```bash
gargula ads reconciliar --ads metricas_meta.csv --checkout vendas_kiwify.csv
```

O Gárgula calcula o faturamento real pago vs compras reportadas pelo Meta e alerta na hora sobre boletos e Pix não pagos que mascaram o ROAS.

### War Room & Auditor de CRO (Stress Test)

Submeta uma página de vendas a 3 personas impiedosas (o cético desconfiado, o impaciente dos 5s e o racional econômico) antes de subir anúncios:

```bash
gargula cro --url https://seusite.com/oferta
# ou com arquivo local / pipe:
gargula cro --arquivo pagina_vendas.html
cat landing.md | gargula cro
```

### Brand & Offer DNA (Filtro Anti-Slop)

Crie a identidade da sua marca e elimine clichês de IA vazios:

```bash
gargula dna inicializar                        # cria os templates padrão em ~/.gargula/dna
gargula dna mostrar                            # visualiza avatar, oferta, marca e anti-slop
gargula dna set avatar "Dores: CPA caro..."    # atualiza uma área do DNA
```

### Fábrica de Criativos & Ganchos

```bash
gargula criativos ganchos --produto "Mentoria de Tráfego" --publico "Gestores locais"
gargula criativos roteiro --produto "Placa NFC" --formato reels
gargula criativos pacote --produto "Curso de Vendas" --preco "R$ 197"
```

### Sniper de WhatsApp (Quebra de Objeções)

```bash
gargula zap objetar "achei muito caro, vou pensar e te falo"
gargula zap objetar "funciona para o meu nicho?" --produto "Software de Automação"
```

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
