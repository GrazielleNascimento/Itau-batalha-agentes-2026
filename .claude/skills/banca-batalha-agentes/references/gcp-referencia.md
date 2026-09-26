# Referência GCP para avaliar (e construir) a solução

Baseado nos workshops do evento (22/09 e 23/09) e na documentação pública do Google em set/2026. O Google renomeou vários produtos: o que era **Vertex AI** agora é **Gemini Enterprise Agent Platform** ("Agent Platform"); **Agent Engine** virou **Agent Runtime**. Aceite qualquer um dos nomes; os mentores do Google no evento são a fonte final.

## Mapa necessidade → serviço

| Necessidade do agente | Serviço GCP (nome atual / antigo) | Observação para a banca |
|---|---|---|
| Framework do agente, multiagente, tools | **ADK** (Agent Development Kit) | Código-first, suporta agentes LLM e workflow agents (sequencial, paralelo, loop). |
| Scaffold, teste e deploy | **Agents CLI** (adk.dev) | Deploy reproduzível conta ponto em engenharia. |
| Protótipo low-code do agente | **Agent Studio** (antigo Agent Builder) | Aceitável para prototipar; exporta para ADK. |
| Hospedar o agente | **Agent Runtime** (antigo Agent Engine) ou **Cloud Run** | Runtime gerenciado com sessões e memória integradas; Cloud Run dá mais controle e divisão de tráfego. |
| Estado da conversa | **Agent Sessions** | Memória de curto prazo, por conversa. |
| Memória de longo prazo | **Memory Bank** | Precisa de política: o que guardar, consentimento, esquecimento. |
| Modelos | **Model Garden** (Gemini Pro/Flash e outros) | Roteamento: Flash para turnos simples, Pro para raciocínio. Confirmar versões no projeto. |
| Conhecimento de referência (produtos, regras, educação financeira) | **RAG Engine** | Grounding com citação da fonte reduz alucinação. |
| Features de personalização | **Feature Store** | Ex.: renda média, padrão de gasto, comprometimento de renda. |
| Dados analíticos e transacionais | **BigQuery**, **BigQuery Graph**, **Cloud Spanner** | BigQuery para histórico e análise; Spanner para dado operacional consistente; Graph para relações (ex.: contas, dependentes, recorrências). |
| Arquivos e documentos | **Cloud Storage** | Base do RAG, artefatos. |
| Gatilho proativo / eventos | **Pub/Sub** | Ex.: evento "salário creditado" ou "fatura fechada" aciona o agente. |
| Experimentação | **Cloud Run — revisões e divisão de tráfego** | A/B e rollout gradual entre versões do agente. |
| Proteção de prompt e resposta | **Model Armor** | Filtra injeção, conteúdo nocivo e vazamento de dados na entrada e na saída. |
| Segredos | **Secret Manager** | Nada de chave em código. |
| Mascaramento de dados pessoais | **Sensitive Data Protection** (antigo Cloud DLP) | Não citado no workshop, mas é o encaixe natural para LGPD em logs e prompts. |
| Observabilidade | **Cloud Logging**, **Cloud Monitoring** (+ Cloud Trace) | Trilha de auditoria, latência, erros, custo. |
| Postura de segurança | **Security Command Center** | Visão de riscos do projeto. |
| Ambiente de desenvolvimento | **Cloud Shell**, **gcloud** | Útil se algum notebook do time der problema. |
| Protótipo navegável de UI | **Google AI Studio** (Build) | Visto no lab 4 do workshop; publica em Cloud Run. |

## Arquitetura de referência (o que uma nota 8+ costuma ter)

```
[Canal: app/protótipo]──►[Model Armor: entrada]
                              │
                              ▼
                 [Orquestrador ADK em Agent Runtime/Cloud Run]
                  │  sessão (Agent Sessions) + memória (Memory Bank, com consentimento)
                  ├─► Agente especialista A ──► tools determinísticas (cálculos em código)
                  ├─► Agente especialista B ──► RAG Engine (conteúdo de referência, com citação)
                  └─► tools de dados ──► BigQuery / Spanner / Feature Store (IAM mínimo)
                              │
                              ▼
                     [Model Armor: saída]──►[Canal]

[Pub/Sub: eventos da conta]──► aciona o orquestrador (modo proativo)
[Secret Manager]  [Sensitive Data Protection nos logs]  [Logging/Monitoring/Trace]  [região southamerica-east1]
[Avaliação offline + Cloud Run traffic split para A/B]
```

Não é obrigatório usar tudo. Um time que usa 6 serviços com propósito claro supera um que lista 15 sem explicar.

## Anti-padrões que a banca penaliza

- "Sopa de logos": ícones sem setas numeradas nem descrição do fluxo.
- Tudo num prompt gigante, sem tools.
- Multiagente sem ganho explicado.
- Model Armor ou LGPD citados sem posição no fluxo.
- Nada deployado ou só rodando localmente.
- Stack principal fora do Google sem justificativa.
