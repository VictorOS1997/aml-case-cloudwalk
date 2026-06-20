"""
Configuração central do projeto AML-FT da CloudWalk.
Define seeds, constantes, caminhos e variáveis de ambiente.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# Seed para reprodutibilidade
SEED = 42
RANDOM_STATE = 42

# Caminhos
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
NOTEBOOKS = PROJECT_ROOT / "notebooks"
CONFIG = PROJECT_ROOT / "config"

# Criar diretórios se não existirem
for path in [DATA_RAW, DATA_PROCESSED, OUTPUTS]:
    path.mkdir(parents=True, exist_ok=True)

# Variáveis de ambiente
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Schema canônico de dados
TRANSACTIONS_SCHEMA = {
    "transaction_id": "str",
    "client_id": "str",
    "timestamp": "datetime",
    "rail": "str",  # pix, card, wire
    "amount": "float",
    "currency": "str",
    "payment_method": "str",
    "capture_method": "str",
    "installments": "int",
    "card_brand": "str",
    "mcc": "str",
    "merchant_id": "str",
    "counterparty_id": "str",
    "direction": "str",  # cash_in, cash_out, debit, credit
    "is_cross_border": "bool",
    "ip_country": "str",
    "ip_address": "str",
    "device_id": "str",
    "lat": "float",
    "lon": "float",
    "three_ds_flag": "bool",
    "eci": "str",
    "chargeback_flag": "bool",
    "status": "str",
}

CLIENTS_SCHEMA = {
    "client_id": "str",
    "document": "str",
    "monthly_income": "float",
    "pep_flag": "bool",
    "onboarding_date": "datetime",
    "country": "str",
    "city": "str",
    "sanctions_flag": "bool",
    "account_age_days": "int",
}

MERCHANTS_SCHEMA = {
    "merchant_id": "str",
    "owner_client_id": "str",
    "mcc": "str",
    "country": "str",
    "chargeback_rate": "float",
}
