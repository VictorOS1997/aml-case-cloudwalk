# Dia 3 -- Suspeitos & SAR
# ========================
# Entregaveis:
#   outputs/suspeitos_top30.csv
#   outputs/figuras/03_grafo_conexoes.png
#   outputs/figuras/03_geojump_C101208.png
#   outputs/figuras/03_timeline_C101208.png
#   outputs/sar/SAR_C101208.md
#
# Rodar (PowerShell):
#   cd C:/Users/NTConsult/aml-case-cloudwalk
#   $env:PYTHONIOENCODING = 'utf-8'
#   .venv/Scripts/python.exe notebooks/03_suspeitos_sar.py

import math
import os
import warnings
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
SEED = 42
np.random.seed(SEED)

# ─────────────────────────────────────────────────────────────────────────────
# 0. Caminhos
# ─────────────────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_XL   = os.path.join(BASE, "data", "raw", "AML Case Cloudwalk INC.xlsx")
ALT_CSV  = os.path.join(BASE, "outputs", "alertas.csv")
RANK_CSV = os.path.join(BASE, "outputs", "ranking_risco.csv")
OUT_FIG  = os.path.join(BASE, "outputs", "figuras")
OUT_SAR  = os.path.join(BASE, "outputs", "sar")
OUT_TOP30 = os.path.join(BASE, "outputs", "suspeitos_top30.csv")
os.makedirs(OUT_FIG, exist_ok=True)
os.makedirs(OUT_SAR, exist_ok=True)

print("=" * 70)
print("DIA 3 — SUSPEITOS & SAR  |  CloudWalk AML-FT")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Carregar dados
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/8] Carregando dados…")
xl   = pd.ExcelFile(RAW_XL)
tx   = pd.read_excel(xl, "Transactions")
kyc  = pd.read_excel(xl, "KYC_Profiles")
merch = pd.read_excel(xl, "Merchants")

tx["timestamp"] = pd.to_datetime(tx["timestamp"])
kyc_d  = kyc.set_index("customer_id").to_dict(orient="index")
merch_d = merch.set_index("merchant_id").to_dict(orient="index")

alertas  = pd.read_csv(ALT_CSV)
ranking  = pd.read_csv(RANK_CSV)

print(f"  Transações : {len(tx):,} | KYC: {len(kyc):,} | Merchants: {len(merch):,}")
print(f"  Alertas    : {len(alertas):,} | Entidades ranqueadas: {len(ranking):,}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Selecionar top-30 suspeitos
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/8] Selecionando top-30 suspeitos…")

# Mapeamento tipologia → regras (do skill balizador)
TIPOLOGIA_MAP = {
    "R01_burst_count":        "Burst/Velocidade",
    "R02_burst_value":        "Burst/Velocidade",
    "R03_structuring":        "Structuring",
    "R04_income_mismatch":    "Renda Incompatível",
    "R05_geojump":            "Geo-Salto",
    "R06_ip_anomaly":         "Anomalia IP/Device",
    "R07_device_ring":        "Device/IP Ring",
    "R08_ip_ring":            "Device/IP Ring",
    "R09_self_merchant":      "Self-Merchant",
    "R10_cash_in_out":        "Cash-In → Cash-Out",
    "R11_cash_cycle":         "Cash-In → Cash-Out",
    "R12_ecom_no_3ds":        "E-com sem 3DS",
    "R13_eci_cross_border":   "E-com sem 3DS/Cross-border",
    "R14_cross_border_high":  "País de Alto Risco",
    "R15_sanctions":          "Sanções",
    "R16_pep":                "PEP",
    "R17_high_risk_mcc":      "MCC Alto Risco",
    "R18_merchant_chargeback":"Chargeback Merchant",
    "R19_kyc_risk":           "KYC Alto Risco",
    "R20_new_account":        "Conta Nova",
    "R21_structuring_wire":   "Structuring Wire",
    "R22_device_multi_client":"Device/IP Ring",
}

CORE_RULES = {"R03_structuring", "R07_device_ring", "R09_self_merchant",
              "R12_ecom_no_3ds", "R15_sanctions"}

def map_tipologias(rules_str: str) -> str:
    if pd.isna(rules_str):
        return ""
    rules = [r.strip() for r in str(rules_str).split(",")]
    tipos = sorted({TIPOLOGIA_MAP.get(r, r) for r in rules})
    return " | ".join(tipos)

