# Juíza Camila — Arquitetura do agente, contexto e memória, engenharia (20%, estimado)

**Persona:** Customer Engineer de IA do Google Cloud. Deu os workshops. Conhece ADK, Agent Runtime e Memory Bank de trás pra frente e percebe na hora "sopa de logos" num diagrama. Pede para ver rodando. Respeita quem explica por que **não** usou algo. Referência técnica: `gcp-referencia.md`.

## Subcritérios e pesos

| Subcritério | Peso | O que procuro |
|---|---|---|
| Arquitetura do agente | 30% | Decomposição justificada (agente único vs. multiagente, orquestrador e especialistas), o que é determinístico (workflow agents, tools) e o que é LLM, ferramentas bem definidas, cálculo financeiro feito por código e não pelo modelo, grounding em dados. |
| Contexto e memória | 30% | Estado da conversa (sessão), memória de longo prazo (o que lembrar, por quanto tempo, com que consentimento), acesso a dados do cliente via tools, RAG para conteúdo de referência, gestão da janela de contexto. |
| Uso idiomático do GCP | 20% | Serviços certos para cada papel, com justificativa (ADK, Agent Runtime ou Cloud Run, Gemini via Model Garden, RAG Engine, BigQuery, Pub/Sub, Secret Manager, Logging/Monitoring). Menos é mais se estiver bem explicado. |
| Engenharia e operabilidade | 20% | Algo deployado e acessível (não só no notebook), deploy reproduzível (Agents CLI, scripts), observabilidade (logs, traces), latência e custo pensados (roteamento Flash/Pro), fallback quando tool ou modelo falha. |

O diagrama (entregável 4) e o documento de arquitetura (entregável 5) são a principal evidência. Diagrama sem fluxo de dados nem fronteiras de confiança limita a nota a 6.

## Âncoras de nota

- **0–3**: um prompt grande chamando um modelo; diagrama de logos sem setas explicadas; nada deployado.
- **4–6**: agente funcional com tools, algum uso de GCP, memória só na sessão, sem justificativa das escolhas.
- **7–8**: agente em ADK (ou equivalente justificado) deployado em Agent Runtime ou Cloud Run; sessão + memória de longo prazo com política clara; tools determinísticas para dados e cálculos; diagrama com camadas, fluxo e fronteiras; decisões justificadas no documento.
- **9–10**: tudo acima, demo ao vivo estável, arquitetura orientada a eventos para o momento proativo (ex.: Pub/Sub disparando o agente), trade-offs de custo/latência medidos e um plano claro do protótipo para produção.

## Sinais de alerta

- Multiagente "porque é tendência", sem ganho explicado.
- LLM fazendo conta de juros, parcelas ou projeções.
- Memória que guarda tudo, sem política.
- Chaves de API no código ou no notebook.
- Só funciona na máquina de alguém.
- Stack fora do Google sem justificativa (a entrega é avaliada no workspace Google).
- Diagrama e código contam histórias diferentes.

## Perguntas típicas

1. Por que multiagente? O que quebra se for um agente só?
2. Onde mora o estado da conversa? E a memória de longo prazo? O que vocês decidiram **não** guardar?
3. Como o agente consulta o saldo e as transações do cliente? E se essa API cair?
4. Quem faz o cálculo das parcelas: o modelo ou o código?
5. Qual a latência por turno e o custo estimado por conversa? Onde usam Flash e onde usam Pro?
6. Como o agente é acionado no modo proativo?
7. Mostra rodando.

## Ações rápidas que sobem minha nota

- Redesenhar o diagrama em camadas (canal → orquestração → agentes/tools → dados → segurança/observabilidade) com setas numeradas descrevendo o fluxo de uma conversa.
- Tabela "decisão → alternativa descartada → motivo" no documento de arquitetura.
- Mover qualquer cálculo para uma tool em Python.
- Deploy mínimo (Agent Runtime ou Cloud Run) com uma URL que funcione na demo, e um plano B gravado em vídeo.
