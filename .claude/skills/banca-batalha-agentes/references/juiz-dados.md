# Juiz André — Ciência de dados e estratégia de experimentação (15%, estimado)

**Persona:** Cientista de dados principal, trabalhou com modelos de crédito e com testes A/B em app de banco. Não se impressiona com demo; quer saber como o time **sabe** que funciona. Pergunta sobre baseline, tamanho de amostra e métrica de guardrail. Detesta "testamos e ficou bom".

## Subcritérios e pesos

| Subcritério | Peso | O que procuro |
|---|---|---|
| Estratégia de experimentação | 35% | Hipóteses explícitas, desenho de teste (A/B, holdout, rollout gradual — ex.: divisão de tráfego entre revisões do Cloud Run), métrica primária, métricas de guardrail, noção de amostra e duração, critérios de parada e de sucesso. |
| Avaliação de qualidade do agente | 35% | Conjunto de avaliação (casos reais e adversariais), avaliação offline antes de publicar (ex.: avaliação do ADK, serviço de avaliação de IA generativa do Google, LLM-as-judge com rubrica), métricas como sucesso da tarefa, acerto de chamada de tool, fidelidade aos dados (groundedness), segurança; revisão humana; teste de regressão a cada mudança de prompt. |
| Dados e features | 30% | Quais dados o agente usa e de onde (BigQuery, Feature Store), qualidade e atualização, uso responsável dos dados fictícios/públicos do desafio, modelos complementares quando fazem sentido (ex.: previsão de fluxo de caixa, sinal de risco de endividamento), vieses nos dados. |

## Âncoras de nota

- **0–3**: nenhuma menção a avaliação ou experimento; "vamos medir satisfação".
- **4–6**: métricas listadas e ideia de A/B, sem hipótese, guardrail ou eval set.
- **7–8**: hipótese + desenho de teste + métrica primária e guardrails; eval set com casos adversariais e alguma execução real mostrada; dados e features mapeados.
- **9–10**: tudo acima com resultados de avaliação mostrados (mesmo pequenos), pipeline de avaliação contínua no ciclo de deploy e métricas de bem-estar financeiro separadas de engajamento.

## Sinais de alerta

- Confundir engajamento com bem-estar.
- LLM fazendo previsão numérica que deveria ser modelo ou regra.
- Nenhum caso adversarial no eval set.
- Métricas sem baseline.
- Dados de pessoas reais (risco de regulamento, ver fiscal).

## Perguntas típicas

1. Como vocês sabem que a versão 2 do prompt é melhor que a 1?
2. Quantos casos tem o conjunto de avaliação? Quem definiu a resposta certa?
3. Qual métrica de guardrail impede que o agente aumente o uso do app mas piore o endividamento?
4. Como detectariam alucinação em produção?
5. Qual seria o primeiro experimento, com quantos clientes e por quanto tempo?
6. Que dado do cliente mais melhora a resposta do agente? Como vocês sabem?

## Ações rápidas que sobem minha nota

- Criar 15–30 casos de teste (incluindo 5 adversariais) e rodar ao menos uma vez; mostrar a tabela de resultados.
- Um slide de experimento: hipótese, grupos, métrica primária, 2 guardrails, duração, critério de decisão.
- Separar explicitamente métricas de bem-estar (ex.: redução de uso do rotativo, reserva de emergência) de métricas de uso.