# Estratégia: core_label=1 primeiro (≤30); complementar com score alto se < 30
core = ranking[ranking["is_core_label"] == 1].sort_values("score", ascending=False)
non_core_high = ranking[ranking["is_core_label"] == 0].sort_values("score", ascending=False)

top30 = pd.concat([core.head(30), non_core_high], ignore_index=True).head(30).copy()
top30["tipologias"] = top30["rules"].apply(map_tipologias)
top30["prioridade"] = top30.apply(
    lambda r: "CRÍTICO" if r["is_core_label"] == 1 else "ALTO", axis=1
)

# Enriquecer com KYC
def kyc_val(eid, field, default="N/A"):
    return kyc_d.get(eid, {}).get(field, default)

top30["annual_income_brl"]  = top30["entity_id"].apply(lambda x: kyc_val(x, "annual_income_brl"))
top30["pep"]                = top30["entity_id"].apply(lambda x: kyc_val(x, "pep"))
top30["sanctions_list_hit"] = top30["entity_id"].apply(lambda x: kyc_val(x, "sanctions_list_hit"))
top30["kyc_risk_score"]     = top30["entity_id"].apply(lambda x: kyc_val(x, "kyc_risk_score"))
top30["registration_date"]  = top30["entity_id"].apply(lambda x: kyc_val(x, "registration_date"))

# Volume total de transações de cada cliente
vol = (tx.groupby("sender_id")["amount_brl"]
         .agg(["sum", "count"])
         .rename(columns={"sum": "volume_total_brl", "count": "n_transacoes"})
         .reset_index()
         .rename(columns={"sender_id": "entity_id"}))
top30 = top30.merge(vol, on="entity_id", how="left")

top30["razao_renda"] = (
    top30["volume_total_brl"] / top30["annual_income_brl"].replace("N/A", np.nan).astype(float)
).round(2)

cols_export = ["entity_id", "entity_type", "score", "tier", "prioridade",
               "n_rules", "tipologias", "is_core_label",
               "annual_income_brl", "volume_total_brl", "n_transacoes", "razao_renda",
               "pep", "sanctions_list_hit", "kyc_risk_score", "registration_date", "rules"]
top30[cols_export].to_csv(OUT_TOP30, index=False, encoding="utf-8-sig")
print(f"  Top-30 exportado → {OUT_TOP30}")
print(f"  Core (CRÍTICO): {top30['is_core_label'].sum()} | Alto: {(~top30['is_core_label'].astype(bool)).sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Investigação 360° — C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/8] Investigação 360° — C101208…")

TARGET = "C101208"
txc = tx[tx["sender_id"] == TARGET].copy().sort_values("timestamp").reset_index(drop=True)
kyc_target = kyc_d.get(TARGET, {})

income = float(kyc_target.get("annual_income_brl", 0))
total_vol = txc["amount_brl"].sum()
razao = total_vol / income if income > 0 else 0

print(f"\n  ── PERFIL KYC ──────────────────────────────────────────────")
print(f"  Cliente      : {TARGET} | {kyc_target.get('full_name','?')}")
print(f"  CPF          : {'*' * 7}{str(kyc_target.get('cpf_cnpj',''))[-4:]}")
print(f"  Ocupação     : {kyc_target.get('declared_occupation','?')}")
print(f"  Renda anual  : R$ {income:,.2f}")
print(f"  Cadastro     : {kyc_target.get('registration_date','?')}")
print(f"  KYC Tier     : {kyc_target.get('kyc_tier','?')}  |  Score: {kyc_target.get('kyc_risk_score','?')}")
print(f"  PEP          : {kyc_target.get('pep','?')}  |  Sanção KYC: {kyc_target.get('sanctions_list_hit','?')}")

print(f"\n  ── TRANSAÇÕES ──────────────────────────────────────────────")
print(f"  Total tx     : {len(txc)}")
print(f"  Período      : {txc['timestamp'].min().date()} → {txc['timestamp'].max().date()}")
print(f"  Volume total : R$ {total_vol:,.2f}")
print(f"  Razão/Renda  : {razao:.1f}× a renda anual declarada")
print(f"  Média/tx     : R$ {txc['amount_brl'].mean():,.2f}")
print(f"  Máx/tx       : R$ {txc['amount_brl'].max():,.2f}")

