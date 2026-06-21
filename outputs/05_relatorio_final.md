# Relatório Final — Sistema AML-FT CloudWalk

**Projeto:** Detecção de Lavagem de Dinheiro e Financiamento ao Terrorismo (AML/PLD-FT)
**Autor:** Victor OS — viictoros20@gmail.com
**Data:** 2026-06-21
**Repositório:** https://github.com/VictorOS1997/aml-case-cloudwalk
**Classificação:** Confidencial — Uso Interno

---

## 1. Resumo Executivo

Este relatório descreve o sistema AML-FT desenvolvido para detectar, investigar e recomendar ações
regulatórias sobre atividades suspeitas de lavagem de dinheiro e financiamento ao terrorismo na
base de transações CloudWalk — **52.000 transações**, R$ 230 milhões movimentados em PIX, Cartão
e Wire entre julho e outubro de 2025.

**Resultados em síntese:**

| Dimensão | Resultado |
|---|---|
| Base analisada | 52.000 transações · 2.500 clientes · 1.000 merchants · R$ 230M |
| Regras implementadas | **22 regras** em 9 frentes de risco |
| Alertas gerados | **10.576** (17 de 22 regras dispararam) |
| Entidades únicas alertadas | **3.475** (clientes + merchants) |
| Suspeitos detalhados | **Top 30** clientes por score de risco |
| SAR elaborado | **1 SAR completo** — Cliente C101208 (score 22/22) |
| Modelo ML (ROC-AUC) | **0.979** · PR-AUC **0.536** · Recall 93,3% |
| Caso principal | C101208 — 7 tipologias · 11,5× renda · sanção confirmada |

A abordagem combinou **regras determinísticas** (cobertura ampla), **rótulo fraco** (weak label de
6 regras-core) e **XGBoost + Isolation Forest** (generalização e detecção de anomalias não
cobertas por regras). Um **pipeline multi-agente LLM** de 5 estágios orquestra o ciclo da
detecção à decisão regulatória.

---

## 2. Achados Suspeitos e SAR (Tarefa 1)

### 2.1 Metodologia de identificação

Clientes foram ranqueados pela soma ponderada de regras acionadas × severidade, resultando em um
**score de risco de 0 a 22** (pontuação máxima). O Top 30 foi selecionado para análise aprofundada.

**Top 5 clientes suspeitos:**

| Rank | Cliente | Score | Tipologias principais | Volume (R$) |
|---|---|---|---|---|
| 1 | **C101208** | 22 | Sanções · Geo-salto · Renda incompat. · 3DS · Cross-border | 150.178 |
| 2 | C101991 | 20 | Renda incompat. · PEP · Geo-salto · MCC risco | 218.340 |
| 3 | C102339 | 19 | Sanções · E-com sem 3DS · Cash-in/out | 87.450 |
| 4 | M200815 | 18 | Self-merchant · Chargeback · Cross-border | 340.201 |
| 5 | C100847 | 17 | Geo-salto · Structuring · MCC risco | 65.730 |

**Tipologias identificadas no Top 30:**

| Tipologia | Clientes | Exemplo |
|---|---|---|
| Renda incompatível (>5× renda anual) | 18 | C101208 (11,5×) |
| Geo-salto (velocidade impossível) | 14 | C101208 (1.092 km/h BR→RU) |
| E-commerce sem 3DS (alto valor) | 12 | C101208, C102339 |
| Cross-border + ECI não-autenticado | 11 | C101208 (9 países) |
| Cash-in → Cash-out (PIX, 24h) | 10 | C101208, C100971 |
| Sanctions screening hit | 7 | C101208 (SY — Síria) |
| PEP ativo + MCC de alto risco | 5 | C101991 |
| Self-merchant | 2 | M200815 |

### 2.2 SAR — Cliente C101208 (Caso Principal)

**Classificação:** CRÍTICO | Score 22/22

Entre **2025-07-03** e **2025-09-29**, o cliente C101208 (Chef, renda declarada R$ 13.047/ano,
KYC Tier L1) realizou **29 transações** totalizando **R$ 150.178** — **11,5× sua renda anual**
— por PIX, Cartão e Wire em **8 países** (BR, PT, BY, SY, GB, ES, RU, YE).

**7 tipologias simultâneas:**
1. **Renda incompatível** — volume/renda = 11,5× (regra R04, severidade 3)
2. **Geo-salto** — 1.092 km/h BR→RU em 13h (física e logisticamente impossível)
3. **Cash-in → Cash-out PIX** — padrão de layering em 24h
4. **E-commerce sem 3DS** — 5 transações card-not-present sem autenticação forte
5. **Cross-border + ECI não-autenticado** — 9 transações internacionais com ECI de risco
6. **Sanctions hit** — transação TNHZDN7D6LYK6 com receptor em Síria (R15, severidade 4)
7. **MCC de alto risco** — 6011 (ATM/dinheiro), 7995 (jogos/apostas), 4789 (transporte)

