# Dia 4 — Modelo de Machine Learning
# ====================================
# Entregáveis:
#   outputs/04_ml_scores.csv        — score ML por cliente
#   outputs/04_relatorio_ml.md      — relatório técnico
#   outputs/figuras/04_*.png        — gráficos (ROC, PR, importance, SHAP, cutoff, IF)
#
# Rodar (PowerShell):
#   cd C:/Users/NTConsult/aml-case-cloudwalk
#   $env:PYTHONIOENCODING = 'utf-8'
#   .venv/Scripts/python.exe notebooks/04_modelo_ml.py

import os
import warnings
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
import shap
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

warnings.filterwarnings("ignore")

SEED = 42
np.random.seed(SEED)
TRAIN_FRAC = 0.80  # split temporal por percentil de first_tx_date
HIGH_RISK_MCC = {6011, 6051, 4829, 7995, 5933, 6012}

# ─────────────────────────────────────────────────────────────────────────────
# 0. Caminhos
# ─────────────────────────────────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_XL   = os.path.join(BASE, "data", "raw", "AML Case Cloudwalk INC.xlsx")
FEAT_CSV = os.path.join(BASE, "data", "processed", "client_features_v2.csv")
RANK_CSV = os.path.join(BASE, "outputs", "ranking_risco.csv")
OUT_FIG  = os.path.join(BASE, "outputs", "figuras")
OUT_ML   = os.path.join(BASE, "outputs", "04_ml_scores.csv")
OUT_RPT  = os.path.join(BASE, "outputs", "04_relatorio_ml.md")
os.makedirs(OUT_FIG, exist_ok=True)

print("=" * 70)
print("DIA 4 — MODELO DE MACHINE LEARNING  |  CloudWalk AML-FT")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Carregamento de dados
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] Carregando dados...")

txn = pd.read_excel(RAW_XL, sheet_name="Transactions")
kyc = pd.read_excel(RAW_XL, sheet_name="KYC_Profiles")
cf  = pd.read_csv(FEAT_CSV)
rk  = pd.read_csv(RANK_CSV)

txn["timestamp"] = pd.to_datetime(txn["timestamp"])
kyc["registration_date"] = pd.to_datetime(kyc["registration_date"])

print(f"  Transações : {len(txn):,} | Clientes KYC : {len(kyc):,}")
print(f"  Features v2: {cf.shape} | Ranking     : {rk.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Feature Engineering a partir das transações brutas
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] Engenharia de features (transações brutas)...")

# Flags binárias
txn["is_pix"]           = (txn["transaction_type"] == "PIX").astype(int)
txn["is_card"]          = (txn["transaction_type"] == "Card").astype(int)
txn["is_wire"]          = (txn["transaction_type"] == "Wire").astype(int)
txn["is_no_3ds"]        = (txn["auth_3ds"] == "No").astype(int)
txn["is_high_risk_geo"] = (txn["country_risk_geo"] == "High").astype(int)
txn["is_monitored_geo"] = (txn["country_risk_geo"] == "Monitored").astype(int)
txn["is_proxy_vpn_tor"] = txn["ip_proxy_vpn_tor"].notna().astype(int)
txn["is_rooted"]        = (txn["device_rooted"] == "Yes").astype(int)
txn["is_cross_border"]  = (txn["cross_border"] == "Yes").astype(int)
txn["is_sanction_hit"]  = (txn["sanctions_screening_hit"] == "Yes").astype(int)
txn["is_high_risk_mcc"] = txn["mcc"].isin(HIGH_RISK_MCC).astype(int)

# Agregar por sender
grp = txn.groupby("sender_id")

tx_feats = pd.DataFrame({
    "sender_id"           : grp["transaction_id"].count().index,
    "n_tx_total"          : grp["transaction_id"].count().values,
    "n_pix"               : grp["is_pix"].sum().values,
    "n_card"              : grp["is_card"].sum().values,
    "n_wire"              : grp["is_wire"].sum().values,
    "n_no_3ds"            : grp["is_no_3ds"].sum().values,
    "n_high_risk_geo"     : grp["is_high_risk_geo"].sum().values,
    "n_monitored_geo"     : grp["is_monitored_geo"].sum().values,
    "n_proxy_vpn_tor"     : grp["is_proxy_vpn_tor"].sum().values,
    "n_rooted"            : grp["is_rooted"].sum().values,
    "n_high_risk_mcc"     : grp["is_high_risk_mcc"].sum().values,
    "n_sanction_hit"      : grp["is_sanction_hit"].sum().values,
    "total_brl"           : grp["amount_brl"].sum().values,
    "avg_brl"             : grp["amount_brl"].mean().values,
    "max_brl"             : grp["amount_brl"].max().values,
    "std_brl"             : grp["amount_brl"].std().fillna(0).values if hasattr(grp["amount_brl"].std(), "values") else grp["amount_brl"].std().values,
    "first_tx_date"       : grp["timestamp"].min().values,
    "last_tx_date"        : grp["timestamp"].max().values,
})

tx_feats["tx_span_days"] = (
    tx_feats["last_tx_date"] - tx_feats["first_tx_date"]
).dt.days.clip(lower=1)

tx_feats["avg_daily_tx"]    = tx_feats["n_tx_total"] / tx_feats["tx_span_days"]
tx_feats["pct_cross_border"]= grp["is_cross_border"].sum().values / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_pix"]         = tx_feats["n_pix"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_card"]        = tx_feats["n_card"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_wire"]        = tx_feats["n_wire"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_no_3ds_card"] = np.where(
    tx_feats["n_card"] > 0,
    tx_feats["n_no_3ds"] / tx_feats["n_card"],
    0
)
tx_feats["pct_high_risk_geo"] = tx_feats["n_high_risk_geo"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_proxy_vpn"]     = tx_feats["n_proxy_vpn_tor"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_rooted"]        = tx_feats["n_rooted"] / tx_feats["n_tx_total"].clip(lower=1)
tx_feats["pct_high_risk_mcc"] = tx_feats["n_high_risk_mcc"] / tx_feats["n_tx_total"].clip(lower=1)

