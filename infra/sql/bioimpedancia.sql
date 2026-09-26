CREATE OR REPLACE TABLE `batalha-time-06-1t82.hackathon_dados.depara_categoria` AS
SELECT DISTINCT
  tipo,
  nom_cate_macro AS macro,
  nom_cate_micro AS micro,
  CASE
    WHEN tipo = 'E' AND nom_cate_macro IN ('Salarios e bonificacoes', 'Beneficios', 'Rendimentos')
      THEN 'renda'
    WHEN tipo = 'E'
      THEN 'entrada_outras'
    WHEN nom_cate_micro IN ('Juros pagos', 'Multa por atraso')
      THEN 'dreno_juros'
    WHEN nom_cate_micro IN ('Outras tarifas financeiras', 'Anuidade e pacote de servico')
      THEN 'dreno_tarifas'
    WHEN nom_cate_micro = 'Titulo de capitalizacao'
      THEN 'atencao_capitalizacao'
    WHEN nom_cate_micro IN ('Seguro residencial', 'Seguro de automovel', 'Outros seguros', 'Seguros')
      THEN 'imunidade'
    WHEN nom_cate_micro IN ('Financiamento de imovel', 'Emprestimos', 'Outros emprestimos')
      THEN 'compromisso_credito'
    WHEN nom_cate_micro = 'Pagamento de fatura'
      THEN 'cartao_opaco'
    WHEN nom_cate_micro IN ('Outras transferencias', 'Saque', 'Boleto', 'Cheque')
      THEN 'opaco'
    WHEN nom_cate_micro IN (
      'Energia eletrica', 'Agua e esgoto', 'Gas', 'Condominio', 'IPTU', 'Pagamento de aluguel',
      'TV Internet celular e telefone', 'Celular', 'Outras despesas de moradia', 'Outras contas',
      'Mercado', 'Casa de Carnes', 'Feira livre', 'Outros mercados',
      'Mensalidade escolar', 'Transporte publico', 'Passagem de onibus', 'Posto de combustivel',
      'Pagamento de impostos', 'Licenciamento IPVA e DPVAT', 'Pensao alimenticia', 'Consorcio')
      THEN 'essencial'
    ELSE 'nao_essencial'
  END AS classe
FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`;

CREATE OR REPLACE VIEW `batalha-time-06-1t82.hackathon_dados.vw_bioimpedancia_mensal` AS
WITH t AS (
  SELECT
    x.id_usuario, x.anomes, x.anomesdia, x.tipo, x.vlr, x.saldo_apos,
    CASE WHEN x.descr = 'debito conta iof' THEN 'dreno_encargos' ELSE d.classe END AS classe,
    x.descr
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico` x
  LEFT JOIN `batalha-time-06-1t82.hackathon_dados.depara_categoria` d
    ON x.tipo = d.tipo AND x.nom_cate_macro = d.macro AND x.nom_cate_micro = d.micro
)
SELECT
  id_usuario,
  anomes,
  ROUND(SUM(IF(classe = 'renda', vlr, 0)), 2)                               AS renda_recorrente,
  ROUND(SUM(IF(tipo = 'E', vlr, 0)), 2)                                     AS entradas,
  ROUND(SUM(IF(tipo = 'S', vlr, 0)), 2)                                     AS saidas,
  ROUND(SUM(IF(classe = 'essencial', vlr, 0)), 2)                           AS essenciais,
  ROUND(SUM(IF(classe IN ('dreno_juros', 'dreno_encargos'), vlr, 0)), 2)    AS dreno_juros,
  ROUND(SUM(IF(descr IN ('debito conta juros lim', 'debito conta juros saldo dev'), vlr, 0)), 2)
                                                                            AS juros_cheque_especial,
  ROUND(SUM(IF(classe = 'dreno_tarifas', vlr, 0)), 2)                       AS dreno_tarifas,
  ROUND(SUM(IF(classe = 'atencao_capitalizacao', vlr, 0)), 2)               AS capitalizacao,
  ROUND(SUM(IF(classe = 'imunidade', vlr, 0)), 2)                           AS seguros,
  ROUND(SUM(IF(classe = 'compromisso_credito', vlr, 0)), 2)                 AS parcelas_credito,
  ROUND(SUM(IF(classe = 'cartao_opaco', vlr, 0)), 2)                        AS fatura_cartao,
  ROUND(MIN(saldo_apos), 2)                                                 AS saldo_minimo,
  ROUND(ARRAY_AGG(saldo_apos ORDER BY anomesdia DESC LIMIT 1)[OFFSET(0)], 2) AS saldo_fechamento,
  COUNT(DISTINCT IF(saldo_apos < 0, DATE(anomesdia), NULL))                 AS dias_com_saldo_negativo
