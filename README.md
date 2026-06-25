# AML-FT Case — CloudWalk

**Detecção de Lavagem de Dinheiro e Financiamento ao Terrorismo (PIX · Cartão · Wire)**

> Pipeline AML-FT completo: regras de alerta + ML + sistema multi-agente LLM, da detecção à
> decisão regulatória — desenvolvido como case técnico para a CloudWalk.

---

## Resultados em síntese

| Entregável | Resultado-chave |
|---|---|
| **Base analisada** | 52.000 tx · 2.500 perfis KYC · 3.310 senders únicos · 3 rails |
| **Motor de regras** | 22 regras (17 dispararam) · 10.576 alertas · 10 frentes de risco |
| **Suspeitos** | Top 30 clientes (4.156 entidades ranqueadas) · 11 tipologias distintas |
| **SAR** | 1 SAR completo — C101208 (score 22/22, 7 tipologias convergentes, sanção confirmada) |
| **Modelo ML** | XGBoost + IF · ROC-AUC **0,979** (CV 0,956) · PR-AUC **0,536** (CV 0,313, ~9,6× baseline) · Recall **93%** |
| **Multi-agente** | 5 agentes + orquestrador · C101208 → APPROVE · report_coaf · D+3 |

---

## Caso principal — C101208

Cliente Chef, renda declarada R$ 13.047/ano, movimentou **R$ 150.178 (11,5× renda)** em 29
transações via PIX, Cartão e Wire em **8 países**, acionando **7 tipologias simultâneas**:

- Renda incompatível (11,5× renda anual)
- Geo-salto com velocidade física impossível (1.092 km/h BR→RU)
- Cash-in → Cash-out PIX (layering)
- E-commerce sem autenticação 3DS
- Cross-border + ECI não-autenticado
- Sanctions screening hit (transação para Síria — lista ONU)
- MCC de alto risco (6011, 7995, 4789)

**Score de risco:** 22/22 (máximo) · percentil 100% no modelo ML · Decisão: APPROVE → COAF

---

## Quick Start

```bash
# Clone e instale dependências
git clone https://github.com/VictorOS1997/aml-case-cloudwalk.git
cd aml-case-cloudwalk
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Reproduzir os resultados em sequência:
python notebooks/01_eda_qualidade.py      # EDA e feature store
python notebooks/02_regras_alertas.py    # 22 regras · 10.576 alertas
python notebooks/03_suspeitos_sar.py     # Top 30 + SAR C101208
python notebooks/04_modelo_ml.py         # XGBoost + IF · ROC-AUC 0.979

# Pipeline multi-agente (requer ANTHROPIC_API_KEY)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python src/agents/pipeline.py --case C101208

# Sem API key (modo simulado):
python notebooks/05_agentes_pipeline.py
```

**Seed:** `SEED = 42` em todos os módulos. Python 3.12+.

---

## Estrutura

```
aml-case-cloudwalk/
├── config/
│   └── rules.yaml                 # limiares parametrizáveis
├── data/
│   ├── raw/                       # base original (gitignored)
│   └── processed/                 # feature store, scores
│       ├── sender_features.csv
│       └── merchant_features.csv
├── notebooks/
│   ├── 01_eda_qualidade.py        # EDA + coerência por rail
│   ├── 02_regras_alertas.py       # motor de 22 regras
│   ├── 03_suspeitos_sar.py        # Top 30 + SAR C101208
│   ├── 04_modelo_ml.py            # XGBoost + Isolation Forest + SHAP
│   └── 05_agentes_pipeline.py     # demo do pipeline multi-agente
├── src/
│   ├── config.py                  # SEED e constantes globais
│   ├── rules_engine.py            # motor de regras
│   ├── features.py                # feature store
│   ├── model.py                   # treino e avaliação ML
│   └── agents/
│       └── pipeline.py            # 5 agentes + orquestrador (Tarefa 4)
├── outputs/
│   ├── alertas.csv                # todos os alertas gerados
│   ├── ranking_risco.csv          # score por entidade
│   ├── suspeitos_top30.csv        # top 30 suspeitos
│   ├── 01_quality_report.csv      # relatório de qualidade dos dados
│   ├── 01_relatorio_eda.md        # relatório EDA
│   ├── 02_relatorio_regras.md     # relatório motor de regras
│   ├── 04_ml_scores.csv           # score ML dos 3.310 clientes
│   ├── 04_documentacao_modelo.md  # documentação técnica do modelo
│   ├── 04_relatorio_ml.md         # relatório técnico ML
│   ├── 05_relatorio_final.md      # relatório técnico final (5–10 páginas)
│   ├── figuras/                   # gráficos (ROC, PR, SHAP, geo, timeline)
│   └── sar/
│       ├── SAR_C101208.md         # SAR completo (Dia 3, analista) — COMITADO
│       └── C101208/               # artefatos do pipeline multi-agente (gerados em runtime)
│           ├── 00_auditoria.json  # ↑ produzidos por src/agents/pipeline.py
│           ├── 01_dados.json      #   ao rodar com ANTHROPIC_API_KEY definida.
│           ├── 02_deteccao.json   #   Não comitados — execução real exige a chave.
│           ├── 03_investigacao.json
│           ├── 04_reporte.json
│           ├── 05_compliance.json
│           └── sar_agente.md      # SAR gerado pelo Agente de Reporte
├── relatorio/
│   └── gerar_relatorio.py         # script de geração do relatório DOCX/PDF
└── apresentacao/
    ├── deck_outline.md            # roteiro do Google Slides (12 slides)
    └── pdf-case.pdf               # enunciado do case
```

