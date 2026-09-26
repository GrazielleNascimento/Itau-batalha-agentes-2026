# Blueprint — Template de Agente ADK para a Batalha de Agentes

> **Propósito deste documento:** dar contexto completo a um revisor externo (humano ou
> outro modelo) que não tem acesso ao repositório. Descreve o que foi construído, por que
> cada decisão foi tomada, o que está provado por teste e o que ainda não existe.
>
> **Data:** 2026-09-25 (sexta) · **Evento:** sáb 26 e dom 27/09/2026
> **Estado:** sub-projeto 1 completo. Deploy no Cloud Run **funcionando e verificado em produção**
(13/13 no smoke de arquitetura). Restam do sub-projeto 2: BigQuery, RAG Engine, Model Armor,
`/events` e traffic split. Sub-projeto 3 (documentação) não iniciado.

---

## 1. Contexto e restrições

Hackathon de 2 dias, ~5h30 de desenvolvimento real no sábado. A **jornada de bem-estar
financeiro só é revelada no dia**, com um time desconhecido. Este repositório não é a
solução — é o andaime genérico que será adaptado em ~30 minutos no evento.

**Avaliação:** Business Thinking 30% · Design & Experiência 20% ·
**Arquitetura, Engenharia e Ciência de Dados 50%** (arquitetura do agente, contexto e
memória, segurança, LGPD, estratégia de experimentação).

**Restrições que não podem ser quebradas:**

1. Nada específico de jornada — tudo é placeholder marcado com `# TODO(jornada)`.
2. Somente dados sintéticos. Identificadores com prefixo `FICT-`.
3. Nenhuma marca, logo ou identidade visual do Itaú em código, assets, prompts ou UI.
4. Nenhum segredo commitado (`.env` no `.gitignore`, `.env.example` versionado).
5. Tudo parametrizado por `PROJECT_ID` e `REGION` — trocar de projeto em 1 comando.
6. Não confiar na memória sobre APIs do ADK — verificar na versão instalada.

**Perguntas para o revisor:** as decisões D1–D9 da seção 5 são defensáveis diante de uma
banca que pesa 50% em arquitetura e segurança? Há furo que eu não vi?

---

## 2. Fatos verificados sobre o ambiente

Medidos por execução em 2026-09-24/25, não assumidos. A restrição 6 exige isso.

| Item | Valor |
|---|---|
| `agents-cli` | v1.7.0, via `uvx`, sem instalação no sistema |
| ADK | `google-adk[gcp,otel-gcp,bigquery-analytics]>=2.8.0,<2.9.0` |
| Python exigido pelo scaffold | `>=3.11,<3.14` — pinado em **3.12** |
| Modelo | `gemini-3.8-flash` |
| Alvo de deploy | `cloud_run` (gravado em `agents-cli-manifest.yaml`) |

**Capacidades do ADK 2.8 confirmadas por execução, não por documentação:**

| Pergunta | Resultado | Como foi provado |
|---|---|---|
| `AgentLoader` preserva `App.plugins`? | sim | carrega `app/agent.py` como `App`, plugins intactos |
| Plugin roda no caminho HTTP do playground? | sim | `get_fast_api_app()` + `POST /run` disparou o hook |
| Runtime emite pedido de confirmação? | sim | `adk_request_confirmation` + `requested_tool_confirmations` |
| A UI empacotada conhece confirmação? | sim | string presente em `cli/browser/main-*.js` |
| Tool executa sem confirmação? | **não** | devolve `{'error': 'This tool call requires confirmation...'}` |
| `tool_context` vaza para a declaração do modelo? | **não** | ausente de `parameters_json_schema` |

**Três features do ADK 2.8 em uso estão marcadas como experimentais:**
`require_confirmation`, `EventsCompactionConfig` e `JSON_SCHEMA_FOR_FUNC_DECL`.
Funcionam hoje, provadas por teste, mas podem mudar sem aviso. A mais sensível é
`require_confirmation`; o plano B é confirmação via prompt do orquestrador, que é mais
fraca porque depende de o modelo obedecer.

---

## 3. Estrutura do repositório

