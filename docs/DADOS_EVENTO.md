# Dados do evento — exploração da base `extrato_sintetico`

> Consultas rodadas em 26/09/2026 na tabela real do projeto do evento
> (`batalha-time-06-1t82.hackathon_dados.extrato_sintetico`), com a conta `central`.
> O snapshot local (`data/evento/extrato.csv`, gerado por `make stage-evento`) tem só
> 200 dos 1.000 usuários; os números abaixo são da base completa.

---

## 1. Esquema e volume

| Item | Valor |
|---|---|
| Colunas | `id_usuario` STRING, `anomesdia` TIMESTAMP, `anomes` INTEGER, `tipo` STRING, `descr` STRING, `vlr` FLOAT, `nom_cate_macro` STRING, `nom_cate_micro` STRING, `saldo_apos` FLOAT, `parcela_atual` FLOAT, `parcela_total` FLOAT |
| Linhas | 467.585 |
| Usuários | 1.000 |
| Período | 01/01/2025 a 31/12/2025 (ano completo) |

A coluna de data se chama **`anomesdia`**, não `data`. `anomes` é o mês em inteiro (ex.: `202503`).

---

## 2. Cuidados verificados

| Cuidado | Resultado | Consequência |
|---|---|---|
| Convenção de sinal | Todos os `vlr` são **positivos**. O sentido vem só de `tipo`: `E` entrada (35.077 linhas), `S` saída (432.508) | Nunca somar `vlr` sem filtrar `tipo` |
| Nulos | Zero em `vlr` e em `saldo_apos` | Sem tratamento de nulo |
| Parcelas em FLOAT | 29.847 linhas parceladas, **zero fracionadas**, máximo 12 | `CAST(... AS INT64)` é seguro |
| PII em `descr` | **Não há nomes.** Descrições são abreviações padronizadas: `pix transf terc`, `pix transf pess`, `pix qrs mercado` | O mascaramento de PII do agente fica ligado por precaução, mas a base não expõe pessoa |
| `id_usuario` | UUID pseudonimizado | Boa narrativa para LGPD |

---

## 3. Juros, encargos e investimentos no texto livre

**Juros existem e são relevantes.** 4.755 linhas em `Juros pagos`:

| nom_cate_micro | descr | n |
|---|---|---|
| Juros pagos | debito conta juros saldo dev | 2.477 |
| Juros pagos | debito conta juros lim | 2.278 |
| Outras despesas com impostos | debito conta iof | 371 |
| Multa por atraso | debito conta juros atraso | 33 |
| Seguros | debito conta seguro auto | 6 |
| Outros seguros | debito conta seguro cartao | 3 |
| Outras tarifas financeiras | debito conta encargo | 1 |
| Outras tarifas financeiras | debito conta encargo banc | 1 |

O restante do regex (`ROTATIV`) só pega estacionamento rotativo — não é cartão.

| Quem paga juros | Valor |
|---|---|
| Usuários com `Juros pagos` no ano | 695 de 1.000 |
| Mediana de juros por usuário/ano | R$ 596,04 |
| Média | R$ 778,69 |
| Máximo | R$ 4.996,78 |

**Investimentos não existem.** Nenhuma linha com CDB, aplicação ou resgate. Qualquer
tratamento que dependa de "o cliente tem aplicações" precisa de complemento sintético.

---

## 4. Panorama da base

**Faixa de salário mensal médio** (`Salarios e bonificacoes`, tipo `E`):

| Faixa | Usuários |
|---|---|
| < R$ 3 mil | 200 |
| R$ 3 a 6 mil | 291 |
| R$ 6 a 10 mil | 509 |
| > R$ 10 mil | 0 |

**Taxa de poupança** (entradas − saídas) / entradas, no ano:

| Métrica | Valor |
|---|---|
| Poupam (entradas > saídas) | 507 |
| Gastam mais do que recebem | 493 |
| Quartil 25% | −19,1% |
| Mediana | 0,2% |
| Quartil 75% | +15,8% |

**Saldo negativo:** 327 usuários ficaram com `saldo_apos < 0` em algum momento (56.141 linhas).

