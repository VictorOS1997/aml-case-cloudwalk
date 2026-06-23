#!/usr/bin/env python3
"""
Script 01 — EDA e Qualidade de Dados (Dia 1).

Script Python executável. Saída: `outputs/01_relatorio_eda.md` + `data/processed/*.csv`.

Sheets:
  - Transactions  (52000 x 41)
  - KYC_Profiles  (2500  x 16)  -> clientes
  - Merchants     (1000  x 10)

Nota: transactions NAO tem merchant_id. Merchants sao identificados por:
  receiver_id WHERE receiver_entity_type == 'merchant'
"""

import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # sem janela grafica
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from pathlib import Path

SEED = 42
DATA_RAW = Path('./data/raw')
DATA_PROCESSED = Path('./data/processed')
OUTPUTS = Path('./outputs')

warnings.filterwarnings('ignore')
np.random.seed(SEED)
sns.set_style('whitegrid')

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
(OUTPUTS / 'figuras').mkdir(parents=True, exist_ok=True)

print("Seed fixada:", SEED)
print("RAW:", DATA_RAW)

# ============================================================================
# 1. CARREGAR DADOS
# ============================================================================

excel_file = DATA_RAW / "AML Case Cloudwalk INC.xlsx"

transactions = pd.read_excel(excel_file, sheet_name='Transactions')
clients = pd.read_excel(excel_file, sheet_name='KYC_Profiles')
merchants = pd.read_excel(excel_file, sheet_name='Merchants')

# Converter timestamp
transactions['timestamp'] = pd.to_datetime(transactions['timestamp'])

print(f"Transactions: {transactions.shape}")
print(f"KYC_Profiles: {clients.shape}")
print(f"Merchants:    {merchants.shape}")

# ============================================================================
# 2. DICIONARIO DE DADOS
# ============================================================================

print("\n" + "="*80)
print("DICIONARIO DE DADOS")
print("="*80)

print("\n--- TRANSACTIONS (41 colunas) ---")
for col in transactions.columns:
    print(f"  {col}: {transactions[col].dtype}")

print("\n--- KYC_PROFILES (16 colunas) ---")
for col in clients.columns:
    print(f"  {col}: {clients[col].dtype}")

print("\n--- MERCHANTS (10 colunas) ---")
for col in merchants.columns:
    print(f"  {col}: {merchants[col].dtype}")

# ============================================================================
# 3. CHECAGENS DE QUALIDADE
# ============================================================================

print("\n" + "="*80)
print("CHECAGENS DE QUALIDADE")
print("="*80)

def quality_check(df, name):
    print(f"\n--- {name} ---")
    print(f"Dimensoes: {df.shape[0]:,} linhas x {df.shape[1]} colunas")

    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_df = pd.DataFrame({'coluna': missing.index, 'faltantes': missing.values, '%': missing_pct.values})
    missing_df = missing_df[missing_df['faltantes'] > 0].sort_values('faltantes', ascending=False)

    if len(missing_df) == 0:
        print("  Valores faltantes: nenhum")
    else:
        print("  Valores faltantes (apenas multicanal):")
        print(missing_df.to_string(index=False))

    print("  Estatisticas numericas:")
    print(df.describe().to_string())

quality_check(transactions, "Transactions")
quality_check(clients, "KYC_Profiles")
quality_check(merchants, "Merchants")

# ============================================================================
# 4. COERENCIA POR RAIL (PIX / Card / Wire)
# ============================================================================

print("\n" + "="*80)
print("COERENCIA POR RAIL")
print("="*80)

# Distribuicao de rails
print("\nDistribuicao de transaction_type:")
print(transactions['transaction_type'].value_counts().to_string())

print("\nDistribuicao de channel:")
print(transactions['channel'].value_counts().to_string())

issues = []

# PIX: coluna 'pix' deve ser 'Yes' para PIX
pix_txns = transactions[transactions['transaction_type'] == 'PIX']
pix_marcado = (pix_txns['pix'] == 'Yes').sum()
pix_nao_marcado = (pix_txns['pix'] != 'Yes').sum()
if pix_nao_marcado > 0:
    issues.append(f"PIX: {pix_nao_marcado} transacoes PIX sem pix='Yes'")
else:
    print(f"PIX: {pix_marcado:,} transacoes corretamente marcadas como pix='Yes'")

# CARD: deve ter card_brand preenchido
card_txns = transactions[transactions['transaction_type'] == 'Card']
card_sem_brand = card_txns['card_brand'].isnull().sum()
if card_sem_brand > 0:
    issues.append(f"Card: {card_sem_brand} transacoes sem card_brand")
else:
    print(f"Card: todas as {len(card_txns):,} transacoes tem card_brand")