**Ação recomendada:**
- **D+0:** Bloqueio preventivo da conta C101208
- **D+1:** Notificação formal ao Compliance Officer
- **D+3:** Avaliação de reporte ao COAF via SISCOAF (prazo: 24h após decisão)

SAR completo: `outputs/sar/SAR_C101208.md`

---

## 3. Sistema de Alertas (Tarefa 2)

### 3.1 Visão geral do motor de regras

**22 regras** em 9 frentes de risco, implementadas em `src/rules_engine.py` com limiares
configuráveis via `config/rules.yaml`.

| Métrica | Valor |
|---|---|
| Regras implementadas | 22 |
| Regras que dispararam | 17 (5 sem ocorrências na base) |
| Total de alertas | 10.576 |
| Entidades únicas | 3.475 |
| Weak label positivos | 108 clientes (3,3% da carteira) |

### 3.2 Catálogo de regras (seleção)

| Regra | Tipologia | Severidade | Alertas | Lógica resumida |
|---|---|---|---|---|
| R04_income_mismatch | Renda × Valor | 3 | 1.016 | Volume ≥ 5× renda anual |
| R05_geojump | Geo-Salto | 3 | 2.119 | Velocidade > 900 km/h entre tx |
| R09_self_merchant | Self-Merchant | 4 | 2 | cliente paga próprio merchant |
| R10_cash_in_out | Cash-in/out | 3 | 802 | saída ≥ 80% entrada PIX em 24h |
| R12_ecom_no_3ds | E-com sem 3DS | 3 | 572 | card-NP, 3DS=No, valor > limiar |
| R15_sanctions | Sanções | 4 | 484 | sanctions_screening_hit=Yes |
| R16_pep | PEP | 3 | 52 | pep_flag=True em tx |
| R17_high_risk_mcc | MCC Risco | 2 | 3.263 | MCC em {6011, 7995, 6051, 4789} |
| R18_chargeback | Chargeback | 2 | 846 | merchant com taxa CB elevada |

### 3.3 Falso-positivo controlado por contexto

Uma regra pode disparar isoladamente (ex.: R17 — MCC de alto risco) sem indicar lavagem real.
O sistema pondera: um merchant de ATM (MCC 6011) em bairro comercial com volume baixo não
dispara investigação — mas combinado com geo-salto + sanção + renda incompatível, eleva o score
ao máximo.

**Exemplo de triangulação (C101208):** R17 sozinha = alerta de baixa prioridade. R17 + R05 +
R15 + R04 = score 22, nível CRÍTICO.

---

## 4. Modelo de Machine Learning (Tarefa 3)

### 4.1 Arquitetura

Ensemble de dois modelos complementares:
- **XGBoost** (supervisionado fraco): aprende dos padrões das 6 regras-core
- **Isolation Forest** (não-supervisionado): captura anomalias fora do catálogo de regras

```
Score Final = 0,70 × XGBoost_proba + 0,30 × IF_score_normalizado
```

### 4.2 Rótulo fraco (weak label)

Cliente marcado `is_core_label=1` se acionar ≥ 2 regras-core de alta confiança:
R04, R05, R06, R10, R14, R15 — regras com menor taxa de falso-positivo.

**Dataset:** 3.310 clientes · 108 positivos (3,3%) · 44 features · split temporal (80/20)

### 4.3 Métricas (conjunto de teste)

| Métrica | Valor |
|---|---|
| **ROC-AUC** | **0,979** |
| **PR-AUC** | **0,536** (16× acima do baseline de 3,3%) |
| Threshold ótimo (max-F1) | 0,437 |
| Precisão | 0,318 |
| **Recall** | **0,933** (captura 14/15 suspeitos) |
| F1 | 0,475 |

> PR-AUC é a métrica-chave para bases desbalanceadas. O valor de 0,536 representa ganho
> real de 16× sobre o classificador aleatório (baseline = 3,3%).

### 4.4 Explicabilidade — C101208

SHAP drivers do score de C101208 (score final 0,797 — percentil 100%):

| Feature | SHAP | Direção |
|---|---|---|
| `n_high_risk_geo` | +0,744 | aumenta risco |
| `pct_high_risk_geo` | +0,378 | aumenta risco |
| `n_no_3ds` | +0,074 | aumenta risco |
| `pct_pix` | +0,026 | aumenta risco |

### 4.5 Distribuição de risco da carteira

| Tier | Score | Clientes | % |
|---|---|---|---|
| Baixo | 0–0,30 | 2.824 | 85,3% |
| Médio | 0,30–0,60 | 237 | 7,2% |
| Alto | 0,60–0,80 | 249 | 7,5% |

### 4.6 Limitações

1. **Rótulo ruidoso:** weak label derivado de regras — o modelo aprende as regras, não lavagem real
2. **Viés circular:** features correlacionadas com regras que geraram o rótulo
3. **Janela curta (3 meses):** não captura padrões sazonais ou layering multi-mês
4. **Score não calibrado:** probabilidades não interpretáveis diretamente sem calibração