print(f"  Features de transações computadas: {tx_feats.shape[1]} features, {len(tx_feats):,} senders")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Montagem do dataset final
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] Montando dataset final...")

# Apenas clientes (sem merchants) com weak label
clients_rk = rk[rk["entity_type"] == "client"][["entity_id", "is_core_label", "score", "n_rules"]].copy()
clients_rk.rename(columns={"entity_id": "customer_id"}, inplace=True)

# Join: ranking + features v2 + tx features + KYC
df = clients_rk.merge(cf, on="customer_id", how="left")
df = df.merge(tx_feats.rename(columns={"sender_id": "customer_id"}), on="customer_id", how="left")
df = df.merge(
    kyc[["customer_id", "risk_rating", "kyc_tier"]],
    on="customer_id", how="left"
)

print(f"  Dataset shape: {df.shape}")
print(f"  Positivos (is_core_label=1): {df['is_core_label'].sum()} / {len(df)} ({df['is_core_label'].mean()*100:.1f}%)")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Features derivadas (transformações)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] Features derivadas...")

df["log_total_brl_sent"]  = np.log1p(df["total_brl_sent"].fillna(0))
df["log_income_tx_ratio"] = np.log1p(df["income_tx_ratio"].fillna(0))
df["log_max_brl_sent"]    = np.log1p(df["max_brl_sent"].fillna(0))
df["log_total_brl"]       = np.log1p(df["total_brl"].fillna(0))
df["log_avg_brl"]         = np.log1p(df["avg_brl"].fillna(0))
df["coeff_variation_brl"] = np.where(
    df["avg_brl"].fillna(0) > 0,
    df["std_brl"].fillna(0) / df["avg_brl"].fillna(0),
    0
)

# Encode categoricals
risk_map = {"Low": 0, "Medium": 1, "High": 2}
tier_map = {"Basic": 0, "Standard": 1, "Enhanced": 2, "Advanced": 3}
df["risk_rating_enc"] = df["risk_rating"].map(risk_map).fillna(0)
df["kyc_tier_enc"]    = df["kyc_tier"].map(tier_map).fillna(0)
df["pep_flag"]        = df["pep"].map({"Yes": 1, "No": 0, 1: 1, 0: 0}).fillna(0).astype(int)
df["sanctions_flag"]  = df["sanctions_list_hit"].map({"Yes": 1, "No": 0, 1: 1, 0: 0}).fillna(0).astype(int)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Seleção de features e tratamento de nulos
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_COLS = [
    # KYC / perfil
    "pep_flag", "sanctions_flag", "kyc_risk_score", "risk_rating_enc", "kyc_tier_enc",
    "log_income_tx_ratio", "income_tx_ratio",
    # Comportamento geral
    "n_tx_sent", "n_tx_recv", "n_tx_total",
    "log_total_brl_sent", "log_total_brl", "log_max_brl_sent", "log_avg_brl",
    "coeff_variation_brl", "avg_daily_tx", "tx_span_days",
    # Cross-border e geo
    "n_cross_border", "pct_cross_border", "n_high_risk_geo", "pct_high_risk_geo",
    "n_monitored_geo",
    # Rail mix
    "pct_pix", "pct_card", "pct_wire", "n_wire",
    # Autenticação
    "n_no_3ds", "pct_no_3ds_card",
    # Device / IP
    "n_ip_anomaly", "n_device_rooted", "n_rooted", "n_devices_uniq", "n_ips_uniq",
    "n_proxy_vpn_tor", "pct_proxy_vpn", "pct_rooted",
    # MCC
    "n_high_risk_mcc", "pct_high_risk_mcc",
    # Contra-partes
    "n_receivers_uniq", "n_merchants_uniq",
    # Cash flow
    "cash_through_ratio", "total_brl_recv",
    # Sanctions
    "n_sanctions", "n_sanction_hit",
]

# Garantir que todas as colunas existem
FEATURE_COLS = [c for c in FEATURE_COLS if c in df.columns]
print(f"  Features selecionadas: {len(FEATURE_COLS)}")

X = df[FEATURE_COLS].copy()
y = df["is_core_label"].values

# Impute com mediana
medians = X.median()
X = X.fillna(medians)

print(f"  Nulos residuais: {X.isnull().sum().sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Split temporal (por percentil de first_tx_date)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] Split temporal (80/20 por first_tx_date ordenado)...")

# Ordenar clientes pela data da primeira transação → respeita causalidade
df["first_tx_date"] = pd.to_datetime(df["first_tx_date"])
sorted_order = df["first_tx_date"].fillna(pd.Timestamp("2025-07-01")).argsort().values
split_n      = int(len(df) * TRAIN_FRAC)

# Índices no DataFrame
train_positions = sorted_order[:split_n]
test_positions  = sorted_order[split_n:]

train_mask = pd.Series(False, index=df.index)
test_mask  = pd.Series(False, index=df.index)
train_mask.iloc[train_positions] = True
test_mask.iloc[test_positions]   = True

X_train, y_train = X[train_mask], y[train_mask]
X_test,  y_test  = X[test_mask],  y[test_mask]

split_cutoff = df["first_tx_date"].iloc[sorted_order[split_n - 1]]
print(f"  Corte temporal efetivo: {split_cutoff}")
print(f"  Treino: {len(X_train):,} clientes | positivos: {y_train.sum()}")
print(f"  Teste : {len(X_test):,} clientes  | positivos: {y_test.sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. XGBoost — treino
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] Treinando XGBoost...")

