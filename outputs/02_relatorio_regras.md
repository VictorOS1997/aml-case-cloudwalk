# Relatório de Regras de Alerta — Dia 2
**Projeto:** AML-FT Case CloudWalk  
**Data:** 2026-06-21  
**Script:** `notebooks/02_regras_alertas.py`  

---

## 1. Resumo Executivo

| Métrica | Valor |
|---------|-------|
| Transações analisadas | 52,000 |
| Regras implementadas | 22 |
| Regras que dispararam alertas | 17 |
| Total de alertas gerados | 10,576 |
| Entidades únicas alertadas | 3,475 |
| Clientes no ranking | 3,310 |
| Merchants no ranking | 846 |
| Weak label positivo (≥2 regras-core) | 108 |

---

## 2. Catálogo de Regras Executadas

★ = regra-core (usada como rótulo fraco para o ML no Dia 4)

| Regra | Nome | Tipologia | Sev | Alertas | Exemplo (ID) |
|-------|------|-----------|-----|---------|--------------|
| R01_velocity | Velocidade | Comportamento/Velocidade | 2 | 0 | `—` |
| R02_burst_value | Burst de Valor | Comportamento/Velocidade | 2 | 90 | `TNVCSNADRX431` |
| R03_structuring | Structuring PIX ★ | Structuring/Smurfing | 3 | 4 | `TH4RQ4N7DS4PL` |
| R04_income_mismatch | Renda Incompatível | Renda × Valor | 2 | 1,016 | `TUILBKR4582YE` |
| R05_geojump | Geo-Salto | Geografia | 3 | 2,119 | `TQJS09NN0BGPZ` |
| R06_ip_anomaly | IP Anômalo/País Risco | Geografia/Device | 2 | 201 | `TFDPTD4FWWTWP` |
| R07_device_ring | Device Ring ★ | Device/IP Ring | 3 | 0 | `—` |
| R08_ip_ring | IP Ring | Device/IP Ring | 3 | 0 | `—` |
| R09_self_merchant | Self-Merchant ★ | Self-Merchant | 4 | 2 | `T89LY8D0GYY1H` |
| R10_cash_in_out | Cash-in → Cash-out | Cash-in/out | 3 | 802 | `T90PBAEUYYDIY` |
| R11_fan_out | Fan-out | Cash-in/out / Dispersão | 2 | 0 | `—` |
| R12_ecom_no_3ds | E-commerce sem 3DS ★ | E-commerce / 3DS | 3 | 572 | `TCRGE3QP5PJX2` |
| R13_eci_cross_border | ECI Cross-border | E-commerce / 3DS | 2 | 765 | `T1AJ938L2PSXF` |
| R14_cross_border_high | Cross-border Alto Valor | País de Risco | 2 | 226 | `TXGJ8KE92NPJX` |
| R15_sanctions | Sanções ★ | Sanções / País Risco | 4 | 484 | `TJRKHTP81JROK` |
| R16_pep | PEP Ativo | PEP / MCC Risco | 3 | 52 | `TGWFWVYJM6BZ1` |
| R17_high_risk_mcc | MCC Alto Risco | PEP / MCC Risco | 2 | 3,263 | `T9HIMVHJ8TMK7` |
| R18_chargeback_merchant | Chargeback Merchant | Chargeback | 2 | 846 | `T9HIMVHJ8TMK7` |
| R19_installments_atypical | Parcelamento Atípico | Comportamento | 1 | 33 | `TSC7GT9MXYMUE` |
| R20_new_account | Conta Nova Alta Atividade | Comportamento | 2 | 98 | `T3K65EEF09DSE` |
| R21_round_values | Valores Redondos | Structuring | 1 | 0 | `—` |
| R22_card_multidevice | Card Multi-Device | Device/IP Ring | 3 | 3 | `T1P7CGQ7JI8QC` |

---

## 3. Top-20 Entidades por Score de Risco

