# Arquitetura

> Documento vivo. A parte genérica está preenchida; o que depende da jornada
> está marcado com `TODO(jornada)` e deve ser completado no evento.

---

## 1. Visão geral

Agente conversacional de bem-estar financeiro construído sobre o **Google Agent
Development Kit (ADK) 2.8**, implantado no **Cloud Run**, com modelos **Gemini** servidos
pelo Vertex AI.

O desenho separa três responsabilidades que costumam se misturar em protótipos de agente:

- **Raciocínio** fica no LLM (orquestração, linguagem, explicação).
- **Fatos e cálculo** ficam em tools determinísticas. O modelo nunca produz número.
- **Política** (segurança, LGPD, autorização) fica numa camada transversal que o modelo
  não pode contornar.

`TODO(jornada)`: descrever a jornada escolhida, o público e o momento de atuação.

---

## 2. Componentes

| Componente | Responsabilidade | Onde |
|---|---|---|
| `orchestrator` | Entende a intenção e roteia. Responde saudações e conversa geral | `app/agent.py` |
| `analyst` | Situação financeira concreta, **apenas** via tools | `app/agent.py` |
| `educator` | Conceitos financeiros, com base no conhecimento recuperado | `app/agent.py` |
| `SecurityPlugin` | Guardrails de entrada, de tool e de saída | `app/plugins/` |
| `AuditPlugin` | Log estruturado sem PII | `app/plugins/` |
| `DataSource` | Contrato de acesso a dados | `app/datasources/` |
| `MemoryStore` | Memória de longo prazo com consentimento e TTL | `app/memory/` |
| Tools | Dados, cálculo, conhecimento, memória, ação | `app/tools/` |
| Prompts | Versionados em arquivo, selecionados por `PROMPT_VERSION` | `app/prompts/` |
| `POST /events` | Agente proativo: evento externo dispara mensagem | `app/events.py`, `app/fast_api_app.py` |

`TODO(jornada)`: renomear `analyst` e `educator` para os papéis da jornada.

---

## 3. Fluxo de uma mensagem

```
CANAL
  │
  ├─ before_agent ─────► semeia customer_id no estado (só em modo demo;
  │                       em produção vem do canal autenticado)
  ▼
SecurityPlugin.before_model
  ├─ detecta injection na mensagem NOVA ──► bloqueia, soma strike, audita
  └─ mascara PII em todo o histórico
  ▼
ORCHESTRATOR (Gemini)
  │
  ├──► ANALYST
  │      ├─ before_tool ──► rejeita identificador nos argumentos
  │      ├─ tool ────────► DataSource ──► projeção mínima
  │      └─ after_tool ──► neutraliza injection vinda dos dados
  │
  ├──► EDUCATOR ──► search_knowledge
  │
  └──► tools de memória ──► MemoryStore
  ▼
SecurityPlugin.after_model ──► PII, suitability, transparência
  ▼
AuditPlugin ──► JSON sem conteúdo
  ▼
CANAL
```

Diagrama visual: `docs/architecture.drawio`.

---

## 4. Decisões técnicas e alternativas descartadas

### 4.1 Guardrails como Plugin, não como callback por agente

**Escolhido:** funções puras em `app/callbacks/` (sem dependência de ADK), aplicadas por um
`SecurityPlugin` registrado uma vez em `App(plugins=[...])`.

**Descartado — callback por agente:** faz a cobertura depender de disciplina. Um subagente
criado sob pressão nasce sem guardrail, silenciosamente.

**Descartado — só plugin, sem funções puras:** regras específicas de um agente virariam
`if agent.name == ...` dentro do plugin.

**Consequência:** tool nova herda os guardrails automaticamente.

### 4.2 Identidade fora da assinatura da tool

**Escolhido:** as tools leem `customer_id` de `tool_context.state`. O parâmetro não existe.

**Descartado — `customer_id` como parâmetro, validado depois:** se é parâmetro, quem o
preenche é o modelo, a partir do texto do usuário. Validar depois converte o ataque em erro,
mas o identificador já transitou pelo prompt.

**Defesa em profundidade:** o `before_tool` rejeita `customer_id`, `cpf`, `client`,
`account` e `user_id` nos argumentos, inclusive aninhados.

### 4.3 Três calculadoras, não uma

**Escolhido:** `compound_interest`, `compare_revolving_vs_installments`, `time_to_reach_goal`.

**Descartado — uma função com parâmetro `mode`:** o modelo escolhe tool lendo docstring, e
uma docstring que descreve três comportamentos roteia pior.

### 4.4 Região do serviço separada da location do modelo

**Escolhido:** `REGION` (Cloud Run, `southamerica-east1`) e `GOOGLE_CLOUD_LOCATION`
(modelo, `global`) como variáveis independentes.

**Descartado — uma variável só:** a disponibilidade de Gemini em `southamerica-east1` é
limitada, e igualar as duas produz 404 de modelo.

### 4.5 Memória como regra de domínio, não como serviço de runner

**Escolhido:** `MemoryStore` como protocolo, exposto ao agente por tools
(`give_consent`, `remember_preference`, `recall_profile`, `forget_me`).

**Descartado — usar apenas o memory service do ADK:** consentimento, TTL e direito de
exclusão são regras de negócio. Como tools, o direito de exclusão é acionável pelo próprio
cliente na conversa.

### 4.6 Sem stub para BigQuery — e, agora, BigQuery de verdade

**Escolhido originalmente:** `NotImplementedError` com mensagem clara, em vez de um stub que
devolve dados falsos e quebra no pior momento.

**Superada em 2026-09-25:** `BigQueryDataSource` foi implementada e está em uso. A decisão
valeu enquanto durou — a fábrica nunca mentiu sobre o que existia — e a troca custou apenas
uma classe nova, porque `DataSource` é protocolo.