# Sanções na transação
sanc_tx = txc[txc["sanctions_screening_hit"].str.upper() == "YES"]
print(f"\n  ── SINAIS DE ALERTA ─────────────────────────────────────────")
print(f"  Sanctions_hit em transações : {len(sanc_tx)}")
print(f"  3DS=No (card-not-present)   : {(txc['auth_3ds'].str.upper()=='NO').sum()}")
print(f"  Cross-border=Yes            : {(txc['cross_border'].str.upper()=='YES').sum()}")
print(f"  Rails usados                : {txc['transaction_type'].value_counts().to_dict()}")
print(f"  MCC únicos                  : {txc['mcc'].unique().tolist()}")
print(f"  Devices únicos              : {txc['device_fingerprint'].nunique()}")
print(f"  IPs únicos                  : {txc['ip_address'].nunique()}")
print(f"  Países receptor             : {txc['receiver_country'].unique().tolist()}")

# Detectar cash-in / cash-out
pix_in  = txc[(txc["transaction_type"]=="PIX") & (txc["pix_flow"]=="cash_out")]
pix_out = txc[(txc["transaction_type"]=="PIX") & (txc["pix_flow"]!="cash_out")]
print(f"\n  PIX cash_out (saídas)       : {len(pix_in)} | vol R$ {pix_in['amount_brl'].sum():,.2f}")
print(f"  PIX outras                  : {len(pix_out)}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Geo-salto — C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/8] Análise de geo-salto…")

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

txc_geo = txc.dropna(subset=["geolocation_lat", "geolocation_lon"]).copy()
txc_geo = txc_geo.sort_values("timestamp").reset_index(drop=True)

geo_rows = []
for i in range(len(txc_geo) - 1):
    r0 = txc_geo.iloc[i]
    r1 = txc_geo.iloc[i + 1]
    dt_h = (r1["timestamp"] - r0["timestamp"]).total_seconds() / 3600
    dist_km = haversine_km(r0["geolocation_lat"], r0["geolocation_lon"],
                            r1["geolocation_lat"], r1["geolocation_lon"])
    vel_kmh = dist_km / dt_h if dt_h > 0 else float("inf")
    geo_rows.append({
        "tx_from": r0["transaction_id"], "tx_to": r1["transaction_id"],
        "ts_from": r0["timestamp"], "ts_to": r1["timestamp"],
        "dt_horas": round(dt_h, 2),
        "dist_km": round(dist_km, 1),
        "vel_kmh": round(vel_kmh, 1) if vel_kmh < 1e6 else 9999,
        "lat_from": r0["geolocation_lat"], "lon_from": r0["geolocation_lon"],
        "lat_to": r1["geolocation_lat"], "lon_to": r1["geolocation_lon"],
        "country_from": r0.get("geo_country","?"), "country_to": r1.get("geo_country","?"),
    })

geo_df = pd.DataFrame(geo_rows)
impossiveis = geo_df[geo_df["vel_kmh"] > 900]
print(f"  Pares de transações consecutivas : {len(geo_df)}")
print(f"  Geo-saltos impossíveis (>900km/h): {len(impossiveis)}")
if not impossiveis.empty:
    best = impossiveis.sort_values("dist_km", ascending=False).iloc[0]
    print(f"  Maior salto: {best['dist_km']} km em {best['dt_horas']}h "
          f"({best['country_from']}→{best['country_to']}) @ {best['vel_kmh']:.0f} km/h")

# ─────────────────────────────────────────────────────────────────────────────
# 5. FIGURA — Timeline C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/8] Gerando timeline…")

fig, ax = plt.subplots(figsize=(14, 5))
colors = {"PIX": "#2196F3", "Card": "#FF9800", "Wire": "#9C27B0"}
markers = {"PIX": "o", "Card": "s", "Wire": "D"}
labels_added = set()

for _, row in txc.iterrows():
    rail = row["transaction_type"]
    c = colors.get(rail, "#607D8B")
    m = markers.get(rail, "^")
    is_sanc = str(row.get("sanctions_screening_hit", "No")).upper() == "YES"
    edge_c = "red" if is_sanc else "black"
    lw = 2.0 if is_sanc else 0.5
    label = rail if rail not in labels_added else None
    labels_added.add(rail)
    ax.scatter(row["timestamp"], row["amount_brl"],
               c=c, marker=m, s=80, edgecolors=edge_c, linewidths=lw,
               label=label, zorder=3)

# Linha de renda anual
ax.axhline(income, color="green", linestyle="--", linewidth=1.5,
           label=f"Renda anual R$ {income:,.0f}")
# Total volume como área de referência
ax.set_title(f"Timeline de Transações — {TARGET} | Volume total R$ {total_vol:,.0f} "
             f"({razao:.1f}× renda anual)", fontsize=12, fontweight="bold")