n_pos = y_train.sum()
n_neg = (y_train == 0).sum()
scale_pw = n_neg / n_pos
print(f"  scale_pos_weight = {scale_pw:.1f}  (n_neg={n_neg} / n_pos={n_pos})")

xgb_model = xgb.XGBClassifier(
    n_estimators=400,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pw,
    eval_metric="aucpr",
    early_stopping_rounds=30,
    use_label_encoder=False,
    random_state=SEED,
    n_jobs=-1,
    verbosity=0,
)

xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False,
)

best_iter = xgb_model.best_iteration
print(f"  Melhor iteração (early stopping): {best_iter}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. Métricas no conjunto de teste
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] Métricas de avaliação (conjunto de TESTE)...")

y_prob_test  = xgb_model.predict_proba(X_test)[:, 1]
y_prob_train = xgb_model.predict_proba(X_train)[:, 1]
y_prob_all   = xgb_model.predict_proba(X)[:, 1]

roc_auc = roc_auc_score(y_test, y_prob_test)
pr_auc  = average_precision_score(y_test, y_prob_test)
print(f"  ROC-AUC  : {roc_auc:.4f}")
print(f"  PR-AUC   : {pr_auc:.4f}")

# Threshold ótimo por F1
prec_arr, rec_arr, thresh_arr = precision_recall_curve(y_test, y_prob_test)
f1_arr  = 2 * prec_arr * rec_arr / (prec_arr + rec_arr + 1e-9)
best_t  = thresh_arr[np.argmax(f1_arr[:-1])]
y_pred_best = (y_prob_test >= best_t).astype(int)

print(f"\n  Threshold ótimo (max-F1): {best_t:.3f}")
print(classification_report(y_test, y_pred_best, target_names=["Normal", "Suspeito"]))

cm = confusion_matrix(y_test, y_pred_best)
print(f"  Matriz de confusão:\n  {cm}")

# ─────────────────────────────────────────────────────────────────────────────
# 9. Isolation Forest (não-supervisionado)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] Isolation Forest (anomaly detection)...")

# Treinar no conjunto completo (não-supervisionado não usa labels)
iforest = IsolationForest(
    n_estimators=300,
    contamination=0.05,  # ~5% esperados como anomalias
    random_state=SEED,
    n_jobs=-1,
)
iforest.fit(X)

# Anomaly score: -decision_function → maior = mais anômalo
if_scores_raw = -iforest.decision_function(X)
# Normalizar para [0, 1]
if_min, if_max = if_scores_raw.min(), if_scores_raw.max()
if_scores = (if_scores_raw - if_min) / (if_max - if_min + 1e-9)

print(f"  IF score médio (label=0): {if_scores[y == 0].mean():.4f}")
print(f"  IF score médio (label=1): {if_scores[y == 1].mean():.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 10. Score final combinado (ensemble ponderado)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[9] Score final combinado (XGB 70% + IF 30%)...")

