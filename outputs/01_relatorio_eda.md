# Relatório de EDA — Entendimento da Base de Dados
**Projeto:** AML-FT Case CloudWalk  
**Data:** 2026-06-20  
**Script:** `notebooks/01_eda_qualidade.py`

---

## 1. Visão Geral

| Métrica | Valor |
|---------|-------|
| Período | 2025-07-01 a 2025-10-04 (95 dias) |
| Total de Transações | 52.000 |
| Valor Total (BRL) | R$ 230.057.857,58 |
| Valor Médio (BRL) | R$ 4.424,19 |
| Valor Máximo (BRL) | R$ 140.910,35 |
| Clientes (KYC_Profiles) | 2.500 |
| Merchants cadastrados | 1.000 |

---

## 2. Estrutura das Tabelas

### 2.1 Transactions (52.000 linhas × 41 colunas)
Principal tabela do projeto. Contém todas as transações nos três rails.

**Chave de ligação:**
- `sender_id` e `receiver_id` → `KYC_Profiles.customer_id`
- `receiver_id` WHERE `receiver_entity_type == 'merchant'` → `Merchants.merchant_id`

> **IMPORTANTE:** A tabela `Transactions` NÃO possui coluna `merchant_id`. Merchants são identificados pelo campo `receiver_id` quando `receiver_entity_type == 'merchant'`.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| transaction_id | str | ID único da transação |
| timestamp | datetime | Data/hora da transação |
| transaction_type | str | Rail: PIX / Card / Wire |
| sender_id | str | ID do remetente |
| sender_entity_type | str | customer ou merchant |
| receiver_id | str | ID do destinatário |
| receiver_entity_type | str | merchant ou customer |
| amount_brl | float | Valor em BRL |
| amount_orig | float | Valor na moeda original |
| currency | str | BRL / USD / EUR |
| fx_to_brl | int | Taxa de câmbio (1 para BRL) |
| status | str | Confirmed / Pending / Failed / Chargeback |
| channel | str | App / API / Terminal / Web |
| capture_method | str | CopyPaste / Pix Key / QR Static / QR Dynamic / Magstripe / NFC / Chip / E-commerce / Domestic / SWIFT |
| payment_method | str | credit / debit (só Card) |
| installments | int | Parcelas (só Card) |
| issuing_or_acquiring | str | acquiring / issuing (só Card) |
| pix | str | Yes / No |
| pix_flow | str | cash_in / cash_out (só PIX) |
| card_brand | str | Visa / Elo / Mastercard / Amex / Hipercard (só Card) |
| card_present | str | Yes / No (só Card) |
| auth_3ds | str | Yes / No (só Card) |
| eci | float | ECI de autenticação 3DS (só Card) |
| mcc | int | Merchant Category Code |
| geo_country | str | País da geolocalização |
| geolocation_lat | float | Latitude |
| geolocation_lon | float | Longitude |
| ip_country | str | País do IP |
| ip_anomaly | str | Yes / No |
| ip_proxy_vpn_tor | str | VPN / Proxy / Tor (93% vazio — só preenchido quando detectado) |
| device_fingerprint | str | Fingerprint do dispositivo |
| ip_address | str | Endereço IP |
| device_rooted | str | Yes / No |
| sender_country | str | País do remetente |
| receiver_country | str | País do destinatário |
| country_risk_geo | str | Low / Monitored / High |
| country_risk_ip | str | Low / Monitored / High |
| country_risk_sender | str | Low / Monitored / High |
| country_risk_receiver | str | Low / Monitored / High |
| cross_border | str | Yes / No |
| sanctions_screening_hit | str | Yes / No |

### 2.2 KYC_Profiles (2.500 linhas × 16 colunas)
Perfil KYC dos clientes. **Sem valores faltantes.**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| customer_id | str | ID único do cliente (ex: C100000) |
| full_name | str | Nome completo |
| cpf_cnpj | int | CPF ou CNPJ |
| date_of_birth | str | Data de nascimento |
| annual_income_brl | int | Renda anual declarada (BRL) |
| declared_occupation | str | Ocupação declarada |
| risk_rating | str | Classificação de risco |
| registration_date | str | Data de cadastro |
| country | str | País |
| state | str | Estado |
| city | str | Cidade |
| beneficial_owner | str | Yes / No — titular beneficiário |
| pep | str | Yes / No — Pessoa Exposta Politicamente |
| kyc_tier | str | L1 / L2 / L3 — nível KYC |
| kyc_risk_score | int | Score de risco KYC (0-100, média=58,6) |
| sanctions_list_hit | str | Yes / No — presença em lista de sanções |