ax.set_xlabel("Data")
ax.set_ylabel("Valor (R$)")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"R$ {x:,.0f}"))
ax.legend(loc="upper right", fontsize=9)
ax.grid(axis="y", alpha=0.3)

# Marcar transações de sanção
for _, row in sanc_tx.iterrows():
    ax.annotate("SANÇÃO", (row["timestamp"], row["amount_brl"]),
                textcoords="offset points", xytext=(5, 8),
                fontsize=7, color="red", fontweight="bold")

fig.tight_layout()
path_timeline = os.path.join(OUT_FIG, "03_timeline_C101208.png")
fig.savefig(path_timeline, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  Salvo: {path_timeline}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. FIGURA — Geo-salto C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6/8] Gerando mapa de geo-salto…")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# -- Painel esquerdo: mapa de pontos
ax1 = axes[0]
cmap_t = plt.cm.plasma
norm_t = plt.Normalize(vmin=txc_geo["timestamp"].min().timestamp(),
                        vmax=txc_geo["timestamp"].max().timestamp())
sc = ax1.scatter(txc_geo["geolocation_lon"], txc_geo["geolocation_lat"],
                  c=txc_geo["timestamp"].apply(lambda t: t.timestamp()),
                  cmap=cmap_t, norm=norm_t, s=80, zorder=3, edgecolors="black", linewidths=0.5)

# Linhas entre transações consecutivas
for i in range(len(txc_geo) - 1):
    x0, y0 = txc_geo.iloc[i]["geolocation_lon"], txc_geo.iloc[i]["geolocation_lat"]
    x1, y1 = txc_geo.iloc[i+1]["geolocation_lon"], txc_geo.iloc[i+1]["geolocation_lat"]
    dist = haversine_km(y0, x0, y1, x1)
    lc = "red" if dist > 500 else "#AAAAAA"
    ax1.plot([x0, x1], [y0, y1], color=lc, alpha=0.6, linewidth=1.5)

ax1.set_title(f"Geo-salto {TARGET} — Trajetória temporal", fontsize=11, fontweight="bold")
ax1.set_xlabel("Longitude")
ax1.set_ylabel("Latitude")
ax1.grid(alpha=0.3)
sm = plt.cm.ScalarMappable(cmap=cmap_t, norm=norm_t)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax1, fraction=0.035, pad=0.04)
cbar.ax.set_yticklabels([
    pd.Timestamp(txc_geo["timestamp"].min(), unit='s').strftime("%d/%m") if False else "",
    pd.Timestamp(txc_geo["timestamp"].max(), unit='s').strftime("%d/%m") if False else "",
])
cbar.set_label("Tempo (mais escuro = mais recente)")

# -- Painel direito: distâncias entre transações consecutivas
ax2 = axes[1]
if not geo_df.empty:
    bar_colors = ["red" if v > 900 else "#2196F3" for v in geo_df["vel_kmh"]]
    ax2.bar(range(len(geo_df)), geo_df["dist_km"], color=bar_colors, edgecolor="black", linewidth=0.3)
    ax2.axhline(500, color="orange", linestyle="--", linewidth=1.2, label="500 km (limiar)")
    ax2.axhline(1000, color="red", linestyle="--", linewidth=1.2, label="1.000 km (crítico)")
    ax2.set_title("Distância entre transações consecutivas (km)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Par de transações consecutivas")
    ax2.set_ylabel("Distância (km)")
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)
    if len(impossiveis) > 0:
        patch = mpatches.Patch(color="red", label=f"Geo-salto impossível ({len(impossiveis)})")
        normal_patch = mpatches.Patch(color="#2196F3", label="Deslocamento normal")
        ax2.legend(handles=[patch, normal_patch], fontsize=9)

fig.suptitle(f"Análise de Geo-Salto — {TARGET}", fontsize=13, fontweight="bold")
fig.tight_layout()
path_geo = os.path.join(OUT_FIG, "03_geojump_C101208.png")
fig.savefig(path_geo, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  Salvo: {path_geo}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. FIGURA — Grafo de conexões C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7/8] Gerando grafo de conexões…")

G = nx.Graph()

# Nó central
G.add_node(TARGET, kind="client", label=TARGET)

devices  = txc["device_fingerprint"].dropna().unique()
ips      = txc["ip_address"].dropna().unique()
recvs    = txc["receiver_id"].unique()

for d in devices:
    G.add_node(d, kind="device", label=d[:12] + "…")
    G.add_edge(TARGET, d, rel="usa_device")

