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

## Guia para o Avaliador

Esta seção mapeia cada tarefa do case aos arquivos correspondentes no repositório.

### Tarefa 1 — Identificação de Suspeitos + SAR

| O quê | Onde encontrar |
|---|---|
| Script de investigação | `notebooks/03_suspeitos_sar.py` |
| Top 30 suspeitos (planilha) | `outputs/suspeitos_top30.csv` |
| Ranking de risco (4.156 entidades) | `outputs/ranking_risco.csv` |
| **SAR completo — C101208** | **`outputs/sar/SAR_C101208.md`** |
| Figuras do caso (grafo · geo-salto · timeline) | `outputs/figuras/03_*.png` |
| Resumo narrativo no relatório | `outputs/05_relatorio_final.md` §2 |

O SAR inclui: identificação do caso, narrativa executiva, 7 alertas acionados com IDs de transação,
linha do tempo de 29 transações, análise de geo-saltos, base legal (BACEN/COAF/FATF) e ações
recomendadas (D+0 → D+3).

### Tarefa 2 — Sistema de Alertas (22 regras)

| O quê | Onde encontrar |
|---|---|
| Motor de regras (implementação) | `src/rules_engine.py` |
| Limiares parametrizáveis | `config/rules.yaml` |
| Script de execução | `notebooks/02_regras_alertas.py` |
| **Catálogo completo das 22 regras** | **`outputs/02_relatorio_regras.md`** |
| Alertas gerados (10.576 linhas) | `outputs/alertas.csv` |
| Resumo no relatório | `outputs/05_relatorio_final.md` §3 |

O catálogo em `outputs/02_relatorio_regras.md` traz cada regra com: nome, tipologia, severidade,
lógica/condição, limiares, exemplo por ID de transação e justificativa de risco.

### Tarefa 3 — Modelo de Machine Learning

| O quê | Onde encontrar |
|---|---|
| Script de treino e avaliação | `notebooks/04_modelo_ml.py` |
| Implementação do modelo | `src/model.py` |
| Scores de risco (3.310 clientes) | `outputs/04_ml_scores.csv` |
| Feature store por entidade | `data/processed/sender_features.csv` |
| **Documentação técnica completa** | **`outputs/04_documentacao_modelo.md`** |
| Relatório com métricas e gráficos | `outputs/04_relatorio_ml.md` |
| Curvas ROC, PR, SHAP, calibração | `outputs/figuras/04_*.png` |
| Resumo no relatório final | `outputs/05_relatorio_final.md` §4 |

Label/alvo: weak label a partir de ≥2 regras-core (R03, R07, R09, R12, R15).
Validação: split temporal (80/20 por `first_tx_date`) + cross-validation 5-fold.

### Tarefa 4 — Sistema Multi-Agente (LLM)

| O quê | Onde encontrar |
|---|---|
| **Pipeline com prompts completos** | **`src/agents/pipeline.py`** |
| Demo sem API key (modo simulado) | `notebooks/05_agentes_pipeline.py` |
| Artefatos JSON por estágio (runtime) | `outputs/sar/C101208/` *(gerado ao executar com ANTHROPIC_API_KEY)* |
| SAR gerado pelo agente (runtime) | `outputs/sar/C101208/sar_agente.md` |
| Resumo no relatório | `outputs/05_relatorio_final.md` §5 |

Os 5 system prompts estão em `src/agents/pipeline.py` (auto-documentado).
Para executar o teste em tempo real: `python src/agents/pipeline.py --case C101208` (requer `ANTHROPIC_API_KEY`).
Para demo sem API key: `python notebooks/05_agentes_pipeline.py`.

### Relatório Final

| O quê | Onde encontrar |
|---|---|
| **Relatório em Markdown** | **`outputs/05_relatorio_final.md`** |
| Script para gerar DOCX | `relatorio/gerar_relatorio.py` |

