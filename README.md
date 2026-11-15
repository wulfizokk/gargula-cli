# Gárgula CLI

```
              █▄              ▄█
               ▀█▄▄████████▄▄█▀
           █▄   ███▄▄████▄▄███   ▄█
           ███▄  ▀██████████▀  ▄███
            ▀████████████████████▀
              ▀█▀████████████▀█▀
                ▄▀█▀▄▀▀▀▀▄▀█▀▄
╭──────────────────────────────────────────────────╮
│  Gárgula CLI (v0.3.0)                            │
│  O primeiro RevOS de terminal para vendas        │
│  online, WhatsApp, Meta Ads e marketing digital  │
╰──────────────────────────────────────────────────╯
```

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-purple.svg)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero%20(stdlib%20only)-green.svg)]()
[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen.svg)]()

O **Gárgula** é um agente autônomo de terminal e **RevOS (Revenue Operating System)** open source feito para quem vende pela internet: infoprodutores, afiliados, gestores de tráfego, e-commerces e equipes de vendas.

No estilo do *Claude Code*, mas especializado em fechar o ciclo de receita no marketing digital: **Medir $\rightarrow$ Decidir $\rightarrow$ Produzir $\rightarrow$ Executar $\rightarrow$ Aprender**.

---

## ⚡ Por Que o Gárgula é Diferente?

1. **Zero Clichês de IA (Filtro Anti-Slop & Brand DNA):** O mercado saturou de textos genéricos de IA (*"no mundo acelerado de hoje"*, *"transforme sua jornada"*). O Gárgula possui um filtro rígido anti-slop e aprende o vocabulário, dores reais e mecanismo único da sua marca.
2. **ROAS Real (Reconciliação com Checkout):** O Meta Ads mente ou atrasa por causa do iOS 14. O Gárgula cruza métricas de anúncios com vendas reais do checkout (Kiwify, Hotmart, Eduzz, Shopify, Stripe, etc.) e caça boletos e Pix não pagos que mascaram o seu lucro.
3. **War Room & Auditor de CRO Pré-Tráfego:** Submete a sua Landing Page a um stress-test implacável com 3 personas (o cético desconfiado, o impaciente dos 5s e o racional econômico) antes de você queimar dinheiro com anúncios.
4. **Sniper de WhatsApp (Fechamento 1 a 1):** Quebra objeções duras no WhatsApp com 3 abordagens táticas (isolamento, custo de inação e reversão de risco), com proteção anti-ban por design.
5. **Creative Factory (Fábrica de Criativos):** Gera 10 ganchos de 3s divididos em 5 arquétipos psicológicos e roteiros completos com indicação de corte e B-Rolls.
6. **Agente com Ferramentas Reais:** Lê e edita arquivos locais, roda comandos no terminal, busca no seu vault do Obsidian e consulta a Graph API do Meta Ads.
7. **100% Biblioteca Padrão:** Não tem 400 MB de dependências do `node_modules` ou pacotes externos. Usa puramente Python 3.9+ padrão, leve e instantâneo.
8. **Agnóstico de LLM:** Use Anthropic (Claude), OpenAI (GPT-4o), Gemini, Groq, OpenRouter, DeepSeek ou Ollama 100% local e gratuito.

---

## 🚀 Instalação Rápida

```bash
# Recomendado (com pipx):
pipx install git+https://github.com/wulfizokk/gargula-cli

# Ou via pip tradicional:
pip install git+https://github.com/wulfizokk/gargula-cli
```

### Configuração Inicial (1 Minuto)

Basta rodar o assistente interativo no terminal:

```bash
gargula inicio
```

Ou configure manualmente suas chaves via variáveis de ambiente:

```bash
# Escolha o seu provedor (PowerShell: $env:ANTHROPIC_API_KEY="...")
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."

# Defina a LLM padrão:
gargula config set provedor anthropic

# Veja quais modelos estão prontos:
gargula provedores
```

---

## 🎯 Os 5 Superpoderes do Gárgula

### 1. Brand & Offer DNA (Filtro Anti-Slop)

Diga adeus ao texto com cara de redação escolar do ChatGPT. O Gárgula armazena a identidade da sua marca em `~/.gargula/dna/`:
- `avatar.md`: dores viscerais, desejos concretos, gírias e termos reais do seu cliente.
- `oferta.md`: promessa principal, mecanismo único, ancoragem, garantia e bônus.
- `marca.md`: tom de voz, posicionamento e regras de estilo.
- `anti_slop.md`: lista de termos e clichês de IA estritamente banidos.

```bash
gargula dna inicializar                        # cria os templates guiados
gargula dna mostrar                            # visualiza o DNA atual
gargula dna set avatar "Dores: CPA acima de R$ 40..."
```
*Todo comando de copy, oferta, criativo e zap absorve o seu DNA automaticamente.*