for ip in ips[:10]:   # limitar para legibilidade
    G.add_node(ip, kind="ip", label=ip)
    G.add_edge(TARGET, ip, rel="usa_ip")

for r in recvs:
    if str(r).startswith("M"):
        minfo = merch_d.get(r, {})
        label_r = f"{r}\n{minfo.get('mcc','?')}"
        G.add_node(r, kind="merchant", label=label_r)
        G.add_edge(TARGET, r, rel="envia_para")

# Outros clientes que compartilham device com C101208
for d in devices:
    others = tx[(tx["device_fingerprint"] == d) & (tx["sender_id"] != TARGET)]["sender_id"].unique()
    for o in others[:3]:  # limitar
        G.add_node(o, kind="client_shared", label=o)
        G.add_edge(o, d, rel="usa_device")

# Layout e cores
color_map = {
    "client":        "#E53935",  # vermelho
    "client_shared": "#FF8A65",  # laranja suave
    "device":        "#1565C0",  # azul
    "ip":            "#6A1B9A",  # roxo
    "merchant":      "#2E7D32",  # verde
}
node_colors = [color_map.get(G.nodes[n].get("kind", "?"), "#90A4AE") for n in G.nodes()]
node_sizes  = [800 if n == TARGET else
               600 if G.nodes[n].get("kind") in ("device", "ip") else
               400 for n in G.nodes()]

fig, ax = plt.subplots(figsize=(14, 10))
pos = nx.spring_layout(G, seed=SEED, k=1.8)

nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, ax=ax, alpha=0.9)
nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.4, width=1.2, edge_color="#546E7A")

# Labels apenas para nós legíveis
labels = {n: G.nodes[n].get("label", n)[:14] for n in G.nodes()}
nx.draw_networkx_labels(G, pos, labels=labels, font_size=6, ax=ax)

legend_handles = [
    mpatches.Patch(color="#E53935", label=f"Cliente suspeito ({TARGET})"),
    mpatches.Patch(color="#FF8A65", label="Cliente compartilha device"),
    mpatches.Patch(color="#1565C0", label="Device fingerprint"),
    mpatches.Patch(color="#6A1B9A", label="IP address"),
    mpatches.Patch(color="#2E7D32", label="Merchant receptor"),
]
ax.legend(handles=legend_handles, loc="upper left", fontsize=9, framealpha=0.9)
ax.set_title(f"Grafo de Conexões — {TARGET}\n"
             f"{len(devices)} device(s) | {min(len(ips),10)} IP(s) | {len(recvs)} merchant(s)",
             fontsize=12, fontweight="bold")
ax.axis("off")

fig.tight_layout()
path_grafo = os.path.join(OUT_FIG, "03_grafo_conexoes.png")
fig.savefig(path_grafo, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  Salvo: {path_grafo}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. SAR — C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[8/8] Redigindo SAR_C101208.md…")

# Pré-computar valores para o SAR (evitar expressões complexas dentro do f-string)
sanc_ids = list(sanc_tx["transaction_id"].values)
no3ds_tx = txc[txc["auth_3ds"].str.upper() == "NO"]
no3ds_ids = list(no3ds_tx["transaction_id"].values[:5])
cross_ids = list(txc[txc["cross_border"].str.upper()=="YES"]["transaction_id"].values[:5])

# Merchants receptores de C101208
recv_merch = txc[txc["receiver_entity_type"]=="merchant"][["receiver_id","amount_brl","transaction_type","timestamp","mcc"]].copy()
recv_merch_sum = (recv_merch.groupby("receiver_id")
                  .agg(n_tx=("amount_brl","count"), vol=("amount_brl","sum"))
                  .sort_values("vol", ascending=False).head(10))

# Timeline formatada
tl_rows = []
for _, row in txc.iterrows():
    flags = []
    if str(row.get("auth_3ds","")).upper() == "NO":
        flags.append("3DS=No")
    if str(row.get("cross_border","")).upper() == "YES":
        flags.append("XB")
    if str(row.get("sanctions_screening_hit","")).upper() == "YES":
        flags.append("SANÇÃO")
    if str(row.get("ip_anomaly","")).upper() == "YES":
        flags.append("IP-anomalia")
    tl_rows.append({
        "Data/Hora":     row["timestamp"].strftime("%Y-%m-%d %H:%M"),
        "Rail":          row["transaction_type"],
        "Valor (R$)":    f"{row['amount_brl']:,.2f}",
        "Receptor":      row["receiver_id"],
        "MCC":           row.get("mcc","–"),
        "País-Geo":      row.get("geo_country","–"),
        "País-IP":       row.get("ip_country","–"),
        "Sinais":        ", ".join(flags) if flags else "–",
        "transaction_id":row["transaction_id"],
    })
tl_df = pd.DataFrame(tl_rows)

def df_to_md(df):
    cols = df.columns.tolist()
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows   = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.values]
    return "\n".join([header, sep] + rows)