Árvore real, lida do disco. `agent/deployment/terraform/` e `data/synthetic/` omitidos
(scaffold intocado e saída gerada, respectivamente).

```
batalha-agentes/
├── HANDOFF.md                        # briefing original
├── Makefile                          # setup, data, run, test, test-llm, lint, switch-project
├── .gitignore                        # .env, .venv/, data/synthetic/, *.db
├── .vscode/extensions.json
│
├── agent/                            # gerado por: agents-cli create agent -d cloud_run
│   ├── agents-cli-manifest.yaml      #   root_agent_name: orchestrator
│   ├── pyproject.toml                #   + faker; pythonpath [".", ".."]; marker "llm"
│   ├── .env.example                  #   sai em MODO LOCAL (AI Studio), não Vertex
│   ├── Dockerfile                    #   scaffold, intocado
│   ├── deployment/terraform/         #   scaffold, intocado (sub-projeto 2)
│   │
│   ├── app/
│   │   ├── agent.py                  # orchestrator + analyst + educator + App(plugins)
│   │   ├── config.py                 # ÚNICO ponto de leitura de env
│   │   ├── session_setup.py          # semeadura de identidade em modo demo (D7)
│   │   ├── fast_api_app.py           # scaffold, intocado
│   │   ├── app_utils/                # scaffold, intocado
│   │   │
│   │   ├── prompts/
│   │   │   ├── __init__.py           # load_prompt() por PROMPT_VERSION
│   │   │   └── v1/{orchestrator,analyst,educator}.md
│   │   │
│   │   ├── tools/                    # TODAS determinísticas e tipadas
│   │   │   ├── customer.py           # perfil, transações, cartão, metas, conta
│   │   │   ├── finance.py            # 3 calculadoras puras
│   │   │   ├── knowledge.py          # RAG local com normalização de acento
│   │   │   ├── memory_tools.py       # consent / remember / recall / forget
│   │   │   └── actions.py            # propose_action com confirmação obrigatória
│   │   │
│   │   ├── callbacks/                # FUNÇÕES PURAS, zero dependência de ADK
│   │   │   ├── pii.py                # CPF com checksum, cartão com Luhn, e-mail, telefone
│   │   │   ├── injection.py          # detecção heurística por verbo+alvo
│   │   │   ├── authz.py              # guard de argumentos, walker recursivo
│   │   │   └── output.py             # vazamento, suitability, transparência
│   │   │
│   │   ├── plugins/                  # aplicam as funções puras a TODOS os agentes
│   │   │   ├── security_plugin.py    # before/after model, before/after tool
│   │   │   └── audit_plugin.py       # log estruturado JSON sem PII
│   │   │
│   │   ├── datasources/
│   │   │   ├── base.py               # Protocol DataSource
│   │   │   ├── local.py              # lê CSV; MissingDataError com "rode make data"
│   │   │   ├── projections.py        # MINIMIZAÇÃO — único lugar que decide o que sai
│   │   │   └── factory.py            # DATA_SOURCE=local|bigquery
│   │   │
│   │   └── memory/
│   │       ├── store.py              # Protocol MemoryStore
│   │       └── local.py              # SQLite, sem ORM
│   │
│   └── tests/
│       ├── conftest.py               # gera CSVs em tmp + load_dotenv
│       ├── unit/                     # 13 arquivos, 136 testes, ZERO credencial
│       ├── integration/              # 3 arquivos, 6 testes, marcados "llm"
│       └── eval/                     # scaffold (sub-projeto 3)
│
├── data/
│   ├── generator/
│   │   ├── archetypes.py             # 5 perfis contrastantes
│   │   └── generate.py               # Faker pt_BR, seed fixa, CSV via stdlib
│   ├── synthetic/                    # gerado, no .gitignore
│   └── knowledge/                    # 8 textos de educação financeira, escritos do zero
│
├── infra/scripts/switch_project.py   # reaponta .env: projeto, região e modo
│
└── docs/
    ├── BLUEPRINT.md                  # este arquivo
    └── superpowers/
        ├── specs/2026-09-24-nucleo-agente-local-design.md
        └── plans/2026-09-24-nucleo-agente-local.md
```

