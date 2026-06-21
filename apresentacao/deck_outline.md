# Deck — Sistema AML-FT CloudWalk
**Google Slides — 12 slides**
**Roteiro:** Objetivo → Dados → Raciocínio → Suspeitos+SAR → Alertas → ML → Multi-agente → Conclusões

---

## Slide 1 — Capa

**Título:** Sistema AML-FT CloudWalk
**Subtítulo:** Detecção de Lavagem de Dinheiro e Financiamento ao Terrorismo em Trilhos PIX · Cartão · Wire
**Autor:** Victor OS | viictoros20@gmail.com
**Data:** Junho 2026

---

## Slide 2 — Objetivo e Escopo

**Título:** Missão: Pipeline AML-FT de ponta a ponta

**Conteúdo:**
- **Base:** 52.000 transações · R$ 230M · PIX, Cartão, Wire · Jul–Out/2025
- **Objetivo:** Detectar, investigar e recomendar ação regulatória sobre atividades suspeitas

**4 tarefas integradas:**
1. Identificação de suspeitos + SAR completo
2. Motor de regras (≥15 regras)
3. Modelo de Machine Learning com score por cliente
4. Pipeline multi-agente LLM da detecção à decisão

---

## Slide 3 — Dados e Qualidade

**Título:** Base: 52.000 transações em 3 trilhos

**Tabela:**
| Dimensão | Valor |
|---|---|
| Transações | 52.000 |
| Valor total | R$ 230,057,857 |
| Clientes (KYC) | 2.500 |
| Merchants | 1.000 |
| Período | 95 dias (Jul–Out/2025) |
| Rails | PIX · Cartão · Wire |

**Coerência por rail validada:** campos como ECI/parcelas exclusivos de Cartão; contraparte obrigatória em PIX/Wire.

*Figura: distribuição de volume por rail*

---

## Slide 4 — Motor de Regras (Tarefa 2)

**Título:** 22 regras · 10.576 alertas · 9 frentes de risco

**Tabela selecionada:**
| Regra | Tipologia | Sev | Alertas |
|---|---|---|---|
| R05_geojump | Geo-salto | 3 | 2.119 |
| R17_high_risk_mcc | MCC risco | 2 | 3.263 |
| R15_sanctions | Sanções | 4 | 484 |
| R04_income_mismatch | Renda incompat. | 3 | 1.016 |
| R12_ecom_no_3ds | E-com sem 3DS | 3 | 572 |

**Princípio:** uma regra isolada raramente é suficiente — a triangulação de 3+ regras eleva a
confiança e reduz falsos positivos.

---

## Slide 5 — Top 30 Suspeitos (Tarefa 1)

**Título:** Top 30 clientes por score de risco

**Visual:** gráfico de barras com top 10, destacando C101208 no topo com score 22/22

**Tipologias encontradas:**
- Renda incompatível (18 clientes)
- Geo-salto velocidade impossível (14)
- E-commerce sem 3DS (12)
- Cash-in → Cash-out PIX (10)
- Sanctions hit (7)
- PEP + MCC risco (5)
- Self-merchant (2)

---

## Slide 6 — SAR: Caso C101208 (Tarefa 1)

**Título:** C101208 — Score 22/22 — 7 Tipologias Simultâneas

**Perfil:**
- Chef · Renda R$ 13.047/ano · KYC L1
- 29 transações · R$ 150.178 (11,5× renda) · 8 países

**7 tipologias:** Renda incompat. · Geo-salto · Cash-in→out · E-com sem 3DS · Cross-border · Sanções · MCC risco

**Visual: mapa de geo-salto**
- BR → RU → BR em 25h (15.907 km, 635 km/h)
- BR → SY (Wire TNHZDN7D6LYK6 — sanção confirmada)

**Ação:** D+0 bloqueio · D+1 Compliance · D+3 COAF/SISCOAF

---

## Slide 7 — Evidências Visuais (C101208)

**Título:** Evidências: Grafo · Timeline · SHAP