**Toda consulta é parametrizada.** Concatenar o `customer_id` no texto do SQL recriaria por
outra via o buraco que a decisão 4.2 fechou no prompt: um identificador com aspas viraria
injeção. Há teste que passa `FICT-0001' OR '1'='1` e verifica que não aparece na query.

**A minimização vale igual nas duas fontes.** `cpf` e `full_name` existem nas tabelas do
BigQuery, e `projections.py` os descarta antes de qualquer dado chegar ao modelo — o mesmo
código, para as duas origens.

### 4.7 Identidade do evento vem do sistema, não do texto

**Escolhido:** o `POST /events` recebe `customer_id` do chamador e o grava no **estado da
sessão**; o texto enviado ao modelo descreve apenas o evento.

**Por que não contradiz a decisão 4.2:** um evento vem de push subscription autenticada por
OIDC — chamador de sistema, não usuário. O que a 4.2 proíbe é o identificador ser extraído
de texto conversacional e chegar ao contexto do modelo. Aqui ele nunca chega: há teste que
inspeciona o `LlmRequest` real e falha se o id aparecer.

Campos de texto livre do evento passam pelo mesmo guard de injeção aplicado aos dados.

---

## 5. Contexto e memória

**Curto prazo.** Session State do ADK guarda `customer_id`, `suitability`,
`consent_given_at` e o contador de guardrails. A compactação de eventos
(`EventsCompactionConfig`, `compaction_interval=10`, `overlap_size=3`) mantém o contexto
sob controle em conversas longas, preservando sobreposição entre janelas.

**Longo prazo.** `MemoryStore` guarda preferências com três campos de governança:
`created_at`, `expires_at` e `consent_given_at`. O consentimento é uma porta: sem ele, a
gravação é recusada. O TTL é aplicado na leitura — linhas expiradas são filtradas e
apagadas.

**Em produção: Agent Engine, em `southamerica-east1`.** O `InMemorySessionService` do
scaffold é um dicionário no processo — com mais de uma instância, o turno 2 de uma conversa
pode chegar onde a sessão não existe. Em produção a sessão vai para o `VertexAiSessionService`
e a memória para o `VertexAiMemoryBankService`, ambos num Agent Engine criado só para isso
(`make agent-engine`); o agente continua servindo pelo Cloud Run.

**Verificado:** uma sessão criada pelo serviço no Cloud Run é lida por um cliente externo
direto no Agent Engine — ela não vive mais no container. E a memória de longo prazo, contra
o serviço real: consentir e guardar numa sessão, lembrar numa sessão nova, esquecer, e uma
terceira sessão nova não lembra mais. Consentimento, persistência entre sessões e exclusão,
os três provados em produção.

**Por que São Paulo, e não a região do modelo:** a sessão persiste o texto **bruto** do
usuário (o mascaramento age no `LlmRequest`, não no evento gravado). Sessão e memória ficam
no Brasil; só a inferência sai, em `global` — a mesma separação da decisão 4.4.

**Localmente** continua SQLite (`MEMORY_BACKEND=local`, o padrão), porque é o modo que roda
sem projeto GCP. O backend gerenciado sem `GOOGLE_CLOUD_AGENT_ENGINE_ID` **falha alto** em
vez de cair no SQLite em silêncio.

---

## 6. Segurança

Detalhamento em `docs/SECURITY_LGPD.md`. Resumo das camadas:

| Camada | O que faz |
|---|---|
| Entrada | Mascara CPF (com dígito verificador), cartão (Luhn), e-mail e telefone; detecta injection |
| Tool (antes) | Rejeita identificador vindo nos argumentos |
| Tool (depois) | Neutraliza instrução plantada em texto de terceiro |
| Saída | Vazamento de PII, produto incompatível com suitability, transparência de IA |
| Auditoria | JSON com metadados, nunca conteúdo |
| Escalonamento | Contador de disparos; ao atingir o limite, oferece atendente humano |

---

## 7. Experimentação

Detalhamento em `docs/EXPERIMENTATION.md`. Os prompts são versionados em arquivo e
selecionados por `PROMPT_VERSION`, o que permite comparar revisões sem alterar código. O
alvo de deploy é Cloud Run justamente para viabilizar split de tráfego entre revisões com
tag.

---

## 8. Observabilidade

- **Log estruturado** em JSON, com `conversation_id`, `prompt_version`, `model`, latência,
  contagem de tokens e qual guardrail foi acionado.
- **Nunca o conteúdo da conversa.** Um log com PII é um vazamento com carimbo de data.
- O `SecurityPlugin` emite a própria linha de auditoria quando age, porque o
  `PluginManager` do ADK interrompe a cadeia no primeiro plugin que retorna algo — sem
  isso, os eventos de segurança ficariam invisíveis.

`TODO(jornada)`: definir alertas e SLOs.

---

## 9. Custo e escala

- Cloud Run com `min-instances=0`: sem tráfego, não há cobrança.
- `max-instances=3` no preparo; ajustar conforme a carga esperada.
- O custo dominante é a inferência. A compactação de contexto reduz tokens por turno.
- Tools determinísticas são mais baratas e mais confiáveis que pedir cálculo ao modelo.

`TODO(jornada)`: estimar custo por conversa com o volume esperado.

---

## 10. Verificação

| Nível | Comando | Cobertura |
|---|---|---|
| Unitário | `make test` | 145 testes, **sem credencial** |
| Integração | `make test-llm` | roteamento e resposta numérica contra o modelo |
| Arquitetura | `make smoke BASE_URL=...` | 13 verificações contra um agente vivo |

O smoke de arquitetura exercita cada decisão deste documento contra o serviço implantado.
Foi ele que encontrou um defeito que os testes unitários não pegavam.