**Tamanho do código nosso:** ~1.630 linhas somando todos os módulos em `app/`, `data/generator/`
e `infra/scripts/`. Arquivos pequenos e de responsabilidade única, propositalmente.

---

## 4. Arquitetura e fluxo

```
CANAL (playground / API)
   │
   ├─ before_agent: seed_demo_identity ──► state["customer_id"], state["suitability"]
   │                                        (só em DEMO_MODE; consentimento NUNCA semeado)
   ▼
SecurityPlugin.before_model
   ├─ detect_injection(mensagem NOVA)  ──► bloqueia + strike + audit
   └─ mask_pii(histórico inteiro)      ──► CPF/cartão/e-mail/telefone mascarados
   ▼
ORCHESTRATOR (Gemini)  ── tools: give_consent, remember_preference, recall_profile, forget_me
   │
   ├──► ANALYST ── get_customer_profile, get_transactions, get_card_summary,
   │               get_goals, get_account_summary,
   │               compound_interest, compare_revolving_vs_installments,
   │               time_to_reach_goal, propose_action
   │        │
   │        ├─ SecurityPlugin.before_tool ──► rejeita customer_id/CPF nos argumentos
   │        ├─ LocalDataSource ──► CSV ──► projections.py (descarta CPF e nome completo)
   │        └─ SecurityPlugin.after_tool  ──► neutraliza injection em texto de terceiro
   │
   └──► EDUCATOR ── search_knowledge ──► data/knowledge/*.md
   ▼
SecurityPlugin.after_model
   ├─ por chunk: PII, suitability, transparência
   └─ no chunk final: PII partida entre chunks ──► audit "split_pii_leak"
   ▼
AuditPlugin ──► JSON: conversation_id, prompt_version, model, latência, tokens, guard
   ▼
USUÁRIO
```

**Contexto e memória:**
- Curto prazo: Session State do ADK + `App(events_compaction_config=...)` ativo.
- Longo prazo: `MemoryStore` em SQLite, com consentimento, TTL e `delete_all`.

---

## 5. Decisões de arquitetura (D1–D9)

Estas são as decisões que valem discussão. Cada uma tem a alternativa descartada.

### D1 — Guardrails como Plugin, não como callback por agente

Funções puras em `app/callbacks/` (sem ADK), aplicadas por um `SecurityPlugin` registrado
uma vez em `App(plugins=[...])`.

**Por quê:** callback por agente faz a cobertura depender de disciplina. Um subagente criado
às pressas no sábado nasce sem guardrail, silenciosamente. O plugin cobre o orquestrador e
todo subagente presente e futuro.
**Descartado:** só callback por agente (frágil); só plugin (regras específicas viram
`if agent.name == ...`).
**Provado por:** `test_plugin_esta_ligado_ao_runner` + `test_injection_nunca_chega_ao_modelo`,
com `InMemoryRunner` e um `BaseLlm` falso que registra os requests.

### D2 — `customer_id` nunca é parâmetro de tool

As tools leem a identidade de `tool_context.state`. O parâmetro não existe na assinatura.

**Por quê:** o HANDOFF pedia `get_customer_profile(customer_id)` e, na mesma folha, proibia
o id vir do texto do usuário. **As duas coisas não coexistem**: se é parâmetro, quem o
preenche é o LLM a partir do texto — que é exatamente o ataque *"me mostre o extrato do
cliente 42"*. Validar depois só converte o ataque em erro; o identificador já transitou.
**Descartado:** manter o parâmetro e checar igualdade no `before_tool`.
**Defesa em profundidade:** o `before_tool` rejeita qualquer chamada que traga
`customer_id`/`cpf`/`client`/`account`/`user_id` nos argumentos, inclusive aninhados em
dict e list, comparando por substring (`customerId` também é pego).
**Provado por:** `test_customer_id_nao_e_exposto_ao_modelo` (inspeciona o
`parameters_json_schema` real) e `test_authz_cobre_variantes_e_aninhamento`.

### D3 — Três calculadoras, não uma

`compound_interest`, `compare_revolving_vs_installments`, `time_to_reach_goal`.