| Rank | Entity ID | Tipo | Score | N° Regras | Core Label | Tier | Regras Disparadas |
|------|-----------|------|-------|-----------|------------|------|-------------------|
| 1 | C101919 | client | 22 | 9 | não | alto | R02_burst_value,R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R14_cross_border_high,R16_pep,R17_high_risk_mcc |
| 2 | C101208 | client | 22 | 7 | ★ SIM | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 3 | C102093 | client | 21 | 8 | ★ SIM | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R12_ecom_no_3ds,R15_sanctions,R16_pep,R17_high_risk_mcc |
| 4 | C100184 | client | 21 | 9 | não | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R14_cross_border_high,R17_high_risk_mcc,R20_new_account |
| 5 | C101775 | client | 20 | 8 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R16_pep,R17_high_risk_mcc |
| 6 | C101028 | client | 20 | 6 | ★ SIM | alto | R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 7 | C100658 | client | 20 | 8 | ★ SIM | alto | R02_burst_value,R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 8 | C100517 | client | 20 | 8 | ★ SIM | alto | R02_burst_value,R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 9 | C101299 | client | 20 | 8 | ★ SIM | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |
| 10 | C101895 | client | 19 | 8 | ★ SIM | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R12_ecom_no_3ds,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |
| 11 | C100237 | client | 19 | 8 | não | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |
| 12 | C101991 | client | 19 | 8 | não | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R14_cross_border_high,R17_high_risk_mcc |
| 13 | C101212 | client | 18 | 8 | não | alto | R02_burst_value,R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R17_high_risk_mcc |
| 14 | C100967 | client | 18 | 7 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R14_cross_border_high,R15_sanctions,R16_pep,R17_high_risk_mcc |
| 15 | C100831 | client | 18 | 7 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R13_eci_cross_border,R15_sanctions,R16_pep,R17_high_risk_mcc |
| 16 | C101583 | client | 18 | 7 | ★ SIM | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 17 | C100735 | client | 17 | 7 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |
| 18 | C101755 | client | 17 | 7 | não | alto | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc |
| 19 | C102388 | client | 17 | 7 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |
| 20 | C100388 | client | 17 | 7 | não | alto | R04_income_mismatch,R05_geojump,R10_cash_in_out,R13_eci_cross_border,R14_cross_border_high,R15_sanctions,R17_high_risk_mcc |

---

## 4. Análise por Tipologia

| Tipologia | Regras | Total Alertas |
|-----------|--------|---------------|
| PEP / MCC Risco | R16_pep, R17_high_risk_mcc | 3,315 |
| Geografia | R05_geojump | 2,119 |
| E-commerce / 3DS | R12_ecom_no_3ds, R13_eci_cross_border | 1,337 |
| Renda × Valor | R04_income_mismatch | 1,016 |
| Chargeback | R18_chargeback_merchant | 846 |
| Cash-in/out | R10_cash_in_out | 802 |
| Sanções / País Risco | R15_sanctions | 484 |
| País de Risco | R14_cross_border_high | 226 |
| Geografia/Device | R06_ip_anomaly | 201 |
| Comportamento | R19_installments_atypical, R20_new_account | 131 |
| Comportamento/Velocidade | R01_velocity, R02_burst_value | 90 |
| Structuring/Smurfing | R03_structuring | 4 |
| Device/IP Ring | R07_device_ring, R08_ip_ring, R22_card_multidevice | 3 |
| Self-Merchant | R09_self_merchant | 2 |
| Cash-in/out / Dispersão | R11_fan_out | 0 |
| Structuring | R21_round_values | 0 |

---

## 5. Distribuição por Severidade

| Severidade | Label | Alertas | % |
|-----------|-------|---------|---|
| 4 | crítica (4) | 13 | 0.1% |
| 3 | alta (3) | 4,025 | 38.1% |
| 2 | média (2) | 6,505 | 61.5% |
| 1 | baixa (1) | 33 | 0.3% |

---

## 6. Sinais de Risco Prioritários (candidatos ao SAR — Dia 3)

Candidatos priorizados por score + weak label (≥2 regras-core):

**1. C101208** — Score 22 pts | 7 regras | R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc
**2. C102093** — Score 21 pts | 8 regras | R04_income_mismatch,R05_geojump,R06_ip_anomaly,R10_cash_in_out,R12_ecom_no_3ds,R15_sanctions,R16_pep,R17_high_risk_mcc
**3. C101028** — Score 20 pts | 6 regras | R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc
**4. C100658** — Score 20 pts | 8 regras | R02_burst_value,R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc
**5. C100517** — Score 20 pts | 8 regras | R02_burst_value,R04_income_mismatch,R05_geojump,R10_cash_in_out,R12_ecom_no_3ds,R13_eci_cross_border,R15_sanctions,R17_high_risk_mcc

---

## 7. Próximos Passos (Dia 3 — Suspeitos & SAR)

- Selecionar ≤30 clientes a partir do ranking acima
- Construir visão 360° do caso #1 (entity_id com maior score + core_label)
- Mapear grafo de relacionamento (device, IP, merchant, contrapartes)
- Escrever 1 SAR completo (template-sar.md) com timeline e evidências

---

## 8. Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `outputs/alertas.csv` | Todos os alertas com evidence_ids |
| `outputs/ranking_risco.csv` | Ranking de risco por entidade |
| `outputs/02_relatorio_regras.md` | Este relatório |
| `outputs/figuras/02_alertas_por_regra.png` | Bar chart alertas × regra |
| `outputs/figuras/02_timeline_alertas.png` | Alertas por dia |
| `outputs/figuras/02_ranking_top20.png` | Top-20 por score |
| `outputs/figuras/02_distribuicao_scores.png` | Distribuição de scores |
| `data/processed/client_features_v2.csv` | Feature store completo (cliente) |
| `data/processed/merchant_features_v2.csv` | Feature store (merchant) |
| `data/processed/device_features.csv` | Feature store (device) |
| `data/processed/ip_features.csv` | Feature store (IP) |