**3 painéis:**
1. Grafo de conexões (client ↔ device ↔ merchant) — `03_grafo_conexoes.png`
2. Timeline de transações com marcação de sanção — `03_timeline_C101208.png`
3. SHAP waterfall C101208: `n_high_risk_geo` (+0,744) domina o score — `04_shap_C101208.png`

---

## Slide 8 — Modelo de Machine Learning (Tarefa 3)

**Título:** XGBoost + Isolation Forest — ROC-AUC 0,979

**Arquitetura:**
```
Weak Label (6 regras-core)
        ↓
XGBoost (70%) + Isolation Forest (30%)
        ↓
Score Final por cliente [0–1]
```

**Métricas:**
| Métrica | Valor |
|---|---|
| ROC-AUC | **0,979** |
| PR-AUC | **0,536** (16× baseline) |
| Recall | **93,3%** |
| F1 | 0,475 |

*C101208: percentil 100% — topo da carteira*

*Figura: curva PR e cutoff curve*

---

## Slide 9 — Distribuição de Risco

**Título:** 85% da carteira em baixo risco · 7,5% no tier alto

**Gráfico:** distribuição de score final (histograma)

| Tier | Clientes | % |
|---|---|---|
| Baixo (0–0,30) | 2.824 | 85,3% |
| Médio (0,30–0,60) | 237 | 7,2% |
| Alto (0,60–0,80) | 249 | 7,5% |

**Curva de cutoff:** threshold 0,437 → Recall 93,3% com 30 FP (operacional)

---

## Slide 10 — Sistema Multi-Agente (Tarefa 4)

**Título:** Pipeline LLM: da detecção à decisão em <60s

**Diagrama de fluxo:**
```
[Dados] → [Detecção] → [Investigação] → [Reporte] → [Compliance]
                                                           ↓
                                                    approve / revise
```

**5 agentes especializados:**
| Agente | Papel | Temperatura |
|---|---|---|
| Dados | Valida + enriquece | 0,0 |
| Detecção | Regras + ML → fila prio. | 0,0 |
| Investigação | Caso 360°, tipologias | 0,2 |
| Reporte | SAR em 7 seções | 0,4 |
| Compliance | Validação regulatória | 0,0 |

**Resultado C101208:** APPROVE · report_coaf · sanção confirmada · SLA D+3

---

## Slide 11 — Resultado do Teste em Tempo Real

**Título:** Teste real: C101208 processado em <60s

**Output do pipeline (captura de tela ou texto formatado):**
```
[1/5] DADOS       → qualidade ok · países risco: SY, RU, YE, BY
[2/5] DETECÇÃO    → 7 regras · priority=39.6 · SANÇÃO no topo
[3/5] INVESTIGAÇÃO → CRÍTICO · 7 tipologias · geo-jump 14.341km
[4/5] REPORTE     → SAR draft 7 seções · layering confirmado
[5/5] COMPLIANCE  → APPROVE · report_coaf · SLA D+3
```

Artefatos JSON versionados por estágio: `outputs/sar/C101208/`

---

## Slide 12 — Conclusões e Próximos Passos

**Título:** Sistema AML-FT: completo, explicável, defensável

**O que entregamos:**
- 22 regras · 10.576 alertas · cobertura em 9 frentes de risco
- 1 SAR completo com 7 tipologias e evidências por ID
- Modelo ML com Recall 93,3% e PR-AUC 16× acima do baseline
- Pipeline multi-agente da detecção à decisão regulatória em <60s

**Limitações honestas:**
- Rótulo fraco (sem labels reais de investigadores)
- Janela de 3 meses — sem sazonalidade
- Score ML não calibrado (uso operacional requer Platt/isotônica)

**Próximos passos:**
- Feedback loop: analista revisa → rótulo refinado
- LangGraph para orquestração com estado e fila persistente
- Graph Neural Network sobre rede de contrapartes
- Monitoramento de data drift em produção

---

*GitHub: https://github.com/VictorOS1997/aml-case-cloudwalk*