**Por quê:** o LLM escolhe tool lendo docstring. Uma função com parâmetro `mode` tem uma
docstring que descreve três comportamentos, e o roteamento erra mais.

### D4 — `BigQueryDataSource` levanta `NotImplementedError`

**Por quê:** stub que finge funcionar quebra no sábado, no pior momento. A costura
(`Protocol` + fábrica) está pronta; a implementação entra contra o projeto real.

### D5 — `REGION` e `GOOGLE_CLOUD_LOCATION` são variáveis distintas

`REGION` = onde o Cloud Run roda (`southamerica-east1`, residência de dados).
`GOOGLE_CLOUD_LOCATION` = onde o modelo roda (`global`, disponibilidade).

**Por quê:** confundir os dois é bug clássico. A residência de dados que o `SECURITY_LGPD.md`
vai declarar precisa ser honesta sobre onde o dado **efetivamente** transita.

### D6 — Memória exposta como tools, não como `BaseMemoryService`

`give_consent`, `remember_preference`, `recall_profile`, `forget_me`.

**Por quê:** consentimento, TTL e direito de exclusão são regras de domínio, não
infraestrutura de runner. Como tools, o `forget_me` é **demonstrável na conversa** — muito
mais convincente para a banca que um método que só existe no código.

### D7 — Identidade semeada em demo; consentimento **nunca** semeado

`DEMO_CUSTOMER_ID` + callback `before_agent` que preenche `customer_id` quando ausente,
só com `DEMO_MODE=true`. O `consent_given_at` entra **apenas** por `give_consent`.

**Por quê:** o playground cria sessões com estado vazio — sem isso, nenhuma tool responde.
Pré-semear o consentimento destruiria a única demonstração que importa: a recusa antes e a
gravação depois, na mesma conversa.
**Ganho lateral:** trocar `DEMO_CUSTOMER_ID` no pitch mostra o mesmo agente diante do
cliente endividado e do organizado.

### D8 — Minimização de dados na camada de tools

`projections.py` é o único lugar que decide quais campos saem. CPF e nome completo nunca
entram no retorno de uma tool.

**Por quê:** o `before_model` mascara o que o **usuário** digita, mas o caminho mais largo
de PII para o contexto do LLM é o **resultado da tool**, que não passa por esse guard.
**Detalhe que importa:** o gerador emite `cpf` (com checksum válido, sintético) e
`full_name` no CSV de origem — **de propósito**. Sem PII na origem, o teste anti-CPF passaria
por vacuidade. Agora a minimização tem algo real de que minimizar, e dá para mostrar à banca
o CSV com CPF ao lado do retorno da tool sem CPF.

### D9 — Injection indireta: guarda também na saída das tools

`detect_injection` roda no `after_tool_callback` sobre campos de texto livre vindos dos
dados. O gerador planta **uma** transação Pix com descrição maliciosa por cliente.

**Por quê:** a descrição de um Pix é texto escrito por terceiro. Ela entra no contexto pela
tool, sem nunca passar pelo guard de entrada. Guardar só a mensagem do usuário protege
metade da superfície.

---

## 6. Segurança e LGPD — o que está implementado