FROM t
GROUP BY id_usuario, anomes;

CREATE OR REPLACE VIEW `batalha-time-06-1t82.hackathon_dados.vw_bioimpedancia` AS
WITH parcelado AS (
  SELECT
    id_usuario,
    ROUND(SUM((CAST(parcela_total AS INT64) - CAST(parcela_atual AS INT64)) * vlr), 2) AS parcelado_a_vencer
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
  WHERE parcela_atual IS NOT NULL
    AND tipo = 'S'
    AND anomes = (SELECT MAX(anomes) FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`)
  GROUP BY id_usuario
),
anual AS (
  SELECT
    id_usuario,
    ROUND(AVG(renda_recorrente), 2)                                                  AS renda_media_mensal,
    ROUND(AVG(entradas), 2)                                                          AS entradas_media_mensal,
    ROUND(AVG(saidas), 2)                                                            AS saidas_media_mensal,
    ROUND(AVG(essenciais), 2)                                                        AS essenciais_media_mensal,
    ROUND(SAFE_DIVIDE(SUM(entradas) - SUM(saidas), SUM(entradas)) * 100, 1)           AS poupanca_sobre_entradas_pct,
    ROUND(SAFE_DIVIDE(SUM(renda_recorrente) - SUM(saidas), SUM(renda_recorrente)) * 100, 1)
                                                                                     AS poupanca_sobre_renda_pct,
    COUNTIF(saidas > entradas)                                                       AS meses_fluxo_negativo,
    COUNTIF(saldo_minimo < 0)                                                        AS meses_saldo_negativo,
    COUNTIF(juros_cheque_especial > 0)                                               AS meses_pagando_juros,
    ROUND(SUM(dreno_juros), 2)                                                       AS juros_encargos_ano,
    ROUND(SUM(dreno_tarifas), 2)                                                     AS tarifas_ano,
    ROUND(SAFE_DIVIDE(SUM(dreno_juros) + SUM(dreno_tarifas), SUM(renda_recorrente)) * 100, 2)
                                                                                     AS dreno_pct_renda,
    ROUND(SUM(capitalizacao), 2)                                                     AS capitalizacao_ano,
    COUNTIF(capitalizacao > 0 AND juros_cheque_especial > 0)                         AS meses_capitalizacao_com_juros,
    ROUND(SAFE_DIVIDE(SUM(essenciais), SUM(renda_recorrente)) * 100, 1)              AS essenciais_pct_renda,
    ROUND(SAFE_DIVIDE(SUM(parcelas_credito), SUM(renda_recorrente)) * 100, 1)        AS comprometimento_credito_pct,
    ROUND(SAFE_DIVIDE(SUM(fatura_cartao), SUM(saidas)) * 100, 1)                     AS fatura_pct_saidas,
    SUM(seguros) > 0                                                                 AS tem_seguro,
    ARRAY_AGG(saldo_fechamento ORDER BY anomes DESC LIMIT 1)[OFFSET(0)]              AS saldo_ultimo_mes,
    ARRAY_AGG(juros_cheque_especial ORDER BY anomes DESC LIMIT 1)[OFFSET(0)]         AS juros_ultimo_mes
  FROM `batalha-time-06-1t82.hackathon_dados.vw_bioimpedancia_mensal`
  GROUP BY id_usuario
)
SELECT
  a.*,
  IFNULL(p.parcelado_a_vencer, 0) AS parcelado_a_vencer
FROM anual a
LEFT JOIN parcelado p USING (id_usuario);

CREATE OR REPLACE VIEW `batalha-time-06-1t82.hackathon_dados.vw_gatilho_dreno` AS
SELECT
  id_usuario,
  juros_ultimo_mes,
  meses_pagando_juros,
  juros_encargos_ano,
  poupanca_sobre_entradas_pct
FROM `batalha-time-06-1t82.hackathon_dados.vw_bioimpedancia`
WHERE juros_ultimo_mes > 0
  AND meses_pagando_juros >= 3;
