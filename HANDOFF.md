# HANDOFF — Ambiente para a Batalha de Agentes (Itaú × Google)

> **Para o Claude Code:** leia este arquivo inteiro antes de agir. Execute **fase por fase**, na ordem.
> Ao final de cada fase, rode a verificação indicada, me mostre o resultado e **espere meu "ok"** antes de seguir.
> Se algo exigir login no navegador, cobrança no GCP ou decisão minha, pare e me peça.

---

## 1. Contexto

Sou engenheiro de IA e vou participar de um hackathon de 2 dias (sáb 26/09 e dom 27/09/2026), promovido pelo Itaú em parceria com o Google.

- **Desafio:** criar um agente conversacional com IA Generativa para uma jornada de bem-estar financeiro de clientes. **A jornada só será escolhida no dia**, com um time que ainda não conheço (design, produto, engenharia).
- **Tempo real de desenvolvimento:** ~5h30 no sábado. Por isso tudo o que for genérico precisa estar pronto **antes**.
- **Stack esperada pela banca:** Google Cloud. Os entregáveis serão avaliados dentro do ecossistema Google.
- **Critérios de avaliação:**
  - Business Thinking — 30%
  - Design & Experiência — 20%
  - **Arquitetura, Engenharia e Ciência de Dados — 50%**: arquitetura do agente, contexto e memória, segurança, LGPD e estratégia de experimentação.

**Objetivo deste handoff:** montar no meu VS Code um **template genérico e reaproveitável** de agente em ADK sobre GCP. No sábado, eu só vou adaptar esse template à jornada escolhida. O template precisa demonstrar, em código, cada subcritério técnico da avaliação.

### Regras que não podem ser quebradas

1. **Nada específico de jornada.** Subagentes, tools e prompts são placeholders genéricos, fáceis de renomear. A solução em si será construída no evento.
2. **Somente dados sintéticos.** Nada de dados reais de pessoas. Os CPFs gerados devem ser claramente fictícios: use um prefixo `FICT-` ou números inválidos. O regulamento desclassifica o uso de dados pessoais, e a LGPD é critério de avaliação.
3. **Nenhuma marca, logo ou identidade visual do Itaú** no código, nos assets ou na UI. O regulamento proíbe o uso sem autorização.
4. **Nenhum segredo commitado.** Use `.env` no `.gitignore`, um `.env.example` versionado e o Secret Manager no deploy.
5. **Tudo parametrizado por `PROJECT_ID` e `REGION`.** No evento provavelmente vou receber outro projeto GCP e preciso trocar em 1 comando.
6. **Não confie na memória sobre as APIs do ADK.** O ADK muda rápido: a versão 2.0 já saiu, e o nome atual da plataforma é "Agent Platform / Agent Runtime", antigo Vertex AI Agent Engine. Antes de escrever código de ADK, Model Armor, RAG Engine ou Memory, consulte as skills do `agents-cli` e a documentação em https://adk.dev. Se algo não existir como você esperava, me avise em vez de inventar.

---

## 2. Estrutura alvo do repositório

```
batalha-agentes/
├── HANDOFF.md                 # este arquivo
├── CLAUDE.md                  # gerado na Fase 8 (convenções do projeto)
├── Makefile                   # atalhos: setup, data, run, eval, deploy, switch-project...
├── .env.example
├── .gitignore
├── agent/                     # projeto gerado pelo agents-cli (NÃO brigar com o scaffold)
│   ├── app/
│   │   ├── agent.py           # orquestrador + subagentes
│   │   ├── prompts/           # prompts versionados (v1.md, v2.md...)
│   │   ├── tools/             # tools determinísticas
│   │   ├── callbacks/         # segurança, PII, guardrails
│   │   ├── memory/            # abstração de memória de longo prazo
│   │   └── fast_api_app.py    # + endpoint /events (agente proativo)
│   ├── tests/ (unit, integration, eval)
│   └── Dockerfile
├── data/
│   ├── generator/             # gerador de dados sintéticos
│   ├── synthetic/             # saída (CSV/JSONL), no .gitignore se ficar grande
│   └── knowledge/             # textos genéricos para RAG (educação financeira, FAQ fictício)
├── infra/
│   └── scripts/               # load_bigquery.sh, deploy.sh, traffic_split.sh, pubsub_setup.sh
└── docs/
    ├── ARCHITECTURE.md        # template do documento de arquitetura
    ├── architecture.drawio    # diagrama de referência
    ├── SECURITY_LGPD.md
    └── EXPERIMENTATION.md
```