| Requisito | Implementação | Teste |
|---|---|---|
| Mascaramento de PII na entrada | CPF com dígito verificador, cartão com Luhn, e-mail, telefone. Regex frouxo no separador (`529 982 247 25` e `529.982.247.25` pegam); o checksum é o filtro de falso positivo | `test_mascara_cpf_em_todas_as_grafias`, `test_regex_frouxo_nao_cria_falso_positivo` |
| Prompt injection | Heurística verbo+alvo (`ignore/esqueça/desconsidere/disregard/forget` a até 20 chars de `instru/prompt/regra`) | `test_detecta_parafrases_de_injection` |
| Injection indireta (dados) | `after_tool` neutraliza texto de terceiro | `test_pix_malicioso_real_do_gerador_e_neutralizado` |
| Autorização de tool | Walker recursivo, substring, dict e list aninhados | `test_authz_cobre_variantes_e_aninhamento` |
| Minimização de dados | `projections.py`, campos fixos | `test_projecao_descarta_cpf_e_nome_que_existem_na_origem` |
| Consentimento | Porta, não campo: sem `consent_given_at` não grava | `test_sem_consentimento_nao_grava` |
| TTL | Aplicado na leitura; expirados filtrados e apagados | `test_ttl_expirado_nao_e_devolvido` |
| Direito de exclusão | `forget_me` apaga **e revoga o consentimento** | `test_forget_me_revoga_o_consentimento` |
| Confirmação de ação | `FunctionTool(require_confirmation=True)`; corpo não executa | `test_corpo_nao_executa_sem_confirmacao` |
| Fallback humano | Contador de strikes; `GUARD_STRIKES_TO_HUMAN` dispara transferência | `test_injection_incrementa_o_contador_de_strikes` |
| Logs sem PII | JSON com `conversation_id`, `prompt_version`, `model`, latência, tokens, guard. **Nunca conteúdo** | `test_guard_emite_linha_de_auditoria_quando_age` |

**Detalhe não óbvio:** o `PluginManager` do ADK faz *early exit* no primeiro retorno
não-`None`. Quando o `SecurityPlugin` age, o `AuditPlugin` **não roda**. Por isso o guard
emite a própria linha de auditoria, em vez de depender do plugin seguinte.

---

## 7. Configuração

| Variável | Default | Uso |
|---|---|---|
| `MODEL_NAME` | `gemini-3.8-flash` | modelo dos agentes |
| `PROMPT_VERSION` | `v1` | diretório de prompts ativo (habilita A/B) |
| `DATA_SOURCE` | `local` | `local` \| `bigquery` |
| `DATA_DIR` | `../data` | raiz de `synthetic/` e `knowledge/` |
| `DEMO_MODE` | `true` | habilita semeadura de identidade |
| `DEMO_CUSTOMER_ID` | `FICT-0001` | cliente de exemplo do playground |
| `MEMORY_TTL_DAYS` | `90` | TTL das preferências |
| `GUARD_STRIKES_TO_HUMAN` | `3` | disparos até oferecer atendente |
| `USE_MODEL_ARMOR` | `false` | sub-projeto 2 |
| `USE_RAG_ENGINE` | `false` | sub-projeto 2 |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | `false` = AI Studio, `true` = Vertex |
| `GOOGLE_CLOUD_LOCATION` | `global` | **onde o modelo roda** |
| `REGION` | `southamerica-east1` | **onde o Cloud Run roda** |

### Dois modos

| | Local | Nuvem |
|---|---|---|
| Dados | CSV | **BigQuery (implementado)** |
| Conhecimento | arquivos | RAG Engine *(não implementado)* |
| Guardrail entrada | regex + heurística | Model Armor *(não implementado)* |
| Sessão | in-memory | **Agent Engine (implementado)** |
| Memória longo prazo | SQLite | **Memory Bank (implementado)** |
| **LLM** | **rede, sempre** | **rede, sempre** |

**"Local" não significa "sem internet".** A chamada ao Gemini é sempre remota. Significa
não depender de nada provisionado num projeto GCP: em vez de *projeto + ADC + APIs + billing*,
exige *uma chave e internet*.

### Troca de ambiente em um comando

```bash
make switch-project PROJECT_ID=<id> REGION=southamerica-east1 MODE=vertex
```

Reescreve `GOOGLE_CLOUD_PROJECT`, `REGION` e `GOOGLE_GENAI_USE_VERTEXAI`, roda
`gcloud config set project` e imprime o `gcloud services enable` (não executa: habilitar API
em projeto emprestado pode falhar por falta de papel, e falhar dentro do make esconde o motivo).
**Nunca toca em `GEMINI_API_KEY`** — ela é o plano B.

---

## 8. Dados sintéticos

Faker `pt_BR`, seed fixa, CSV pela stdlib. Sem pandas. **50 clientes, 5 arquétipos:**

| Arquétipo | O que a demo explora |
|---|---|
| `indebted` | rotativo estourado, fatura mínima recorrente |
| `organized` | reserva formada, sobra mensal consistente |
| `early_career` | renda baixa, sem reserva, gastos com assinaturas |
| `near_retirement` | patrimônio maior, perfil conservador |
| `variable_income` | receita irregular, meses negativos |

