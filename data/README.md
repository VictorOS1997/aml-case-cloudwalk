# Dados do Projeto AML-FT

## Estrutura

- **raw/** — Base de dados original da CloudWalk (3 CSVs). **Não comitada** (gitignored).
  Coloque aqui:
  - `transactions.csv`
  - `kyc_profiles.csv`
  - `merchants.csv`
- **processed/** — Feature store e tabelas derivadas geradas pelos scripts em `notebooks/`:
  - `sender_features.csv` — agregações por cliente (entidade `client`)
  - `merchant_features.csv` — agregações por merchant

> O esquema abaixo reflete o que `src/rules_engine.py` consome (constantes `C_*`, `K_*`, `M_*`).
> Se a base original trouxer nomes diferentes, mapeie-os antes de rodar o motor.

---

## Schema real

### `transactions.csv` (52.000 linhas × 41 colunas)

Tabela principal. Contém todas as transações nos três rails.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `transaction_id` | str | ID único da transação |
| `timestamp` | datetime | Data/hora da transação |
| `sender_id` | str | ID do cliente remetente (FK → `kyc_profiles.customer_id`) |
| `receiver_id` | str | ID do receptor (cliente ou merchant) |
| `receiver_entity_type` | str | `client` ou `merchant` |
| `amount_brl` | float | Valor em BRL |
| `transaction_type` | str | Rail: `PIX` / `Card` / `Wire` |
| `currency` | str | Moeda da transação |
| `fx_to_brl` | float | Taxa de conversão para BRL (se cross-border) |
| `cross_border` | str | `Yes` / `No` |
| `mcc` | int | Merchant Category Code |
| `device_fingerprint` | str | Fingerprint do dispositivo |
| `ip_address` | str | Endereço IP |
| `ip_country` | str | País do IP |
| `ip_anomaly` | str | `Yes` / `No` (VPN/Tor/proxy) |
| `country_risk_ip` | str | `Low` / `Monitored` / `High` |
| `country_risk_sender` | str | Risco do país do remetente |
| `country_risk_receiver` | str | Risco do país do receptor |
| `geolocation_lat` | float | Latitude da transação |
| `geolocation_lon` | float | Longitude da transação |
| `sanctions_screening_hit` | str | `Yes` / `No` |
| `status` | str | `success` / `failed` / `pending` |
| `channel` | str | App / API / Terminal / Web |
| `capture_method` | str | Método de captura (Card: chip/NFC/magstripe/ecommerce) |
| `payment_method` | str | `credit` / `debit` (exclusivo Card) |
| `installments` | int | Parcelas (exclusivo Card) |
| `card_brand` | str | Visa / Mastercard / Elo / Amex / Hipercard (exclusivo Card) |
| `card_present` | str | `Yes` / `No` (exclusivo Card) |
| `auth_3ds` | str | `Yes` / `No` (exclusivo Card) |
| `eci` | float | ECI 3DS — ex.: `07` = não autenticado (exclusivo Card) |
| `issuing_or_acquiring` | str | `acquiring` / `issuing` (exclusivo Card) |
| `pix_flow` | str | `cash_in` / `cash_out` (exclusivo PIX) |

> **Coerência por rail:** muitos campos só existem em um dos rails. `notebooks/01_eda_qualidade.py`
> valida e reporta isso (saída em `outputs/01_relatorio_eda.md`). Os ~13,8% de campos faltantes
> são **estruturais e esperados** — não são "dados sujos".

---

### `kyc_profiles.csv` (2.500 linhas × 16 colunas)

Perfil de cada cliente (chave primária `customer_id`).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `customer_id` | str | ID único do cliente (PK) |
| `annual_income_brl` | float | Renda anual declarada |
| `pep` | str | `Yes` / `No` — Pessoa Exposta Politicamente |
| `registration_date` | date | Data de onboarding |
| `sanctions_list_hit` | str | `Yes` / `No` — em lista de sanções |
| `kyc_risk_score` | int | Score interno de risco KYC (0–100) |
| `kyc_tier` | str | Nível de verificação (L1 / L2 / L3) |
| `risk_rating` | str | Classificação (`Low` / `Medium` / `High`) |
| `declared_occupation` | str | Ocupação declarada |
| `date_of_birth` | date | Data de nascimento |
| `state` | str | UF |
| `city` | str | Cidade |
| `country` | str | País (sigla ISO) |
| `beneficial_owner` | str | UBO declarado (nulo quando ausente) |

---

### `merchants.csv` (1.000 linhas × 10 colunas)

Dados de merchants (chave primária `merchant_id`).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `merchant_id` | str | ID único do merchant (PK) |
| `owner_customer_id` | str | Cliente dono (FK → `kyc_profiles.customer_id`) |
| `mcc` | int | Merchant Category Code |
| `mcc_risk` | str | `Normal` / `High` |
| `merchant_high_risk_flag` | str | `Yes` / `No` |
| `merchant_chargeback_ratio_90d` | float | Taxa de chargeback nos últimos 90 dias |

---

## Checklist do Dia 1 (EDA — `notebooks/01_eda_qualidade.py`)

Após executar o script, confira em `outputs/01_relatorio_eda.md`:

- [x] Colunas reais vs schema acima
- [x] Tipo de dados de cada coluna
- [x] Valores faltantes por coluna (com explicação por rail)
- [x] Distribuição de rails (PIX 60,7% · Card 34,5% · Wire 4,8%)
- [x] Período de dados (Jul–Out/2025)
- [x] Contagens (52k tx · 2,5k clientes · 1k merchants · 3.310 senders ativos)
- [x] Checagem de coerência por rail (`installments` só em Card, `pix_flow` só em PIX, etc.)

Toda execução grava o relatório em `outputs/01_relatorio_eda.md`.

---

## Reprodutibilidade

```bash
python notebooks/01_eda_qualidade.py    # gera processed/ + outputs/01_*
python notebooks/02_regras_alertas.py   # gera outputs/alertas.csv, ranking_risco.csv, outputs/02_*
python notebooks/03_suspeitos_sar.py    # gera outputs/suspeitos_top30.csv, outputs/sar/SAR_*
python notebooks/04_modelo_ml.py        # gera outputs/04_ml_scores.csv, figuras 04_*, outputs/04_*
python notebooks/05_agentes_pipeline.py # demo do pipeline multi-agente (modo simulado sem API key)
```

`SEED = 42` em todos os scripts. Python 3.12+. Versões em `requirements.txt`.