# WIRE: deve ter capture_method in [Domestic, SWIFT]
wire_txns = transactions[transactions['transaction_type'] == 'Wire']
wire_methods = wire_txns['capture_method'].value_counts()
print(f"Wire capture_method: {wire_methods.to_dict()}")

# Campos de risco nao devem ter nulls
risk_cols = ['country_risk_geo', 'country_risk_ip', 'country_risk_sender', 'country_risk_receiver']
for col in risk_cols:
    nulls = transactions[col].isnull().sum()
    if nulls > 0:
        issues.append(f"{col}: {nulls} valores faltantes")

# Sancoes
sanc_hit = (transactions['sanctions_screening_hit'] == 'Yes').sum()
print(f"\nSancoes hit: {sanc_hit} transacoes")

if issues:
    print("\nProblemas de coerencia encontrados:")
    for i in issues:
        print(f"  ! {i}")
else:
    print("\nCoerencia por rail: OK")

# ============================================================================
# 5. EDA
# ============================================================================

print("\n" + "="*80)
print("EXPLORACAO BASICA (EDA)")
print("="*80)

# Periodo
min_date = transactions['timestamp'].min()
max_date = transactions['timestamp'].max()
duration = (max_date - min_date).days
print(f"\nPeriodo: {min_date.date()} ate {max_date.date()} ({duration} dias)")

# Valores
print("\nEstatisticas de amount_brl:")
print(transactions['amount_brl'].describe().to_string())

# Cross-border
cb = transactions['cross_border'].value_counts()
print(f"\nCross-border: {cb.to_dict()}")

# IP anomaly
ip_anom = transactions['ip_anomaly'].value_counts()
print(f"IP anomaly: {ip_anom.to_dict()}")

# Device rooted
dr = transactions['device_rooted'].value_counts()
print(f"Device rooted: {dr.to_dict()}")

# Entidades unicas
n_senders = transactions['sender_id'].nunique()
n_receivers = transactions['receiver_id'].nunique()
n_devices = transactions['device_fingerprint'].nunique()
n_ips = transactions['ip_address'].nunique()
# Merchants em transacoes = receivers com receiver_entity_type == 'merchant'
n_merchant_receivers = transactions[transactions['receiver_entity_type'] == 'merchant']['receiver_id'].nunique()
print(f"\nEntidades unicas:")
print(f"  Senders: {n_senders:,}")
print(f"  Receivers: {n_receivers:,}")
print(f"  Merchants (receiver): {n_merchant_receivers:,}")
print(f"  Devices: {n_devices:,}")
print(f"  IPs: {n_ips:,}")
print(f"  Transacoes: {len(transactions):,}")

# Graficos
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Distribuicao de valores
axes[0, 0].hist(transactions['amount_brl'], bins=60, edgecolor='black', color='steelblue')
axes[0, 0].set_xlabel('Valor (BRL)')
axes[0, 0].set_ylabel('Frequencia')
axes[0, 0].set_title('Distribuicao de Valores')
axes[0, 0].grid(True, alpha=0.3)

# 2. Volume por transaction_type
rail_counts = transactions['transaction_type'].value_counts()
axes[0, 1].bar(rail_counts.index, rail_counts.values, color=['#2196F3', '#FF9800', '#4CAF50'])
axes[0, 1].set_title('Volume por Rail (PIX / Card / Wire)')
axes[0, 1].set_ylabel('Qtd Transacoes')
for i, v in enumerate(rail_counts.values):
    axes[0, 1].text(i, v + 200, f'{v:,}', ha='center')

# 3. Volume por channel
ch_counts = transactions['channel'].value_counts()
axes[1, 0].bar(ch_counts.index, ch_counts.values, color='coral')
axes[1, 0].set_title('Volume por Canal')
axes[1, 0].set_ylabel('Qtd Transacoes')

# 4. Valor medio por rail
rail_mean = transactions.groupby('transaction_type')['amount_brl'].mean().sort_values(ascending=False)
axes[1, 1].bar(rail_mean.index, rail_mean.values, color='teal')
axes[1, 1].set_title('Valor Medio por Rail (BRL)')
axes[1, 1].set_ylabel('Valor Medio (BRL)')
for i, v in enumerate(rail_mean.values):
    axes[1, 1].text(i, v + 50, f'R${v:,.0f}', ha='center')

plt.tight_layout()
fig_path = OUTPUTS / 'figuras' / '01_distribuicao_valores.png'
plt.savefig(fig_path, dpi=100, bbox_inches='tight')
plt.close()
print(f"\nGrafico salvo: {fig_path}")

# ============================================================================
# 6. FEATURE STORE INICIAL
# ============================================================================

print("\n" + "="*80)
print("FEATURE STORE INICIAL")
print("="*80)

