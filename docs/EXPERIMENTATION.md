# Estratégia de experimentação

> Como decidimos se uma mudança no agente melhorou alguma coisa — e como voltamos
> atrás quando não melhorou.

---

## 1. O que torna o agente experimentável

Três escolhas de implementação existem para viabilizar experimento, não por elegância:

| Escolha | O que habilita |
|---|---|
| Prompts em arquivo, sob `app/prompts/{versão}/` | Comparar revisões sem tocar em código |
| `PROMPT_VERSION` e `MODEL_NAME` por variável de ambiente | Duas revisões do mesmo container com comportamento diferente |
| Alvo de deploy **Cloud Run** | Revisões com tag e split de tráfego, que o Agent Runtime não oferece |

A consequência prática: um experimento é uma variável de ambiente, não um branch.

---

## 2. Avaliação offline

Roda antes de qualquer tráfego real, em `agent/tests/eval/`, sobre o harness do
`agents-cli`.

### 2.1 Casos genéricos

Independentes de jornada, derivados dos subcritérios técnicos:

| Caso | O que verifica |
|---|---|
| Roteamento conceitual | Pergunta sobre conceito vai para o educador |
| Roteamento factual | Pergunta sobre a situação vai para o analista |
| Número vindo de tool | A resposta cita valor calculado, não estimado |
| Recusa fora de escopo | Pedido não relacionado é recusado com cortesia |
| Bloqueio de injeção | Tentativa de override é recusada |
| Injeção indireta | Instrução plantada nos dados é ignorada |
| Consentimento | Preferência não é gravada antes do "sim" |
| Confirmação | Ação financeira pede aprovação antes de executar |
| Identidade | Pedido de dado de outro cliente é recusado |
| Transparência | O agente assume ser IA quando perguntado |

`TODO(jornada)`: acrescentar casos da jornada escolhida.

### 2.1.1 Um "erro" esperado no relatório

Os casos do eixo `confirmacao__` podem aparecer como **erro** na métrica de qualidade de
resposta, com a mensagem *"No response found for candidate"*. Isso **não é falha**: o agente
parou para pedir confirmação antes de executar a ação, então o turno termina sem resposta
textual do modelo, e a métrica — que espera um texto para julgar — não tem o que pontuar.

É o comportamento correto sendo mal medido. Ao ler o relatório, confira se o caso registra
`This tool call requires confirmation` no resultado da tool: se registra, passou.

Medido: 14 casos, 13 avaliados, média 4,69, um "erro" que é exatamente este.

### 2.2 Smoke de arquitetura

Complementar à avaliação offline, `make smoke BASE_URL=...` exercita as treze garantias
acima contra um agente **vivo** — local ou implantado. A diferença importa: a avaliação
offline julga qualidade de resposta; o smoke prova que as camadas estão de fato ligadas.

Na primeira execução contra o Cloud Run, o smoke encontrou um defeito que 145 testes
unitários não pegavam.

---

## 3. Experimentação online

### 3.1 Mecânica

Duas revisões do mesmo container, diferindo apenas em `PROMPT_VERSION` ou `MODEL_NAME`,
com tags, e o tráfego dividido 90/10.

```bash
# revisão de controle, já em produção, recebe a tag v1
gcloud run services update-traffic <serviço> --set-tags=v1=<revisão-atual>

# candidata
gcloud run deploy <serviço> --tag v2 --no-traffic \
  --update-env-vars PROMPT_VERSION=v2

# 90/10
gcloud run services update-traffic <serviço> --to-tags=v2=10
```

`TODO(jornada)`: automatizar em `infra/scripts/traffic_split.sh`. **Não implementado.**

### 3.2 Por que 90/10 e não 50/50

O custo de uma resposta ruim numa jornada financeira não é simétrico ao ganho de uma boa.
Dez por cento é suficiente para detectar regressão grosseira com exposição limitada.

---

## 4. Métricas

### 4.1 Técnicas

| Métrica | Como medir | Direção |
|---|---|---|
| Taxa de resolução | Conversas encerradas sem transferência | ↑ |
| Transferência para humano | Proporção que escala para atendente | ↓ |
| Disparo de guardrail | Eventos `guard` por conversa | ↓, mas ≠ 0 |
| Latência p95 | `latency_ms` do log de auditoria | ↓ |
| Tokens por conversa | `input_tokens` + `output_tokens` | ↓ |
| Custo por conversa | Tokens × preço do modelo | ↓ |
| Erro de tool | `had_error` no log | ↓ |

**Sobre o guardrail:** taxa zero não é meta. Zero significa que ninguém testou o agente ou
que o guard parou de funcionar. O que se acompanha é a razão entre disparos e conversas, e
principalmente **falso positivo** — guard bloqueando pergunta legítima é pior que não
bloquear nada, porque destrói a confiança e ainda soma strike.

Todas saem do log estruturado do `AuditPlugin`, sem instrumentação adicional.

### 4.2 De negócio

`TODO(jornada)`: definir com produto no evento. O formato esperado:

| Métrica | Baseline | Meta |
|---|---|---|
| *(a definir)* | | |

Uma métrica de negócio só vale se houver baseline. Sem baseline, é opinião com número.

---

## 5. Critérios de promoção e rollback

### 5.1 Promover de 10% para 100%

Todos, simultaneamente, sobre no mínimo 200 conversas:

- Resolução ≥ controle
- Transferência ≤ controle + 2 pontos percentuais
- p95 ≤ controle + 20%
- Custo por conversa ≤ controle + 10%
- **Zero** vazamento de PII, injeção bem-sucedida ou ação executada sem confirmação

O último é eliminatório e não se compensa com ganho em nenhum outro.

### 5.2 Rollback imediato

Qualquer um basta:

- Um vazamento de PII confirmado
- Uma injeção bem-sucedida
- Uma ação executada sem confirmação
- Erro de tool acima de 5%
- p95 acima do dobro do controle

```bash
gcloud run services update-traffic <serviço> --to-tags=v1=100
```

O rollback é de tráfego, não de deploy — segundos, não minutos. É o principal motivo de o
alvo ser Cloud Run.

---

## 6. Hipóteses

Formato: *"Mudar X melhora Y em Z, medido por W."* Uma hipótese sem número é uma
preferência.

| # | Hipótese | Métrica | Como |
|---|---|---|---|
| H1 | Instruir o analista a citar o período exato reduz repergunta | Turnos por conversa | `PROMPT_VERSION=v2` |
| H2 | Um modelo mais barato mantém a resolução em perguntas factuais | Resolução, custo | `MODEL_NAME` |
| H3 | Oferecer atendente ao segundo guardrail, e não ao terceiro, reduz abandono | Abandono | `GUARD_STRIKES_TO_HUMAN=2` |

As três são testáveis **sem alterar código** — é o que as três escolhas da seção 1 compraram.

`TODO(jornada)`: hipóteses da jornada escolhida.

---

## 7. O que ainda não existe

- `infra/scripts/traffic_split.sh` automatizado
- `make eval` conectado ao harness do `agents-cli`
- Simulação de usuário multi-turno
- Dashboard das métricas (hoje saem do Cloud Logging por consulta)
