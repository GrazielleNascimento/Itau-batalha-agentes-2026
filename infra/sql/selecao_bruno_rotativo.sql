-- Vita — Seleção do Bruno (rotativo) e reconstrução da fatura. Script do time, 26/09.
-- T = batalha-time-06-1t82.hackathon_dados.extrato_sintetico
-- Constantes deduzidas da base: pagamento mínimo = 15% da fatura; rotativo = 14% a.m.

-- 1) View: fatura mês a mês com modo e reconstrução (fonte da tool get_fatura_rotativo)
CREATE OR REPLACE VIEW `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal` AS
WITH fatura AS (
  SELECT id_usuario, anomes, SUM(vlr) AS pago,
    CASE
      WHEN LOGICAL_OR(LOWER(descr) LIKE '%parcial') THEN 'parcial'
      WHEN LOGICAL_OR(REGEXP_CONTAINS(LOWER(descr), r'(minimo|mínimo|min)$')) THEN 'minimo'
      ELSE 'integral'
    END AS modo
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
  WHERE tipo = 'S' AND nom_cate_micro = 'Pagamento de fatura'
  GROUP BY id_usuario, anomes
),
juros AS (
  SELECT id_usuario, anomes, SUM(vlr) AS juros_rotativo
  FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`
  WHERE descr = 'debito conta juros lim'
  GROUP BY id_usuario, anomes
)
SELECT
  f.id_usuario, f.anomes, MOD(f.anomes, 100) AS mes, f.modo,
  ROUND(f.pago, 2) AS pago,
  ROUND(IFNULL(j.juros_rotativo, 0), 2) AS juros_rotativo,
  IF(f.modo = 'minimo', ROUND(f.pago / 0.15, 2), NULL) AS fatura_total_reconstruida,
  IF(IFNULL(j.juros_rotativo, 0) > 0, ROUND(j.juros_rotativo / 0.14, 2), NULL) AS saldo_rotativo_reconstruido
FROM fatura f
LEFT JOIN juros j USING (id_usuario, anomes);

-- 2) Candidatos a Bruno: 3+ faturas seguidas não integrais, 1+ mínimo, renda 6-10 mil,
--    financiamento de imóvel, juros de rotativo no último mês, fora da faixa V.
WITH ref AS (SELECT MAX(anomes) AS ultimo FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico`),
sequencias AS (
  SELECT id_usuario, mes - ROW_NUMBER() OVER (PARTITION BY id_usuario ORDER BY mes) AS grp
  FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal` WHERE modo != 'integral'),
maior_sequencia AS (
  SELECT id_usuario, MAX(n) AS meses_seguidos_nao_integral
  FROM (SELECT id_usuario, grp, COUNT(*) AS n FROM sequencias GROUP BY 1, 2) GROUP BY 1),
resumo_fatura AS (
  SELECT id_usuario, COUNTIF(modo = 'minimo') AS meses_minimo, COUNTIF(modo != 'integral') AS meses_nao_integral,
    ROUND(SUM(juros_rotativo), 2) AS juros_rotativo_ano,
    ROUND(SUM(IF(anomes = ref.ultimo, juros_rotativo, 0)), 2) AS juros_rotativo_ultimo_mes
  FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal` CROSS JOIN ref GROUP BY 1),
perfil AS (
  SELECT id_usuario, AVG(renda) AS renda_mensal, AVG(parcelas_credito) AS parcelas_mensais,
    LOGICAL_OR(tem_imovel) AS tem_financiamento_imovel
  FROM (
    SELECT id_usuario, anomes,
      SUM(IF(tipo = 'E' AND nom_cate_macro IN ('Salarios e bonificacoes', 'Beneficios', 'Rendimentos'), vlr, 0)) AS renda,
      SUM(IF(tipo = 'S' AND nom_cate_micro IN ('Financiamento de imovel', 'Emprestimos', 'Outros emprestimos'), vlr, 0)) AS parcelas_credito,
      LOGICAL_OR(nom_cate_micro = 'Financiamento de imovel') AS tem_imovel
    FROM `batalha-time-06-1t82.hackathon_dados.extrato_sintetico` GROUP BY 1, 2)
  GROUP BY 1)
SELECT r.id_usuario, s.meses_seguidos_nao_integral, r.meses_nao_integral, r.meses_minimo,
  r.juros_rotativo_ultimo_mes, r.juros_rotativo_ano, ROUND(p.renda_mensal, 2) AS renda_mensal,
  ROUND(p.parcelas_mensais, 2) AS parcelas_mensais,
  ROUND(SAFE_DIVIDE(p.parcelas_mensais, p.renda_mensal), 3) AS comprometimento,
  ROUND(p.renda_mensal - p.parcelas_mensais, 2) AS sobra_apos_parcelas
FROM resumo_fatura r JOIN maior_sequencia s USING (id_usuario) JOIN perfil p USING (id_usuario)
WHERE s.meses_seguidos_nao_integral >= 3 AND r.meses_minimo >= 1
  AND p.renda_mensal BETWEEN 6000 AND 10000 AND p.tem_financiamento_imovel
  AND r.juros_rotativo_ultimo_mes > 0 AND p.renda_mensal - p.parcelas_mensais >= 600
  AND SAFE_DIVIDE(p.parcelas_mensais, p.renda_mensal) < 0.50
ORDER BY r.juros_rotativo_ultimo_mes DESC LIMIT 10;

-- 3) Fatura do escolhido, mês a mês (bq query --parameter=id_usuario:STRING:<id>)
SELECT * FROM `batalha-time-06-1t82.vita_sintetico.vw_fatura_mensal`
WHERE id_usuario = @id_usuario ORDER BY anomes;
