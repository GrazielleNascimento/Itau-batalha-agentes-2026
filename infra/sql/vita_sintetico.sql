-- =====================================================================
-- Vita — Gerador de dados sintéticos v2 (rodar como UM script no BigQuery)
--
--   * Persona principal: Bruno = 36d74064 (rotativo), mês de referência dez/2025.
--   * Faixa de risco considera juros de rotativo E de cheque especial.
--   * Faixa V pelo mínimo existencial (sobra após parcelas < R$ 600) ou
--     comprometimento >= 50%.
--   * Limite de cheque especial limitado a ~2x a renda (sem saldo_apos).
--   * CDB da persona cobre o saldo do rotativo do mês de referência.
--   * Tabela perfil_risco com o motivo da faixa (explicabilidade).
--
-- Pré-requisito: view vita_sintetico.vw_fatura_mensal (selecao_bruno_rotativo.sql).
-- A base original (hackathon_dados.extrato_sintetico) NÃO é alterada.
-- Determinístico (FARM_FINGERPRINT): rerodar gera os mesmos valores.
-- Uso: bq --project_id=batalha-time-06-1t82 --location=us-central1 query \
--        --use_legacy_sql=false < infra/sql/vita_sintetico.sql
-- =====================================================================

DECLARE persona_id STRING DEFAULT '36d74064-cc59-4ad2-9304-aeae46e660e4';
DECLARE guardrail_prefixo STRING DEFAULT '8fbc8ba3';
DECLARE ref_anomes INT64 DEFAULT (
  SELECT MAX(anomes) FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`);

DECLARE teto_ce FLOAT64 DEFAULT 0.08;
DECLARE taxa_rotativo FLOAT64 DEFAULT 0.14;
DECLARE pagamento_minimo FLOAT64 DEFAULT 0.15;
DECLARE guardrail_atencao FLOAT64 DEFAULT 0.35;
DECLARE guardrail_vulneravel FLOAT64 DEFAULT 0.50;
DECLARE minimo_existencial FLOAT64 DEFAULT 600;
DECLARE limite_max_renda FLOAT64 DEFAULT 2.0;

CREATE SCHEMA IF NOT EXISTS `batalha-time-06-1t82.vita_sintetico`
  OPTIONS (location = 'us-central1');

CREATE TEMP FUNCTION u(id STRING, sal STRING) AS (
  ABS(MOD(FARM_FINGERPRINT(CONCAT(id, ':', sal)), 1000000)) / 1000000.0
);

-- 1) Agregados da base real
CREATE TEMP TABLE mensal AS
SELECT
  id_usuario,
  anomes,
  SUM(IF(tipo = 'E' AND nom_cate_macro IN ('Salarios e bonificacoes', 'Beneficios', 'Rendimentos'), vlr, 0)) AS renda,
  SUM(IF(tipo = 'E', vlr, 0)) AS entradas,
  SUM(IF(tipo = 'S', vlr, 0)) AS saidas,
  SUM(IF(tipo = 'S' AND nom_cate_micro IN ('Financiamento de imovel', 'Emprestimos', 'Outros emprestimos'), vlr, 0)) AS parcelas_credito,
  SUM(IF(descr = 'debito conta juros saldo dev', vlr, 0)) AS juros_ce,
  SUM(IF(descr = 'debito conta juros lim', vlr, 0)) AS juros_rot
FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
GROUP BY id_usuario, anomes;

CREATE TEMP TABLE usuario AS
SELECT
  id_usuario,
  AVG(renda)                                        AS renda_mensal,
  AVG(parcelas_credito)                             AS parcelas_mensais,
  SUM(entradas) - SUM(saidas)                       AS poupanca_ano,
  SAFE_DIVIDE(SUM(parcelas_credito), SUM(renda))    AS comprometimento,
  AVG(renda) - AVG(parcelas_credito)                AS sobra_apos_parcelas,
  COUNTIF(juros_ce > 0)                             AS meses_juros_ce,
  COUNTIF(juros_rot > 0)                            AS meses_juros_rot,
  COUNTIF(juros_ce > 0 OR juros_rot > 0)            AS meses_com_juros,
  SUM(IF(anomes = ref_anomes, juros_ce, 0))         AS juros_ce_ultimo_mes,
  MAX(juros_ce)                                     AS juros_ce_max_mes
FROM mensal
GROUP BY id_usuario;

-- Faixa de risco com motivo (ordem importa: V primeiro)
CREATE TEMP TABLE risco AS
SELECT
  *,
  CASE
    WHEN IFNULL(sobra_apos_parcelas, 0) < minimo_existencial THEN 'V'
    WHEN comprometimento >= guardrail_vulneravel THEN 'V'
    WHEN comprometimento >= guardrail_atencao OR meses_com_juros >= 9 THEN 'C'
    WHEN meses_com_juros >= 4 THEN 'B'
    ELSE 'A'
  END AS faixa_risco,
  CASE
    WHEN IFNULL(sobra_apos_parcelas, 0) < minimo_existencial THEN 'sobra apos parcelas abaixo do minimo existencial'
    WHEN comprometimento >= guardrail_vulneravel THEN 'comprometimento de credito >= 50%'
    WHEN comprometimento >= guardrail_atencao THEN 'comprometimento de credito entre 35% e 50%'
    WHEN meses_com_juros >= 9 THEN 'juros em 9 ou mais meses'
    WHEN meses_com_juros >= 4 THEN 'juros em 4 a 8 meses'
    ELSE 'comprometimento < 35% e juros em menos de 4 meses'
  END AS motivo_faixa
FROM usuario;

-- 2) Parâmetros do modelo, com procedência
CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.parametros_modelo` AS
SELECT * FROM UNNEST([
  STRUCT('taxa_rotativo_cartao' AS parametro, taxa_rotativo AS valor, '% a.m.' AS unidade,
         'inferida_da_base' AS origem, 'razao juros/pagamento minimo constante em 0,793' AS fonte),
  STRUCT('pagamento_minimo_fatura', pagamento_minimo, '% da fatura',
         'inferida_da_base', 'mesma deducao da taxa do rotativo'),
  STRUCT('teto_juros_cheque_especial', teto_ce, '% a.m.',
         'regulatorio', 'Res. CMN 4.765/2019 (validar vigencia)'),
  STRUCT('limite_encargos_rotativo', 1.00, '% da divida original',
         'regulatorio', 'Lei 14.690/2023 (validar vigencia)'),
  STRUCT('minimo_existencial', minimo_existencial, 'R$ por mes',
         'regulatorio', 'Lei 14.181/2021 e Decreto 11.150/2022; R$ 600 mantido pelo STF em abr/2026'),
  STRUCT('guardrail_atencao', guardrail_atencao, 'comprometimento/renda',
         'decisao_do_time', 'acima: oferta so se a parcela for <= custo mensal atual de juros'),
  STRUCT('guardrail_vulneravel', guardrail_vulneravel, 'comprometimento/renda',
         'decisao_do_time', 'acima: sem oferta de credito, renegociacao assistida'),
  STRUCT('limite_cheque_especial_max_renda', limite_max_renda, 'multiplo da renda',
         'decisao_do_time', 'teto do limite sintetico de cheque especial')
]);

-- 3) Perfil de risco (fonte da faixa para todas as modalidades)
CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.perfil_risco` AS
SELECT
  id_usuario,
  faixa_risco,
  motivo_faixa,
  ROUND(renda_mensal, 2)         AS renda_mensal,
  ROUND(parcelas_mensais, 2)     AS parcelas_mensais,
  ROUND(comprometimento, 4)      AS comprometimento,
  ROUND(sobra_apos_parcelas, 2)  AS sobra_apos_parcelas,
  meses_juros_rot,
  meses_juros_ce,
  'sintetico_regra' AS origem
FROM risco;

-- 4) Contrato de cheque especial (limite sem saldo_apos, teto em 2x a renda)
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
    CEIL(LEAST(
           GREATEST(saldo_max_impl, 0.3 * IFNULL(renda_mensal, 0), 500) * (1.2 + 0.6 * u(id_usuario, 'limite')),
           GREATEST(limite_max_renda * IFNULL(renda_mensal, 0), saldo_max_impl * 1.2, 500)
         ) / 500) * 500 AS limite
  FROM s
)
SELECT
  id_usuario,
  faixa_risco,
  taxa                                            AS taxa_mensal_contratual,
  limite,
  ROUND(saldo_atual_impl, 2)                      AS saldo_devedor_atual_implicito,
  ROUND(saldo_max_impl, 2)                        AS saldo_devedor_max_implicito,
  ROUND(SAFE_DIVIDE(saldo_atual_impl, limite), 4) AS utilizacao_limite,
  meses_juros_ce,
  ROUND(juros_ce_ultimo_mes, 2)                   AS juros_ce_ultimo_mes_observado,
  'sintetico_regra' AS origem
FROM l;

-- 5) Posição de investimentos (CDB DI, liquidez diária)
CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.posicao_investimentos` AS
WITH rotativo_ref AS (
  SELECT id_usuario, IFNULL(saldo_rotativo_reconstruido, 0) AS saldo_rot
  FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal`
  WHERE anomes = ref_anomes
),
base AS (
  SELECT r.id_usuario, r.poupanca_ano, r.renda_mensal, IFNULL(f.saldo_rot, 0) AS saldo_rot
  FROM risco r
  LEFT JOIN rotativo_ref f USING (id_usuario)
),
regra AS (
  SELECT
    id_usuario,
    saldo_rot,
    CASE
      WHEN poupanca_ano > 0 THEN 'reserva de emergencia'
      WHEN u(id_usuario, 'separado') < 0.35 THEN 'objetivo'
    END AS finalidade_regra,
    CASE
      WHEN poupanca_ano > 0 THEN ROUND(poupanca_ano * (0.5 + 1.5 * u(id_usuario, 'reserva')), -1)
      WHEN u(id_usuario, 'separado') < 0.35
        THEN ROUND(IFNULL(renda_mensal, 0) * (0.2 + 0.4 * u(id_usuario, 'valor_separado')), -1)
    END AS saldo_regra
  FROM base
),
resultado AS (
  SELECT
    id_usuario,
    IF(id_usuario = persona_id, IFNULL(finalidade_regra, 'reserva de emergencia'), finalidade_regra) AS finalidade,
    IF(id_usuario = persona_id,
       GREATEST(IFNULL(saldo_regra, 0), CEIL(saldo_rot * 1.25 / 100) * 100, 1000),
       saldo_regra) AS saldo,
    IF(id_usuario = persona_id, 'sintetico_cenario_demo', 'sintetico_regra') AS origem
  FROM regra
)
SELECT
  id_usuario,
  'CDB DI'  AS produto,
  'diaria'  AS liquidez,
  ROUND(0.95 + 0.10 * u(id_usuario, 'cdi'), 2) AS percentual_cdi,
  finalidade,
  saldo,
  origem
FROM resultado
WHERE finalidade IS NOT NULL AND saldo > 0;

-- 6) Catálogo de ofertas (faixa V não tem linha: sem oferta de crédito)
CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.catalogo_ofertas` AS
SELECT * FROM UNNEST([
  STRUCT('parcelamento_fatura' AS modalidade, 'A' AS faixa_risco, 0.065 AS taxa_mensal,
         3 AS prazo_min, 24 AS prazo_max, 30 AS carencia_dias, 'sintetico' AS origem),
  STRUCT('parcelamento_fatura',          'B', 0.075, 3, 24, 30, 'sintetico'),
  STRUCT('parcelamento_fatura',          'C', 0.085, 3, 24, 30, 'sintetico'),
  STRUCT('parcelamento_cheque_especial', 'A', 0.030, 6, 24, 30, 'sintetico'),
  STRUCT('parcelamento_cheque_especial', 'B', 0.038, 6, 24, 30, 'sintetico'),
  STRUCT('parcelamento_cheque_especial', 'C', 0.045, 6, 24, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'A', 0.035, 6, 36, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'B', 0.045, 6, 36, 30, 'sintetico'),
  STRUCT('credito_pessoal',              'C', 0.055, 6, 36, 30, 'sintetico')
]);

-- 7) Cadastro fictício das personas (só front-end; o LLM nunca recebe)
CREATE OR REPLACE TABLE `batalha-time-06-1t82.vita_sintetico.cadastro_personas` AS
SELECT
  id_usuario, nome_ficticio, idade, cidade, ocupacao, cliente_desde, papel_demo,
  'sintetico_persona' AS origem
