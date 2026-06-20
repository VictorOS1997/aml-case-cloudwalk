# Dados do Projeto AML-FT

## Estrutura

- **raw/** — Base de dados original (não comitar para GitHub)
- **processed/** — Feature store, alertas e scores gerados

## Schema Canônico

### transactions
Registros de transações por rail (PIX, Cartão, Wire).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| transaction_id | str | ID único da transação |
| client_id | str | ID do cliente |
| timestamp | datetime | Data/hora da transação |
| rail | str | Canal (pix/card/wire) |
| amount | float | Valor |
| currency | str | Moeda |
| payment_method | str | Método de pagamento |
| capture_method | str | Método de captura |
| installments | int | Parcelas (Cartão) |
| card_brand | str | Bandeira (Cartão) |
| mcc | str | Merchant Category Code |
| merchant_id | str | ID do merchant |
| counterparty_id | str | ID da contraparte (PIX/Wire) |
| direction | str | cash_in/cash_out/debit/credit |
| is_cross_border | bool | Transação internacional? |
| ip_country | str | País do IP |
| ip_address | str | Endereço IP |
| device_id | str | ID do dispositivo |
| lat | float | Latitude |
| lon | float | Longitude |
| three_ds_flag | bool | 3DS presente? |
| eci | str | ECI (nível autenticação) |
| chargeback_flag | bool | Chargeback? |
| status | str | Status (success/failed/pending) |

### clients (KYC)
Perfil do cliente.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| client_id | str | ID único |
| document | str | CPF/documento |
| monthly_income | float | Renda mensal |
| pep_flag | bool | Pessoa Exposta Politicamente? |
| onboarding_date | datetime | Data de cadastro |
| country | str | País |
| city | str | Cidade |
| sanctions_flag | bool | Em lista de sanções? |
| account_age_days | int | Dias desde abertura |

### merchants
Dados de merchants.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| merchant_id | str | ID único |
| owner_client_id | str | Cliente dono |
| mcc | str | Merchant Category Code |
| country | str | País |
| chargeback_rate | float | Taxa de chargeback |

## Checklist Dia 1 (EDA)

Após carregar os dados, preencha:

- [ ] Colunas reais vs schema canônico (quais faltam?)
- [ ] Tipo de dados de cada coluna
- [ ] Valores faltantes por coluna
- [ ] Distribuição de rails (PIX/Card/Wire)
- [ ] Período de dados (data min/max)
- [ ] Número de clientes, merchants, transações
- [ ] Checagem de coerência por rail (ex: installments só em Card)

Registre tudo em `notebooks/01_eda_qualidade.ipynb`.