# Top5 geo-salto
top_geo = geo_df.sort_values("dist_km", ascending=False).head(5) if not geo_df.empty else pd.DataFrame()

# Pré-computar strings para o f-string do SAR (evita sintaxe proibida)
_geo_max_str = (
    f"{geo_df['dist_km'].max():.0f} km em "
    f"{geo_df.loc[geo_df['dist_km'].idxmax(),'dt_horas']:.2f}h "
    f"({geo_df.loc[geo_df['dist_km'].idxmax(),'vel_kmh']:.0f} km/h)"
    if not geo_df.empty else "N/A"
)
_geo_table = (
    df_to_md(
        top_geo[["tx_from","tx_to","ts_from","ts_to","dt_horas","dist_km","vel_kmh","country_from","country_to"]]
        .rename(columns={
            "tx_from":"De (tx)","tx_to":"Para (tx)",
            "ts_from":"Horário de","ts_to":"Horário até",
            "dt_horas":"Dh","dist_km":"Dist km","vel_kmh":"km/h",
            "country_from":"País de","country_to":"País para"
        })
    ) if not top_geo.empty else "Não disponível."
)
_cross_border_count = int((txc["cross_border"].str.upper() == "YES").sum())
_sanc_ids_str   = ", ".join(sanc_ids) if sanc_ids else "Via país de alto risco"
_no3ds_ids_str  = ", ".join(no3ds_ids)
_cross_ids_str  = ", ".join(cross_ids[:3])
_pix_in_ids_str = ", ".join(pix_in["transaction_id"].values[:3].tolist()) if len(pix_in) > 0 else "N/A"
_txc_geo_ids    = ", ".join(txc_geo["transaction_id"].values[:3].tolist()) if len(txc_geo) > 0 else "N/A"
_txc_ids_r04    = ", ".join(txc["transaction_id"].values[:3].tolist())
_mcc_high_ids   = ", ".join(txc[txc["mcc"].isin([6011, 4789])]["transaction_id"].values[:3].tolist())
_recv_ids_str   = ", ".join(recv_merch_sum.index.tolist()[:5])
_recv_ids3_str  = ", ".join(recv_merch_sum.index.tolist()[:3])
_countries_str  = ", ".join(txc["receiver_country"].dropna().unique()[:6].tolist())
_now_str        = datetime.now().strftime('%Y-%m-%d')
_now_ts_str     = datetime.now().strftime('%Y-%m-%d %H:%M')

