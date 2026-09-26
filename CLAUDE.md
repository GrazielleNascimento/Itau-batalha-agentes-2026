# Convenções do projeto

> Contexto para uma sessão nova de agente de código. Leia antes de alterar qualquer coisa.
> As convenções do scaffold do `agents-cli` ficam em `agent/CLAUDE.md` e continuam valendo.

---

## O que é este repositório

Template genérico de agente conversacional em **ADK 2.8** sobre **GCP**, para um hackathon
de bem-estar financeiro. **Não é a solução** — é o andaime que será adaptado à jornada
no dia do evento.

Leitura na primeira vez, nesta ordem: `docs/BLUEPRINT.md` (o quadro completo), depois
`docs/SATURDAY_CHECKLIST.md` (o que fazer no evento).

---

## Regras que não podem ser quebradas

1. **Nada específico de jornada** fora dos pontos marcados. Use `grep -rn "TODO(jornada)"`.
2. **Somente dados sintéticos.** Identificadores com prefixo `FICT-`. Nenhum dado real de
   pessoa, em nenhuma circunstância.
3. **Nenhuma marca, logo ou identidade visual do Itaú** em código, assets, prompts ou UI.
4. **Nenhum segredo commitado.** `.env` é ignorado; `.env.example` é versionado sem valores.
5. **Tudo parametrizado** por `PROJECT_ID` e `REGION`.
6. **Não confie na memória sobre as APIs do ADK.** Ele muda rápido. Verifique na versão
   instalada (`agent/.venv`) antes de escrever código. Se algo não existir como esperado,
   diga em vez de inventar.

---

## Invariantes de desenho

Quebrar qualquer um destes invalida o argumento técnico do projeto. Há teste para todos.

| Invariante | Onde vive |
|---|---|
| **Número nunca vem do LLM.** Toda cifra vem de tool determinística | `app/tools/finance.py`, `app/tools/customer.py` |
| **`customer_id` nunca é parâmetro de tool.** Vem de `tool_context.state` | `app/tools/customer.py` |
| **Tool nunca devolve CPF ou nome completo.** Projeção num ponto só | `app/datasources/projections.py` |
| **Guardrail é transversal.** Plugin no `App`, não callback por agente | `app/plugins/security_plugin.py` |
| **Consentimento é porta.** Sem ele, não grava | `app/memory/local.py` |
| **Ação financeira exige confirmação** | `app/tools/actions.py` |
| **Log nunca tem conteúdo de conversa** | `app/plugins/audit_plugin.py` |

---

## Estrutura

```
agent/app/
  agent.py         orquestrador + subagentes + App(plugins)
  config.py        ÚNICO ponto de leitura de env
  session_setup.py semeadura de identidade em modo demo
  prompts/v1/      prompts versionados, escolhidos por PROMPT_VERSION
  tools/           tools determinísticas e tipadas
  callbacks/       funções puras de guarda, SEM dependência de ADK
  plugins/         aplicam as funções puras a todos os agentes
  datasources/     Protocol + implementação local + projeções
  memory/          Protocol + SQLite
data/
  generator/       gerador sintético, seed fixa
  knowledge/       textos de educação financeira
infra/scripts/     switch_project, deploy, teardown, smoke
docs/              blueprint, arquitetura, LGPD, experimentação, checklist
```

---

## Comandos

| Comando | O que faz |
|---|---|
| `make setup` | venv 3.12 + dependências + `.env` |
| `make data` | gera os dados sintéticos |
| `make test` | 145 testes, **sem credencial nenhuma** |
| `make test-llm` | inclui os que chamam o modelo |
| `make lint` | ruff check + format |
| `make run` | playground local |
| `make switch-project PROJECT_ID=x [REGION=y] [MODE=vertex\|local]` | troca projeto, região e modo |
| `make deploy PROJECT_ID=x [DRY_RUN=1]` | deploy no Cloud Run |
| `make smoke BASE_URL=x [TOKEN=y]` | 13 verificações contra agente vivo |
| `make teardown PROJECT_ID=x [DRY_RUN=1]` | apaga o que o deploy criou |

---

## Estilo

- **Código e identificadores em inglês; comentários, docstrings e documentação em
  português.** Os prompts também são em português — é a língua do cliente.
- Python tipado, formatado com Ruff (`line-length = 88`).
- Funções pequenas, arquivos de responsabilidade única.
- **Docstring de tool é interface, não decoração.** O modelo escolhe tool lendo docstring.
  Descreva o que ela faz, os argumentos e o que devolve, em linguagem direta.
- Comentário explica **por que**, não o que. Se explicar o que, apague.

---

## Ao escrever uma tool nova

1. Não receba `customer_id`. Leia de `tool_context.state`.
2. Não devolva PII. Projete os campos em `datasources/projections.py`.
3. Docstring clara, com `Args:` e `Returns:`.
4. Registre no subagente certo em `app/agent.py`. **Os guardrails são herdados
   automaticamente** — não plugue nada.
5. Se mudar algo, use `FunctionTool(..., require_confirmation=True)`.

---

## Ao escrever um teste

**Use os objetos reais do ADK como dublê, não `dict`.** O `State` do ADK não tem `pop()`
nem `__delitem__`; um `dict` tem. Essa divergência já deixou um bug chegar à produção que
145 testes não pegaram.

```python
from google.adk.sessions.state import State
ctx = SimpleNamespace(state=State(value={"customer_id": "FICT-0001"}, delta={}))
```

Teste que precisa de modelo leva `pytest.mark.llm` — `make test` os exclui, e o critério de
"funciona sem credencial" depende disso.

---

## Armadilhas conhecidas

| Sintoma | Causa |
|---|---|
| Modelo dá 404 | `GOOGLE_CLOUD_LOCATION`, não o nome do modelo. Deixe `global` |
| 429 `generate_content_free_tier_requests` | Está no AI Studio, não no Vertex — ou o projeto dono da chave não tem billing |
| `storage.objects.get denied` em `run-sources-*` | SA padrão do Compute sem papel de build. O `deploy.sh` concede |
| `ALREADY_EXISTS` no deploy | Dois deploys simultâneos |
| Teste lê CSV e falha | `conftest.py` gera em `tmp`; rode `make data` se persistir |
| Porta 8000 ocupada nos testes e2e | Eles escolhem porta livre; `E2E_PORT` força |

**`REGION` e `GOOGLE_CLOUD_LOCATION` são variáveis diferentes.** A primeira é onde o Cloud
Run roda; a segunda é onde o modelo roda. Nunca derive uma da outra.

---

## Três features experimentais do ADK 2.8 em uso

`require_confirmation`, `EventsCompactionConfig` e `JSON_SCHEMA_FOR_FUNC_DECL`. Funcionam e
têm teste, mas podem mudar sem aviso. A mais sensível é a confirmação de ação.

---

## O que não existe

`BigQueryDataSource`, RAG Engine, Model Armor, endpoint `/events` com Pub/Sub,
`traffic_split.sh`, `make eval`. As costuras (`Protocol` + fábrica + flags) estão prontas
para recebê-los.