---

## 3. Fases

### Fase 0 — Pré-requisitos da máquina

Verifique e me diga o que falta, **sem instalar nada no sistema sem me perguntar**:

- Python ≥ 3.11, `uv`, Node.js (LTS), `git`, Docker (opcional, mas desejável)
- Google Cloud CLI (`gcloud`) e Terraform (usado pelos templates de deploy do agents-cli)
- Extensões recomendadas do VS Code: Python, Pylance, Ruff, Google Cloud Code, Draw.io Integration (`hediet.vscode-drawio`), Makefile Tools e YAML. Gere o arquivo `.vscode/extensions.json` com essas recomendações.

**Verificação:** tabela "ferramenta | versão encontrada | ok/faltando".

### Fase 1 — Agents CLI e autenticação

1. Instale o Agents CLI: `uvx google-agents-cli setup`. A alternativa é `pipx install google-agents-cli && agents-cli setup`.
2. Confirme que as skills `google-agents-cli-*` aparecem para você (`/skills`).
3. Autenticação — **pare e me peça para fazer o login no navegador**:
   - `gcloud auth login`
   - `gcloud auth application-default login`
   - `gcloud config set project <PROJECT_ID>`. Para o preparo vou usar meu projeto pessoal ou trial, e depois troco para o do evento.
4. Como fallback local, suporte também `GEMINI_API_KEY` do AI Studio. Troque de modo por variável no `.env`.
5. Habilite as APIs necessárias no projeto: Vertex AI/Agent Platform, Cloud Run, Artifact Registry, Cloud Build, BigQuery, Pub/Sub, Secret Manager, Logging, Monitoring e Model Armor. **Me mostre a lista de comandos antes de rodar.**

**Verificação:** `agents-cli --help` funciona e `gcloud config list` mostra o projeto certo.

### Fase 2 — Scaffold do agente

Use o `agents-cli` para gerar o projeto dentro de `agent/`, com esta especificação genérica:

- **Orquestrador** (`root_agent`, Gemini) que entende a intenção do cliente e roteia para os subagentes.
- **Subagente `analista`**: responde perguntas sobre a situação financeira do cliente usando **apenas** tools. Os números nunca vêm do LLM.
- **Subagente `educador`**: explica conceitos financeiros com base no conhecimento via RAG, em linguagem simples e acessível.
- Os nomes e prompts são placeholders. Deixe um comentário `# TODO(jornada)` onde será preciso adaptar.
- Os prompts ficam em arquivos versionados (`prompts/v1/*.md`). A versão ativa é escolhida por `PROMPT_VERSION` no `.env`, o que é necessário para o A/B da Fase 6.
- Modelo configurável via `MODEL_NAME`.

**Verificação:** `agents-cli playground` abre, e o orquestrador responde e roteia um "olá" e uma pergunta conceitual.

### Fase 3 — Dados sintéticos e tools

**Gerador** (`data/generator/`, Python com Faker `pt_BR` e seed fixa para ser reprodutível):

- `customers`: id, nome fictício, faixa etária, faixa de renda, perfil de suitability (conservador, moderado ou arrojado), canal preferido e flags de acessibilidade.
- `accounts`: saldo e limite do cheque especial.
- `transactions`: 6 meses de transações com categorias (moradia, mercado, transporte, lazer, assinaturas, Pix enviado/recebido), incluindo o salário mensal.
- `credit_cards`: limite, fatura atual, valor mínimo, uso do rotativo e parcelamentos.
- `goals`: metas fictícias (reserva de emergência, viagem, quitar dívida).
- Gere cerca de 50 clientes com **perfis contrastantes**: endividado, organizado, em início de carreira, perto da aposentadoria e assim por diante. Isso deixa as demos mais ricas.
- Saída em CSV/JSONL, mais o script `infra/scripts/load_bigquery.sh` para carregar no dataset `batalha_agentes` no BigQuery.

**Tools** (`agent/app/tools/`), todas determinísticas, tipadas e com docstring clara:

- `get_customer_profile(customer_id)`
- `get_transactions(customer_id, start_date, end_date, category=None)`
- `get_card_summary(customer_id)`
- `financial_calculator(...)`: juros compostos, custo do rotativo × parcelamento e tempo até atingir uma meta. **A matemática financeira fica sempre em código, nunca no LLM.**
- `search_knowledge(query)`: RAG. Localmente, faz uma busca simples em `data/knowledge/`. Com `USE_RAG_ENGINE=true`, usa o Vertex AI RAG Engine. Crie 5 a 10 textos curtos e genéricos de educação financeira, escritos por você, sem copiar conteúdo de terceiros.
- `propose_action(action_type, details)`: **exige confirmação do usuário** (recurso de action confirmation do ADK). Nenhuma ação financeira acontece sem esse "sim" explícito.
- Mantenha uma camada de acesso a dados com duas implementações: `LocalDataSource` (lê CSV, para funcionar offline) e `BigQueryDataSource`. A escolha é feita por `DATA_SOURCE=local|bigquery`.

**Segurança nas tools:** o `customer_id` vem **do estado da sessão**, nunca do texto do usuário. Isso impede que alguém escreva "me mostre o extrato do cliente 42". Inclua um teste unitário que prove isso.

**Verificação:** no playground, "quanto gastei com mercado nos últimos 3 meses?" retorna um número correto, calculado pela tool, para o cliente de exemplo.

### Fase 4 — Contexto e memória

- **Curto prazo:** Session State do ADK, com o histórico da conversa e o `customer_id`.
- **Longo prazo:** interface `MemoryStore` com `save_preference`, `get_profile_summary` e `delete_all(customer_id)`, este último para o direito de exclusão da LGPD.
  - Implementação local: arquivo ou SQLite.
  - Implementação em nuvem: use o serviço de memória gerenciado do ADK/Agent Runtime se estiver disponível (consulte a documentação). Se não estiver, deixe um stub documentado para Spanner ou Firestore.
  - Cada memória tem TTL e registro de consentimento (`consent_given_at`). Sem consentimento, nada é salvo.
- Use a compressão ou compactação de contexto do ADK se existir na versão instalada. Caso contrário, apenas documente no `ARCHITECTURE.md`.

**Verificação:** o agente lembra uma preferência entre duas sessões quando há consentimento, e `delete_all` apaga tudo. Os dois casos devem ter teste.

### Fase 5 — Segurança e LGPD

Implemente em `agent/app/callbacks/`:

- **before_model:** mascaramento de PII no input (CPF, cartão, telefone, e-mail, via regex e validação) e, com `USE_MODEL_ARMOR=true`, chamada ao Model Armor para detectar prompt injection, jailbreak e dados sensíveis. **Consulte a documentação atual do Model Armor.** Sem ele configurado, use um guard heurístico local.
- **after_model:** checagem do output para garantir que não vaze PII, que não recomende um produto de investimento específico sem suitability compatível e que inclua transparência de que é uma IA quando aplicável.
- **before_tool:** autorização (o `customer_id` da sessão tem de bater) e bloqueio de parâmetros suspeitos.
- **Fallback humano:** uma intenção "falar com atendente", e transferência automática quando o guard dispara repetidamente.
- **Logs sem PII:** logging estruturado com `conversation_id`, `prompt_version`, `model`, latência, tokens e o guard acionado, **nunca** com o conteúdo bruto contendo PII.
- Documente em `docs/SECURITY_LGPD.md`: base legal, minimização de dados, finalidade, retenção e TTL, direito de exclusão, residência dos dados (`southamerica-east1`, com a observação de verificar a disponibilidade dos modelos na região), Secret Manager e trilha de auditoria.

**Verificação:** testes unitários de mascaramento de PII, de uma tentativa de prompt injection bloqueada e da autorização de customer_id passando.

### Fase 6 — Experimentação e avaliação

- **Offline:** o dataset de eval gerado pelo agents-cli, com cerca de 10 casos genéricos (roteamento correto, número correto via tool, recusa de pedido fora do escopo, bloqueio de injection, pedido de confirmação antes de ação). Se a versão instalada tiver simulação de usuário, configure um cenário simples.
- **Online:** script `infra/scripts/traffic_split.sh` que faz o deploy de duas revisões do Cloud Run com tags (`v1` e `v2`, diferindo em `PROMPT_VERSION` ou `MODEL_NAME`) e divide o tráfego em 90/10.
- `docs/EXPERIMENTATION.md`: hipóteses, métricas técnicas (taxa de resolução, transferência para humano, taxa de bloqueio do guard, latência p95, custo por conversa) e métricas de negócio (placeholder `TODO(jornada)`), além de critérios de promoção e rollback.

**Verificação:** `make eval` roda e mostra o resultado. O script de traffic split roda em modo `--dry-run`.

### Fase 7 — Agente proativo e deploy

