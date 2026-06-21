#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
"""
Notebook 02 — Motor de Regras & Alertas AML
============================================
Executa as 22 regras do catálogo sobre a base completa (52K transações).

Saídas:
  outputs/alertas.csv              — todos os alertas com IDs de evidência
  outputs/ranking_risco.csv        — ranking de clientes/merchants por score
  outputs/02_relatorio_regras.md   — relatório textual para o case
  outputs/figuras/02_alertas_por_regra.png   — bar chart alertas × regra
  outputs/figuras/02_timeline_alertas.png    — alertas por dia
  outputs/figuras/02_ranking_top20.png       — top-20 entidades por score

Reprodutibilidade: SEED = 42 | Python 3.x | pandas, numpy, matplotlib
"""

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings('ignore')
SEED = 42
np.random.seed(SEED)
sns.set_style('whitegrid')

# ── Caminhos ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / 'data' / 'raw'
DATA_PROC = ROOT / 'data' / 'processed'
OUTPUTS = ROOT / 'outputs'
FIGURAS = OUTPUTS / 'figuras'
SRC = ROOT / 'src'
CONFIG_PATH = ROOT / 'config' / 'rules.yaml'

sys.path.insert(0, str(SRC))
from rules_engine import RulesEngine, build_ranking
from features import create_feature_store

OUTPUTS.mkdir(parents=True, exist_ok=True)
FIGURAS.mkdir(parents=True, exist_ok=True)
DATA_PROC.mkdir(parents=True, exist_ok=True)

print(f"{'='*70}")
print(f"NOTEBOOK 02 — MOTOR DE REGRAS AML  |  SEED={SEED}")
print(f"{'='*70}")
print(f"Raiz do projeto: {ROOT}")

# ── Severidade → cor ──────────────────────────────────────────────────────────
SEV_COLOR = {1: '#AED6F1', 2: '#F39C12', 3: '#E74C3C', 4: '#8E44AD'}
SEV_LABEL = {1: 'baixa (1)', 2: 'média (2)', 3: 'alta (3)', 4: 'crítica (4)'}

# ============================================================================
# 1. CARREGAR DADOS
# ============================================================================
print(f"\n{'-'*60}")
print("1. CARREGANDO DADOS")
print(f"{'-'*60}")

excel_file = DATA_RAW / 'AML Case Cloudwalk INC.xlsx'
transactions = pd.read_excel(excel_file, sheet_name='Transactions')
clients = pd.read_excel(excel_file, sheet_name='KYC_Profiles')
merchants = pd.read_excel(excel_file, sheet_name='Merchants')

transactions['timestamp'] = pd.to_datetime(transactions['timestamp'])
clients['registration_date'] = pd.to_datetime(clients['registration_date'], errors='coerce')

print(f"Transactions : {transactions.shape[0]:,} linhas × {transactions.shape[1]} colunas")
print(f"KYC_Profiles : {clients.shape[0]:,} linhas × {clients.shape[1]} colunas")
print(f"Merchants    : {merchants.shape[0]:,} linhas × {merchants.shape[1]} colunas")
print(f"Período      : {transactions['timestamp'].min().date()} → {transactions['timestamp'].max().date()}")

# ============================================================================
# 2. FEATURE STORE
# ============================================================================
print(f"\n{'-'*60}")
print("2. FEATURE STORE")
print(f"{'-'*60}")

features = create_feature_store(transactions, clients, merchants)

client_features = features['client']
merchant_features = features['merchant']
device_features = features['device']
ip_features = features['ip']

client_features.to_csv(DATA_PROC / 'client_features_v2.csv', index=False)
merchant_features.to_csv(DATA_PROC / 'merchant_features_v2.csv', index=False)
device_features.to_csv(DATA_PROC / 'device_features.csv', index=False)
ip_features.to_csv(DATA_PROC / 'ip_features.csv', index=False)

print(f"client_features  : {len(client_features):,} entidades")
print(f"merchant_features: {len(merchant_features):,} entidades")
print(f"device_features  : {len(device_features):,} devices  | rings(≥6): {device_features['is_device_ring'].sum()}")
print(f"ip_features      : {len(ip_features):,} IPs      | rings(≥6): {ip_features['is_ip_ring'].sum()}")

# ============================================================================
# 3. EXECUTAR REGRAS
# ============================================================================
print(f"\n{'-'*60}")
print("3. EXECUTANDO 22 REGRAS")
print(f"{'-'*60}")