---

### 2. Reconciliação de Atribuição & ROAS Real

O Meta Ads diz que você teve ROAS 3.0, mas na sua conta bancária o dinheiro não caiu. O motivo? Boletos gerados e Pix não pagos.

O Gárgula cruza o gasto real do Meta Ads com os relatórios de checkout (Kiwify, Hotmart, Eduzz, Braip, Yampi, Asaas, Stripe, etc.):

```bash
gargula ads reconciliar --ads metricas_meta.csv --checkout vendas_kiwify.csv
```

**Resultado no terminal:**
```text
Campanha                      Gasto Meta  Meta Compras  Real Pagas  Real Pend.  Receita Real  ROAS Meta  ROAS Real   Lucro Real  Veredito
────────────────────────────  ──────────  ────────────  ──────────  ──────────  ────────────  ─────────  ─────────  ───────────  ────────────────────────────
Escala - Oferta Principal      R$ 600,00            12           4           8     R$ 388,00      2,40x      0,65x  -R$ 212,00   ALERTA (BOLETO/PIX FANTASMA)
Retargeting - Depoimentos      R$ 150,00             5           5           0     R$ 485,00      3,20x      3,23x   R$ 335,00   ESCALAR (LUCRO REAL)

RESUMO GERAL DO COFRE:
  • Gasto Total em Ads:  R$ 750,00
  • Receita Real Paga:   R$ 873,00
  • Lucro Líquido Real:  R$ 123,00
  • ROAS Real Efetivo:   1,16x
  • Vendas: 9 pagas no checkout vs 17 registradas no Meta
```

---

### 3. War Room & Auditor de CRO Pré-Tráfego (Stress Test)

Antes de gastar R$ 1.000 em tráfego pago, passe a sua página de vendas pelo crivo de 3 personas impiedosas:
1. **O Cético Implacável:** caça promessas exageradas, falta de rosto/CNPJ e garantias vagas.
2. **O Impaciente dos 5s:** testa se a primeira dobra deixa claro o que é, para quem é e onde clica.
3. **O Racional Econômico:** compara sua oferta com alternativas gratuitas no YouTube.

```bash
# Analisa direto da URL:
gargula cro --url https://minhapagina.com/oferta

# Ou passe o arquivo local ou envie via pipe:
gargula cro --arquivo landing.html
cat lp.md | gargula cro
```

O Gárgula devolve um **Score de Prontidão (0 a 100)**, os 3 vazamentos críticos onde o lead vai desistir e a reescrita imediata da headline e CTA.

---

### 4. Sniper de WhatsApp (Quebra de Objeções 1 a 1)

Quando o lead mandar *"tá caro"*, *"vou falar com meu sócio"* ou *"preciso pensar"*, não perca a venda com respostas amadoras:

```bash
gargula zap objetar "achei muito caro" --produto "Mentoria de Tráfego" --preco "R$ 997"
```

O Gárgula gera 3 abordagens táticas validadas:
1. **Isolamento de Objeção:** descobre se o preço é a barreira real ou cortina de fumaça.
2. **Custo de Inação:** faz o lead sentir o peso financeiro de continuar adiando o problema.
3. **Reversão de Risco / Flexibilização:** garantia incondicional ou parcelamento facilitado.

Formatado em blocos naturais, prontos para copiar e mandar no WhatsApp.

---

### 5. Creative Factory (Fábrica de Criativos)

Produza ganchos e roteiros de anúncios validados para Reels, TikTok, Shorts e VSL:

```bash
# 10 ganchos de 3s divididos em 5 arquétipos (Quebra de Padrão, Curiosidade, Dor, Inimigo Comum, Mecanismo):
gargula criativos ganchos --produto "Placa NFC para Barbearias"

# Roteiro completo de 30-60s com indicações visuais de corte e B-Roll:
gargula criativos roteiro --produto "Curso de Vendas" --formato reels

# Pacote completo pronto para subir no Gerenciador de Anúncios:
gargula criativos pacote --produto "Software de Automação" --preco "R$ 197"
```

---

## 🤖 O Agente Autônomo

O Gárgula é um agente de terminal interativo. Ele pensa, decide quais ferramentas usar e executa tarefas multi-etapas de forma autônoma:

```bash
gargula config set pasta_base "C:\Users\voce\meu-vault-obsidian"
gargula
```

Ou execute tarefas diretas com aprovação automática de leitura/escrita:
```bash
gargula --auto chat "leia minhas notas sobre a Black Friday, veja o CPA das campanhas no Meta Ads e monte uma oferta nova"
```

### Matriz de Ferramentas e Permissões