O relatório cobre as 5 seções obrigatórias: resumo executivo · achados suspeitos + SAR ·
regras/alertas · modelo de ML · arquitetura multi-agente. Para gerar o arquivo DOCX:

```bash
pip install python-docx
python relatorio/gerar_relatorio.py
# Saída: relatorio/Relatorio_AML_FT_CloudWalk.docx
```

### Apresentação

| O quê | Onde encontrar |
|---|---|
| Roteiro de 12 slides (conteúdo completo) | `apresentacao/deck_outline.md` |
| Enunciado original do case | `apresentacao/pdf-case.pdf` |

O arquivo `deck_outline.md` contém o conteúdo integral de cada um dos 12 slides
(título, dados, tabelas, visuais e narrativa), estruturado para ser montado no Google Slides.

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

# Gerar relatório DOCX:
python relatorio/gerar_relatorio.py
```

**Seed:** `SEED = 42` em todos os módulos (`src/config.py`). Python 3.12+.

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
│   ├── 02_relatorio_regras.md     # catálogo completo das 22 regras (Tarefa 2)
│   ├── 04_ml_scores.csv           # score ML dos 3.310 clientes
│   ├── 04_documentacao_modelo.md  # documentação técnica do modelo
│   ├── 04_relatorio_ml.md         # relatório técnico ML
│   ├── 05_relatorio_final.md      # relatório técnico final (5–10 páginas)
│   ├── figuras/                   # gráficos (ROC, PR, SHAP, geo, timeline)
│   └── sar/
│       ├── SAR_C101208.md         # SAR completo (Tarefa 1) — COMITADO
│       └── C101208/               # artefatos do pipeline multi-agente (gerados em runtime)
│           ├── 00_auditoria.json  # ↑ produzidos por src/agents/pipeline.py
│           ├── 01_dados.json      #   ao rodar com ANTHROPIC_API_KEY definida.
│           ├── 02_deteccao.json   #   Não comitados — execução real exige a chave.
│           ├── 03_investigacao.json
│           ├── 04_reporte.json
│           ├── 05_compliance.json
│           └── sar_agente.md      # SAR gerado pelo Agente de Reporte
├── relatorio/
│   └── gerar_relatorio.py         # script de geração do relatório DOCX
└── apresentacao/
    ├── deck_outline.md            # roteiro completo dos 12 slides (Tarefa Apresentação)
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

Catálogo completo com lógica, limiares, exemplo por ID e justificativa: `outputs/02_relatorio_regras.md`

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

O CV é a referência (estável, sem dependência de um split específico). Discussão completa em
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

Os 5 system prompts estão no próprio `src/agents/pipeline.py` (auto-documentado).

---

## Reprodutibilidade

- `SEED = 42` definido em `src/config.py` e importado por todos os módulos
- `requirements.txt` com versões fixas
- Dados originais em `data/raw/` (gitignored — não sobem ao repo)
- Coerência por rail validada e reportada no script `notebooks/01_eda_qualidade.py`
  (saída em `outputs/01_relatorio_eda.md`)

---

## Documentação

| Arquivo | Conteúdo |
|---|---|
| `outputs/05_relatorio_final.md` | Relatório técnico completo (5–10 páginas) |
| `outputs/02_relatorio_regras.md` | Catálogo das 22 regras com lógica, limiares e exemplos (Tarefa 2) |
| `outputs/04_documentacao_modelo.md` | Documentação técnica do modelo ML (Tarefa 3) |
| `outputs/04_relatorio_ml.md` | Relatório de métricas e gráficos do modelo |
| `outputs/sar/SAR_C101208.md` | SAR completo do caso principal (Tarefa 1) |
| `apresentacao/deck_outline.md` | Roteiro dos 12 slides da apresentação |
| `relatorio/gerar_relatorio.py` | Script para gerar `Relatorio_AML_FT_CloudWalk.docx` |

---

**Status:** Completo — 5 dias | **Seed:** 42 | **Python:** 3.12+