FROM (
  SELECT DISTINCT
    id_usuario,
    IF(id_usuario = persona_id, 'Bruno Carvalho', 'Marcos Teixeira') AS nome_ficticio,
    IF(id_usuario = persona_id, 41, 47) AS idade,
    IF(id_usuario = persona_id, 'Guarulhos-SP', 'Sao Bernardo do Campo-SP') AS cidade,
    IF(id_usuario = persona_id, 'Supervisor de atendimento (CLT)', 'Tecnico de manutencao (CLT)') AS ocupacao,
    IF(id_usuario = persona_id, DATE '2014-03-01', DATE '2009-08-01') AS cliente_desde,
    IF(id_usuario = persona_id, 'persona_principal', 'guardrail_vulnerabilidade') AS papel_demo
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
  WHERE id_usuario = persona_id OR STARTS_WITH(id_usuario, guardrail_prefixo)
);

-- 8) Checagens de coerência: se alguma falhar, o script para aqui
ASSERT (SELECT COUNT(*) FROM `batalha-time-06-1t82.vita_sintetico.perfil_risco`)
     = (SELECT COUNT(DISTINCT id_usuario) FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`)
  AS 'perfil_risco: deve haver exatamente um perfil por usuario';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
  WHERE limite < saldo_devedor_max_implicito)
  AS 'limite menor que o saldo devedor implicito';

ASSERT NOT EXISTS (
  SELECT 1
  FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial` c
  JOIN `batalha-time-06-1t82.vita_sintetico.perfil_risco` p USING (id_usuario)
  WHERE c.limite > GREATEST(limite_max_renda * IFNULL(p.renda_mensal, 0), c.saldo_devedor_max_implicito * 1.2, 500) + 500)
  AS 'limite acima do teto de ~2x a renda';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.contrato_cheque_especial`
  WHERE taxa_mensal_contratual > teto_ce)
  AS 'taxa de cheque especial acima do teto';

ASSERT NOT EXISTS (
  SELECT 1 FROM `batalha-time-06-1t82.vita_sintetico.catalogo_ofertas`
  WHERE (modalidade = 'parcelamento_cheque_especial' AND taxa_mensal >= teto_ce)
     OR (modalidade = 'parcelamento_fatura' AND taxa_mensal >= taxa_rotativo))
  AS 'oferta mais cara que a divida que ela substitui';

ASSERT (SELECT faixa_risco FROM `batalha-time-06-1t82.vita_sintetico.perfil_risco`
        WHERE id_usuario = persona_id) = 'C'
  AS 'Bruno deveria estar na faixa C (comprometimento entre 35% e 50%)';

ASSERT (SELECT saldo_rotativo_reconstruido FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal`
        WHERE id_usuario = persona_id AND anomes = ref_anomes) > 0
  AS 'Bruno sem saldo no rotativo no mes de referencia';