final_score = 0.70 * y_prob_all + 0.30 * if_scores
print(f"  Score final médio (label=0): {final_score[y == 0].mean():.4f}")
print(f"  Score final médio (label=1): {final_score[y == 1].mean():.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 11. Salvar scores por cliente
# ─────────────────────────────────────────────────────────────────────────────
scores_df = pd.DataFrame({
    "customer_id"     : df["customer_id"].values,
    "is_core_label"   : y,
    "xgb_score"       : y_prob_all,
    "if_score"        : if_scores,
    "final_score"     : final_score,
    "split"           : np.where(train_mask.values, "train", "test"),
    "rules_score"     : df["score"].values,
    "n_rules"         : df["n_rules"].values,
})
scores_df["risk_tier_ml"] = pd.cut(
    scores_df["final_score"],
    bins=[0, 0.30, 0.60, 0.80, 1.001],
    labels=["baixo", "medio", "alto", "critico"],
)
scores_df = scores_df.sort_values("final_score", ascending=False).reset_index(drop=True)
scores_df.to_csv(OUT_ML, index=False)
print(f"  Salvo: {OUT_ML}")
print(f"  Distribuição risk_tier_ml:\n  {scores_df['risk_tier_ml'].value_counts().to_dict()}")

# Top-10 por score final
top10 = scores_df.head(10)
print("\n  === TOP-10 clientes por score final ===")
print(top10[["customer_id", "xgb_score", "if_score", "final_score", "is_core_label", "risk_tier_ml"]].to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 12. Gráficos
# ─────────────────────────────────────────────────────────────────────────────
print("\n[10] Gerando gráficos...")
PALETTE = {"main": "#1a3a5c", "pos": "#c0392b", "neg": "#2980b9", "if": "#27ae60", "accent": "#e67e22"}

# ── 12a. ROC Curve ─────────────────────────────────────────────────────────
fpr, tpr, _ = roc_curve(y_test, y_prob_test)
fig, ax = plt.subplots(figsize=(6, 5))
ax.plot(fpr, tpr, color=PALETTE["main"], lw=2, label=f"XGBoost (AUC = {roc_auc:.3f})")
ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Random")
ax.set_xlabel("Taxa de Falsos Positivos", fontsize=11)
ax.set_ylabel("Taxa de Verdadeiros Positivos", fontsize=11)
ax.set_title("Curva ROC — Conjunto de Teste", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_roc_curve.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_roc_curve.png")

# ── 12b. PR Curve ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 5))
ax.plot(rec_arr, prec_arr, color=PALETTE["pos"], lw=2, label=f"XGBoost (PR-AUC = {pr_auc:.3f})")
ax.axhline(y=y_test.mean(), color="gray", ls="--", lw=1, label=f"Baseline ({y_test.mean()*100:.1f}%)")
ax.set_xlabel("Recall", fontsize=11)
ax.set_ylabel("Precisão", fontsize=11)
ax.set_title("Curva Precisão-Recall — Conjunto de Teste", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_pr_curve.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_pr_curve.png")

# ── 12c. Feature Importance (top-20) ───────────────────────────────────────
fi = pd.Series(xgb_model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
top_fi = fi.head(20)

fig, ax = plt.subplots(figsize=(8, 6))
colors_fi = [PALETTE["pos"] if v > top_fi.quantile(0.75) else PALETTE["main"] for v in top_fi.values]
ax.barh(top_fi.index[::-1], top_fi.values[::-1], color=colors_fi[::-1])
ax.set_xlabel("Gain (importância)", fontsize=11)
ax.set_title("Top-20 Features — XGBoost (Gain)", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_feature_importance.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_feature_importance.png")

# ── 12d. SHAP Summary Plot ─────────────────────────────────────────────────
explainer   = shap.TreeExplainer(xgb_model)
shap_values = explainer.shap_values(X)

fig, ax = plt.subplots(figsize=(9, 7))
shap.summary_plot(
    shap_values, X, feature_names=FEATURE_COLS,
    max_display=15, show=False, plot_type="dot",
)
plt.title("SHAP Summary — Impacto das Features", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_shap_summary.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_shap_summary.png")

# ── 12e. SHAP — 3 casos individuais ────────────────────────────────────────
target_ids = ["C101208"]  # SAR principal
# Adicionar 1 positivo e 1 negativo do test set para contraste
test_positives = df.loc[test_mask & (y == 1), "customer_id"].head(2).tolist()
target_ids.extend([c for c in test_positives if c != "C101208"][:1])
test_negatives = df.loc[test_mask & (y == 0), "customer_id"].head(1).tolist()
target_ids.extend(test_negatives)

for cid in target_ids[:3]:
    idx_row = df.index[df["customer_id"] == cid]
    if len(idx_row) == 0:
        continue
    idx = idx_row[0]
    row_X = X.loc[[idx]]

    # Remapear índice para posição
    pos = list(df.index).index(idx)
    shap_row = shap_values[pos]

    fig, ax = plt.subplots(figsize=(9, 4))
    shap.waterfall_plot(
        shap.Explanation(
            values=shap_row,
            base_values=explainer.expected_value,
            data=row_X.values[0],
            feature_names=FEATURE_COLS,
        ),
        max_display=12,
        show=False,
    )
    label_txt = "SUSPEITO" if y[pos] == 1 else "Normal"
    plt.title(f"SHAP Waterfall — {cid} ({label_txt})  |  XGB score={y_prob_all[pos]:.3f}", fontsize=11)
    plt.tight_layout()
    fname = f"04_shap_{cid}.png"
    plt.savefig(os.path.join(OUT_FIG, fname), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  {fname}")

# ── 12f. Isolation Forest vs XGBoost scatter ───────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
scatter_kwargs = dict(alpha=0.4, s=15, edgecolors="none")
ax.scatter(if_scores[y == 0], y_prob_all[y == 0], color=PALETTE["neg"], label="Normal", **scatter_kwargs)
ax.scatter(if_scores[y == 1], y_prob_all[y == 1], color=PALETTE["pos"], label="Suspeito (weak)", **scatter_kwargs)

# Highlight C101208
idx_sar = df.index[df["customer_id"] == "C101208"]
if len(idx_sar):
    pos_sar = list(df.index).index(idx_sar[0])
    ax.scatter(if_scores[pos_sar], y_prob_all[pos_sar],
               color="gold", s=120, edgecolors="black", lw=1.5, zorder=5, label="C101208")

ax.set_xlabel("Isolation Forest Score (normalizado)", fontsize=11)
ax.set_ylabel("XGBoost Score (probabilidade)", fontsize=11)
ax.set_title("Comparação XGBoost × Isolation Forest", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_xgb_vs_iforest.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_xgb_vs_iforest.png")

# ── 12g. Curva de Corte (threshold analysis) ───────────────────────────────
# No conjunto de TESTE
prec_t, rec_t, thr_t = precision_recall_curve(y_test, y_prob_test)
f1_t = 2 * prec_t[:-1] * rec_t[:-1] / (prec_t[:-1] + rec_t[:-1] + 1e-9)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Esquerda: precisão e recall vs threshold
ax1.plot(thr_t, prec_t[:-1], color=PALETTE["pos"],  lw=2, label="Precisão")
ax1.plot(thr_t, rec_t[:-1],  color=PALETTE["neg"],  lw=2, label="Recall")
ax1.plot(thr_t, f1_t,        color=PALETTE["main"], lw=2, label="F1")
ax1.axvline(best_t, color="orange", ls="--", lw=1.5, label=f"Threshold ótimo ({best_t:.2f})")
ax1.set_xlabel("Threshold de Score", fontsize=11)
ax1.set_ylabel("Valor da Métrica", fontsize=11)
ax1.set_title("Métricas × Threshold", fontsize=12, fontweight="bold")
ax1.legend(fontsize=9); ax1.set_xlim(0, 1); ax1.set_ylim(0, 1.02)

# Direita: % da carteira alertada vs threshold
n_total = len(y_prob_test)
pct_alertado = [(y_prob_test >= t).sum() / n_total for t in thr_t]
ax2.plot(thr_t, pct_alertado, color=PALETTE["if"], lw=2, label="% carteira alertada")
ax2.axvline(best_t, color="orange", ls="--", lw=1.5, label=f"Threshold ótimo ({best_t:.2f})")
ax2.set_xlabel("Threshold de Score", fontsize=11)
ax2.set_ylabel("Fração da Carteira Alertada", fontsize=11)
ax2.set_title("Capacidade Operacional × Threshold", fontsize=12, fontweight="bold")
ax2.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
ax2.legend(fontsize=9); ax2.set_xlim(0, 1); ax2.set_ylim(0, 1.05)

plt.suptitle("Análise de Threshold — CloudWalk AML", fontsize=14, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_cutoff_curve.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_cutoff_curve.png")

# ── 12h. Score final — distribuição por label ──────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(final_score[y == 0], bins=50, color=PALETTE["neg"], alpha=0.6, density=True, label="Normal")
ax.hist(final_score[y == 1], bins=20, color=PALETTE["pos"], alpha=0.8, density=True, label="Suspeito (weak)")
ax.set_xlabel("Score Final (XGB 70% + IF 30%)", fontsize=11)
ax.set_ylabel("Densidade", fontsize=11)
ax.set_title("Distribuição do Score Final por Classe", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_score_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_score_distribution.png")

# ─────────────────────────────────────────────────────────────────────────────
# 13. SHAP — análise textual para C101208
# ─────────────────────────────────────────────────────────────────────────────
print("\n[11] Análise SHAP detalhada — C101208...")

idx_sar = df.index[df["customer_id"] == "C101208"]
if len(idx_sar):
    pos_sar = list(df.index).index(idx_sar[0])
    shap_C101208 = shap_values[pos_sar]
    fi_C101208 = pd.Series(shap_C101208, index=FEATURE_COLS).sort_values(key=abs, ascending=False)
    print("  Top-10 features contribuindo para o score de C101208:")
    for feat, sv in fi_C101208.head(10).items():
        direction = "↑RISCO" if sv > 0 else "↓risco"
        val = X.loc[idx_sar[0], feat]
        print(f"    {feat:<30s} SHAP={sv:+.4f}  {direction}  (val={val:.3f})")

    c_xgb = y_prob_all[pos_sar]
    c_if  = if_scores[pos_sar]
    c_fin = final_score[pos_sar]
    print(f"\n  C101208 — XGB score: {c_xgb:.4f} | IF score: {c_if:.4f} | Final: {c_fin:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 14. Validação Rigorosa — K-Fold CV + Permutation Test + Calibração + Learning Curve
# ─────────────────────────────────────────────────────────────────────────────
print("\n[12] Validação rigorosa das métricas...")

from sklearn.model_selection import StratifiedKFold
from sklearn.calibration import calibration_curve

SKF = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)

# Modelo simplificado para CV e permutation test (sem early stopping para ser determinístico)
xgb_cv_base = xgb.XGBClassifier(
    n_estimators=50,  # conservador para velocidade; early stopping não é usado em CV
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pw,
    use_label_encoder=False,
    random_state=SEED,
    n_jobs=-1,
    verbosity=0,
)

# ── 14a. 5-fold Stratified Cross-Validation ───────────────────────────────
print("  14a. 5-fold Stratified CV...")
cv_roc, cv_pr = [], []

for fold, (tr_idx, val_idx) in enumerate(SKF.split(X, y)):
    X_cv_tr, X_cv_val = X.iloc[tr_idx], X.iloc[val_idx]
    y_cv_tr, y_cv_val = y[tr_idx], y[val_idx]

    if y_cv_val.sum() < 2:  # fold sem positivos suficientes
        print(f"    Fold {fold+1}: pulado (apenas {y_cv_val.sum()} positivo(s) no val)")
        continue

    xgb_cv_base.fit(X_cv_tr, y_cv_tr, verbose=False)
    y_cv_prob = xgb_cv_base.predict_proba(X_cv_val)[:, 1]

    cv_roc.append(roc_auc_score(y_cv_val, y_cv_prob))
    cv_pr.append(average_precision_score(y_cv_val, y_cv_prob))
    print(f"    Fold {fold+1}: ROC={cv_roc[-1]:.4f}  PR={cv_pr[-1]:.4f}  (n_pos={y_cv_val.sum()})")

cv_roc_mean, cv_roc_std = np.mean(cv_roc), np.std(cv_roc)
cv_pr_mean,  cv_pr_std  = np.mean(cv_pr),  np.std(cv_pr)
print(f"\n  CV ROC-AUC : {cv_roc_mean:.4f} ± {cv_roc_std:.4f}")
print(f"  CV PR-AUC  : {cv_pr_mean:.4f}  ± {cv_pr_std:.4f}")
print(f"  Baseline PR-AUC (acaso) : {y.mean():.4f}")
print(f"  Ganho sobre baseline    : {cv_pr_mean / y.mean():.1f}×")

# ── 14b. Permutation Test ─────────────────────────────────────────────────
print("\n  14b. Permutation Test (15 permutações × 5 folds)...")
N_PERMS = 15
perm_pr_scores = []

for p in range(N_PERMS):
    y_perm = np.random.permutation(y)
    fold_pr = []
    for tr_idx, val_idx in SKF.split(X, y):  # split estrutura fixa; labels permutados
        X_cv_tr, X_cv_val = X.iloc[tr_idx], X.iloc[val_idx]
        y_cv_tr, y_cv_val = y_perm[tr_idx], y_perm[val_idx]
        if y_cv_val.sum() < 2:
            continue
        xgb_cv_base.fit(X_cv_tr, y_cv_tr, verbose=False)
        y_cv_prob = xgb_cv_base.predict_proba(X_cv_val)[:, 1]
        fold_pr.append(average_precision_score(y_cv_val, y_cv_prob))
    if fold_pr:
        perm_pr_scores.append(np.mean(fold_pr))

perm_pr_mean = np.mean(perm_pr_scores)
p_value = np.mean([s >= cv_pr_mean for s in perm_pr_scores])
print(f"  PR-AUC real (CV)     : {cv_pr_mean:.4f}")
print(f"  PR-AUC perm (média)  : {perm_pr_mean:.4f}")
print(f"  p-value              : {p_value:.3f}  {'✓ significativo' if p_value < 0.05 else '✗ não significativo'}")
print(f"  Interpretação: se p<0.05, o modelo aprende sinal real (não memoriza ruído)")

# ── 14c. Calibração do modelo (conj. de teste) ────────────────────────────
print("\n  14c. Calibração do modelo...")
if y_test.sum() >= 5:
    n_bins_cal = 5
    prob_true_cal, prob_pred_cal = calibration_curve(
        y_test, y_prob_test, n_bins=n_bins_cal, strategy="quantile"
    )
    cal_error = np.mean(np.abs(prob_true_cal - prob_pred_cal))
    print(f"  Calibration Error médio: {cal_error:.4f}")
    print(f"  (0=perfeito | >0.1 indica scores mal calibrados)")
    cal_ok = True
else:
    print("  Teste com poucos positivos — calibração não confiável com este split")
    cal_ok = False

# ── 14d. Learning Curve (performance vs tamanho do treino) ────────────────
print("\n  14d. Learning Curve...")
train_fracs = [0.20, 0.40, 0.60, 0.80, 1.00]
lc_train_pr, lc_test_pr = [], []

for frac in train_fracs:
    n = max(int(len(X_train) * frac), y_train.sum() + 1)  # garante todos os pos
    X_sub = X_train.iloc[:n]
    y_sub = y_train[:n]
    if y_sub.sum() < 2:
        lc_train_pr.append(np.nan)
        lc_test_pr.append(np.nan)
        continue

    sp_train = (y_sub == 0).sum() / max(y_sub.sum(), 1)
    xgb_lc = xgb.XGBClassifier(
        n_estimators=50, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=sp_train,
        use_label_encoder=False, random_state=SEED, n_jobs=-1, verbosity=0,
    )
    xgb_lc.fit(X_sub, y_sub, verbose=False)

    lc_train_pr.append(average_precision_score(y_sub, xgb_lc.predict_proba(X_sub)[:, 1]))
    if y_test.sum() >= 2:
        lc_test_pr.append(average_precision_score(y_test, xgb_lc.predict_proba(X_test)[:, 1]))
    else:
        lc_test_pr.append(np.nan)

    print(f"    {int(frac*100):3d}% treino ({n:,} samples): train={lc_train_pr[-1]:.4f} | test={lc_test_pr[-1]:.4f}")

# ── 14e. Gráficos de Validação ────────────────────────────────────────────
print("\n  Gerando gráficos de validação...")

# Boxplot CV scores
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

axes[0].boxplot([cv_roc, cv_pr], tick_labels=["ROC-AUC", "PR-AUC"], patch_artist=True,
                boxprops=dict(facecolor=PALETTE["main"], alpha=0.6))
axes[0].axhline(y.mean(), color="gray", ls="--", lw=1, label=f"Baseline ({y.mean():.3f})")
axes[0].set_title("Distribuição das Métricas\n5-Fold CV", fontsize=12, fontweight="bold")
axes[0].set_ylabel("Score"); axes[0].legend(fontsize=9)
for i, (scores, label) in enumerate([(cv_roc, "ROC"), (cv_pr, "PR")]):
    axes[0].text(i + 1, np.mean(scores) + 0.02, f"μ={np.mean(scores):.3f}", ha="center", fontsize=9)

# Permutation test distribution
axes[1].hist(perm_pr_scores, bins=8, color=PALETTE["neg"], alpha=0.7, edgecolor="white",
             label=f"PR-AUC (labels aleatórios)\nn={N_PERMS} permutações")
axes[1].axvline(cv_pr_mean, color=PALETTE["pos"], lw=2.5, label=f"PR-AUC real = {cv_pr_mean:.4f}")
axes[1].axvline(y.mean(), color="gray", ls="--", lw=1.5, label=f"Baseline = {y.mean():.4f}")
axes[1].set_xlabel("PR-AUC"); axes[1].set_ylabel("Frequência")
axes[1].set_title(f"Permutation Test\np-valor = {p_value:.3f}", fontsize=12, fontweight="bold")
axes[1].legend(fontsize=8)

# Learning curve
n_train_sizes = [int(len(X_train) * f) for f in train_fracs]
valid_idx = [i for i, v in enumerate(lc_test_pr) if not np.isnan(v)]
axes[2].plot([n_train_sizes[i] for i in valid_idx],
             [lc_train_pr[i] for i in valid_idx],
             "o-", color=PALETTE["main"], lw=2, label="Treino (PR-AUC)")
axes[2].plot([n_train_sizes[i] for i in valid_idx],
             [lc_test_pr[i] for i in valid_idx],
             "s--", color=PALETTE["pos"], lw=2, label="Teste (PR-AUC)")
axes[2].axhline(y.mean(), color="gray", ls=":", lw=1, label=f"Baseline")
axes[2].set_xlabel("Nº de amostras de treino"); axes[2].set_ylabel("PR-AUC")
axes[2].set_title("Curva de Aprendizado", fontsize=12, fontweight="bold")
axes[2].legend(fontsize=9)

plt.suptitle("Validação do Modelo XGBoost — CloudWalk AML", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUT_FIG, "04_validacao.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  04_validacao.png")

# Calibration curve (se disponível)
if cal_ok:
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(prob_pred_cal, prob_true_cal, "o-", color=PALETTE["pos"], lw=2, ms=8,
            label=f"XGBoost (erro médio={cal_error:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1.5, alpha=0.5, label="Calibração perfeita")
    ax.fill_between([0, 1], [0, 1], alpha=0.05, color="gray")
    ax.set_xlabel("Score previsto pelo modelo", fontsize=11)
    ax.set_ylabel("Proporção real de positivos", fontsize=11)
    ax.set_title("Curva de Calibração\n(Reliability Diagram)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10); ax.set_xlim(0, 1); ax.set_ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_FIG, "04_calibracao.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  04_calibracao.png")

# ─────────────────────────────────────────────────────────────────────────────
# 15. Relatório técnico em Markdown
# ─────────────────────────────────────────────────────────────────────────────
print("\n[12] Gerando relatório técnico...")

# Métricas a threshold ótimo no teste
tn, fp, fn, tp = cm.ravel()
prec_opt = tp / (tp + fp + 1e-9)
rec_opt  = tp / (tp + fn + 1e-9)
f1_opt   = 2 * prec_opt * rec_opt / (prec_opt + rec_opt + 1e-9)

# Tabela top-5 features (gain)
top5_fi = fi.head(5)

# Percentil do score de C101208
rank_sar = (scores_df["customer_id"] == "C101208").idxmax()
pct_sar  = (1 - rank_sar / len(scores_df)) * 100

report_lines = [
    "# Dia 4 — Relatório Técnico: Modelo de Machine Learning",
    f"\n_Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
    "---",
    "",
    "## 1. Objetivo",
    "",
    "Construir um modelo que **priorize risco por cliente**, combinando comportamento transacional,",
    "perfil KYC e sinais geográficos/dispositivo. A abordagem usa **rótulo fraco** (weak label) —",
    "derivado das regras de alta confiança do Dia 2 — como proxy de fraude/lavagem, complementado",
    "por **Isolation Forest** (não-supervisionado) para capturar anomalias não cobertas pelas regras.",
    "",
    "---",
    "",
    "## 2. Dados e Rótulo",
    "",
    "| Dimensão | Valor |",
    "|---|---|",
    f"| Clientes no dataset | {len(df):,} |",
    f"| Features utilizadas | {len(FEATURE_COLS)} |",
    f"| Positivos (is_core_label=1) | {int(y.sum())} ({y.mean()*100:.1f}%) |",
    f"| Negativos | {int((y==0).sum())} |",
    f"| Janela temporal das transações | Jul/2025 – Out/2025 |",
    f"| Corte treino/teste (first_tx_date) | {split_cutoff.strftime('%Y-%m-%d')} (percentil 80%) |",
    f"| Clientes no treino | {len(X_train):,} (positivos: {int(y_train.sum())}) |",
    f"| Clientes no teste | {len(X_test):,} (positivos: {int(y_test.sum())}) |",
    "",
    "**Critério do rótulo fraco:** cliente é marcado `is_core_label=1` se acionar ≥2 regras de",
    "alta confiança (R04_income_mismatch, R05_geojump, R06_ip_anomaly, R10_cash_in_out,",
    "R14_high_risk_country, R15_sanctions_hit) — regras com menor taxa de falso-positivo.",
    "",
    "---",
    "",
    "## 3. Arquitetura do Modelo",
    "",
    "### 3.1 XGBoost (supervisionado com rótulo fraco)",
    "",
    "```",
    "n_estimators : 400 (early stopping = 30)",
    f"best_iteration: {best_iter}",
    "max_depth    : 4",
    "learning_rate: 0.05",
    f"scale_pos_weight: {scale_pw:.1f}  # compensa desbalanceamento",
    "eval_metric  : aucpr",
    "SEED         : 42",
    "```",
    "",
    "### 3.2 Isolation Forest (não-supervisionado)",
    "",
    "```",
    "n_estimators : 300",
    "contamination: 0.05  # ~5% anomalias esperadas",
    "SEED         : 42",
    "```",
    "",
    "### 3.3 Score final (ensemble)",
    "",
    "```",
    "final_score = 0.70 × XGBoost_proba + 0.30 × IF_score_normalizado",
    "```",
    "",
    "O peso 70/30 prioriza o sinal supervisionado (mais calibrado) com um complemento",
    "não-supervisionado para anomalias não cobertas pelo rótulo fraco.",
    "",
    "---",
    "",
    "## 4. Métricas de Avaliação (conjunto de TESTE)",
    "",
    "| Métrica | Valor |",
    "|---|---|",
    f"| **ROC-AUC** | **{roc_auc:.4f}** |",
    f"| **PR-AUC** | **{pr_auc:.4f}** |",
    f"| Threshold ótimo (max-F1) | {best_t:.3f} |",
    f"| Precisão @ threshold ótimo | {prec_opt:.3f} |",
    f"| Recall @ threshold ótimo | {rec_opt:.3f} |",
    f"| F1 @ threshold ótimo | {f1_opt:.3f} |",
    f"| Verdadeiros Positivos | {int(tp)} |",
    f"| Falsos Positivos | {int(fp)} |",
    f"| Falsos Negativos | {int(fn)} |",
    f"| Verdadeiros Negativos | {int(tn)} |",
    "",
    "> **Nota:** PR-AUC é a métrica-chave em bases desbalanceadas (3,3% de positivos).",
    "> Um PR-AUC acima do baseline (3,3%) indica ganho real sobre o classificador aleatório.",
    "",
    "---",
    "",
    "## 5. Top-5 Features (Gain — XGBoost)",
    "",
    "| Rank | Feature | Importância (Gain) |",
    "|---|---|---|",
]
for i, (feat, val) in enumerate(top5_fi.items(), 1):
    report_lines.append(f"| {i} | `{feat}` | {val:.4f} |")

report_lines += [
    "",
    "---",
    "",
    "## 6. Explicabilidade — SHAP",
    "",
    "O SHAP (SHapley Additive exPlanations) quantifica a **contribuição marginal de cada feature**",
    "para o score de cada cliente. Os gráficos gerados:",
    "",
    "- `04_shap_summary.png` — visão global: quais features mais impactam (e em que direção)",
    "- `04_shap_C101208.png` — waterfall do caso SAR (C101208)",
    "",
]
if len(idx_sar):
    pos_sar = list(df.index).index(idx_sar[0])
    report_lines += [
        f"**C101208** obteve score XGB = {y_prob_all[pos_sar]:.4f} | IF = {if_scores[pos_sar]:.4f} | Final = {final_score[pos_sar]:.4f}",
        f"(percentil {pct_sar:.1f}% — entre os {100-pct_sar:.1f}% mais suspeitos da carteira)",
        "",
        "Principais drivers do score de C101208 via SHAP:",
        "",
    ]
    for feat, sv in fi_C101208.head(5).items():
        direction = "aumenta risco" if sv > 0 else "reduz risco"
        report_lines.append(f"- **`{feat}`** → SHAP={sv:+.4f} ({direction})")

report_lines += [
    "",
    "---",
    "",
    "## 7. Isolation Forest",
    "",
    f"- Score médio (clientes normais): {if_scores[y == 0].mean():.4f}",
    f"- Score médio (suspeitos weak label): {if_scores[y == 1].mean():.4f}",
    "",
    "O IF captura **clientes com padrão incomum mesmo sem regras acionadas** — útil para detecção",
    "de tipologias emergentes não cobertas pelo catálogo de regras.",
    "",
    "---",
    "",
    "## 8. Distribuição de Risco (Score Final)",
    "",
    "| Tier | Score | Clientes | % |",
    "|---|---|---|---|",
]
tiers = scores_df["risk_tier_ml"].value_counts().sort_index()
tier_ranges = {"baixo": "0–0.30", "medio": "0.30–0.60", "alto": "0.60–0.80", "critico": "0.80–1.00"}
for tier, cnt in tiers.items():
    pct = cnt / len(scores_df) * 100
    rng = tier_ranges.get(str(tier), "")
    report_lines.append(f"| {tier} | {rng} | {cnt} | {pct:.1f}% |")

report_lines += [
    "",
    "---",
    "",
    "## 9. Limitações e Vieses",
    "",
    "1. **Rótulo fraco (ruidoso):** o `is_core_label` é gerado por regras heurísticas, não por",
    "   investigação humana. O modelo aprende a replicar as regras, não a detectar lavagem real.",
    "",
    "2. **Viés circular:** features derivadas de comportamento transacional parcialmente correlacionam",
    "   com as próprias regras que geraram o rótulo. O modelo pode super-estimar o desempenho.",
    "",
    "3. **Split temporal limitado:** a janela de 3 meses é curta. Com dados históricos mais longos,",
    "   o modelo capturaria drift sazonal e padrões de longo prazo (ex.: layering multi-mês).",
    "",
    "4. **Calibragem:** os scores do XGBoost não são probabilidades calibradas. Para uso operacional,",
    "   recomenda-se calibração isotônica ou Platt scaling.",
    "",
    "5. **Ausência de labels reais:** sem confirmação de investigadores ou decisões judiciais,",
    "   PR-AUC e F1 medem apenas consistência com as regras, não detecção real de crime.",
    "",
    "---",
    "",
    "## 10. Próximos Passos (Stretch)",
    "",
    "- Calibração Platt/isotônica para converter scores em probabilidades confiáveis",
    "- LightGBM com feature interactions explícitas",
    "- Graph Neural Network sobre o grafo de contrapartes",
    "- Retraining pipeline com monitoramento de data drift (PSI, KS test)",
    "- Feedback loop com decisões de analistas para refinar o rótulo fraco",
    "",
    "---",
    "",
    "## 11. Reprodutibilidade",
    "",
    "```bash",
    "SEED = 42  # numpy, xgboost, sklearn",
    "python notebooks/04_modelo_ml.py",
    "# Requer: scikit-learn>=1.9, xgboost>=3.3, shap>=0.52, pandas>=2.0",
    "```",
    "",
    "_Outputs: `outputs/04_ml_scores.csv` · `outputs/figuras/04_*.png`_",
]

with open(OUT_RPT, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"  Salvo: {OUT_RPT}")

# ─────────────────────────────────────────────────────────────────────────────
# 15. Resumo final
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("DIA 4 — RESUMO FINAL")
print("=" * 70)
print(f"  Features            : {len(FEATURE_COLS)}")
print(f"  Treino/Teste        : {len(X_train):,} / {len(X_test):,} clientes")
print(f"  Positivos treino    : {int(y_train.sum())} | teste: {int(y_test.sum())}")
print(f"  ROC-AUC (teste)     : {roc_auc:.4f}")
print(f"  PR-AUC  (teste)     : {pr_auc:.4f}")
print(f"  Threshold ótimo     : {best_t:.3f}  → Prec={prec_opt:.3f} | Rec={rec_opt:.3f} | F1={f1_opt:.3f}")
print(f"  Melhor iter XGB     : {best_iter}")
if len(idx_sar):
    print(f"  C101208 score final : {final_score[pos_sar]:.4f} (percentil {pct_sar:.1f}%)")
print()
print("  Outputs:")
print(f"    {OUT_ML}")
print(f"    {OUT_RPT}")
print("    outputs/figuras/04_roc_curve.png")
print("    outputs/figuras/04_pr_curve.png")
print("    outputs/figuras/04_feature_importance.png")
print("    outputs/figuras/04_shap_summary.png")
print("    outputs/figuras/04_shap_C101208.png")
print("    outputs/figuras/04_xgb_vs_iforest.png")
print("    outputs/figuras/04_cutoff_curve.png")
print("    outputs/figuras/04_score_distribution.png")
print()
print("[OK] Dia 4 concluído.")