**Estatísticas relevantes:**
- Renda anual média: R$ 19.418 | Máxima: R$ 166.141
- KYC Risk Score médio: 58,6 (escala 0–100)

### 2.3 Merchants (1.000 linhas × 10 colunas)

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| merchant_id | str | ID único (ex: M200000) |
| merchant_name | str | Nome do merchant |
| cnpj | int | CNPJ |
| mcc | int | Merchant Category Code |
| country | str | País |
| city | float | **100% vazio — ignorar** |
| owner_customer_id | str | ID do cliente dono (65,1% vazio) |
| merchant_high_risk_flag | str | Yes / No |
| merchant_chargeback_ratio_90d | float | Taxa de chargeback 90 dias (média=6,2%) |
| mcc_risk | str | Normal / High |

**Observação:** 349 merchants (34,9%) possuem `owner_customer_id` — base para detecção de **self-merchant fraud**.

---

## 3. Distribuição por Rail

| Rail | Qtd | % | Capture Methods |
|------|-----|---|-----------------|
| PIX | 31.547 | 60,7% | CopyPaste, Pix Key, QR Static, QR Dynamic |
| Card | 17.930 | 34,5% | Magstripe, NFC, Chip, E-commerce |
| Wire | 2.523 | 4,8% | Domestic (1.252), SWIFT (1.271) |

**Canal de acesso:**

| Canal | Qtd |
|-------|-----|
| App | 20.893 |
| API | 20.843 |
| Terminal | 5.156 |
| Web | 5.108 |

---

## 4. Valores Faltantes — Explicação por Rail

Os 13,8% de campos faltantes são **estruturais e esperados** — cada rail tem campos exclusivos:

| Campo | % Faltante | Motivo |
|-------|-----------|--------|
| ip_proxy_vpn_tor | 92,96% | Só preenchido quando proxy/VPN/Tor detectado |
| auth_3ds / eci | 86,36% | Exclusivo de Card (34,5% do volume) |
| payment_method / card_brand / card_present / issuing_or_acquiring | 65,52% | Exclusivo de Card |
| pix_flow | 39,33% | Exclusivo de PIX com fluxo definido |

**Campos sem faltantes em KYC_Profiles:** todos os 16 campos completos.

---

## 5. Sinais de Risco Identificados

| Sinal | Qtd | % | Prioridade AML |
|-------|-----|---|----------------|
| Cross-border | 10.113 | 19,4% | Alta |
| Device rooted | 1.562 | 3,0% | Média |
| IP anomaly | 190 | 0,4% | Alta |
| IP via Proxy/VPN/Tor | 3.663 | 7,0% | Alta |
| Sanctions screening hit | 2 | ~0% | CRÍTICA |

---

## 6. Observações Críticas para as Próximas Etapas

1. **2 transações com sanctions_screening_hit = 'Yes'** — investigar imediatamente; candidatos diretos ao SAR.

2. **Devices e IPs únicos por transação** — 52.000 devices para 52.000 transações. Pode indicar **device spoofing em massa** ou característica do dataset sintético. Avaliar agrupamento por `device_fingerprint` com cuidado.

3. **349 merchants com owner_customer_id** — base direta para regra de **self-merchant** (R09 do catálogo): cliente que envia para merchant do qual é dono.

4. **Wire via SWIFT (1.271 transações)** — canal de maior risco para cross-border e lavagem via FX. Priorizar nas regras de país de alto risco.

5. **MCC de alto risco presentes** — MCCs 7995 (jogos/apostas), 6011 (saques ATM), 6051 (câmbio/cripto) aparecem na base. Verificar concentração.

6. **Campo `city` em Merchants 100% vazio** — não usar em análises geográficas de merchants.

7. **Renda incompatível** — renda anual média de R$ 19.418 vs. valor médio por transação de R$ 4.424. Clientes com múltiplas transações de alto valor merecem atenção na Regra R04.

8. **Chargeback rate de merchants** — média de 6,2%, máximo de 26,2%. Merchants acima de 10% são candidatos a alertas (R18 do catálogo).

---

## 7. Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `outputs/01_quality_report.csv` | Relatório de qualidade resumido |
| `outputs/figuras/01_distribuicao_valores.png` | Distribuição de valores e volume por rail |
| `data/processed/sender_features.csv` | Feature store por sender (3.497 entidades) |
| `data/processed/merchant_features.csv` | Feature store por merchant receiver (1.000 entidades) |

---

## 8. Próximos Passos (Dia 2)

- Implementar ≥15 regras do catálogo no motor de regras
- Rodar motor sobre a base completa
- Gerar lista de alertas com exemplos reais (IDs)
- Criar ranking de risco por cliente/merchant
