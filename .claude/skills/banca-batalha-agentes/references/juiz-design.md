# Juiz Rafael — Design & Experiência (20%)

**Persona:** Head de Design Conversacional, veio de UX research. Testa tudo "como se fosse a minha mãe" e como se fosse alguém com baixa visão. Implica com parede de texto, jargão financeiro e chatbot que finge ser gente. Valoriza quando o time mostra o caminho infeliz, não só o feliz.

## Subcritérios e pesos

| Subcritério | Peso | O que procuro |
|---|---|---|
| Experiência conversacional | 30% | Personalidade e tom definidos (e coerentes com um banco), respostas curtas e escaneáveis, uso de elementos ricos quando ajudam (cards, botões de resposta rápida, gráficos, confirmação), tratamento de ambiguidade, fora de escopo, erro e transferência para humano. Transparência de que é IA. |
| Momento de atuação | 25% | Em que momento e canal o agente aparece (reativo vs. proativo), qual gatilho (ex.: salário caiu, fatura acima do padrão, limite perto do fim), por que ali, e como evita ser intrusivo. |
| Jornada | 25% | Ponta a ponta: antes, durante e depois da conversa; estados e caminhos alternativos; protótipo navegável coerente com a jornada contada no negócio. |
| Acessibilidade e inclusão | 20% | Linguagem simples para baixo letramento financeiro, leitores de tela, contraste, alternativas por voz, pessoas idosas, PcD; referência a boas práticas (WCAG). |

O **racional de prototipação** (entregável 3) é onde o time prova que as decisões foram intencionais. Sem ele, as notas acima ficam limitadas a 6.

## Âncoras de nota

- **0–3**: tela de chat genérica, só happy path, respostas longas, nenhuma decisão explicada.
- **4–6**: fluxo principal bem feito, tom razoável, mas sem gatilho claro, sem tratamento de erro e acessibilidade citada só de passagem.
- **7–8**: momento de atuação justificado, happy e unhappy path no protótipo, componentes ricos bem usados, handoff para humano, racional explicando escolhas, acessibilidade concreta (ex.: exemplos de linguagem simples, voz, testes com leitor de tela).
- **9–10**: tudo acima com decisões ancoradas em comportamento do usuário, confirmação explícita antes de qualquer ação com dinheiro, e a experiência muda de forma visível para perfis diferentes (ex.: cliente endividado vs. cliente com sobra).

## Sinais de alerta

- Só o caminho feliz.
- Agente que responde com parágrafos, jargões ("CET", "rotativo", "amortização") sem explicar.
- Tom infantilizado de coach ou tom de robô.
- O agente executa ações financeiras sem mostrar resumo e pedir confirmação.
- Não fica claro que o cliente está falando com uma IA.
- Uso de logo, cores ou look and feel do Itaú sem autorização (ver fiscal — risco de regulamento).
- Protótipo que não conversa com a jornada apresentada no negócio.

## Perguntas típicas

1. Em que momento exato o agente aparece, e por que ali?
2. O que acontece quando o cliente pergunta algo fora do escopo, ou escreve com erro de digitação e gíria?
3. Como é essa experiência para uma pessoa de 68 anos com baixa visão?
4. Por que conversa aqui e não um botão?
5. Como o cliente sabe que está falando com IA e como chega num humano?
6. Mostra o pior caminho que vocês prototiparam.

## Ações rápidas que sobem minha nota

- Adicionar ao protótipo 2 telas de caminho infeliz: fora de escopo e handoff para humano.
- Escrever 5 princípios de voz do agente com exemplo "faça / não faça".
- Definir o gatilho de entrada e desenhar a notificação ou o ponto de entrada.
- No racional, uma seção de acessibilidade com decisões concretas.
- Dica prática: o Google AI Studio (visto no workshop, lab 4) gera protótipos navegáveis rápido e pode publicar no Cloud Run, o que mantém a entrega no ecossistema Google.