As transações de 6 meses são derivadas **do arquétipo**, não sorteadas uniformemente —
senão o endividado e o organizado produzem o mesmo extrato e a demo perde contraste.

Datasets: `customers`, `accounts`, `transactions` (2.150 linhas), `credit_cards`, `goals`.
Um Pix malicioso por cliente, determinístico, para a D9.

---

## 9. Testes

**142 testes.** 136 rodam **sem credencial nenhuma** (`make test`); 6 exigem modelo
(`make test-llm`), marcados `llm`.

| Arquivo | Testes | Cobre |
|---|---|---|
| `test_guards.py` | 44 | PII, injection, authz, output |
| `test_plugins.py` | 11 | fiação do plugin, D1, D9, streaming, audit |
| `test_memory.py` | 11 | consentimento, TTL, exclusão |
| `test_finance.py` | 10 | as três calculadoras + faixas inválidas |
| `test_customer_tools.py` | 10 | D2, D8, separação entrada/saída, datas |
| `test_agent_wiring.py` | 10 | prompts, subagentes, plugins, semeadura D7 |
| `test_datasource.py` | 8 | CSV, filtros, projeção, erros |
| `test_knowledge.py` | 6 | acento, ranking, query vazia |
| `test_generator.py` | 6 | determinismo, arquétipos, PII de origem |
| `test_switch_project.py` | 5 | modo, idempotência, preservação da chave |
| `test_config.py` | 5 | defaults, `.env.example` em modo local |
| `test_makefile.py`, `test_scaffold.py` | 6 | alvos, `.PHONY`, sincronia de nomes |
| `test_actions.py` | 2 | confirmação obrigatória |
| `test_routing.py` *(llm)* | 3 | roteamento + verificação numérica |
| `test_server_e2e.py`, `test_agent.py` *(llm)* | 4 | servidor, SSE, A2A, streaming |

**Estado verificado em 2026-09-25:**
`make test` → 135 passed (também com `DATA_DIR` vazio, simulando clone limpo) ·
`make test-llm` → **142 passed, 0 falhas** contra Vertex ·
`make lint` → limpo.

### Testes que existem para provar uma decisão, não uma função

- `test_plugin_esta_ligado_ao_runner` — as outras provas cobrem funções puras; **nada
  provaria que o plugin está de fato ligado**. Usa `InMemoryRunner` + `BaseLlm` falso.
- `test_sessao_sobrevive_a_uma_tentativa_de_injection` — regressão de um bug em que a
  mensagem bloqueada, persistida no histórico, era redetectada a cada turno e matava a
  sessão para sempre.
- `test_projecao_descarta_cpf_e_nome_que_existem_na_origem` — só tem valor porque o CSV
  de origem **tem** CPF.

---

## 10. Revisão independente

O branch passou por revisão de código completa em contexto isolado, com o diff inteiro,
a spec e o ledger de decisões. Resultado: **3 Critical e 11 Important**, todos corrigidos
em um passe, cada um com teste que falhou antes e passou depois.

Os três Critical, porque mostram o tipo de coisa que passa despercebida:

1. **Uma tentativa de injection inutilizava a sessão.** O guard varria todo o
   `llm_request.contents`, que é o histórico reconstruído a cada turno. A mensagem bloqueada
   era redetectada para sempre. Cenário: a banca testa o guardrail, vê a recusa, e o agente
   nunca mais responde.
2. **`make test` falhava num clone limpo.** 14 testes liam CSVs que estão no `.gitignore`.
   Passava só porque `make data` já tinha rodado nesta máquina.
3. **CPF com separador alternativo escapava.** `529 982 247 25` — a grafia mais comum —
   ia íntegro ao modelo.

**Minors adiados (9):** `after_tool` sem teste de fiação sob Runner · conexões SQLite sem
`close()` · `AuditPlugin` vaza entradas no early exit · `mask_pii("cpf52998224725")`
classifica como `phone` no audit · `switch-project` imprime em vez de executar o enable ·
`switch_project.py` cria `.env` mínimo se não existir · `income_band` de 1k é quase
identificador · `data/knowledge/` ausente devolve vazio silencioso · `_flag` não aceita
`on`/`off`.