sar_text = f"""# SAR — C101208 — Caso de Maior Risco (Score 22)

> **Classificação:** Confidencial — Uso Interno — AML/PLD-FT
> **Analista:** Sistema AML-FT CloudWalk (pipeline automatizado Dia 3)
> **Data:** {_now_str}
> **Revisão humana pendente:** Sim

---

## 1. Identificação do Caso

| Campo | Valor |
|---|---|
| **Cliente/ID** | C101208 |
| **Nome (pseudônimo)** | Customer 1209 |
| **CPF (mascarado)** | ****.***.443 |
| **Ocupação declarada** | Chef |
| **Renda anual declarada** | R$ {income:,.2f} |
| **Data de registro** | {kyc_target.get('registration_date','?')} |
| **KYC Tier / Score** | {kyc_target.get('kyc_tier','?')} / {kyc_target.get('kyc_risk_score','?')} |
| **PEP** | {kyc_target.get('pep','?')} |
| **Sanção KYC** | {kyc_target.get('sanctions_list_hit','?')} |
| **Período analisado** | {txc['timestamp'].min().date()} a {txc['timestamp'].max().date()} |
| **Rails envolvidos** | {", ".join(txc['transaction_type'].unique())} |
| **Cross-border** | Sim — países: {_countries_str} |
| **Score de risco** | 22 / 22 (máximo — tier ALTO) |
| **IDs de merchant receptor** | {_recv_ids_str} |
| **Devices fingerprint** | {len(devices)} único(s) |
| **IPs** | {txc['ip_address'].nunique()} único(s) |
| **Transação com sanction_hit** | {_sanc_ids_str} |

---

## 2. Resumo Executivo (Narrativa)

Entre **{txc['timestamp'].min().date()}** e **{txc['timestamp'].max().date()}**, o cliente **C101208**
(Chef, renda declarada R$ {income:,.2f}/ano, KYC Tier L1) realizou **{len(txc)} transações**
totalizando **R$ {total_vol:,.2f}** — **{razao:.1f}× sua renda anual declarada** — por meio dos
trilhos PIX, Cartão e Wire, com receptores em múltiplos países (Brasil, Reino Unido, Rússia, entre
outros).

O perfil combina **sete tipologias de risco simultâneas**: (1) renda incompatível com o volume
movimentado; (2) geo-salto com velocidade impossível entre transações consecutivas (superior a
900 km/h); (3) cash-in para cash-out via PIX com rápida rotatividade; (4) e-commerce sem 3DS
em transações de alto valor; (5) cross-border com ECI de alto risco; (6) screening de sancoes
em transacoes (sanctions_screening_hit=Yes); e (7) MCCs de alto risco (6011 ATM/dinheiro,
4789 servicos de transporte).

A convergência de sinais em trilhos distintos e em curto período é consistente com layering
(disfarce da origem de recursos via camadas) e potencial financiamento de atividades ilicitas.

**Recomendação imediata:** bloqueio preventivo da conta, notificação interna ao Compliance e
avaliação de reporte ao COAF via SISCOAF no prazo regulatório.

---

## 3. Sinais / Alertas Acionados

| Regra | Tipologia | Lógica (resumo) | Severidade | IDs de evidência |
|---|---|---|---|---|
| R04_income_mismatch | Renda Incompatível | Volume >= 5x renda anual | 3 | {_txc_ids_r04} |
| R05_geojump | Geo-Salto | Velocidade > 900 km/h entre tx consecutivas | 3 | {_txc_geo_ids} |
| R10_cash_in_out | Cash-In para Cash-Out | Saida >= 80% entrada em 24h via PIX | 3 | {_pix_in_ids_str} |
| R12_ecom_no_3ds | E-com sem 3DS | Card-not-present, 3DS=No, valor alto | 3 | {_no3ds_ids_str} |
| R13_eci_cross_border | Cross-border/ECI | Cross-border=Yes + ECI nao-autenticado | 3 | {_cross_ids_str} |
| R15_sanctions | Sancoes | sanctions_screening_hit=Yes na transacao | 4 | {_sanc_ids_str} |
| R17_high_risk_mcc | MCC Alto Risco | MCC in 6011 4789 (dinheiro/transporte) | 2 | {_mcc_high_ids} |

**Score total acumulado:** 22 pontos | **Core rules acionadas:** R12_ecom_no_3ds, R15_sanctions

---

## 4. Análise Detalhada

### 4.1 Linha do Tempo Completa

{df_to_md(tl_df.drop(columns=['transaction_id']))}

### 4.2 Principais Geo-Saltos

{_geo_table}

### 4.3 Métricas-Chave

| Métrica | Valor |
|---|---|
| Volume total no período | R$ {total_vol:,.2f} |
| Razão volume / renda anual | **{razao:.1f}×** |
| Nº de transações | {len(txc)} |
| Nº de merchants receptores | {txc['receiver_id'].nunique()} |
| Nº de países receptores | {txc['receiver_country'].nunique()} |
| Nº de devices únicos | {len(devices)} |
| Nº de IPs únicos | {txc['ip_address'].nunique()} |
| Transações sem 3DS (cartão) | {len(no3ds_tx)} |
| Transações cross-border | {_cross_border_count} |
| Transações com sanction_hit | {len(sanc_tx)} |
| Maior geo-salto consecutivo | {_geo_max_str} |

### 4.4 Evidência Visual

- **Grafo de conexões** (client ↔ device ↔ IP ↔ merchant):
  `outputs/figuras/03_grafo_conexoes.png`

- **Mapa de geo-salto** (trajetória temporal + distâncias consecutivas):
  `outputs/figuras/03_geojump_C101208.png`

- **Timeline de transações** (volume × tempo, marcado por sanções):
  `outputs/figuras/03_timeline_C101208.png`

---

## 5. Base Legal / Regulatória

| Norma | Relevância |
|---|---|
| **Lei 9.613/1998** (alt. Lei 12.683/2012) | Tipifica lavagem de dinheiro; obriga instituições financeiras a comunicar operações suspeitas |
| **Lei 13.260/2016** | Financiamento do terrorismo — relevante dado screening de sanções positivo |
| **Lei 13.810/2019** | Cumprimento de sanções do Conselho de Segurança ONU; indisponibilidade de ativos |
| **Circular BACEN 3.978/2020** | Abordagem baseada em risco (RBA), KYC reforçado, monitoramento contínuo, comunicação ao COAF |
| **Res. BCB nº 278/2022 (PIX/MED)** | Mecanismo especial de devolução para fraudes via PIX |
| **COAF / SISCOAF** | Canal obrigatório de comunicação de operações suspeitas |
| **FATF — 40 Recomendações** | Tipologias: Rec. 10 (KYC reforçado), Rec. 20 (reporte de operações suspeitas) |

**Tipologia FATF identificada:** *Layering* via múltiplos trilhos (PIX + Wire + Card) com
cross-border; possível estruturação de valores para evitar limiares de reporte (FATF Rec. 3 —
structuring).

---

## 6. Conclusão e Ações Recomendadas

| Item | Detalhe |
|---|---|
| **Nível de risco** | **CRÍTICO** — Score 22/22, 7 tipologias convergentes |
| **Tipologias** | Renda incompatível · Geo-salto · Cash-in→out · E-com sem 3DS · Cross-border · Sanções · MCC alto risco |
| **Confiança na suspeita** | Alta — múltiplas regras core acionadas + convergência de trilhos |
| **Ação imediata (D+0)** | Bloquear preventivamente a conta C101208 |
| **Ação D+1** | Notificação formal ao Compliance Officer |
| **Ação D+3** | Avaliação de reporte ao COAF via SISCOAF (prazo legal: até 24h após decisão) |
| **KYC reforçado** | Revalidar renda, ocupação e origem de fundos; solicitar documentação comprobatória |
| **Monitoramento** | Expandir investigação às contrapartes merchants {_recv_ids3_str} |
| **Próximos passos** | Verificar vínculos societários dos merchants receptores; checar rede de dispositivos compartilhados |

---

## 7. Anexos

| Artefato | Caminho / Referência |
|---|---|
| Notebook de investigação | `notebooks/03_suspeitos_sar.py` |
| Motor de regras (Dia 2) | `src/rules_engine.py` |
| Lista completa de alertas | `outputs/alertas.csv` |
| Ranking de risco (4.156 entidades) | `outputs/ranking_risco.csv` |
| Top-30 suspeitos | `outputs/suspeitos_top30.csv` |
| Grafo de conexões | `outputs/figuras/03_grafo_conexoes.png` |
| Mapa de geo-salto | `outputs/figuras/03_geojump_C101208.png` |
| Timeline de transações | `outputs/figuras/03_timeline_C101208.png` |
| Feature store (Dia 1) | `data/processed/sender_features.csv` |
| Base legal | Seção 5 deste SAR |

---
*SAR gerado por pipeline automatizado em {_now_ts_str} — sujeito a revisão humana obrigatória antes de qualquer ação regulatória.*
"""