| Ferramenta | Permissão | O que faz |
|---|---|---|
| `ler_arquivo`, `listar`, `buscar_texto` | Leitura (livre) | Inspeciona código e arquivos locais |
| `buscar_notas` | Leitura (livre) | Busca semântica e por termos no seu Obsidian / Vault |
| `ler_url` | Leitura (livre) | Baixa e limpa páginas da web para análise de concorrentes e CRO |
| `meta_ads_insights` | Leitura (livre) | Consulta métricas da Graph API do Meta Ads |
| `obter_dna` | Leitura (livre) | Lê regras de marca, avatar, oferta e anti-slop |
| `reconciliar_checkout` | Leitura (livre) | Cruza dados de anúncios com o checkout financeiro |
| `escrever_arquivo`, `editar_arquivo` | Escrita (pergunta) | Cria e modifica arquivos com segurança |
| `executar` | Escrita (pergunta) | Roda comandos no terminal (PowerShell / Bash) |
| `whatsapp_enviar` | **Sempre pergunta** | Envia 1 mensagem com confirmação humana obrigatória |

---

## 📋 Tabela Geral de Comandos

| Comando | Descrição |
|---|---|
| `gargula inicio` | Assistente interativo de configuração no terminal |
| `gargula` | Abre o chat REPL interativo com o agente autônomo |
| `gargula chat "..."` | Executa uma tarefa direta com streaming de resposta |
| `gargula cro` | War Room: stress-test de CRO de página com 3 personas |
| `gargula criativos ganchos` | Gera 10 ganchos de alta retenção em 5 arquétipos |
| `gargula criativos roteiro` | Gera roteiro de anúncio com indicações de cena e B-Roll |
| `gargula criativos pacote` | Pacote completo para o Meta Ads (copys, títulos, descrições e UTMs) |
| `gargula copy` | Variações de copy de resposta direta |
| `gargula oferta` | Estrutura oferta irresistível (mecanismo, bônus, garantia) |
| `gargula funil` | Desenha o funil com métricas-chave por etapa |
| `gargula zap msg` | Gera fluxos e mensagens para WhatsApp |
| `gargula zap objetar` | Sniper de quebra de objeções no 1 a 1 |
| `gargula zap enviar` | Envia 1 mensagem de WhatsApp com trava anti-ban |
| `gargula ads insights` | Tabela detalhada de métricas do Meta Ads |
| `gargula ads diagnostico` | Veredito da IA por campanha (escalar, manter, ajustar, cortar) |
| `gargula ads reconciliar` | Reconciliação financeira: ROAS Real vs ROAS do Meta |
| `gargula dna mostrar\|set\|inicializar` | Gerencia o DNA da marca, oferta, avatar e regras anti-slop |
| `gargula provedores` | Lista as LLMs e o status das credenciais |
| `gargula config` | Gerencia configurações em `~/.gargula/config.json` |

---

## 🔒 Segurança e Trava Anti-Ban

* **Segredos Blindados:** O Gárgula nunca lê `.env`, `.secrets`, arquivos de credenciais ou chaves. O terminal do agente não herda variáveis com segredos.
* **Proteção Anti-Ban no WhatsApp:** O Gárgula se recusa a fazer disparos em massa ou listas frias. Todo envio passa por confirmação humana, exige intervalo mínimo de 60 segundos entre mensagens e avisa imediatamente se houver instabilidade na API.
* **Meta Ads em Modo Estrito de Leitura:** O Gárgula audita e recomenda, mas nunca edita ou desliga campanhas sozinho. Você tem 100% de controle sobre sua conta.

---

## 🛠️ Variáveis de Ambiente

| Variável | Uso |
|---|---|
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` | Chaves de API das LLMs |
| `GARGULA_PROVEDOR`, `GARGULA_MODELO`, `GARGULA_BASE_URL` | Define provedor e modelo padrão |
| `META_ACCESS_TOKEN`, `META_AD_ACCOUNT`, `META_GRAPH_VERSION` | Token com permissão `ads_read` (Meta Ads) |
| `EVOLUTION_URL`, `EVOLUTION_INSTANCIA`, `EVOLUTION_API_KEY` | Evolution API (WhatsApp) |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` | WhatsApp Cloud API Oficial |
| `GARGULA_HOME` | Pasta base de configuração (padrão: `~/.gargula`) |
| `GARGULA_PASTA` | Pasta base das suas notas / vault do Obsidian |
| `NO_COLOR` | Desativa cores ANSI no terminal |

*Dica: Você pode salvar arquivos `.env` e carregá-los automaticamente adicionando caminhos em `gargula config set env_arquivos "C:\cofre\chaves.env"`.*

---

## 🧪 Desenvolvimento e Testes

```bash
git clone https://github.com/wulfizokk/gargula-cli && cd gargula-cli
pip install -e .
python -m unittest discover -s tests -v
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE) para mais detalhes.