ASSERT (SELECT saldo FROM `batalha-time-06-1t82.vita_sintetico.posicao_investimentos`
        WHERE id_usuario = persona_id)
    >= (SELECT saldo_rotativo_reconstruido FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal`
        WHERE id_usuario = persona_id AND anomes = ref_anomes)
  AS 'CDB do Bruno nao cobre o saldo do rotativo';

ASSERT (SELECT faixa_risco FROM `batalha-time-06-1t82.vita_sintetico.perfil_risco`
        WHERE STARTS_WITH(id_usuario, guardrail_prefixo)) = 'V'
  AS 'Marcos deveria estar na faixa V';

ASSERT (SELECT COUNT(*) FROM `batalha-time-06-1t82.vita_sintetico.cadastro_personas`) = 2
  AS 'cadastro_personas: esperado Bruno + Marcos';

-- 9a) O Bruno em uma linha
SELECT
  p.id_usuario, p.faixa_risco, p.motivo_faixa, p.renda_mensal, p.comprometimento, p.sobra_apos_parcelas,
  f.modo AS modo_ref, f.pago AS pago_ref, f.juros_rotativo AS juros_ref,
  f.fatura_total_reconstruida, f.saldo_rotativo_reconstruido,
  i.saldo AS saldo_cdb, i.percentual_cdi, i.finalidade
FROM `batalha-time-06-1t82.vita_sintetico.perfil_risco` p
JOIN `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal` f
  ON f.id_usuario = p.id_usuario AND f.anomes = ref_anomes
LEFT JOIN `batalha-time-06-1t82.vita_sintetico.posicao_investimentos` i
  ON i.id_usuario = p.id_usuario
WHERE p.id_usuario = persona_id;

-- 9b) Clientes por faixa (para a tabela de faixas do PRD)
SELECT faixa_risco, motivo_faixa, COUNT(*) AS clientes
FROM `batalha-time-06-1t82.vita_sintetico.perfil_risco`
GROUP BY faixa_risco, motivo_faixa
ORDER BY faixa_risco, clientes DESC;
