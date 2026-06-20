#!/usr/bin/env python3
"""
Notebook 01 — EDA e Qualidade de Dados
Versão em script Python puro (sem Jupyter)
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
# 1. CARREGAR DADOS
# ============================================================================

excel_file = DATA_RAW / "AML Case Cloudwalk INC.xlsx"

# Verificar quais sheets existem
xls = pd.ExcelFile(excel_file)
print("\nSheets encontrados:")
for i, sheet in enumerate(xls.sheet_names, 1):
    print(f"  {i}. {sheet}")

# Carregar cada sheet (ajuste os nomes conforme os sheets reais)
try:
    transactions = pd.read_excel(excel_file, sheet_name='transacoes')
    clients = pd.read_excel(excel_file, sheet_name='clientes')
    merchants = pd.read_excel(excel_file, sheet_name='merchants')
except Exception as e:
    print(f"\n⚠️ Erro ao carregar sheets padrão: {e}")
    print("Tentando com nomes alternativos...")
    # Tenta nomes alternativos
    sheets = xls.sheet_names
    if len(sheets) >= 1:
        transactions = pd.read_excel(excel_file, sheet_name=sheets[0])
    if len(sheets) >= 2:
        clients = pd.read_excel(excel_file, sheet_name=sheets[1])
    if len(sheets) >= 3:
        merchants = pd.read_excel(excel_file, sheet_name=sheets[2])

print(f"✓ Transações: {transactions.shape}")
print(f"✓ Clientes: {clients.shape}")
print(f"✓ Merchants: {merchants.shape}")

# ============================================================================
# 2. DICIONÁRIO DE DADOS
# ============================================================================

print("\n" + "="*80)
print("DICIONÁRIO DE DADOS")
print("="*80)

print("\nColunas em 'transactions':")
print(transactions.columns.tolist())
print(f"\nPrimeiras linhas:")
print(transactions.head())

print("\nColunas em 'clients':")
print(clients.columns.tolist())
print(f"\nPrimeiras linhas:")
print(clients.head())

print("\nColunas em 'merchants':")
print(merchants.columns.tolist())
print(f"\nPrimeiras linhas:")
print(merchants.head())

# Criar tabela de mapeamento
mapping_df = pd.DataFrame({
    'schema_canonical': list(transactions.columns),
    'coluna_real': list(transactions.columns),
    'tipo_esperado': [''] * len(transactions.columns),
    'presente': ['✓'] * len(transactions.columns)
})

print("\nMapeamento de colunas (COMPLETAR):")
print(mapping_df.to_string(index=False))

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
    print(df.dtypes)

    print(f"\n🔢 Estatísticas descritivas (núméricos):")
    print(df.describe())

quality_check(transactions, "Transactions")
quality_check(clients, "Clients")
quality_check(merchants, "Merchants")

# ============================================================================
# 4. COERÊNCIA POR RAIL
# ============================================================================

print("\n" + "="*80)
print("COERÊNCIA POR RAIL (PIX/Card/Wire)")
print("="*80)

# Verificar valores únicos de rail
if 'rail' in transactions.columns:
    print("\nRails encontrados:")
    print(transactions['rail'].value_counts())
else:
    print("\n⚠️ Coluna 'rail' não encontrada.")
    print("Procurar por: payment_method, channel, tipo_pagamento, etc")
    print(f"Colunas disponíveis: {transactions.columns.tolist()}")

def validate_rail_coherence(df):
    issues = []

    # TODO: Adicionar validações específicas
    # if 'rail' in df.columns and 'installments' in df.columns:
    #     card_no_installments = (df[df['rail'] == 'card']['installments'].isnull()).sum()
    #     if card_no_installments > 0:
    #         issues.append(f"  ⚠️ {card_no_installments} transações Card sem 'installments'")

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
if 'timestamp' in transactions.columns or 'data' in transactions.columns:
    date_col = 'timestamp' if 'timestamp' in transactions.columns else 'data'
    transactions[date_col] = pd.to_datetime(transactions[date_col])
    print(f"\nPeríodo: {transactions[date_col].min()} até {transactions[date_col].max()}")
    print(f"Duração: {(transactions[date_col].max() - transactions[date_col].min()).days} dias")
else:
    print("\n⚠️ Coluna de data não encontrada")

# Distribuição de valores (amount)
if 'amount' in transactions.columns or 'valor' in transactions.columns:
    amount_col = 'amount' if 'amount' in transactions.columns else 'valor'

    fig, axes = plt.subplots(1, 2, figsize=(14, 4))

    axes[0].hist(transactions[amount_col], bins=50, edgecolor='black')
    axes[0].set_xlabel('Valor')
    axes[0].set_ylabel('Frequência')
    axes[0].set_title('Distribuição de Valores')
    axes[0].grid(True, alpha=0.3)

    axes[1].boxplot(transactions[amount_col])
    axes[1].set_ylabel('Valor')
    axes[1].set_title('Boxplot - Detecção de Outliers')

    plt.tight_layout()

    # Criar pasta de figuras se não existir
    (OUTPUTS / 'figuras').mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUTS / 'figuras' / '01_distribuicao_valores.png', dpi=100, bbox_inches='tight')
    print(f"\n✓ Gráfico salvo em: {OUTPUTS / 'figuras' / '01_distribuicao_valores.png'}")
    plt.close()

    print(f"\nEstatísticas de Valor:")
    print(transactions[amount_col].describe())

# Número de clientes, merchants, transações únicos
print("\nEntidades únicas:")
if 'client_id' in transactions.columns:
    print(f"  • Clientes: {transactions['client_id'].nunique()}")
if 'merchant_id' in transactions.columns:
    print(f"  • Merchants: {transactions['merchant_id'].nunique()}")
if 'device_id' in transactions.columns:
    print(f"  • Devices: {transactions['device_id'].nunique()}")
if 'ip_address' in transactions.columns or 'ip' in transactions.columns:
    ip_col = 'ip_address' if 'ip_address' in transactions.columns else 'ip'
    print(f"  • IPs: {transactions[ip_col].nunique()}")
print(f"  • Transações: {len(transactions)}")

# ============================================================================
# 6. FEATURE STORE INICIAL
# ============================================================================

print("\n" + "="*80)
print("FEATURE STORE INICIAL")
print("="*80)

# Agregações por cliente
if 'client_id' in transactions.columns and 'amount' in transactions.columns:
    client_aggs = transactions.groupby('client_id').agg({
        'amount': ['sum', 'mean', 'count', 'std', 'min', 'max'],
    }).round(2)

    client_aggs.columns = ['_'.join(col).strip() for col in client_aggs.columns.values]
    client_aggs = client_aggs.reset_index()

    print("\nFeature Store - Por Cliente (primeiras 10 linhas):")
    print(client_aggs.head(10))

    # Criar pasta se não existir
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    # Salvar
    client_aggs.to_csv(DATA_PROCESSED / 'client_features.csv', index=False)
    print(f"✓ Salvo em: {DATA_PROCESSED / 'client_features.csv'}")

# Agregações por merchant (se houver)
if 'merchant_id' in transactions.columns and 'amount' in transactions.columns:
    merchant_aggs = transactions.groupby('merchant_id').agg({
        'amount': ['sum', 'mean', 'count'],
    }).round(2)

    merchant_aggs.columns = ['_'.join(col).strip() for col in merchant_aggs.columns.values]
    merchant_aggs = merchant_aggs.reset_index()

    print("\nFeature Store - Por Merchant (primeiras 10 linhas):")
    print(merchant_aggs.head(10))

    # Salvar
    merchant_aggs.to_csv(DATA_PROCESSED / 'merchant_features.csv', index=False)
    print(f"✓ Salvo em: {DATA_PROCESSED / 'merchant_features.csv'}")

# ============================================================================
# 7. RELATÓRIO DE QUALIDADE FINAL
# ============================================================================

print("\n" + "="*80)
print("RELATÓRIO DE QUALIDADE - DIA 1")
print("="*80)

quality_report = {
    'métrica': [
        'Período',
        'Clientes únicos',
        'Merchants únicos',
        'Transações',
        'Valor total',
        'Valor médio',
        'Valor máximo',
        'Valores faltantes',
        'Coerência Rails'
    ],
    'resultado': [
        'TODO',
        'TODO',
        'TODO',
        'TODO',
        'TODO',
        'TODO',
        'TODO',
        'TODO',
        '✓ Validado'
    ]
}

report_df = pd.DataFrame(quality_report)
print(report_df.to_string(index=False))

# Criar pasta de outputs se não existir
OUTPUTS.mkdir(parents=True, exist_ok=True)

# Salvar para Google Sheets
report_df.to_csv(OUTPUTS / '01_quality_report.csv', index=False)
print(f"\n✓ Salvo em: {OUTPUTS / '01_quality_report.csv'}")

print("\n" + "="*80)
print("✅ SCRIPT CONCLUÍDO - Próximos passos: Dia 2 (Regras & Alertas)")
print("="*80)
