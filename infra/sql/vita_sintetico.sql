DECLARE persona_id STRING DEFAULT '2fad9515-3c09-4400-8269-d83fd4e2c063';
DECLARE ref_anomes INT64 DEFAULT (
  SELECT MAX(anomes) FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`);

DECLARE teto_ce FLOAT64 DEFAULT 0.08;
DECLARE taxa_rotativo FLOAT64 DEFAULT 0.14;
DECLARE pagamento_minimo FLOAT64 DEFAULT 0.15;
DECLARE guardrail_atencao FLOAT64 DEFAULT 0.35;
DECLARE guardrail_vulneravel FLOAT64 DEFAULT 0.50;

CREATE SCHEMA IF NOT EXISTS `batalha-time-06-1t82.vita_sintetico`
  OPTIONS (location = 'us-central1');

CREATE TEMP FUNCTION u(id STRING, sal STRING) AS (
  ABS(MOD(FARM_FINGERPRINT(CONCAT(id, ':', sal)), 1000000)) / 1000000.0
);

CREATE TEMP TABLE mensal AS
SELECT
  id_usuario,
  anomes,
  SUM(IF(tipo = 'E' AND nom_cate_macro IN ('Salarios e bonificacoes', 'Beneficios', 'Rendimentos'), vlr, 0)) AS renda,
  SUM(IF(tipo = 'E', vlr, 0)) AS entradas,
  SUM(IF(tipo = 'S', vlr, 0)) AS saidas,
  SUM(IF(tipo = 'S' AND nom_cate_micro IN ('Financiamento de imovel', 'Emprestimos', 'Outros emprestimos'), vlr, 0)) AS parcelas_credito,
  SUM(IF(descr = 'debito conta juros saldo dev', vlr, 0)) AS juros_ce,
  MIN(saldo_apos) AS saldo_min
FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
GROUP BY id_usuario, anomes;

CREATE TEMP TABLE usuario AS
SELECT
  id_usuario,
  AVG(renda)                                   AS renda_mensal,
  SUM(entradas) - SUM(saidas)                  AS poupanca_ano,
  SAFE_DIVIDE(SUM(parcelas_credito), SUM(renda)) AS comprometimento,
  COUNTIF(juros_ce > 0)                        AS meses_juros_ce,
  SUM(IF(anomes = ref_anomes, juros_ce, 0))    AS juros_ce_ultimo_mes,
  MAX(juros_ce)                                AS juros_ce_max_mes,
  MIN(saldo_min)                               AS saldo_min_ano
FROM mensal
GROUP BY id_usuario;

CREATE TEMP TABLE risco AS
SELECT
  *,
  CASE
    WHEN comprometimento IS NULL THEN 'C'
    WHEN comprometimento >= guardrail_vulneravel THEN 'V'
    WHEN comprometimento >= guardrail_atencao OR meses_juros_ce >= 9 THEN 'C'
    WHEN meses_juros_ce >= 4 THEN 'B'
    ELSE 'A'
  END AS faixa_risco
FROM usuario;

CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.parametros_modelo` AS
SELECT * FROM UNNEST([
  STRUCT('taxa_rotativo_cartao' AS parametro, taxa_rotativo AS valor, '% a.m.' AS unidade,
         'inferida_da_base' AS origem, 'razão juros/pagamento mínimo constante em 0,793' AS fonte),
  STRUCT('pagamento_minimo_fatura', pagamento_minimo, '% da fatura',
         'inferida_da_base', 'mesma dedução da taxa do rotativo'),
  STRUCT('teto_juros_cheque_especial', teto_ce, '% a.m.',
         'regulatorio', 'Res. CMN 4.765/2019 (validar vigência)'),
  STRUCT('limite_encargos_rotativo', 1.00, '% da dívida original',
         'regulatorio', 'Lei 14.690/2023 (validar vigência)'),
  STRUCT('guardrail_atencao', guardrail_atencao, 'comprometimento/renda',
         'decisao_do_time', 'acima: oferta só se a parcela for <= custo mensal atual'),
  STRUCT('guardrail_vulneravel', guardrail_vulneravel, 'comprometimento/renda',
         'decisao_do_time', 'acima: sem oferta de crédito, renegociação assistida')
]);

CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial` AS
WITH t AS (
  SELECT
    r.*,
    CASE r.faixa_risco WHEN 'A' THEN 0.065 WHEN 'B' THEN 0.072 ELSE teto_ce END AS taxa
  FROM risco r
),
s AS (
  SELECT
    t.*,
    juros_ce_ultimo_mes / taxa AS saldo_atual_impl,
    juros_ce_max_mes / taxa    AS saldo_max_impl
  FROM t
),
l AS (
  SELECT
    s.*,
    CEIL(GREATEST(saldo_max_impl, ABS(LEAST(saldo_min_ano, 0)), 0.3 * IFNULL(renda_mensal, 0), 500)
         * (1.2 + 0.6 * u(id_usuario, 'limite')) / 500) * 500 AS limite
  FROM s
)
SELECT
  id_usuario,
  faixa_risco,
  taxa                                           AS taxa_mensal_contratual,
  limite,
  ROUND(saldo_atual_impl, 2)                     AS saldo_devedor_atual_implicito,
  ROUND(saldo_max_impl, 2)                       AS saldo_devedor_max_implicito,
  ROUND(SAFE_DIVIDE(saldo_atual_impl, limite), 4) AS utilizacao_limite,
  meses_juros_ce,
  ROUND(juros_ce_ultimo_mes, 2)                  AS juros_ce_ultimo_mes_observado,
  'sintetico_regra' AS origem
FROM l;

CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.posicao_investimentos` AS
WITH base AS (
  SELECT r.id_usuario, r.poupanca_ano, r.renda_mensal, c.saldo_devedor_atual_implicito AS saldo_ce
  FROM risco r
  JOIN `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial` c USING (id_usuario)
),
regra AS (
  SELECT
    id_usuario,
    CASE
      WHEN id_usuario = persona_id THEN 'objetivo: troca do carro'
      WHEN poupanca_ano > 0 THEN 'reserva de emergencia'
      WHEN u(id_usuario, 'separado') < 0.35 THEN 'objetivo'
    END AS finalidade,
    CASE
      WHEN id_usuario = persona_id THEN GREATEST(1000, CEIL(saldo_ce * 1.25 / 100) * 100)
      WHEN poupanca_ano > 0 THEN ROUND(poupanca_ano * (0.5 + 1.5 * u(id_usuario, 'reserva')), -1)
      WHEN u(id_usuario, 'separado') < 0.35
        THEN ROUND(IFNULL(renda_mensal, 0) * (0.2 + 0.4 * u(id_usuario, 'valor_separado')), -1)
    END AS saldo,
    IF(id_usuario = persona_id, 'sintetico_cenario_demo', 'sintetico_regra') AS origem
  FROM base
)
SELECT
  id_usuario,
  'CDB DI'  AS produto,
  'diaria'  AS liquidez,
  ROUND(0.95 + 0.10 * u(id_usuario, 'cdi'), 2) AS percentual_cdi,
  finalidade,
  saldo,
  origem
FROM regra
WHERE finalidade IS NOT NULL AND saldo > 0;

CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.catalogo_ofertas` AS
SELECT * FROM UNNEST([
  STRUCT('parcelamento_cheque_especial' AS modalidade, 'A' AS faixa_risco, 0.030 AS taxa_mensal,
         6 AS prazo_min, 24 AS prazo_max, 30 AS carencia_dias, 'sintetico' AS origem),
  STRUCT('parcelamento_cheque_especial', 'B', 0.038, 6, 24, 30, 'sintetico'),
  STRUCT('parcelamento_cheque_especial', 'C', 0.045, 6, 24, 30, 'sintetico'),
  STRUCT('parcelamento_fatura',          'A', 0.065, 3, 24, 30, 'sintetico'),
  STRUCT('parcelamento_fatura',          'B', 0.075, 3, 24, 30, 'sintetico'),
  STRUCT('parcelamento_fatura',          'C', 0.085, 3, 24, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'A', 0.035, 6, 36, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'B', 0.045, 6, 36, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'C', 0.055, 6, 36, 30, 'sintetico')
]);

CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.cadastro_personas` AS
SELECT
  id_usuario, nome_ficticio, idade, cidade, ocupacao, cliente_desde, papel_demo,
  'sintetico_persona' AS origem
FROM (
  SELECT DISTINCT
    id_usuario,
    CASE
      WHEN id_usuario = persona_id THEN 'Bruno Carvalho'
      ELSE 'Marcos Teixeira'
    END AS nome_ficticio,
    IF(id_usuario = persona_id, 41, 47) AS idade,
    IF(id_usuario = persona_id, 'Guarulhos-SP', 'Sao Bernardo do Campo-SP') AS cidade,
    IF(id_usuario = persona_id, 'Supervisor de atendimento (CLT)', 'Tecnico de manutencao (CLT)') AS ocupacao,
    IF(id_usuario = persona_id, DATE '2014-03-01', DATE '2009-08-01') AS cliente_desde,
    IF(id_usuario = persona_id, 'persona_principal', 'guardrail_vulnerabilidade') AS papel_demo
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
  WHERE id_usuario = persona_id OR STARTS_WITH(id_usuario, '8fbc8ba3')
);

ASSERT (SELECT COUNT(*) FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`)
     = (SELECT COUNT(DISTINCT id_usuario) FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`)
  AS 'contrato_cheque_especial: deve haver exatamente um contrato por usuario';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
  WHERE limite < saldo_devedor_max_implicito)
  AS 'limite menor que o saldo devedor implicito';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
  WHERE taxa_mensal_contratual > teto_ce)
  AS 'taxa de cheque especial acima do teto';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.catalogo_ofertas`
  WHERE (modalidade = 'parcelamento_cheque_especial' AND taxa_mensal >= teto_ce)
     OR (modalidade = 'parcelamento_fatura' AND taxa_mensal >= taxa_rotativo))
  AS 'oferta mais cara que a divida que ela substitui';

ASSERT (SELECT faixa_risco FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
        WHERE id_usuario = persona_id) != 'V'
  AS 'persona caiu no guardrail de vulnerabilidade: revisar limites';

ASSERT (SELECT saldo_devedor_atual_implicito FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
        WHERE id_usuario = persona_id) > 0
  AS 'persona sem juros de cheque especial no ultimo mes';

ASSERT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.posicao_investimentos` WHERE id_usuario = persona_id)
  AS 'persona sem CDB do cenario de demo';

ASSERT (SELECT COUNT(*) FROM `batalha-time-06-1t82.vita_sintetico.cadastro_personas`) = 2
  AS 'cadastro_personas: esperado Bruno + usuario 8fbc8ba3';

SELECT
  c.id_usuario, c.faixa_risco, c.taxa_mensal_contratual, c.limite,
  c.saldo_devedor_atual_implicito, c.utilizacao_limite, c.juros_ce_ultimo_mes_observado,
  p.produto, p.finalidade, p.saldo AS saldo_cdb, p.percentual_cdi
FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial` c
LEFT JOIN `batalha-time-06-1t82.vita_sintetico.posicao_investimentos` p USING (id_usuario)
WHERE c.id_usuario = persona_id;
