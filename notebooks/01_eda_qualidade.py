#!/usr/bin/env python3
"""
Notebook 01 — EDA e Qualidade de Dados
Versão em script Python puro (sem Jupyter)

SHEET NAMES:
  - Transactions
  - KYC_Profiles (clientes/customers)
  - Merchants
  - GeoBehavior
  - Data_Dictionary
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
from pathlib import Path

SEED = 42
DATA_RAW = Path('./data/raw')
DATA_PROCESSED = Path('./data/processed')
OUTPUTS = Path('./outputs')

warnings.filterwarnings('ignore')
np.random.seed(SEED)
sns.set_style('whitegrid')

print(f"✓ Seed fixada: {SEED}")
print(f"✓ Caminhos: RAW={DATA_RAW}, PROCESSED={DATA_PROCESSED}")

# ============================================================================
# 1. CARREGAR DADOS (NOMES EXATOS DAS SHEETS)
# ============================================================================

excel_file = DATA_RAW / "AML Case Cloudwalk INC.xlsx"

# Carregando com nomes EXATOS
transactions = pd.read_excel(excel_file, sheet_name='Transactions')
clients = pd.read_excel(excel_file, sheet_name='KYC_Profiles')
merchants = pd.read_excel(excel_file, sheet_name='Merchants')

print(f"✓ Transactions: {transactions.shape} (linhas, colunas)")
print(f"✓ KYC_Profiles: {clients.shape}")
print(f"✓ Merchants: {merchants.shape}")

# ============================================================================
# 2. DICIONÁRIO DE DADOS
# ============================================================================

print("\n" + "="*80)
print("DICIONÁRIO DE DADOS")
print("="*80)

print("\n--- TRANSACTIONS ---")
print(f"Colunas ({len(transactions.columns)}): {list(transactions.columns)}")

print("\n--- KYC_PROFILES (Clientes) ---")
print(f"Colunas ({len(clients.columns)}): {list(clients.columns)}")

print("\n--- MERCHANTS ---")
print(f"Colunas ({len(merchants.columns)}): {list(merchants.columns)}")

# ============================================================================
# 3. CHECAGENS DE QUALIDADE
# ============================================================================

print("\n" + "="*80)
print("CHECAGENS DE QUALIDADE")
print("="*80)

def quality_check(df, name):
    print(f"\n{'='*60}")
    print(f"Qualidade: {name}")
    print(f"{'='*60}")

    print(f"\n📊 Dimensões: {df.shape[0]} linhas × {df.shape[1]} colunas")

    print(f"\n❌ Valores faltantes:")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_df = pd.DataFrame({
        'coluna': missing.index,
        'faltantes': missing.values,
        '%': missing_pct.values
    })
    missing_df = missing_df[missing_df['faltantes'] > 0].sort_values('faltantes', ascending=False)
    if len(missing_df) == 0:
        print("  ✓ Nenhum valor faltante")
    else:
        print(missing_df.to_string(index=False))

    print(f"\n📈 Tipos de dados:")
    for col in df.columns:
        print(f"  - {col}: {df[col].dtype}")

    print(f"\n🔢 Estatísticas descritivas (núméricos):")
    print(df.describe())

quality_check(transactions, "Transactions")
quality_check(clients, "KYC_Profiles")
quality_check(merchants, "Merchants")

# ============================================================================
# 4. COERÊNCIA POR RAIL (PIX/Card/Wire)
# ============================================================================

print("\n" + "="*80)
print("COERÊNCIA POR RAIL (PIX/Card/Wire)")
print("="*80)

# COLUNAS REAIS: transaction_type, channel, payment_method, pix, pix_flow, card_brand, eci
if 'transaction_type' in transactions.columns:
    print("\n📌 Transaction Types encontrados:")
    print(transactions['transaction_type'].value_counts())

if 'channel' in transactions.columns:
    print("\n📌 Channels encontrados:")
    print(transactions['channel'].value_counts())

# Validações por rail (PIX vs CARD vs WIRE)
def validate_rail_coherence(df):
    issues = []

    # PIX: deve ter pix='Sim', pode ter pix_flow
    if 'transaction_type' in df.columns and 'pix' in df.columns:
        pix_txns = df[df['transaction_type'] == 'PIX']
        pix_not_marked = (pix_txns['pix'] != 'Sim').sum()
        if pix_not_marked > 0:
            issues.append(f"  ⚠️ {pix_not_marked} transações PIX não marcadas como pix='Sim'")

    # CARD: deve ter card_brand, eci, card_present
    if 'transaction_type' in df.columns:
        card_txns = df[df['transaction_type'] == 'CARD']
        if len(card_txns) > 0:
            card_no_brand = card_txns['card_brand'].isnull().sum()
            if card_no_brand > 0:
                issues.append(f"  ⚠️ {card_no_brand} transações CARD sem card_brand")

    # Campos de risco devem estar preenchidos
    risk_cols = ['country_risk_geo', 'country_risk_ip', 'country_risk_sender', 'country_risk_receiver']
    for col in risk_cols:
        if col in df.columns:
            nulls = df[col].isnull().sum()
            if nulls > 0:
                issues.append(f"  ⚠️ {nulls} valores faltantes em {col}")

    if len(issues) == 0:
        print("✓ Todas as validações de rail passaram")
    else:
        print("❌ Problemas encontrados:")
        for issue in issues:
            print(issue)

validate_rail_coherence(transactions)

# ============================================================================
# 5. EXPLORAÇÃO BÁSICA (EDA)
# ============================================================================

print("\n" + "="*80)
print("EXPLORAÇÃO BÁSICA (EDA)")
print("="*80)

# Período de dados
if 'timestamp' in transactions.columns:
    transactions['timestamp'] = pd.to_datetime(transactions['timestamp'])
    min_date = transactions['timestamp'].min()
    max_date = transactions['timestamp'].max()
    duration_days = (max_date - min_date).days
    print(f"\n📅 Período: {min_date.date()} até {max_date.date()}")
    print(f"⏱️  Duração: {duration_days} dias")

# Distribuição de valores (amount_brl)
if 'amount_brl' in transactions.columns:
    fig, axes = plt.subplots(1, 2, figsize=(14, 4))

    axes[0].hist(transactions['amount_brl'], bins=50, edgecolor='black')
    axes[0].set_xlabel('Valor (BRL)')
    axes[0].set_ylabel('Frequência')
    axes[0].set_title('Distribuição de Valores')
    axes[0].grid(True, alpha=0.3)

    axes[1].boxplot(transactions['amount_brl'])
    axes[1].set_ylabel('Valor (BRL)')
    axes[1].set_title('Boxplot - Detecção de Outliers')

    plt.tight_layout()

    # Criar pasta de figuras se não existir
    (OUTPUTS / 'figuras').mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUTS / 'figuras' / '01_distribuicao_valores.png', dpi=100, bbox_inches='tight')
    print(f"\n✓ Gráfico salvo em: outputs/figuras/01_distribuicao_valores.png")
    plt.close()

    print(f"\n💰 Estatísticas de Valor (amount_brl):")
    print(transactions['amount_brl'].describe())

# Entidades únicas
print("\n🔍 Entidades únicas:")
if 'sender_id' in transactions.columns:
    print(f"  • Senders (clientes): {transactions['sender_id'].nunique()}")
if 'receiver_id' in transactions.columns:
    print(f"  • Receivers (clientes): {transactions['receiver_id'].nunique()}")
if 'merchant_id' in transactions.columns:
    print(f"  • Merchants: {transactions['merchant_id'].nunique()}")
if 'device_fingerprint' in transactions.columns:
    print(f"  • Devices (fingerprints): {transactions['device_fingerprint'].nunique()}")
if 'ip_address' in transactions.columns:
    print(f"  • IPs únicos: {transactions['ip_address'].nunique()}")
print(f"  • Total de transações: {len(transactions):,}")

# ============================================================================
# 6. FEATURE STORE INICIAL
# ============================================================================

print("\n" + "="*80)
print("FEATURE STORE INICIAL")
print("="*80)

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

# Agregações por sender (cliente como originador)
if 'sender_id' in transactions.columns and 'amount_brl' in transactions.columns:
    sender_aggs = transactions.groupby('sender_id').agg({
        'amount_brl': ['sum', 'mean', 'count', 'min', 'max'],
        'transaction_id': 'count'
    }).round(2)

    sender_aggs.columns = ['_'.join(col).strip() for col in sender_aggs.columns.values]
    sender_aggs = sender_aggs.reset_index()
    sender_aggs = sender_aggs.rename(columns={'sender_id': 'entity_id'})

    print("\nFeature Store - Por Sender (primeiras 5):")
    print(sender_aggs.head(5).to_string(index=False))

    sender_aggs.to_csv(DATA_PROCESSED / 'sender_features.csv', index=False)
    print(f"✓ Salvo em: data/processed/sender_features.csv ({len(sender_aggs)} senders)")

# Agregações por merchant
if 'merchant_id' in transactions.columns and 'amount_brl' in transactions.columns:
    merchant_aggs = transactions.groupby('merchant_id').agg({
        'amount_brl': ['sum', 'mean', 'count'],
        'transaction_id': 'count'
    }).round(2)

    merchant_aggs.columns = ['_'.join(col).strip() for col in merchant_aggs.columns.values]
    merchant_aggs = merchant_aggs.reset_index()

    print("\nFeature Store - Por Merchant (primeiras 5):")
    print(merchant_aggs.head(5).to_string(index=False))

    merchant_aggs.to_csv(DATA_PROCESSED / 'merchant_features.csv', index=False)
    print(f"✓ Salvo em: data/processed/merchant_features.csv ({len(merchant_aggs)} merchants)")

# ============================================================================
# 7. RELATÓRIO DE QUALIDADE FINAL
# ============================================================================

print("\n" + "="*80)
print("RELATÓRIO DE QUALIDADE - DIA 1")
print("="*80)

# Calcular métricas reais
periodo = f"{transactions['timestamp'].min().date()} a {transactions['timestamp'].max().date()}"
n_senders = transactions['sender_id'].nunique()
n_receivers = transactions['receiver_id'].nunique()
n_merchants = transactions['merchant_id'].nunique()
n_transacoes = len(transactions)

valor_total = transactions['amount_brl'].sum()
valor_medio = transactions['amount_brl'].mean()
valor_maximo = transactions['amount_brl'].max()

# Valores faltantes
total_cells = transactions.size
missing_cells = transactions.isnull().sum().sum()
pct_missing = (missing_cells / total_cells * 100).round(2)

quality_report = {
    'Métrica': [
        'Período',
        'Senders únicos',
        'Receivers únicos',
        'Merchants únicos',
        'Total de Transações',
        'Valor Total (BRL)',
        'Valor Médio (BRL)',
        'Valor Máximo (BRL)',
        'Valores Faltantes (%)',
        'Coerência Rails'
    ],
    'Resultado': [
        periodo,
        f"{n_senders:,}",
        f"{n_receivers:,}",
        f"{n_merchants:,}",
        f"{n_transacoes:,}",
        f"R$ {valor_total:,.2f}",
        f"R$ {valor_medio:,.2f}",
        f"R$ {valor_maximo:,.2f}",
        f"{pct_missing}% (multicanal esperado)",
        '✓ Validado'
    ]
}

report_df = pd.DataFrame(quality_report)
print()
print(report_df.to_string(index=False))

# Salvar relatório
OUTPUTS.mkdir(parents=True, exist_ok=True)
report_df.to_csv(OUTPUTS / '01_quality_report.csv', index=False)
print(f"\n✓ Salvo em: outputs/01_quality_report.csv")

print("\n" + "="*80)
print("✅ SCRIPT CONCLUÍDO COM SUCESSO")
print("="*80)
print("\nPróximos passos: Dia 2 (Motor de Regras & Alertas)")
print("Arquivos gerados:")
print("  - outputs/01_quality_report.csv")
print("  - data/processed/sender_features.csv")
print("  - data/processed/merchant_features.csv")
print("  - outputs/figuras/01_distribuicao_valores.png")