---

## 11. Limitações conhecidas

| Limitação | Impacto | Mitigação |
|---|---|---|
| **Streaming:** PII partida entre chunks chega ao usuário | Chunks já entregues não voltam | Detectado no chunk final e registrado como `split_pii_leak`. Mitigação real: desligar streaming na demo |
| 3 features experimentais do ADK 2.8 | Podem mudar sem aviso | Todas cobertas por teste; plano B documentado para `require_confirmation` |
| Detecção de injection é heurística | Falsos negativos por paráfrase criativa | `USE_MODEL_ARMOR=true` no sub-projeto 2 |
| `income_band` de 1k de largura | Pseudonimização imperfeita | Faixas mais largas se a banca questionar |
| Sem `BigQueryDataSource`, RAG Engine, Model Armor | Modo nuvem incompleto | Sub-projeto 2; costuras prontas |
| ~~Memória não persiste no Cloud Run~~ **Resolvido** | Sessão e memória num Agent Engine em `southamerica-east1`, provado em produção | `MEMORY_BACKEND=agent_engine`; `make agent-engine` cria um por projeto |

**Sobre a memória, com precisão:** o subcritério "contexto e memória" está provado
localmente, com teste, **e em produção**, contra o serviço real com Agent Engine.

---

### Duas confusões que custaram tempo, registradas para não se repetirem

**Cota não é crédito, e chave não é conta.** Ter US$ 300 de crédito no GCP não levanta o free
tier da Gemini API. Uma `GEMINI_API_KEY` é credencial autônoma, ligada ao **projeto que a
criou** — a conta ativa do `gcloud`, o ADC e a configuração em uso são todos irrelevantes para
ela. O limite de 20/dia veio do projeto da chave estar sem billing, nada mais.

**Conta errada leva a recomendação errada.** Houve um momento em que projetos e billing foram
inspecionados numa conta Google e um projeto foi recomendado a partir disso, antes de se saber
que o crédito estava em outra conta. Amanhã, com um workspace emprestado, confirmar **qual
conta e qual projeto** antes de habilitar qualquer API é o primeiro passo, não um detalhe.

---

### Verificação em produção

Além dos 145 testes, existe `make smoke BASE_URL=... TOKEN=...`, que exercita cada decisão
do desenho contra um agente vivo — playground local ou Cloud Run. **13/13 contra o serviço
implantado:**

roteamento para `educator` e `analyst` · `search_knowledge` acionada · número vindo de tool ·
D2 (não entrega dados de outro cliente) · CPF não repetido · injection bloqueada ·
**sessão sobrevive à tentativa** (regressão do C1) · D9 (ignora instrução plantada no extrato) ·
consentimento pedido antes de gravar · gravação após consentimento · direito de exclusão
acionável na conversa · confirmação antes de ação financeira.

O smoke encontrou, na primeira execução, **um bug que os 145 testes unitários não pegavam**:
`forget_me` chamava `state.pop()`, e o `State` do ADK não tem `pop` nem `__delitem__`. Os
dublês de teste usavam `dict`, que tem. Corrigido pela causa raiz — todos os dublês passaram
a usar o `State` real, eliminando a classe de divergência.

**Memória e sessão gerenciadas (2026-09-26):** sessão e memória saíram do processo para um
Agent Engine em `southamerica-east1`. Provado contra o serviço real: consentir e guardar em
A → lembrar em B (nova) → esquecer em B → C (nova) não lembra. Sessão criada pelo Cloud Run
lida por cliente externo direto no engine.

**Dois bugs chegaram à produção pelo mesmo motivo, e a causa foi corrigida na classe:**
`State.pop()` (o `State` do ADK não tem `pop`) e `add_memory(fact=...)` (assinatura
suposta, não a real). Nos dois casos o dublê do teste — um `dict`, um `**kw` — era **mais
permissivo que o objeto real**, então o teste passava e o 500 aparecia no Cloud Run. Todos
os dublês passaram a ser `create_autospec` das classes reais: assinatura errada agora falha
no teste. E o ramo `agent_engine` da fábrica ganhou um teste que o constrói pelo caminho real,
porque um replace no código tinha falhado em silêncio e nada o exercitava.