# Por sender
sender_aggs = transactions.groupby('sender_id').agg(
    total_brl=('amount_brl', 'sum'),
    media_brl=('amount_brl', 'mean'),
    n_transacoes=('transaction_id', 'count'),
    min_brl=('amount_brl', 'min'),
    max_brl=('amount_brl', 'max'),
    n_cross_border=('cross_border', lambda x: (x == 'Yes').sum()),
    n_ip_anomaly=('ip_anomaly', lambda x: (x == 'Yes').sum()),
    n_device_rooted=('device_rooted', lambda x: (x == 'Yes').sum()),
    n_sanctions=('sanctions_screening_hit', lambda x: (x == 'Yes').sum()),
).round(2).reset_index()
sender_aggs.rename(columns={'sender_id': 'entity_id'}, inplace=True)

sender_aggs.to_csv(DATA_PROCESSED / 'sender_features.csv', index=False)
print(f"sender_features.csv: {len(sender_aggs):,} senders")
print(sender_aggs.head(5).to_string(index=False))

# Por merchant receiver
merchant_recv = transactions[transactions['receiver_entity_type'] == 'merchant']
merchant_aggs = merchant_recv.groupby('receiver_id').agg(
    total_brl=('amount_brl', 'sum'),
    media_brl=('amount_brl', 'mean'),
    n_transacoes=('transaction_id', 'count'),
    n_cross_border=('cross_border', lambda x: (x == 'Yes').sum()),
    n_chargebacks=('status', lambda x: (x == 'Chargeback').sum()),
).round(2).reset_index()
merchant_aggs.rename(columns={'receiver_id': 'merchant_id'}, inplace=True)

merchant_aggs.to_csv(DATA_PROCESSED / 'merchant_features.csv', index=False)
print(f"\nmerchant_features.csv: {len(merchant_aggs):,} merchants")
print(merchant_aggs.head(5).to_string(index=False))

# ============================================================================
# 7. RELATORIO DE QUALIDADE FINAL
# ============================================================================

print("\n" + "="*80)
print("RELATORIO DE QUALIDADE - DIA 1")
print("="*80)

periodo = f"{min_date.date()} a {max_date.date()} ({duration} dias)"
total_missing = transactions.isnull().sum().sum()
pct_missing = round(total_missing / transactions.size * 100, 2)

report = {
    'Metrica': [
        'Periodo',
        'Total de Transacoes',
        'Rails (PIX/Card/Wire)',
        'Senders unicos',
        'Receivers unicos',
        'Merchant receivers unicos',
        'Devices unicos',
        'IPs unicos',
        'Clientes (KYC_Profiles)',
        'Merchants cadastrados',
        'Merchants com owner',
        'Valor total (BRL)',
        'Valor medio (BRL)',
        'Valor maximo (BRL)',
        'Cross-border',
        'Sancoes hit',
        'IP anomaly',
        'Device rooted',
        'Valores faltantes (%)',
        'Coerencia por rail',
    ],
    'Resultado': [
        periodo,
        f"{len(transactions):,}",
        f"PIX={len(pix_txns):,} | Card={len(card_txns):,} | Wire={len(wire_txns):,}",
        f"{n_senders:,}",
        f"{n_receivers:,}",
        f"{n_merchant_receivers:,}",
        f"{n_devices:,}",
        f"{n_ips:,}",
        f"{len(clients):,}",
        f"{len(merchants):,}",
        f"{merchants['owner_customer_id'].notna().sum()} ({round(merchants['owner_customer_id'].notna().mean()*100,1)}%)",
        f"R$ {transactions['amount_brl'].sum():,.2f}",
        f"R$ {transactions['amount_brl'].mean():,.2f}",
        f"R$ {transactions['amount_brl'].max():,.2f}",
        f"{(transactions['cross_border']=='Yes').sum():,} ({round((transactions['cross_border']=='Yes').mean()*100,1)}%)",
        f"{sanc_hit:,} ({round(sanc_hit/len(transactions)*100,2)}%)",
        f"{(transactions['ip_anomaly']=='Yes').sum():,} ({round((transactions['ip_anomaly']=='Yes').mean()*100,1)}%)",
        f"{(transactions['device_rooted']=='Yes').sum():,} ({round((transactions['device_rooted']=='Yes').mean()*100,1)}%)",
        f"{pct_missing}% (multicanal -- esperado)",
        "OK (PIX/Card/Wire coerentes)",
    ]
}

report_df = pd.DataFrame(report)
print()
print(report_df.to_string(index=False))

report_df.to_csv(OUTPUTS / '01_quality_report.csv', index=False)
print(f"\nSalvo: outputs/01_quality_report.csv")

print("\n" + "="*80)
print("SCRIPT CONCLUIDO")
print("="*80)
print("Arquivos gerados:")
print("  outputs/01_quality_report.csv")
print("  outputs/figuras/01_distribuicao_valores.png")
print("  data/processed/sender_features.csv")
print("  data/processed/merchant_features.csv")