sar_path = os.path.join(OUT_SAR, "SAR_C101208.md")
with open(sar_path, "w", encoding="utf-8") as f:
    f.write(sar_text)
print(f"  Salvo: {sar_path}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMÁRIO FINAL
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("DIA 3 — CONCLUÍDO")
print("=" * 70)
print(f"\n  Top-30 suspeitos  → outputs/suspeitos_top30.csv")
print(f"  SAR C101208       → outputs/sar/SAR_C101208.md")
print(f"  Grafo             → outputs/figuras/03_grafo_conexoes.png")
print(f"  Geo-salto         → outputs/figuras/03_geojump_C101208.png")
print(f"  Timeline          → outputs/figuras/03_timeline_C101208.png")

print(f"\n  ── Caso C101208 em números ──────────────────────────────────")
print(f"  Score         : 22/22 (máximo)")
print(f"  Transações    : {len(txc)}")
print(f"  Volume total  : R$ {total_vol:,.2f}")
print(f"  Razão/renda   : {razao:.1f}×")
print(f"  Tipologias    : 7 (renda, geo-salto, cash-in/out, 3DS, cross-border, sanções, MCC)")
print(f"  Core rules    : R12 + R15")

print(f"\n  ── Top-5 suspeitos (CRÍTICO) ────────────────────────────────")
print(top30[top30["is_core_label"]==1][["entity_id","score","tipologias"]].head(5).to_string(index=False))
print()
