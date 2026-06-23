# Dia 4 — Relatório Técnico: Modelo de Machine Learning

_Gerado em: 2026-06-21 01:13_

---

## 1. Objetivo

Construir um modelo que **priorize risco por cliente**, combinando comportamento transacional,
perfil KYC e sinais geográficos/dispositivo. A abordagem usa **rótulo fraco** (weak label) —
derivado das regras de alta confiança do Dia 2 — como proxy de fraude/lavagem, complementado
por **Isolation Forest** (não-supervisionado) para capturar anomalias não cobertas pelas regras.

---

## 2. Dados e Rótulo

| Dimensão | Valor |
|---|---|
| Clientes no dataset | 3,310 |
| Features utilizadas | 44 |
| Positivos (is_core_label=1) | 108 (3.3%) |
| Negativos | 3202 |
| Janela temporal das transações | Jul/2025 – Out/2025 |
| Corte treino/teste (first_tx_date) | 2025-07-12 (percentil 80%) |
| Clientes no treino | 2,648 (positivos: 93) |
| Clientes no teste | 662 (positivos: 15) |

**Critério do rótulo fraco (canônico em `src/rules_engine.py`, `CORE_RULES`, linha 82):**
cliente é marcado `is_core_label = 1` se acionar **≥ 2 regras-core de alta confiança**:
**R03_structuring, R07_device_ring, R09_self_merchant, R12_ecom_no_3ds, R15_sanctions** —
5 regras com menor taxa de falso-positivo (severidades 3 e 4).

---

## 3. Arquitetura do Modelo

### 3.1 XGBoost (supervisionado com rótulo fraco)

```
n_estimators : 400 (early stopping = 30)
best_iteration: 21
max_depth    : 4
learning_rate: 0.05
scale_pos_weight: 27.5  # compensa desbalanceamento
eval_metric  : aucpr
SEED         : 42
```

### 3.2 Isolation Forest (não-supervisionado)

```
n_estimators : 300
contamination: 0.05  # ~5% anomalias esperadas
SEED         : 42
```

### 3.3 Score final (ensemble)

```
final_score = 0.70 × XGBoost_proba + 0.30 × IF_score_normalizado
```

O peso 70/30 prioriza o sinal supervisionado (mais calibrado) com um complemento
não-supervisionado para anomalias não cobertas pelo rótulo fraco.

---

## 4. Métricas de Avaliação

| Métrica | Teste único | Cross-validation (5-fold) |
|---|---|---|
| **ROC-AUC** | **0.9793** | 0.9559 ± 0.0074 |
| **PR-AUC**  | **0.5359** | **0.3127 ± 0.0484** |
| Threshold ótimo (max-F1) | 0.437 | — |
| Precisão @ threshold     | 0.318 | — |
| Recall @ threshold       | 0.933 | — |
| F1 @ threshold           | 0.475 | — |
| Verdadeiros Positivos    | 14 | — |
| Falsos Positivos         | 30 | — |
| Falsos Negativos         | 1  | — |
| Verdadeiros Negativos    | 617 | — |

> **Nota:** PR-AUC é a métrica-chave em bases desbalanceadas (baseline = 3,3%). O **CV é a
> referência** — o teste único deu PR-AUC mais alto por sorteio favorável do conjunto de teste.
> Permutation test (15 execuções com labels embaralhados) deu p < 0,01, confirmando sinal real.
> Discussão completa em `outputs/04_documentacao_modelo.md` §6–§7.

---

## 5. Top-5 Features (Gain — XGBoost)

| Rank | Feature | Importância (Gain) |
|---|---|---|
| 1 | `n_high_risk_geo` | 0.3822 |
| 2 | `pct_high_risk_geo` | 0.2831 |
| 3 | `n_cross_border` | 0.0292 |
| 4 | `pct_no_3ds_card` | 0.0286 |
| 5 | `cash_through_ratio` | 0.0213 |

---

## 6. Explicabilidade — SHAP

O SHAP (SHapley Additive exPlanations) quantifica a **contribuição marginal de cada feature**
para o score de cada cliente. Os gráficos gerados:

- `04_shap_summary.png` — visão global: quais features mais impactam (e em que direção)
- `04_shap_C101208.png` — waterfall do caso SAR (C101208)

**C101208** obteve score XGB = 0.7848 | IF = 0.8263 | Final = 0.7973
(percentil 100.0% — entre os 0.0% mais suspeitos da carteira)

Principais drivers do score de C101208 via SHAP:

- **`n_high_risk_geo`** → SHAP=+0.7445 (aumenta risco)
- **`pct_high_risk_geo`** → SHAP=+0.3782 (aumenta risco)
- **`n_no_3ds`** → SHAP=+0.0745 (aumenta risco)
- **`pct_pix`** → SHAP=+0.0261 (aumenta risco)
- **`n_cross_border`** → SHAP=+0.0192 (aumenta risco)

---

## 7. Isolation Forest

- Score médio (clientes normais): 0.2871
- Score médio (suspeitos weak label): 0.3855

O IF captura **clientes com padrão incomum mesmo sem regras acionadas** — útil para detecção
de tipologias emergentes não cobertas pelo catálogo de regras.

---

## 8. Distribuição de Risco (Score Final)

| Tier | Score | Clientes | % |
|---|---|---|---|
| baixo | 0–0.30 | 2824 | 85.3% |
| medio | 0.30–0.60 | 237 | 7.2% |
| alto | 0.60–0.80 | 249 | 7.5% |
| critico | 0.80–1.00 | 0 | 0.0% |

---

## 9. Limitações e Vieses

1. **Rótulo fraco (ruidoso):** o `is_core_label` é gerado por regras heurísticas, não por
   investigação humana. O modelo aprende a replicar as regras, não a detectar lavagem real.

2. **Viés circular:** features derivadas de comportamento transacional parcialmente correlacionam
   com as próprias regras que geraram o rótulo. O modelo pode super-estimar o desempenho.

3. **Split temporal limitado:** a janela de 3 meses é curta. Com dados históricos mais longos,
   o modelo capturaria drift sazonal e padrões de longo prazo (ex.: layering multi-mês).

4. **Calibragem:** os scores do XGBoost não são probabilidades calibradas. Para uso operacional,
   recomenda-se calibração isotônica ou Platt scaling.

5. **Ausência de labels reais:** sem confirmação de investigadores ou decisões judiciais,
   PR-AUC e F1 medem apenas consistência com as regras, não detecção real de crime.

---

## 10. Próximos Passos (Stretch)

- Calibração Platt/isotônica para converter scores em probabilidades confiáveis
- LightGBM com feature interactions explícitas
- Graph Neural Network sobre o grafo de contrapartes
- Retraining pipeline com monitoramento de data drift (PSI, KS test)
- Feedback loop com decisões de analistas para refinar o rótulo fraco

---

## 11. Reprodutibilidade

```bash
SEED = 42  # numpy, xgboost, sklearn
python notebooks/04_modelo_ml.py
# Requer: scikit-learn>=1.9, xgboost>=3.3, shap>=0.52, pandas>=2.0
```

_Outputs: `outputs/04_ml_scores.csv` · `outputs/figuras/04_*.png`_