engine = RulesEngine(str(CONFIG_PATH))
alerts = engine.execute_all_rules(transactions, clients, merchants)

print(f"\nTotal de alertas gerados: {len(alerts):,}")
if not alerts.empty:
    print(f"Entidades únicas alertadas: {alerts['entity_id'].nunique():,}")
    print(f"Regras disparadas: {alerts['rule_id'].nunique()}/22")

# ============================================================================
# 4. ANÁLISE DE ALERTAS
# ============================================================================
print(f"\n{'-'*60}")
print("4. ANÁLISE DE ALERTAS")
print(f"{'-'*60}")

if alerts.empty:
    print("[WARN] Nenhum alerta gerado. Verifique as colunas da base.")
    sys.exit(1)

# 4.1 Contagem por regra
print("\n--- Alertas por Regra ---")
by_rule = (
    alerts.groupby(['rule_id', 'severity'])
    .size()
    .reset_index(name='n_alertas')
    .sort_values('n_alertas', ascending=False)
)
print(by_rule.to_string(index=False))

# 4.2 Contagem por severidade
print("\n--- Alertas por Severidade ---")
by_sev = alerts.groupby('severity').size().reset_index(name='n_alertas')
for _, r in by_sev.iterrows():
    print(f"  Severidade {int(r['severity'])} ({SEV_LABEL[int(r['severity'])]}): {int(r['n_alertas'])} alertas")

# 4.3 Contagem por entidade_tipo
print("\n--- Alertas por Tipo de Entidade ---")
print(alerts.groupby('entity_type').size().to_string())

# ============================================================================
# 5. RANKING DE RISCO
# ============================================================================
print(f"\n{'-'*60}")
print("5. RANKING DE RISCO")
print(f"{'-'*60}")

ranking = build_ranking(alerts)
print(f"\nEntidades no ranking: {len(ranking):,}")
print(f"Com weak label (core ≥2): {ranking['is_core_label'].sum()}")

print("\n--- Top 20 Entidades por Score de Risco ---")
top20 = ranking.head(20)
print(top20[['entity_id', 'entity_type', 'score', 'n_rules', 'is_core_label', 'tier', 'rules']].to_string(index=False))

# ============================================================================
# 6. VISUALIZAÇÕES
# ============================================================================
print(f"\n{'-'*60}")
print("6. GERANDO VISUALIZAÇÕES")
print(f"{'-'*60}")

# ── 6.1 Alertas por regra (bar chart horizontal) ──────────────────────────
fig, ax = plt.subplots(figsize=(12, 8))

by_rule_plot = by_rule.sort_values('n_alertas')
colors = [SEV_COLOR.get(int(s), '#95A5A6') for s in by_rule_plot['severity']]
bars = ax.barh(by_rule_plot['rule_id'], by_rule_plot['n_alertas'], color=colors, edgecolor='white', linewidth=0.5)

for bar, val in zip(bars, by_rule_plot['n_alertas']):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f'{int(val):,}', va='center', fontsize=9)