---

## 5. Sistema Multi-Agente (Tarefa 4)

### 5.1 Arquitetura

5 agentes especializados + orquestrador, implementados como papéis LLM via Anthropic API:

```
Dados Brutos → [DADOS] → [DETECÇÃO] → [INVESTIGAÇÃO] → [REPORTE] → [COMPLIANCE] → Decisão
                  │            │               │               │             │
              qualidade    alertas+        caso 360°,      rascunho    approve/revise
              + enrich.   fila prio.      timeline,        de SAR      + base legal
                                          tipologias
```

**Orquestrador:** roteia estágios em sequência, salva artefatos JSON por estágio, registra
trilha de auditoria com timestamp, re-enfileira casos `revise` com motivos.

### 5.2 Agentes e prompts

| # | Agente | Papel | Temperatura |
|---|---|---|---|
| 1 | Dados | Valida schema, coerência por rail, enriquece geo/IP | 0,0 |
| 2 | Detecção | Avalia regras + ML, gera fila priorizada por score | 0,0 |
| 3 | Investigação | Caso 360°: timeline, grafo, tipologias, evidências | 0,2 |
| 4 | Reporte | Rascunho de SAR em 7 seções (markdown + JSON) | 0,4 |
| 5 | Compliance | Valida SAR, checa sanções, decide approve/revise | 0,0 |

Implementação: `src/agents/pipeline.py`
Prompts completos: system prompts no próprio arquivo (auto-documentado)

### 5.3 Resultado do teste em tempo real — C101208

```
[ORQUESTRADOR] Caso: C101208
[1/5] Dados       → qualidade ok, SY/RU/YE sinalizados como alto risco
[2/5] Detecção    → 7 regras acionadas, priority=39.6 (sanctions no topo)
[3/5] Investigação → CRITICO, 7 tipologias, geo-salto 14.341 km confirmado
[4/5] Reporte     → SAR draft 7 seções gerado (sar_agente.md)
[5/5] Compliance  → DECISION: APPROVE
                    Ação: report_coaf (comunicação ao SISCOAF)
                    Sanções: confirmadas (TNHZDN7D6LYK6 → SY)
                    SLA: D+3 (prazo de reporte)
```

Artefatos gerados: `outputs/sar/C101208/{00_auditoria, 01_dados, 02_deteccao, 03_investigacao,
04_reporte, 05_compliance}.json` + `sar_agente.md`

### 5.4 Visão de produto

O pipeline representa um **produto AML mínimo e completo**: recebe um caso priorizado pelo motor
de regras + score de ML e, em menos de 60 segundos, entrega uma decisão regulatória rastreável
com base legal, trilha de auditoria e prazo de SLA — reduzindo de horas (analista manual) para
segundos a triagem inicial de casos.

**Próximos passos para escala:**
- Orquestrador com fila priorizada via LangGraph (estado compartilhado, re-enfileiramento)
- Feedback loop: analista revisa → rótulo refinado → modelo atualizado
- Monitoramento de drift (PSI, KS test) e alertas de degradação do modelo

---

## 6. Conclusões

1. A base CloudWalk contém padrões de risco reais e diversificados — 17 de 22 regras dispararam
   alertas, evidenciando boa cobertura do catálogo.

2. O cliente C101208 é o caso de maior risco identificado: **7 tipologias simultâneas** em 3 rails,
   incluindo sanção confirmada — ação regulatória recomendada com alta confiança.

3. O modelo de ML (ROC-AUC 0,979, Recall 93,3%) demonstra que os padrões de comportamento
   suspeito são capturáveis por features comportamentais + geográficas, mesmo com rótulo fraco.

4. O pipeline multi-agente entrega rastreabilidade e defensabilidade regulatória — cada decisão
   cita evidências, IDs de transação e base legal.

5. **Limitações principais:** rótulo fraco (sem labels reais), janela temporal de 3 meses e
   ausência de feedback de investigadores humanos.

---

## Anexos

| Artefato | Caminho |
|---|---|
| Notebooks completos | `notebooks/01` a `04_*.py` |
| Motor de regras | `src/rules_engine.py` |
| Pipeline multi-agente | `src/agents/pipeline.py` |
| Catálogo de regras | `config/rules.yaml` |
| SAR completo C101208 | `outputs/sar/SAR_C101208.md` |
| SAR gerado pelo agente | `outputs/sar/C101208/sar_agente.md` |
| Scores ML | `outputs/04_ml_scores.csv` |
| Ranking de risco | `outputs/ranking_risco.csv` |
| Top 30 suspeitos | `outputs/suspeitos_top30.csv` |
| Alertas completos | `outputs/alertas.csv` |
| Figuras | `outputs/figuras/` |

---
*Relatório gerado em 2026-06-21 — Sistema AML-FT CloudWalk — Revisão humana obrigatória antes de qualquer ação regulatória.*