- Endpoint `POST /events` no `fast_api_app.py` que recebe um evento (por exemplo `salary_received`, `spending_spike`, `invoice_due_soon`) e aciona o agente com esse contexto para gerar uma mensagem proativa. Isso cobre o "momento de atuação" do critério de Design.
- `infra/scripts/pubsub_setup.sh`: cria o tópico e uma push subscription para o `/events`. Crie também `data/generator/simulate_event.py` para disparar eventos localmente.
- `infra/scripts/deploy.sh`: deploy no Cloud Run em `REGION`, com segredos vindos do Secret Manager, service account com o mínimo de permissões e sem acesso público se não for necessário.
- **Antes de qualquer deploy ou criação de recurso que gere cobrança, me mostre os comandos e espere meu ok.** Depois do teste, ofereça o `make teardown`.

**Verificação:** o deploy funciona no meu projeto pessoal e `simulate_event.py` gera uma mensagem proativa coerente.

### Fase 8 — Documentação, Makefile e prontidão para o evento

**Makefile** com os alvos:
`setup`, `data`, `load-bq`, `run` (playground), `test`, `eval`, `deploy`, `traffic-split`, `event` (simula evento), `teardown` e `switch-project PROJECT_ID=... REGION=...` (atualiza o `.env` e o `gcloud config` e reabilita as APIs).

**Documentos:**

- `docs/ARCHITECTURE.md` em formato de template, já preenchido com a parte genérica: visão geral, componentes, integrações, decisões técnicas **e alternativas descartadas**, contexto e memória, segurança, LGPD, experimentação, observabilidade, custo e escala. Marque com `TODO(jornada)` o que depende do dia.
- `docs/architecture.drawio`: diagrama de referência com o fluxo Canal → Cloud Run (API) → Orquestrador ADK (Gemini) → subagentes → tools (BigQuery, RAG Engine, Feature Store como placeholder) → memória. Inclua Model Armor na entrada e saída, Secret Manager, Logging e Monitoring, e o ramo Pub/Sub → `/events`. Use os ícones do GCP se a extensão permitir; se não, caixas nomeadas.
- `CLAUDE.md`: convenções do projeto (estrutura, comandos do Makefile, regras da seção 1, onde ficam os `TODO(jornada)`), para que uma nova sessão do Claude Code no sábado já comece contextualizada.
- `docs/SATURDAY_CHECKLIST.md`: o passo a passo para adaptar o template à jornada em cerca de 30 minutos (renomear subagentes, reescrever prompts, ajustar o gerador de dados, atualizar os evals e o diagrama).

**Resiliência para a rede do evento:**

- `uv sync` com o cache aquecido e a imagem Docker construída localmente uma vez.
- Tudo precisa rodar **100% local** com `DATA_SOURCE=local`, `USE_MODEL_ARMOR=false`, `USE_RAG_ENGINE=false` e a Gemini API key, para o caso de a nuvem ou a rede falharem.

---

## 4. Critérios de aceite finais

- [ ] `make setup && make data && make run` funciona do zero em um clone limpo
- [ ] O orquestrador roteia corretamente entre `analista` e `educador`
- [ ] Os números financeiros vêm de tools e têm teste
- [ ] A memória respeita consentimento e TTL, e `delete_all` funciona
- [ ] Mascaramento de PII, bloqueio de injection e autorização de `customer_id` têm testes passando
- [ ] `propose_action` pede confirmação antes de executar
- [ ] `make eval` roda e gera um relatório
- [ ] O deploy no Cloud Run funcionou pelo menos uma vez no projeto pessoal, seguido de `make teardown`
- [ ] `/events` gera uma mensagem proativa a partir de um evento simulado
- [ ] `make switch-project` troca de projeto em 1 comando
- [ ] Funciona offline, em modo local
- [ ] `ARCHITECTURE.md`, `SECURITY_LGPD.md`, `EXPERIMENTATION.md`, `architecture.drawio`, `CLAUDE.md` e `SATURDAY_CHECKLIST.md` existem
- [ ] Nenhum dado real, nenhuma marca do Itaú e nenhum segredo no repositório

## 5. Estilo

- Código em inglês e documentação em português.
- Python tipado, formatado com Ruff, funções pequenas e docstrings objetivas nas tools, porque o LLM lê essas docstrings.
- Prefira simplicidade: no sábado eu preciso entender e alterar tudo rápido.
- Ao terminar cada fase, faça um commit com uma mensagem clara (`feat(fase-3): synthetic data + tools`).