patches = [mpatches.Patch(color=v, label=SEV_LABEL[k]) for k, v in SEV_COLOR.items() if k in by_rule['severity'].values]
ax.legend(handles=patches, title='Severidade', loc='lower right', fontsize=9)
ax.set_xlabel('Número de Alertas', fontsize=11)
ax.set_title('Alertas por Regra AML (22 Regras Implementadas)', fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
fig.savefig(FIGURAS / '02_alertas_por_regra.png', dpi=120, bbox_inches='tight')
plt.close()
print(f"  Salvo: outputs/figuras/02_alertas_por_regra.png")

# ── 6.2 Timeline de alertas por dia ────────────────────────────────────────
# Resgata timestamps originais via evidence_ids → join com transactions
alerts_with_ts = alerts.copy()

# Pegar a data de pelo menos uma evidência por alerta
def _first_ts(ev_str):
    try:
        first_id = ev_str.split(';')[0].strip()
        row = transactions[transactions['transaction_id'] == first_id]
        if not row.empty:
            return row.iloc[0]['timestamp'].date()
    except Exception:
        pass
    return None

alerts_with_ts['date'] = alerts_with_ts['evidence_ids'].apply(_first_ts)
alerts_with_ts = alerts_with_ts.dropna(subset=['date'])

if not alerts_with_ts.empty:
    daily_alerts = alerts_with_ts.groupby('date').size().reset_index(name='n_alertas')
    daily_alerts['date'] = pd.to_datetime(daily_alerts['date'])

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(daily_alerts['date'], daily_alerts['n_alertas'], color='#2980B9', alpha=0.8, width=0.8)
    ax.set_xlabel('Data', fontsize=11)
    ax.set_ylabel('Número de Alertas', fontsize=11)
    ax.set_title('Volume de Alertas por Dia (Jul–Out 2025)', fontsize=13, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    fig.savefig(FIGURAS / '02_timeline_alertas.png', dpi=120, bbox_inches='tight')
    plt.close()
    print(f"  Salvo: outputs/figuras/02_timeline_alertas.png")

# ── 6.3 Top-20 entidades (horizontal bar) ──────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 8))
top20_plot = top20.sort_values('score')
tier_colors = {'alto': '#E74C3C', 'medio': '#F39C12', 'baixo': '#27AE60'}
t_colors = [tier_colors.get(str(t), '#95A5A6') for t in top20_plot['tier']]
bars = ax.barh(top20_plot['entity_id'], top20_plot['score'], color=t_colors, edgecolor='white')

for bar, n_r, lbl in zip(bars, top20_plot['n_rules'], top20_plot['is_core_label']):
    core_mark = ' ★' if lbl else ''
    ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
            f'{int(bar.get_width())} pts ({int(n_r)} regras){core_mark}',
            va='center', fontsize=8)

patches_tier = [mpatches.Patch(color=v, label=k.capitalize()) for k, v in tier_colors.items()]
ax.legend(handles=patches_tier, title='Tier de Risco', loc='lower right')
ax.set_xlabel('Score de Risco (Σ Severidades)', fontsize=11)
ax.set_title('Top-20 Entidades por Score de Risco AML', fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
fig.savefig(FIGURAS / '02_ranking_top20.png', dpi=120, bbox_inches='tight')
plt.close()
print(f"  Salvo: outputs/figuras/02_ranking_top20.png")

# ── 6.4 Distribuição de scores ─────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].hist(ranking['score'], bins=30, color='#2980B9', edgecolor='white')
axes[0].set_xlabel('Score de Risco')
axes[0].set_ylabel('Frequência')
axes[0].set_title('Distribuição de Scores de Risco')
axes[0].grid(alpha=0.3)

tier_counts = ranking['tier'].value_counts()
colors_t = [tier_colors.get(str(t), '#95A5A6') for t in tier_counts.index]
axes[1].pie(tier_counts.values, labels=tier_counts.index, autopct='%1.1f%%',
            colors=colors_t, startangle=90)
axes[1].set_title('Distribuição por Tier de Risco')

plt.tight_layout()
fig.savefig(FIGURAS / '02_distribuicao_scores.png', dpi=120, bbox_inches='tight')
plt.close()
print(f"  Salvo: outputs/figuras/02_distribuicao_scores.png")

# ============================================================================
# 7. EXPORTAR CSV
# ============================================================================
print(f"\n{'-'*60}")
print("7. EXPORTANDO OUTPUTS")
print(f"{'-'*60}")

alerts.to_csv(OUTPUTS / 'alertas.csv', index=False, encoding='utf-8-sig')
print(f"  alertas.csv: {len(alerts):,} registros")

ranking.to_csv(OUTPUTS / 'ranking_risco.csv', index=False, encoding='utf-8-sig')
print(f"  ranking_risco.csv: {len(ranking):,} entidades")

# ============================================================================
# 8. RELATÓRIO DE REGRAS (Markdown)
# ============================================================================
print(f"\n{'-'*60}")
print("8. GERANDO RELATÓRIO DE REGRAS")
print(f"{'-'*60}")

# Mapa de regras para o relatório
RULE_META = {
    'R01_velocity':             ('Velocidade', 'Comportamento/Velocidade', 2),
    'R02_burst_value':          ('Burst de Valor', 'Comportamento/Velocidade', 2),
    'R03_structuring':          ('Structuring PIX ★', 'Structuring/Smurfing', 3),
    'R04_income_mismatch':      ('Renda Incompatível', 'Renda × Valor', 2),
    'R05_geojump':              ('Geo-Salto', 'Geografia', 3),
    'R06_ip_anomaly':           ('IP Anômalo/País Risco', 'Geografia/Device', 2),
    'R07_device_ring':          ('Device Ring ★', 'Device/IP Ring', 3),
    'R08_ip_ring':              ('IP Ring', 'Device/IP Ring', 3),
    'R09_self_merchant':        ('Self-Merchant ★', 'Self-Merchant', 4),
    'R10_cash_in_out':          ('Cash-in → Cash-out', 'Cash-in/out', 3),
    'R11_fan_out':              ('Fan-out', 'Cash-in/out / Dispersão', 2),
    'R12_ecom_no_3ds':          ('E-commerce sem 3DS ★', 'E-commerce / 3DS', 3),
    'R13_eci_cross_border':     ('ECI Cross-border', 'E-commerce / 3DS', 2),
    'R14_cross_border_high':    ('Cross-border Alto Valor', 'País de Risco', 2),
    'R15_sanctions':            ('Sanções ★', 'Sanções / País Risco', 4),
    'R16_pep':                  ('PEP Ativo', 'PEP / MCC Risco', 3),
    'R17_high_risk_mcc':        ('MCC Alto Risco', 'PEP / MCC Risco', 2),
    'R18_chargeback_merchant':  ('Chargeback Merchant', 'Chargeback', 2),
    'R19_installments_atypical':('Parcelamento Atípico', 'Comportamento', 1),
    'R20_new_account':          ('Conta Nova Alta Atividade', 'Comportamento', 2),
    'R21_round_values':         ('Valores Redondos', 'Structuring', 1),
    'R22_card_multidevice':     ('Card Multi-Device', 'Device/IP Ring', 3),
}

n_core = ranking['is_core_label'].sum()
top1 = ranking.iloc[0] if not ranking.empty else None

# Conta alertas por regra para exemplos
rule_alerts = alerts.groupby('rule_id').first().reset_index()

lines = [
    "# Relatório de Regras de Alerta — Dia 2",
    f"**Projeto:** AML-FT Case CloudWalk  ",
    f"**Data:** 2026-06-21  ",
    f"**Script:** `notebooks/02_regras_alertas.py`  ",
    "",
    "---",
    "",
    "## 1. Resumo Executivo",
    "",
    f"| Métrica | Valor |",
    f"|---------|-------|",
    f"| Transações analisadas | {len(transactions):,} |",
    f"| Regras implementadas | 22 |",
    f"| Regras que dispararam alertas | {alerts['rule_id'].nunique()} |",
    f"| Total de alertas gerados | {len(alerts):,} |",
    f"| Entidades únicas alertadas | {alerts['entity_id'].nunique():,} |",
    f"| Clientes no ranking | {len(ranking[ranking['entity_type']=='client']):,} |",
    f"| Merchants no ranking | {len(ranking[ranking['entity_type']=='merchant']):,} |",
    f"| Weak label positivo (≥2 regras-core) | {int(n_core)} |",
    "",
    "---",
    "",
    "## 2. Catálogo de Regras Executadas",
    "",
    "★ = regra-core (usada como rótulo fraco para o ML no Dia 4)",
    "",
    "| Regra | Nome | Tipologia | Sev | Alertas | Exemplo (ID) |",
    "|-------|------|-----------|-----|---------|--------------|",
]

for rule_id, (name, tipologia, sev) in RULE_META.items():
    n_a = len(alerts[alerts['rule_id'] == rule_id]) if not alerts.empty else 0
    first_alert = alerts[alerts['rule_id'] == rule_id]
    if not first_alert.empty:
        ex = first_alert.iloc[0]['evidence_ids'].split(';')[0]
    else:
        ex = '—'
    lines.append(f"| {rule_id} | {name} | {tipologia} | {sev} | {n_a:,} | `{ex}` |")

lines += [
    "",
    "---",
    "",
    "## 3. Top-20 Entidades por Score de Risco",
    "",
    "| Rank | Entity ID | Tipo | Score | N° Regras | Core Label | Tier | Regras Disparadas |",
    "|------|-----------|------|-------|-----------|------------|------|-------------------|",
]

for i, row in ranking.head(20).iterrows():
    core_str = "★ SIM" if row['is_core_label'] else "não"
    lines.append(
        f"| {ranking.index.get_loc(i)+1} | {row['entity_id']} | {row['entity_type']} "
        f"| {int(row['score'])} | {int(row['n_rules'])} | {core_str} | {row['tier']} "
        f"| {row['rules']} |"
    )

lines += [
    "",
    "---",
    "",
    "## 4. Análise por Tipologia",
    "",
    "| Tipologia | Regras | Total Alertas |",
    "|-----------|--------|---------------|",
]

tipologia_map = {}
for rule_id, (_, tipologia, _) in RULE_META.items():
    if tipologia not in tipologia_map:
        tipologia_map[tipologia] = {'rules': [], 'alerts': 0}
    tipologia_map[tipologia]['rules'].append(rule_id)
    if not alerts.empty:
        tipologia_map[tipologia]['alerts'] += len(alerts[alerts['rule_id'] == rule_id])

for tip, data in sorted(tipologia_map.items(), key=lambda x: -x[1]['alerts']):
    rules_str = ', '.join(data['rules'])
    lines.append(f"| {tip} | {rules_str} | {data['alerts']:,} |")

lines += [
    "",
    "---",
    "",
    "## 5. Distribuição por Severidade",
    "",
    "| Severidade | Label | Alertas | % |",
    "|-----------|-------|---------|---|",
]
total_alerts = len(alerts)
for sev_val in [4, 3, 2, 1]:
    n_s = len(alerts[alerts['severity'] == sev_val]) if not alerts.empty else 0
    pct = n_s / total_alerts * 100 if total_alerts > 0 else 0
    lines.append(f"| {sev_val} | {SEV_LABEL[sev_val]} | {n_s:,} | {pct:.1f}% |")

lines += [
    "",
    "---",
    "",
    "## 6. Sinais de Risco Prioritários (candidatos ao SAR — Dia 3)",
    "",
]

# Candidatos ao SAR: clientes com score mais alto E is_core_label
sar_candidates = ranking[
    (ranking['entity_type'] == 'client') & (ranking['is_core_label'] == 1)
].head(5)

if sar_candidates.empty:
    sar_candidates = ranking[ranking['entity_type'] == 'client'].head(5)

lines.append("Candidatos priorizados por score + weak label (≥2 regras-core):\n")
for i, (_, row) in enumerate(sar_candidates.iterrows(), 1):
    lines.append(f"**{i}. {row['entity_id']}** — Score {int(row['score'])} pts | "
                 f"{int(row['n_rules'])} regras | {row['rules']}")

lines += [
    "",
    "---",
    "",
    "## 7. Próximos Passos (Dia 3 — Suspeitos & SAR)",
    "",
    "- Selecionar ≤30 clientes a partir do ranking acima",
    "- Construir visão 360° do caso #1 (entity_id com maior score + core_label)",
    "- Mapear grafo de relacionamento (device, IP, merchant, contrapartes)",
    "- Escrever 1 SAR completo (template-sar.md) com timeline e evidências",
    "",
    "---",
    "",
    "## 8. Arquivos Gerados",
    "",
    "| Arquivo | Descrição |",
    "|---------|-----------|",
    "| `outputs/alertas.csv` | Todos os alertas com evidence_ids |",
    "| `outputs/ranking_risco.csv` | Ranking de risco por entidade |",
    "| `outputs/02_relatorio_regras.md` | Este relatório |",
    "| `outputs/figuras/02_alertas_por_regra.png` | Bar chart alertas × regra |",
    "| `outputs/figuras/02_timeline_alertas.png` | Alertas por dia |",
    "| `outputs/figuras/02_ranking_top20.png` | Top-20 por score |",
    "| `outputs/figuras/02_distribuicao_scores.png` | Distribuição de scores |",
    "| `data/processed/client_features_v2.csv` | Feature store completo (cliente) |",
    "| `data/processed/merchant_features_v2.csv` | Feature store (merchant) |",
    "| `data/processed/device_features.csv` | Feature store (device) |",
    "| `data/processed/ip_features.csv` | Feature store (IP) |",
]

report_path = OUTPUTS / '02_relatorio_regras.md'
report_path.write_text('\n'.join(lines), encoding='utf-8')
print(f"  02_relatorio_regras.md: {len(lines)} linhas")

# ============================================================================
# 9. RESUMO FINAL
# ============================================================================
print(f"\n{'='*70}")
print("NOTEBOOK 02 CONCLUÍDO")
print(f"{'='*70}")
print(f"  Total alertas:       {len(alerts):,}")
print(f"  Regras disparadas:   {alerts['rule_id'].nunique()}/22")
print(f"  Entidades únicas:    {alerts['entity_id'].nunique():,}")
print(f"  Weak label positivo: {int(n_core)} clientes/merchants")
if top1 is not None:
    print(f"  Candidato #1 SAR:    {top1['entity_id']} (score={int(top1['score'])}, tier={top1['tier']})")
print()
print("Arquivos salvos em outputs/:")
for f in sorted(OUTPUTS.glob('*.csv')) + sorted(OUTPUTS.glob('*.md')):
    print(f"  {f.name}")
for f in sorted(FIGURAS.glob('02_*.png')):
    print(f"  figuras/{f.name}")
print(f"\n  → Próximo passo: Dia 3 — Suspeitos & SAR")