---

## Motor de Regras (Tarefa 2)

22 regras em 10 frentes, com limiares em `config/rules.yaml`. 17 das 22 dispararam na base
(R01, R07, R08, R11, R21 não tiveram hits — preservadas no catálogo para cobertura).

| Frente | Regras | Alertas |
|---|---|---|
| Comportamento/Velocidade | R01, R02, R20 | 188 |
| Structuring | R03, R21 | 4 |
| Renda × Valor | R04 | 1.016 |
| Geografia | R05, R06, R14 | 2.546 |
| Device/IP | R07, R08, R22 | 3 |
| Self-Merchant | R09 | 2 |
| Cash-in/out | R10, R11 | 802 |
| E-commerce / 3DS | R12, R13 | 1.337 |
| PEP / MCC / Chargeback / Sanções | R15, R16, R17, R18 | 4.645 |
| Parcelamento atípico | R19 | 33 |
| **Total** | **22** | **10.576** |

---

## Modelo ML (Tarefa 3)

**Arquitetura:** XGBoost supervisionado (weak label) + Isolation Forest (anomalias)
```
Score Final = 0,70 × XGB_proba + 0,30 × IF_normalizado
```

**Weak label:** cliente com ≥2 core rules de alta confiança (R03_structuring, R07_device_ring,
R09_self_merchant, R12_ecom_no_3ds, R15_sanctions) → `is_core_label = 1`. Resulta em 108
positivos / 3.310 clientes (3,3% — base desbalanceada). Definição canônica em
`src/rules_engine.py` (`CORE_RULES`, linha 82).

| Métrica | Teste único | Cross-validation (5-fold) |
|---|---|---|
| ROC-AUC | 0,9793 | 0,9559 ± 0,0074 |
| PR-AUC | 0,5359 | 0,3127 ± 0,0484 (~9,6× baseline 0,0326) |
| Recall @ threshold 0,437 | 93% | — |
| Precisão @ threshold 0,437 | 32% | — |
| Clientes no tier "alto" | 249 (7,5%) | — |

O CV é a referência (estável, sem dependência de um split específico). O teste único deu
PR-AUC mais alto por sorteio favorável do conjunto de teste — discussão completa em
`outputs/04_documentacao_modelo.md` §6.

---

## Pipeline Multi-Agente (Tarefa 4)

```
[Dados] → [Detecção] → [Investigação] → [Reporte] → [Compliance] → approve/revise
  t=0,0      t=0,0          t=0,2          t=0,4         t=0,0
```

Cada agente recebe a saída do anterior como entrada. O orquestrador salva artefatos JSON por
estágio e registra trilha de auditoria. Casos `revise` são re-enfileirados com motivos.

**Resultado C101208:** APPROVE → `report_coaf` → SLA D+3 (prazo COAF)

---

## Reprodutibilidade

- `SEED = 42` definido em `src/config.py` e importado por todos os módulos
- `requirements.txt` com versões fixas
- Dados originais em `data/raw/` (gitignored — não sobem ao repo)
- Coerência por rail validada e reportada no script `notebooks/01_eda_qualidade.py`
  (saída em `outputs/01_relatorio_eda.md`)

---

## Documentação

- `outputs/05_relatorio_final.md` — relatório técnico completo (5–10 páginas)
- `apresentacao/deck_outline.md` — roteiro do Google Slides (12 slides)
- `outputs/sar/SAR_C101208.md` — SAR completo do caso principal
- `outputs/04_relatorio_ml.md` — relatório técnico do modelo ML

---

**Status:** Completo — 5 dias | **Seed:** 42 | **Python:** 3.12+