**Atenção a `Recebimentos diversos`:** 18.363 linhas somando R$ 33,4 milhões — mais da
metade do total de salários (R$ 52,7 milhões). Decidir se conta como renda muda toda a
análise de poupança.

---

## 5. A persona "Bruno" (renda R$ 7.700, poupança −43%)

Renda de R$ 7.700 existe; **poupança de −43% não**. Entre usuários com salário médio
entre R$ 7.000 e 8.500, os piores casos:

| id_usuario | salário médio | entradas/mês | saídas/mês | poupança | meses no vermelho |
|---|---|---|---|---|---|
| e2c16f30-b0b7-41cb-9946-1ced70d1a291 | 7.009 | 11.209 | 14.326 | −27,8% | 11 de 12 |
| 3f3f7877-71fd-4073-b0a8-692b105609d8 | 7.061 | 11.017 | 13.558 | −23,1% | 10 de 12 |
| 77c4e67b-f7cf-4fcb-8f73-145e228860b1 | 7.116 | 11.719 | 14.051 | −19,9% | 4 de 12 |
| 1094a8b2-badd-4b50-9ba0-a165c9594346 | 7.758 | 12.005 | 14.028 | −16,9% | 5 de 12 |
| edb3ff54-1c9a-40e3-abc0-36a4a34fb9e2 | 8.161 | 11.991 | 13.831 | −15,3% | 8 de 12 |
| 9242baec-1517-4311-84e5-881bcd9b5add | 7.202 | 9.467 | 10.908 | −15,2% | 9 de 12 |

Há 15 candidatos com poupança negativa nessa faixa. O primeiro é o melhor para demo:
renda na faixa, no vermelho quase o ano inteiro, com dado real.

---

## 6. Consultas usadas

Todas em SQL padrão, `T` = `` `batalha-time-06-1t82.hackathon_dados.extrato_sintetico` ``.

```sql
-- domínio de tipo e categorias
SELECT tipo, nom_cate_macro, nom_cate_micro, COUNT(*) n, ROUND(SUM(vlr),2) total
FROM T GROUP BY 1,2,3 ORDER BY n DESC;

-- juros, encargos, investimentos no texto livre
SELECT nom_cate_micro, descr, COUNT(*) n FROM T
WHERE REGEXP_CONTAINS(UPPER(descr), r'JURO|ENCARG|IOF|ROTATIV|CH ESP|CDB|APLIC|RESGATE|SEGURO')
GROUP BY 1,2 ORDER BY n DESC LIMIT 100;

-- sinal e nulos
SELECT tipo, COUNTIF(vlr < 0) neg, COUNTIF(vlr > 0) pos, COUNTIF(vlr IS NULL) nulos,
       COUNTIF(saldo_apos IS NULL) saldo_nulo FROM T GROUP BY 1;

-- parcelas fracionadas
SELECT COUNTIF(parcela_atual IS NOT NULL) com_parcela,
       COUNTIF(parcela_atual != CAST(parcela_atual AS INT64)
            OR parcela_total != CAST(parcela_total AS INT64)) fracionadas,
       MAX(parcela_total) max_total FROM T;

-- taxa de poupança e meses no vermelho por usuário (base da "bioimpedância")
WITH m AS (
  SELECT id_usuario, FORMAT_DATE('%Y-%m', DATE(anomesdia)) mes,
         SUM(IF(tipo='E' AND nom_cate_macro='Salarios e bonificacoes', vlr, 0)) sal,
         SUM(IF(tipo='E', vlr, 0)) ent,
         SUM(IF(tipo='S', ABS(vlr), 0)) sai
  FROM T GROUP BY 1,2)
SELECT id_usuario, ROUND(AVG(sal)) sal_med, ROUND(AVG(ent)) ent_med, ROUND(AVG(sai)) sai_med,
       ROUND(SAFE_DIVIDE(SUM(ent)-SUM(sai), SUM(ent))*100,1) poupanca_pct,
       COUNTIF(sai>ent) meses_no_vermelho, COUNT(*) meses
FROM m GROUP BY 1 ORDER BY poupanca_pct;
```

---

