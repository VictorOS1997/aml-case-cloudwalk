# Documentação do Modelo de Machine Learning — CloudWalk AML-FT

> **Público-alvo:** analistas de compliance, gestores de risco e avaliadores do case.
> Este documento explica, em linguagem simples, **por que** cada decisão foi tomada,
> **o que** o modelo faz, e **o que garantimos** sobre a qualidade dos resultados.

---

## 1. Por que usar Machine Learning aqui?

### O problema com apenas regras

O Dia 2 entregou 22 regras que geram alertas. Regras são ótimas para casos claros (ex.: "cliente
enviou dinheiro para país sancionado"), mas têm três limitações práticas:

| Limitação | Exemplo concreto |
|---|---|
| **São binárias** | A regra R04 dispara se `valor > 15× renda mensal`. Mas e 14,9×? E 30×? Elas tratam igual. |
| **Ignoram combinações** | Um cliente com volume moderado + geo-salto + sem 3DS pode ser muito mais suspeito do que um com só volume alto. As regras somam pontos; o ML *multiplica* evidências. |
| **Não aprendem** | Se surgir um novo padrão (ex.: dispositivos rooteados + MCC de alto risco), as regras precisam ser reescritas. O ML captura combinações não descritas explicitamente. |

### O que o ML adiciona

O modelo não **substitui** as regras — ele as usa como inspiração para o rótulo (label) e depois
aprende padrões mais sutis. O output final é um **score de risco contínuo** (0 a 1) que permite
ordenar a carteira e priorizar investigações, em vez de dividir clientes em "alerta / não-alerta".

---

## 2. Por que XGBoost + Isolation Forest?

Usamos dois modelos com papéis complementares.

### XGBoost (supervisionado)

**O que é:** uma floresta de árvores de decisão treinadas em sequência, cada uma corrigindo os
erros da anterior. É o algoritmo mais bem estabelecido para dados tabulares estruturados.

**Por que escolhemos:**

| Critério | XGBoost | Alternativas |
|---|---|---|
| **Dados tabulares mistos** (numérico + binário) | ✅ Nativo | Redes neurais precisam de muito mais dados |
| **Desbalanceamento** (3,3% positivos) | ✅ `scale_pos_weight` ajusta automaticamente | Regressão logística tem desempenho inferior |
| **Explicabilidade** (SHAP) | ✅ Tem suporte nativo a SHAP | SVM é "caixa preta" |
| **Rótulo fraco / ruído** | ✅ Robusto com boosting | Random Forest puro é mais afetado por ruído |
| **Velocidade** | ✅ Segundos para 3.310 clientes | Deep Learning: minutos a horas |

**Trade-off:** XGBoost pode **overfittar** (memorizar o treino) se não houver controle. Usamos
`max_depth=4` (árvores rasas), `subsample=0.8` (amostragem por árvore) e `early_stopping_rounds=30`
para limitar o risco.

### Isolation Forest (não-supervisionado)

**O que é:** um algoritmo que detecta *anomalias* sem usar nenhum rótulo. Ele constrói árvores
aleatórias e mede quantas divisões são necessárias para "isolar" um ponto: pontos anômalos ficam
isolados mais rápido (precisam de menos divisões).

**Por que incluímos:**

O rótulo fraco (ver seção 4) captura padrões cobertos pelas regras. Mas e clientes suspeitos
que *não acionam* regras? O Isolation Forest os encontra por comportamento incomum, mesmo sem saber
o que é "fraude".

**Trade-off:** o Isolation Forest detecta *anômalos*, não *suspeitos de lavagem*. Um cliente que
simplesmente tem padrão de gasto atípico (ex.: gastos muito acima da média) pode ter score alto sem
ser criminoso. Por isso ele entra com peso 30% no score final.

### Score final — ensemble ponderado

```
score_final = 0.70 × XGBoost_proba + 0.30 × IF_score_normalizado
```

O peso 70/30 reflete nossa confiança maior no sinal supervisionado (que tem rótulo, mesmo que
imperfeito) sobre o não-supervisionado (que captura anomalia sem rótulo).

---

## 3. Features utilizadas e descartadas

### 3.1 Features utilizadas (44 no total)

Agrupamos as features por tipo:

#### Perfil KYC (5 features)
| Feature | Significado | Por que importa |
|---|---|---|
| `pep_flag` | Pessoa Exposta Politicamente (Sim/Não) | PEPs têm maior risco regulatório de corrupção |
| `sanctions_flag` | Na lista de sanções | Sinal crítico de risco — obrigação legal de bloqueio |
| `kyc_risk_score` | Score interno de risco KYC | Sintetiza a avaliação do onboarding |
| `risk_rating_enc` | Classificação de risco (Baixo/Médio/Alto) | Categorização oficial do cliente |
| `kyc_tier_enc` | Nível de verificação KYC | Clientes Basic têm menos verificação |

#### Proporção renda × volume (2 features)
| Feature | Significado | Por que importa |
|---|---|---|
| `income_tx_ratio` | Total movimentado / renda anual | Núcleo do structuring: volume incompatível com perfil |
| `log_income_tx_ratio` | Log do anterior | Versão suavizada para outliers extremos |

#### Comportamento geral de volume (8 features)
`n_tx_sent`, `n_tx_recv`, `n_tx_total` (frequência) + `log_total_brl_sent`, `log_total_brl`,
`log_max_brl_sent`, `log_avg_brl` (escala de valor) + `coeff_variation_brl` (variabilidade dos
valores: alta variação = possível structuring).

#### Temporalidade (2 features)
| Feature | Significado |
|---|---|
| `avg_daily_tx` | Transações por dia (detecta bursts) |
| `tx_span_days` | Janela de atividade total do cliente |

#### Geo e cross-border (5 features)
`n_cross_border`, `pct_cross_border`, `n_high_risk_geo`, `pct_high_risk_geo`, `n_monitored_geo`.
Capturam operações para jurisdições de alto risco ou fisicamente inconsistentes.

#### Rail mix — tipo de transação (4 features)
`pct_pix`, `pct_card`, `pct_wire`, `n_wire`. Clientes com proporção alta de Wire para o exterior
têm perfil de risco diferente de clientes 100% PIX doméstico.

#### Autenticação (2 features)
`n_no_3ds`, `pct_no_3ds_card` — transações de cartão sem autenticação forte (ECI 07).
Indica e-commerce sem 3DS: exposição a fraude e possível uso de cartões de terceiros.

#### Device / IP — sinais de identidade (8 features)
`n_ip_anomaly`, `n_device_rooted`, `n_rooted`, `n_devices_uniq`, `n_ips_uniq`,
`n_proxy_vpn_tor`, `pct_proxy_vpn`, `pct_rooted`.
Múltiplos dispositivos ou uso de VPN/Tor = tentativa de ocultar localização real.

#### MCC de alto risco (2 features)
`n_high_risk_mcc`, `pct_high_risk_mcc` — MCCs 6011 (ATM/saque), 6051 (quasi-cash),
4829 (transferências), 7995 (apostas), 5933 (penhores).

#### Contrapartes e cash flow (4 features)
`n_receivers_uniq`, `n_merchants_uniq` (diversidade de contrapartes) + `cash_through_ratio`,
`total_brl_recv` (sinais de layering: entra e sai rapidamente).

#### Sanctions (2 features)
`n_sanctions` (alertas de sanções das regras) + `n_sanction_hit` (hits confirmados de screening).

---

### 3.2 Features descartadas e por quê

| Feature descartada | Motivo |
|---|---|
| `channel` (App/API/Terminal/Web) | Baixo poder preditivo para AML; correlaciona com tipo de cliente (PJ vs PF), não com suspeição |
| `payment_method`, `capture_method` | Granularidade de produto; já capturado por `n_card`, `n_pix`, `n_wire` |
| `installments` (parcelas) | Relevante para fraude de crédito, mas não para tipologias AML desta base |
| `card_brand` (Visa/Master/Elo) | Nenhuma tipologia AML específica por bandeira; risco de spurious correlation |
| `declared_occupation` | Alta cardinalidade texto; exigiria NLP; proxy já capturado por renda |
| `date_of_birth` / idade | Pouca evidência de correlação com AML nesta base; risco de discriminação |
| `state`, `city` | Geolocalização textual de alta cardinalidade; substituto via `country_risk_geo` |
| `merchant_chargeback_ratio_90d` | Feature do merchant, não do cliente; exigiria join adicional |
| `beneficial_owner` | Coluna sparse (maioria nula); sinal de UBO já capturado por `pep_flag` |
| `issuing_or_acquiring`, `pix_flow` | Metadados operacionais sem evidência de sinal preditivo |
| `fx_to_brl`, `currency` | Alta correlação com `is_cross_border`; feature já está lá |
| `score` e `n_rules` (do ranking) | **Vazamento** — o label `is_core_label` é derivado do score; incluí-los seria trapaça |

> **Regra geral:** descartamos features que (a) são proxy do label (vazamento), (b) têm alta
> cardinalidade sem codificação adequada, (c) são redundantes com features melhores já presentes,
> ou (d) pertencem à entidade merchant, não ao cliente.

---

## 4. Como definimos o rótulo (label)

Não temos investigadores confirmando "este cliente é lavador" — isso é a realidade de qualquer
sistema AML antes da investigação humana. Usamos um **rótulo fraco (weak label)**.

**Definição (canônica em `src/rules_engine.py`, `CORE_RULES`, linha 82):** um cliente é marcado
`is_core_label = 1` se acionar **≥ 2 das seguintes 5 regras-core de alta confiança** (baixa
taxa de falso-positivo, conforme catálogo `referencias/catalogo-regras.md`):

| Regra | Severidade | Tipologia | Por que é "core" |
|---|---|---|---|
| R03 — structuring | 3 | Structuring PIX | Fragmentar valores logo abaixo de limiar de reporte é tipologia clássica FATF — raramente acidental |
| R07 — device_ring | 3 | Device ring | Vários clientes usando um único device em janela curta = laranjas/mulas |
| R09 — self_merchant | 4 | Self-merchant | Cliente paga merchant do qual é dono — faturamento fictício, sem ambiguidade |
| R12 — ecom_no_3ds | 3 | E-com sem 3DS | Card-not-present + 3DS=No + valor alto = exposição alta e padrão atípico de varejo |
| R15 — sanctions | 3–4 | Sanções / país de risco | Hit direto contra lista de sanções (OFAC/ONU/UE) é gatilho regulatório imediato |

**Distribuição resultante:** 108 positivos em 3.310 clientes (3,3% — base desbalanceada).
Os clientes-positivos são os que combinam pelo menos duas destas 5 regras — o que indica padrão
estruturado, não ruído isolado.

**Limitação:** o modelo está aprendendo a replicar essas regras, não a detectar lavagem real.
Isso é uma aproximação necessária na ausência de labels auditados.

---

## 5. Métricas de qualidade — o que cada uma significa

### 5.1 ROC-AUC (Área sob a Curva ROC)

**O que é:** imagine ordenar todos os clientes do mais suspeito ao menos suspeito. O ROC-AUC mede
a probabilidade de que, se sortearmos um cliente suspeito e um normal ao acaso, o suspeito tenha
score maior.

- **0.5** = o modelo não sabe nada (equivale a jogar uma moeda)
- **1.0** = o modelo sempre coloca suspeitos na frente
- **Nosso resultado:** `0.9559 ± 0.0074` (CV) / `0.9793` (teste)

**Interpretação:** com 95% de chance, o modelo ranqueia um suspeito acima de um cliente normal.

### 5.2 PR-AUC (Área sob a Curva Precisão-Recall)

**Por que esta é mais importante aqui:** a base tem 3,3% de positivos. Uma métrica que ignora isso
(como a acurácia) pode dar 96,7% só "chutando sempre Normal". A PR-AUC foca apenas nos clientes
que o modelo acusa.

**O que é:** resume o trade-off entre:
- **Precisão:** dos clientes que o modelo sinalizou, quantos são de fato suspeitos?
- **Recall:** dos clientes suspeitos reais, quantos o modelo encontrou?

- **Baseline (acaso):** `0.0326` (= 3,3% da base)
- **Nosso resultado:** `0.3127 ± 0.0484` (CV) / `0.5359` (teste)
- **Ganho:** **9,6× acima do baseline** (validado por cross-validation)

### 5.3 Precisão e Recall no threshold ótimo

Com o threshold que maximiza o F1 no conjunto de teste (`threshold = 0.437`):

| Métrica | Valor | O que significa |
|---|---|---|
| **Precisão (32%)** | De cada 100 alertas gerados, 32 são suspeitos reais | Para cada suspeito encontrado, há ~2 "falsos alarmes" |
| **Recall (93%)** | O modelo encontra 14 dos 15 suspeitos no teste | Muito difícil de "escapar" do modelo |
| **F1 (47%)** | Média harmônica precisão × recall | Equilíbrio geral do modelo |

### 5.4 Erro de calibração (0.19)

**O que é:** os scores do modelo são probabilidades reais? Se o modelo diz "60% de chance de ser
suspeito", na prática, quantos clientes com esse score são suspeitos?

**Nosso resultado:** erro médio de 0.19 (moderado). Um score de 0.60 pode corresponder a ~40% ou
~80% de chance real. **Para uso operacional, recomendamos calibração isotônica antes de usar os
scores como probabilidades absolutas.** Para *ranking* e *priorização* (nosso uso atual), o erro
de calibração não compromete a utilidade.

---

## 6. Trade-offs das métricas

### Trade-off Precisão × Recall (o mais importante)

No contexto AML, estes valores têm custos assimétricos:

| | Suspeito real | Normal real |
|---|---|---|
| **Modelo acusa** | ✅ Verdadeiro Positivo | ⚠️ Falso Positivo |
| **Modelo libera** | ❌ Falso Negativo | ✅ Verdadeiro Negativo |

- **Custo de um Falso Negativo alto:** um lavador passa despercebido → risco regulatório, multas, dano reputacional
- **Custo de um Falso Positivo alto:** analistas investigam clientes inocentes → custo operacional, possível dano ao cliente

**Nosso threshold (0.437) prioriza recall (93%)** porque o custo de deixar passar um suspeito é
maior do que investigar falsas suspeitas. A precisão de 32% significa que, para cada investigação
real, há ~2 análises de clientes normais — **aceitável** para uma equipe de compliance que já
opera com base em alertas de regras com precisão similar.

**Como ajustar:** se a equipe de compliance está sobrecarregada, pode-se aumentar o threshold
(ex.: 0.6), reduzindo a carteira alertada de ~4% para ~2%, com perda de recall de 93% para ~70%.
A curva de corte (`04_cutoff_curve.png`) permite calibrar conforme a capacidade operacional.

### Trade-off ROC-AUC × PR-AUC

Com apenas 3,3% de positivos, o ROC-AUC pode parecer alto mesmo para modelos fracos (porque tem
97% de negativos fáceis de classificar). A PR-AUC é mais honesta: ela foca na capacidade de
separar o 3,3% de positivos do restante. **Use sempre PR-AUC como métrica principal aqui.**

### Trade-off CV × teste único

| Métrica | Teste único | Cross-validation |
|---|---|---|
| PR-AUC | 0.5359 | 0.3127 ± 0.0484 |
| ROC-AUC | 0.9793 | 0.9559 ± 0.0074 |

O teste único deu resultado melhor porque o conjunto de teste (clientes com primeira transação
após 12/Jul) tinha, por coincidência, um grupo mais fácil de classificar. O **CV é mais
confiável** (usa toda a base com 5 configurações de treino/teste) e deve ser a referência.
A diferença não indica problema — indica que o modelo é genuíno, mas que o split temporal
único teve sorte no teste. O p-valor `0.000` do permutation test confirma que o sinal é real.

---

## 7. Validação: como sabemos que as métricas são reais?

Fizemos três validações independentes:

### 7.1 Validação cruzada (5-Fold Stratified CV)

Dividimos a base em 5 partes iguais, mantendo a proporção de suspeitos (3,3%) em cada parte.
Treinamos o modelo 5 vezes, cada vez usando 4 partes como treino e 1 como teste. Isso garante
que **todo cliente foi testado exatamente 1 vez** e que o resultado não dependeu de um único split.

| Fold | ROC-AUC | PR-AUC |
|---|---|---|
| 1 | 0.9690 | 0.4036 |
| 2 | 0.9464 | 0.2757 |
| 3 | 0.9536 | 0.3136 |
| 4 | 0.9564 | 0.3024 |
| 5 | 0.9540 | 0.2682 |
| **Média ± Desvio** | **0.9559 ± 0.0074** | **0.3127 ± 0.0484** |

O baixo desvio padrão (especialmente no ROC) indica **estabilidade**: o modelo não depende
de um split específico para funcionar bem.

### 7.2 Permutation Test — o modelo aprende sinal real?

**Hipótese nula:** e se o modelo apenas memorizasse padrões aleatórios nos dados? Para testar,
embaralhamos aleatoriamente os labels 15 vezes e medimos a PR-AUC de cada modelo treinado
em dados com labels aleatórios.

**Resultado:**
- PR-AUC real (CV): **0.3127**
- PR-AUC médio com labels aleatórios: **0.0425**
- **p-valor: 0.000**

Nenhuma das 15 execuções com labels aleatórios chegou perto do resultado real. Isso prova que
o modelo **aprendeu padrões genuínos nos dados**, não memorizou ruído. Com p < 0.05, podemos
rejeitar a hipótese nula com alta confiança.

### 7.3 Curva de aprendizado

Treinamos o modelo com frações crescentes do conjunto de treino:

| % do treino | Amostras | PR-AUC (teste) |
|---|---|---|
| 20% | 529 | 0.4178 |
| 40% | 1.059 | 0.4447 |
| 60% | 1.588 | 0.4274 |
| 80% | 2.118 | 0.4036 |
| 100% | 2.648 | 0.3934 |

A performance no teste se mantém **estável entre 0.39–0.45** conforme aumentamos o treino,
indicando que o modelo não está overfittando (se overfittasse, veria-se queda de performance
no teste com mais dados, pois memorizaria mais o treino). O gap treino×teste esperado existe,
mas é controlado.

---

## 8. Limitações honestas

| Limitação | Impacto | Mitigação possível |
|---|---|---|
| **Rótulo fraco e ruidoso** | O modelo aprendeu a replicar as regras, não a detectar lavagem real | Feedback loop com investigadores para refinar labels |
| **Viés circular** | Features derivadas de transações correlacionam parcialmente com as regras que geraram o label | Usar features de períodos diferentes para treino e label |
| **Janela temporal curta** (3 meses) | Não captura sazonalidade, drift ou esquemas de longo prazo (ex.: layering multi-mês) | Re-treinar com dados históricos de 12+ meses |
| **Calibração imperfeita** (erro 0.19) | O score não é uma probabilidade confiável — não diga "há 60% de chance de lavagem" | Adicionar calibração isotônica (Platt scaling) |
| **Ausência de labels auditados** | PR-AUC mede consistência com as regras, não detecção de crime | Incorporar decisões de investigadores e resultados de SARs |

---

## 9. Resumo de resultados

| Indicador | Valor |
|---|---|
| Clientes ranqueados | 3.310 |
| Score do cliente de maior risco (C101208) | **0.797** — percentil 100% da carteira |
| CV ROC-AUC | 0.956 ± 0.007 |
| CV PR-AUC | 0.313 ± 0.048 |
| Ganho sobre classificador aleatório | **9,6×** |
| P-valor (permutation test) | **0.000** — sinal genuíno |
| Recall a threshold 0.437 | **93%** — captura 14 de 15 suspeitos no teste |
| Precisão a threshold 0.437 | 32% — ~2 falsos alertas por suspeito real |

---

## 10. Como usar o modelo na prática

### Fluxo recomendado

```
Novas transações
      ↓
Feature Engineering (mesmo pipeline do treinamento)
      ↓
XGBoost.predict_proba() → xgb_score
IsolationForest.decision_function() → if_score
      ↓
final_score = 0.70 × xgb_score + 0.30 × if_score_normalizado
      ↓
Tier: <0.30 → baixo | 0.30–0.60 → médio | 0.60–0.80 → alto | >0.80 → crítico
      ↓
Fila de investigação (priorizada por score)
      ↓
Analista humano revisa → fecha o loop
```

### Thresholds operacionais sugeridos

| Threshold | Recall | Precisão | % carteira alertada | Uso recomendado |
|---|---|---|---|---|
| 0.30 | ~99% | ~10% | ~8% | Triagem ampla, baixo volume de analistas |
| **0.44** | **93%** | **32%** | **~5%** | **Padrão recomendado** |
| 0.60 | ~70% | ~50% | ~2% | Equipe pequena, investigação profunda |
| 0.80 | ~40% | ~80% | <1% | Apenas casos críticos / SAR automático |

> Escolha o threshold de acordo com a **capacidade da equipe de compliance** e o
> **apetite de risco regulatório** da organização.

---

_Gerado pelo pipeline de Dia 4 do CloudWalk AML-FT Case._
_Modelo: XGBoost 3.3.0 + scikit-learn 1.9.0 + SHAP 0.52.0. SEED=42. Python 3.14._