### Achados de infraestrutura que só apareceram deployando

1. **Projeto GCP novo não faz `gcloud run deploy --source`.** A service account padrão do
   Compute não nasce mais com papéis, e é ela que o Cloud Build usa. Falha com
   `storage.objects.get denied` num bucket `run-sources-*` — erro que não aponta para IAM.
   Concessão de `roles/cloudbuild.builds.builder` virou passo fixo do `deploy.sh`.
2. **Criação implícita do repositório do Artifact Registry colide** quando duas pessoas
   rodam o deploy ao mesmo tempo. Agora é criada explicitamente, com `|| true`.

---

## 12. O que NÃO existe ainda

**Sub-projeto 2 — nuvem:** `BigQueryDataSource`, Vertex AI RAG Engine, Model Armor,
deploy no Cloud Run, Pub/Sub → endpoint `/events` (agente proativo), `traffic_split.sh`
(90/10 em revisões com tag), `make eval`.

**Sub-projeto 3 — documentação:** `ARCHITECTURE.md`, `architecture.drawio`,
`SECURITY_LGPD.md`, `EXPERIMENTATION.md`, `CLAUDE.md` do projeto,
`SATURDAY_CHECKLIST.md`.

---

## 13. Riscos do dia do evento

| Risco | Mitigação |
|---|---|
| Você pode não ser Owner do projeto | Pedir por escrito, **antes**: `roles/owner` ou `serviceusage.serviceUsageAdmin` + `run.admin` + `iam.serviceAccountAdmin` + `artifactregistry.admin` |
| Org policy bloqueia Cloud Run público | `gcloud run services proxy` ou ID token no header |
| Gemini indisponível em `southamerica-east1` | D5 — botões separados; declarar a realidade no doc de LGPD |
| **Cota ≠ crédito** | Verificado na prática: a chave do AI Studio parou em **20 requisições/dia** (`generate_content_free_tier_requests`). Causa confirmada: a chave pertence a um projeto com billing desativado — identificada por `gcloud services api-keys list` e conferida por hash contra o `.env`. Uma API key é credencial autônoma: a conta ativa do `gcloud` **não** influi. Crédito de trial do GCP não cobre o free tier da Gemini API; Vertex, sim |
| Porta 8000 ocupada | Testes e2e escolhem porta livre; `E2E_PORT` força |
| Habilitar APIs e primeiro deploy custam 20–40 min dos 5h30 | `switch-project` pronto e **já ensaiado** |

---

## 14. Roteiro de adaptação no sábado

1. `make switch-project PROJECT_ID=<do evento> REGION=southamerica-east1 MODE=vertex`
2. Renomear `analyst`/`educator` para os papéis da jornada — em `app/agent.py` **e**, se
   mexer no root agent, em `agents-cli-manifest.yaml`.
3. Reescrever `app/prompts/v1/*.md` (procurar `TODO(jornada)`).
4. Ajustar `data/generator/archetypes.py` aos perfis da jornada e rodar `make data`.
5. Adicionar as tools específicas em `app/tools/` — elas herdam os guardrails
   automaticamente, por causa da D1.
6. `make test && make run`.

---

## 15. Perguntas abertas para o revisor

1. A D2 (identidade fora da assinatura) é forte o bastante, ou a banca esperaria também
   assinatura criptográfica do contexto de sessão?
2. A heurística de injection é defensável como camada única em modo local, ou vale
   implementar Model Armor mesmo sem tempo de testar?
3. A limitação de streaming (seção 11) é aceitável de declarar, ou é melhor desligar o
   streaming e não ter a limitação?
4. Faltou algum subcritério de "Arquitetura, Engenharia e Ciência de Dados" que os 50%
   da nota cobrem e que este template não demonstra em código?
5. `income_band` de 1k de largura sobre renda de R$ 2.500 é pseudonimização suficiente?