## 7. Resultado completo da query 1 (tipo × macro × micro)

| tipo | nom_cate_macro | nom_cate_micro | n | total |
|---|---|---|---|---|
| S | Mercado | Mercado | 42.513 | 2.619.248,39 |
| S | Assinaturas | Assinaturas | 36.252 | 1.005.603,28 |
| S | Delivery | Delivery | 27.886 | 1.576.423,37 |
| S | Transferencias diversas | Outras transferencias | 23.645 | 4.480.825,70 |
| S | Restaurantes | Restaurantes | 21.365 | 967.283,10 |
| S | Posto de combustivel | Posto de combustivel | 19.829 | 1.484.906,61 |
| S | Transporte por app | Transporte por app | 18.692 | 344.398,62 |
| E | Recebimentos diversos | Recebimentos diversos | 18.363 | 33.417.426,23 |
| S | Casa | Energia eletrica | 12.000 | 2.255.596,25 |
| S | Casa | TV Internet celular e telefone | 12.000 | 853.920,73 |
| S | Produtos financeiros | Pagamento de fatura | 12.000 | 18.241.986,03 |
| S | Casa | Agua e esgoto | 12.000 | 1.404.606,44 |
| S | Produtos financeiros | Anuidade e pacote de servico | 12.000 | 435.890,45 |
| S | Casa | Celular | 12.000 | 521.829,84 |
| S | Restaurantes | Padaria | 11.147 | 1.157.700,26 |
| S | Lojas e sites | Compras | 10.968 | 1.704.779,77 |
| S | Casa | Gas | 10.632 | 841.091,00 |
| E | Salarios e bonificacoes | Salario CLT | 9.600 | 52.708.565,88 |
| S | Emprestimos e financiamentos | Financiamento de imovel | 8.400 | 23.899.067,63 |
| S | Lojas e sites | Vestuario e acessorios | 8.400 | 1.443.033,18 |
| S | Educacao | Mensalidade escolar | 7.000 | 7.225.261,33 |
| S | Casa | Seguro residencial | 5.124 | 143.833,25 |
| S | Casa | Condominio | 5.064 | 4.051.790,03 |
| S | Produtos financeiros | Juros pagos | 4.755 | 541.191,80 |
| S | Veiculos | Estacionamento | 4.645 | 90.399,13 |
| S | Restaurantes | Cafeteria | 4.633 | 268.514,48 |
| S | Casa | IPTU | 4.380 | 1.296.158,89 |
| S | Lazer | Eletronicos | 4.159 | 2.302.746,44 |
| S | Lojas e sites | Brinquedos e artigos infantis | 3.796 | 198.351,16 |
| S | Lojas e sites | Artigos esportivos | 3.665 | 423.164,62 |
| S | Viagens | Hospedagem | 3.644 | 766.951,34 |
| E | Rendimentos | Recebimento Aluguel | 3.600 | 4.127.524,47 |
| S | Viagens | Passagem aerea e taxas | 3.475 | 1.310.024,69 |
| S | Lojas e sites | Moveis e decoracao | 3.428 | 778.590,96 |
| S | Veiculos | Pedagio | 3.300 | 79.311,34 |
| S | Veiculos | Seguro de automovel | 3.168 | 2.497.142,87 |
| S | Outros gastos | Diversos | 2.818 | 233.316,67 |
| S | Cuidados pessoais | Salao de beleza ou barbearia | 2.566 | 247.536,12 |
| S | Transporte publico | Transporte publico | 2.554 | 45.589,73 |
| S | Restaurantes | Outras comidas e bebidas | 2.539 | 113.136,47 |
| S | Produtos financeiros | Outras tarifas financeiras | 2.487 | 123.384,33 |
| S | Produtos financeiros | Outros seguros | 1.623 | 162.181,16 |
| S | Outros gastos | Frete e correios | 1.611 | 83.193,15 |
| E | Salarios e bonificacoes | 13o salario | 1.600 | 4.392.380,36 |
| S | Emprestimos e financiamentos | Emprestimos | 1.556 | 511.281,82 |
| S | Transporte publico | Passagem de onibus | 1.550 | 179.491,04 |
| S | Saque | Saque | 1.527 | 593.955,04 |
| S | Mercado | Casa de Carnes | 1.508 | 223.036,29 |
| S | Cuidados pessoais | Outros cuidados pessoais | 1.480 | 384.920,66 |
| S | Outros gastos | Outros gastos | 1.464 | 211.879,06 |
| S | Produtos financeiros | Seguros | 1.457 | 146.543,78 |
| S | Boletos diversos | Boleto | 1.444 | 1.230.748,00 |
| S | Lazer | Cinema | 1.423 | 90.092,58 |
| S | Casa | Pagamento de aluguel | 1.200 | 1.799.151,38 |
| E | Beneficios | Beneficio INSS | 1.200 | 3.148.129,08 |
| S | Lazer | Outros entretenimentos | 1.049 | 113.083,67 |
| S | Mercado | Feira livre | 1.042 | 11.986,94 |
| S | Cuidados pessoais | Produtos de beleza | 1.041 | 199.107,00 |
| S | Educacao | Outras despesas de educacao | 1.038 | 345.574,53 |
| S | Casa | Outras contas | 1.027 | 611.504,54 |
| S | Casa | Empregados domesticos | 1.019 | 164.887,17 |
| S | Lazer | Livros musica e video | 1.006 | 94.839,68 |
| S | Lojas e sites | Manutencao da casa | 999 | 264.433,51 |
| S | Posto de combustivel | Loja de conveniencia | 973 | 27.444,41 |
| S | Emprestimos e financiamentos | Outros emprestimos | 971 | 550.496,34 |
| S | Veiculos | Manutencao e reparo | 946 | 531.308,49 |
| S | Outros gastos | Outras despesas com impostos | 938 | 21.826,87 |
| S | Lazer | Videogames | 832 | 39.494,18 |
| S | Educacao | Curso de idiomas | 828 | 246.297,99 |
| S | Outros gastos | Pagamento de impostos | 790 | 309.362,61 |
| S | Outros gastos | Outros servicos | 741 | 118.367,13 |
| S | Lazer | Ingresso de shows | 741 | 203.652,04 |
| S | Casa | Outras despesas de moradia | 725 | 307.424,39 |
| E | Salarios e bonificacoes | Bonus PLR | 714 | 3.493.370,67 |
| S | Lazer | Associacoes e clubes | 713 | 50.409,98 |
| S | Mercado | Outros mercados | 700 | 194.462,58 |
| S | Produtos financeiros | Titulo de capitalizacao | 550 | 34.620,47 |
| S | Pets | Pet shop | 535 | 64.380,24 |
| S | Cuidados pessoais | Outros esportes | 531 | 113.657,77 |
| S | Outros gastos | Contabilidade | 520 | 142.191,03 |
| S | Lazer | Eventos e festas | 512 | 1.312.379,78 |
| S | Lazer | Museu e teatro | 496 | 32.819,88 |
| S | Casa | Jardinagem | 489 | 53.902,35 |
| S | Casa | Lavanderia | 488 | 30.330,44 |
| S | Outros gastos | Multa por atraso | 481 | 4.490,42 |
| S | Produtos financeiros | Consorcio | 466 | 336.464,95 |
| S | Viagens | Outros gastos de viagem | 446 | 292.840,17 |
| S | Pets | Outros gastos de animais | 361 | 42.299,32 |
| S | Veiculos | Licenciamento IPVA e DPVAT | 260 | 134.411,76 |
| S | Outros gastos | Publicidade | 259 | 240.464,78 |
| S | Veiculos | Outros gastos com transporte | 252 | 74.215,73 |
| S | Educacao | Entidades de classe | 238 | 71.344,00 |
| S | Veiculos | Aluguel de carro | 148 | 69.214,92 |
| S | Viagens | Compra de moedas | 140 | 281.510,64 |
| S | Pets | Veterinario | 136 | 35.003,90 |
| S | Veiculos | Multa | 136 | 36.784,30 |
| S | Outros gastos | Pensao alimenticia | 91 | 928,92 |
| S | Outros gastos | Cheque | 82 | 207.549,65 |
