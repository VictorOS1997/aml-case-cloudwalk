"""
Motor de regras AML-FT — 22 regras implementadas.

Colunas reais da base (EDA Dia 1):
  Transactions: sender_id, amount_brl, transaction_type (PIX/Card/Wire),
    device_fingerprint, ip_address, cross_border (Yes/No), ip_anomaly (Yes/No),
    auth_3ds (Yes/No), eci, mcc, geolocation_lat, geolocation_lon,
    sanctions_screening_hit (Yes/No), receiver_id, receiver_entity_type,
    capture_method, pix_flow, card_brand, installments, status,
    country_risk_geo/ip/sender/receiver (Low/Monitored/High), ip_country
  KYC_Profiles: customer_id, annual_income_brl, pep (Yes/No),
    registration_date, sanctions_list_hit (Yes/No), kyc_risk_score
  Merchants: merchant_id, owner_customer_id, merchant_chargeback_ratio_90d,
    mcc, merchant_high_risk_flag, mcc_risk (Normal/High)

Regras core (rótulo fraco para ML): R03, R07, R09, R12, R15
Saída de cada regra: List[Dict] com campos:
  entity_id, entity_type, rule_id, severity, evidence_ids, rule_desc
"""

from __future__ import annotations

import math
import warnings
from typing import Dict, List

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings('ignore')
SEED = 42
np.random.seed(SEED)

# ── Colunas: Transactions ─────────────────────────────────────────────────────
C_TXN = 'transaction_id'
C_TS = 'timestamp'
C_CLIENT = 'sender_id'
C_RECV = 'receiver_id'
C_RECV_TYPE = 'receiver_entity_type'
C_AMOUNT = 'amount_brl'
C_RAIL = 'transaction_type'
C_DEVICE = 'device_fingerprint'
C_IP = 'ip_address'
C_CROSS = 'cross_border'
C_AUTH3DS = 'auth_3ds'
C_ECI = 'eci'
C_MCC = 'mcc'
C_LAT = 'geolocation_lat'
C_LON = 'geolocation_lon'
C_SANCTIONS = 'sanctions_screening_hit'
C_IP_RISK = 'country_risk_ip'
C_SEND_RISK = 'country_risk_sender'
C_RECV_RISK = 'country_risk_receiver'
C_IP_ANOMALY = 'ip_anomaly'
C_IP_COUNTRY = 'ip_country'
C_STATUS = 'status'
C_CAPTURE = 'capture_method'
C_CARD_BRAND = 'card_brand'
C_INSTALLMENTS = 'installments'
C_PIX_FLOW = 'pix_flow'

# ── Colunas: KYC_Profiles ─────────────────────────────────────────────────────
K_CUSTOMER = 'customer_id'
K_INCOME = 'annual_income_brl'
K_PEP = 'pep'
K_REG_DATE = 'registration_date'
K_SANCTIONS = 'sanctions_list_hit'
K_KYC_SCORE = 'kyc_risk_score'

# ── Colunas: Merchants ────────────────────────────────────────────────────────
M_ID = 'merchant_id'
M_OWNER = 'owner_customer_id'
M_CHARGEBACK = 'merchant_chargeback_ratio_90d'
M_MCC = 'mcc'
M_HIGH_RISK = 'merchant_high_risk_flag'
M_MCC_RISK = 'mcc_risk'

# ── Constantes de risco ───────────────────────────────────────────────────────
HIGH_RISK_MCC = {6011, 6051, 7995, 4829, 6012}
ECOM_CAPTURES = {'E-commerce'}
CORE_RULES = {'R03_structuring', 'R07_device_ring', 'R09_self_merchant',
              'R12_ecom_no_3ds', 'R15_sanctions'}


def _yes(series: pd.Series) -> pd.Series:
    return series == 'Yes'


def _td_ns(minutes: float) -> np.timedelta64:
    """Converte minutos para timedelta64 em nanosegundos."""
    return np.timedelta64(int(minutes * 60 * 1_000_000_000), 'ns')


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class RulesEngine:
    """Executa as 22 regras AML sobre os dados reais."""

    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def execute_all_rules(
        self,
        tx: pd.DataFrame,
        clients: pd.DataFrame,
        merchants: pd.DataFrame
    ) -> pd.DataFrame:
        """Executa todas as regras e retorna DataFrame de alertas."""
        rule_fns = [
            self.rule_R01_velocity,
            self.rule_R02_burst_value,
            self.rule_R03_structuring,
            self.rule_R04_income_mismatch,
            self.rule_R05_geojump,
            self.rule_R06_ip_anomaly,
            self.rule_R07_device_ring,
            self.rule_R08_ip_ring,
            self.rule_R09_self_merchant,
            self.rule_R10_cash_in_out,
            self.rule_R11_fan_out,
            self.rule_R12_ecom_no_3ds,
            self.rule_R13_eci_cross_border,
            self.rule_R14_cross_border_high,
            self.rule_R15_sanctions,
            self.rule_R16_pep,
            self.rule_R17_high_risk_mcc,
            self.rule_R18_chargeback_merchant,
            self.rule_R19_installments_atypical,
            self.rule_R20_new_account,
            self.rule_R21_round_values,
            self.rule_R22_card_multidevice,
        ]
        all_alerts: List[Dict] = []
        print(f"\n{'='*60}")
        print(f"Executando {len(rule_fns)} regras sobre {len(tx):,} transações")
        print(f"{'='*60}")
        for fn in rule_fns:
            try:
                results = fn(tx, clients, merchants)
                all_alerts.extend(results)
                print(f"  {fn.__name__:35s}: {len(results):4d} alertas")
            except Exception as e:
                print(f"  [WARN] {fn.__name__}: {e}")

        if not all_alerts:
            cols = ['entity_id', 'entity_type', 'rule_id', 'severity', 'evidence_ids', 'rule_desc']
            return pd.DataFrame(columns=cols)

        df = pd.DataFrame(all_alerts)
        df['evidence_ids'] = df['evidence_ids'].apply(
            lambda x: ';'.join(map(str, x)) if isinstance(x, list) else str(x)
        )
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # R01 — Velocidade (burst count)
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R01_velocity(self, tx, clients, merchants) -> List[Dict]:
        """R01: ≥5 transações do mesmo cliente em 30 minutos."""
        n, window_min, sev = 5, 30, 2
        alerts, window_ns = [], _td_ns(window_min)

        for cid, grp in tx.sort_values([C_CLIENT, C_TS]).groupby(C_CLIENT, sort=False):
            if len(grp) < n:
                continue
            ts = grp[C_TS].values
            txids = grp[C_TXN].values
            for i in range(len(ts)):
                mask = (ts >= ts[i]) & (ts < ts[i] + window_ns)
                cnt = int(mask.sum())
                if cnt >= n:
                    alerts.append({
                        'entity_id': cid, 'entity_type': 'client',
                        'rule_id': 'R01_velocity', 'severity': sev,
                        'evidence_ids': txids[mask].tolist()[:10],
                        'rule_desc': f'Burst velocidade: {cnt} tx em {window_min}min',
                    })
                    break
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R02 — Burst de valor
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R02_burst_value(self, tx, clients, merchants) -> List[Dict]:
        """R02: Soma >R$50k pelo mesmo cliente em 60 minutos."""
        threshold, window_min, sev = 50_000, 60, 2
        alerts, window_ns = [], _td_ns(window_min)

        for cid, grp in tx.sort_values([C_CLIENT, C_TS]).groupby(C_CLIENT, sort=False):
            g = grp.sort_values(C_TS)
            ts = g[C_TS].values
            amounts = g[C_AMOUNT].values
            txids = g[C_TXN].values
            for i in range(len(ts)):
                mask = (ts >= ts[i]) & (ts < ts[i] + window_ns)
                total = float(amounts[mask].sum())
                if total >= threshold:
                    alerts.append({
                        'entity_id': cid, 'entity_type': 'client',
                        'rule_id': 'R02_burst_value', 'severity': sev,
                        'evidence_ids': txids[mask].tolist()[:10],
                        'rule_desc': f'Burst valor: R${total:,.0f} em {window_min}min',
                    })
                    break
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R03★ — Structuring PIX
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R03_structuring(self, tx, clients, merchants) -> List[Dict]:
        """R03★: ≥3 PIX em [R$7k–R$10k] pelo mesmo cliente em 7 dias (faixa abaixo do limiar)."""
        k, low, high, days, sev = 3, 7_000, 10_000, 7, 3
        pix = tx[(tx[C_RAIL] == 'PIX') & tx[C_AMOUNT].between(low, high)].copy()
        if pix.empty:
            return []

        alerts, window_ns = [], _td_ns(days * 24 * 60)
        for cid, grp in pix.sort_values([C_CLIENT, C_TS]).groupby(C_CLIENT, sort=False):
            ts = grp[C_TS].values
            txids = grp[C_TXN].values
            for i in range(len(ts)):
                mask = (ts >= ts[i]) & (ts < ts[i] + window_ns)
                cnt = int(mask.sum())
                if cnt >= k:
                    alerts.append({
                        'entity_id': cid, 'entity_type': 'client',
                        'rule_id': 'R03_structuring', 'severity': sev,
                        'evidence_ids': txids[mask].tolist(),
                        'rule_desc': f'Structuring PIX: {cnt} tx em [R$9k-10k] em {days}d',
                    })
                    break
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R04 — Renda incompatível
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R04_income_mismatch(self, tx, clients, merchants) -> List[Dict]:
        """R04: Transação >15× renda mensal do cliente."""
        mult, sev = 15, 2
        if K_INCOME not in clients.columns:
            return []

        kc = clients[[K_CUSTOMER, K_INCOME]].copy()
        kc['monthly_income'] = kc[K_INCOME] / 12
        kc = kc[kc['monthly_income'] > 0]

        m = tx.merge(kc, left_on=C_CLIENT, right_on=K_CUSTOMER, how='inner')
        m['income_ratio'] = m[C_AMOUNT] / m['monthly_income']
        hits = m[m['income_ratio'] > mult]

        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R04_income_mismatch', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'Renda incompatível: R${r[C_AMOUNT]:,.0f} = {r["income_ratio"]:.1f}× renda mensal',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R05 — Geo-salto
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R05_geojump(self, tx, clients, merchants) -> List[Dict]:
        """R05: ≥500 km entre transações do mesmo cliente em ≤12h."""
        km_thr, hours_thr, sev = 500, 12, 3
        if C_LAT not in tx.columns or C_LON not in tx.columns:
            return []

        geo = tx[[C_CLIENT, C_TS, C_TXN, C_LAT, C_LON]].dropna(
            subset=[C_LAT, C_LON]
        ).sort_values([C_CLIENT, C_TS])

        alerts = []
        for cid, grp in geo.groupby(C_CLIENT, sort=False):
            if len(grp) < 2:
                continue
            g = grp.reset_index(drop=True)
            for i in range(1, len(g)):
                dt_h = (g.at[i, C_TS] - g.at[i - 1, C_TS]).total_seconds() / 3600
                if dt_h <= 0 or dt_h > hours_thr:
                    continue
                dist = _haversine_km(
                    g.at[i - 1, C_LAT], g.at[i - 1, C_LON],
                    g.at[i, C_LAT], g.at[i, C_LON]
                )
                if dist >= km_thr:
                    alerts.append({
                        'entity_id': cid, 'entity_type': 'client',
                        'rule_id': 'R05_geojump', 'severity': sev,
                        'evidence_ids': [g.at[i - 1, C_TXN], g.at[i, C_TXN]],
                        'rule_desc': f'Geo-salto: {dist:.0f}km em {dt_h:.1f}h',
                    })
                    break
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R06 — IP anomalia / país de alto risco
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R06_ip_anomaly(self, tx, clients, merchants) -> List[Dict]:
        """R06: IP via Proxy/VPN/Tor OU country_risk_ip = 'High'."""
        sev = 2
        mask = _yes(tx[C_IP_ANOMALY])
        if C_IP_RISK in tx.columns:
            mask = mask | (tx[C_IP_RISK] == 'High')

        hits = tx[mask]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R06_ip_anomaly', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'IP anômalo/alto-risco: ip_anomaly={r[C_IP_ANOMALY]}, risk={r.get(C_IP_RISK, "?")}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R07★ — Device ring
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R07_device_ring(self, tx, clients, merchants) -> List[Dict]:
        """R07★: ≥3 clientes distintos no mesmo device (qualquer período)."""
        min_clients, sev = 3, 3
        t = tx[[C_CLIENT, C_TS, C_TXN, C_DEVICE]].copy()

        # Agrupa por device (todo o período) para capturar reuso entre clientes
        ring_devs = (
            t.groupby(C_DEVICE)[C_CLIENT].nunique()
            .reset_index(name='n_clients')
        )
        ring_devs = ring_devs[ring_devs['n_clients'] >= min_clients]

        alerts = []
        for _, row in ring_devs.iterrows():
            dev = row[C_DEVICE]
            sub = t[t[C_DEVICE] == dev]
            ev = sub[C_TXN].tolist()[:10]
            for cid in sub[C_CLIENT].unique():
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R07_device_ring', 'severity': sev,
                    'evidence_ids': ev,
                    'rule_desc': f'Device ring: {int(row["n_clients"])} clientes compartilham device {dev[:12]}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R08 — IP ring
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R08_ip_ring(self, tx, clients, merchants) -> List[Dict]:
        """R08: ≥3 clientes distintos no mesmo IP (todo o período)."""
        min_clients, sev = 3, 3
        t = tx[[C_CLIENT, C_TS, C_TXN, C_IP]].copy()

        ring_ips = (
            t.groupby(C_IP)[C_CLIENT].nunique()
            .reset_index(name='n_clients')
        )
        ring_ips = ring_ips[ring_ips['n_clients'] >= min_clients]

        alerts = []
        for _, row in ring_ips.iterrows():
            ip_addr = row[C_IP]
            sub = t[t[C_IP] == ip_addr]
            ev = sub[C_TXN].tolist()[:10]
            for cid in sub[C_CLIENT].unique():
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R08_ip_ring', 'severity': sev,
                    'evidence_ids': ev,
                    'rule_desc': f'IP ring: {int(row["n_clients"])} clientes compartilham IP {ip_addr}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R09★ — Self-merchant
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R09_self_merchant(self, tx, clients, merchants) -> List[Dict]:
        """R09★: Cliente enviando para merchant do qual é dono (self-merchant)."""
        sev = 4
        if M_OWNER not in merchants.columns:
            return []

        merch_tx = tx[tx[C_RECV_TYPE] == 'merchant'][[C_CLIENT, C_TXN, C_AMOUNT, C_RECV]].copy()
        m = merchants[[M_ID, M_OWNER]].dropna(subset=[M_OWNER])
        merged = merch_tx.merge(m, left_on=C_RECV, right_on=M_ID, how='inner')
        hits = merged[merged[C_CLIENT] == merged[M_OWNER]]

        alerts = []
        for _, r in hits.iterrows():
            alerts.append({
                'entity_id': r[C_CLIENT], 'entity_type': 'client',
                'rule_id': 'R09_self_merchant', 'severity': sev,
                'evidence_ids': [r[C_TXN]],
                'rule_desc': f'Self-merchant: R${r[C_AMOUNT]:,.0f} → próprio merchant {r[C_RECV]}',
            })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R10 — Cash-in → cash-out rápido
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R10_cash_in_out(self, tx, clients, merchants) -> List[Dict]:
        """R10: Saída ≥80% da entrada do mesmo cliente no mesmo dia (>R$1k)."""
        ratio_thr, floor, sev = 0.80, 1_000, 3

        # Saídas (cliente como sender)
        out_df = tx[[C_CLIENT, C_TS, C_TXN, C_AMOUNT]].copy()
        out_df.columns = ['customer_id', 'timestamp', 'tx_id', 'amount']
        out_df['direction'] = 'out'

        # Entradas (cliente como receiver, não merchant)
        recv_mask = tx[C_RECV_TYPE] == 'customer'
        in_df = tx.loc[recv_mask, [C_RECV, C_TS, C_TXN, C_AMOUNT]].copy()
        in_df.columns = ['customer_id', 'timestamp', 'tx_id', 'amount']
        in_df['direction'] = 'in'

        flows = pd.concat([out_df, in_df], ignore_index=True)
        flows['date'] = flows['timestamp'].dt.date

        daily = (
            flows.pivot_table(
                index=['customer_id', 'date'],
                columns='direction',
                values='amount',
                aggfunc='sum',
            )
            .fillna(0)
            .reset_index()
        )
        if 'in' not in daily.columns or 'out' not in daily.columns:
            return []

        daily['pass_through'] = (
            (daily['out'] >= ratio_thr * daily['in']) &
            (daily['in'] >= floor)
        )
        flagged = daily[daily['pass_through']]

        alerts, seen = [], set()
        for _, row in flagged.iterrows():
            cid = row['customer_id']
            if cid in seen:
                continue
            seen.add(cid)
            day = pd.Timestamp(row['date'])
            ev = tx[
                (tx[C_CLIENT] == cid) &
                (tx[C_TS] >= day) &
                (tx[C_TS] < day + pd.Timedelta(days=1))
            ][C_TXN].tolist()[:10]
            pct = row['out'] / row['in'] * 100 if row['in'] > 0 else 0
            alerts.append({
                'entity_id': cid, 'entity_type': 'client',
                'rule_id': 'R10_cash_in_out', 'severity': sev,
                'evidence_ids': ev,
                'rule_desc': f'Cash passthrough: saída = {pct:.0f}% da entrada (R${row["in"]:,.0f}) em {row["date"]}',
            })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R11 — Fan-out (dispersão)
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R11_fan_out(self, tx, clients, merchants) -> List[Dict]:
        """R11: Cliente enviando para ≥5 receivers distintos em 1 dia."""
        min_recv, sev = 5, 2
        t = tx[[C_CLIENT, C_TS, C_TXN, C_RECV]].copy()
        t['day'] = t[C_TS].dt.date

        fan = (
            t.groupby([C_CLIENT, 'day'])[C_RECV].nunique()
            .reset_index(name='n_recv')
        )
        fan = fan[fan['n_recv'] >= min_recv]

        alerts, seen = [], set()
        for _, row in fan.iterrows():
            cid = row[C_CLIENT]
            if cid in seen:
                continue
            seen.add(cid)
            day = pd.Timestamp(row['day'])
            ev = t[(t[C_CLIENT] == cid) & (t['day'] == row['day'])][C_TXN].tolist()[:10]
            alerts.append({
                'entity_id': cid, 'entity_type': 'client',
                'rule_id': 'R11_fan_out', 'severity': sev,
                'evidence_ids': ev,
                'rule_desc': f'Fan-out: {int(row["n_recv"])} destinatários distintos em {row["day"]}',
            })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R12★ — E-commerce sem 3DS de alto valor
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R12_ecom_no_3ds(self, tx, clients, merchants) -> List[Dict]:
        """R12★: Card e-commerce sem auth_3ds com valor ≥R$2k."""
        threshold, sev = 2_000, 3
        if C_AUTH3DS not in tx.columns:
            return []

        hits = tx[
            (tx[C_RAIL] == 'Card') &
            (tx[C_CAPTURE].isin(ECOM_CAPTURES)) &
            (tx[C_AUTH3DS] == 'No') &
            (tx[C_AMOUNT] >= threshold)
        ]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R12_ecom_no_3ds', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'E-com sem 3DS: R${r[C_AMOUNT]:,.0f} via {r[C_CAPTURE]}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R13 — ECI suspeito + cross-border
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R13_eci_cross_border(self, tx, clients, merchants) -> List[Dict]:
        """R13: ECI não-autenticado (≥7) em transação cross-border."""
        sev = 2
        if C_ECI not in tx.columns:
            return []

        hits = tx[
            (tx[C_ECI].notna()) &
            (tx[C_ECI] >= 7) &
            (_yes(tx[C_CROSS]))
        ]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R13_eci_cross_border', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'ECI={r[C_ECI]:.0f} cross-border: R${r[C_AMOUNT]:,.0f}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R14 — Cross-border de alto valor
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R14_cross_border_high(self, tx, clients, merchants) -> List[Dict]:
        """R14: Transação cross-border >R$20k (Wire/Card)."""
        threshold, sev = 20_000, 2
        hits = tx[
            _yes(tx[C_CROSS]) &
            (tx[C_AMOUNT] > threshold)
        ]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R14_cross_border_high', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'Cross-border alto valor: R${r[C_AMOUNT]:,.0f} ({r[C_RAIL]})',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R15★ — Sanções
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R15_sanctions(self, tx, clients, merchants) -> List[Dict]:
        """R15★: Sanctions hit na transação OU cliente em lista de sanções."""
        sev = 4
        alerts = []

        # a) Transações com sanctions_screening_hit = 'Yes'
        hits_tx = tx[_yes(tx[C_SANCTIONS])]
        for _, r in hits_tx.iterrows():
            alerts.append({
                'entity_id': r[C_CLIENT], 'entity_type': 'client',
                'rule_id': 'R15_sanctions', 'severity': sev,
                'evidence_ids': [r[C_TXN]],
                'rule_desc': f'Sanctions screening hit: R${r[C_AMOUNT]:,.0f}',
            })

        # b) Clientes na lista de sanções KYC
        if K_SANCTIONS in clients.columns:
            pep_clients = clients[clients[K_SANCTIONS] == 'Yes'][K_CUSTOMER].tolist()
            if pep_clients:
                client_tx = tx[tx[C_CLIENT].isin(pep_clients)]
                seen: set = set()
                for _, r in client_tx.iterrows():
                    cid = r[C_CLIENT]
                    if cid not in seen:
                        seen.add(cid)
                        alerts.append({
                            'entity_id': cid, 'entity_type': 'client',
                            'rule_id': 'R15_sanctions', 'severity': sev,
                            'evidence_ids': [r[C_TXN]],
                            'rule_desc': f'Cliente em lista de sanções (KYC): R${r[C_AMOUNT]:,.0f}',
                        })

        # c) Country risk = High (sender ou receiver)
        for col, label in [(C_SEND_RISK, 'sender'), (C_RECV_RISK, 'receiver')]:
            if col in tx.columns:
                high_risk = tx[tx[col] == 'High']
                seen2: set = set()
                for _, r in high_risk.iterrows():
                    cid = r[C_CLIENT]
                    if cid not in seen2:
                        seen2.add(cid)
                        alerts.append({
                            'entity_id': cid, 'entity_type': 'client',
                            'rule_id': 'R15_sanctions', 'severity': 3,
                            'evidence_ids': [r[C_TXN]],
                            'rule_desc': f'País alto risco ({label}): country_risk=High',
                        })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R16 — PEP com atividade incompatível
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R16_pep(self, tx, clients, merchants) -> List[Dict]:
        """R16: Cliente PEP com transação >10× renda mensal."""
        mult, sev = 10, 3
        if K_PEP not in clients.columns or K_INCOME not in clients.columns:
            return []

        peps = clients[clients[K_PEP] == 'Yes'][[K_CUSTOMER, K_INCOME]].copy()
        peps['monthly_income'] = peps[K_INCOME] / 12
        peps = peps[peps['monthly_income'] > 0]

        m = tx.merge(peps, left_on=C_CLIENT, right_on=K_CUSTOMER, how='inner')
        m['pep_ratio'] = m[C_AMOUNT] / m['monthly_income']
        hits = m[m['pep_ratio'] > mult]

        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R16_pep', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'PEP ativo: R${r[C_AMOUNT]:,.0f} = {r["pep_ratio"]:.1f}× renda mensal',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R17 — MCC de alto risco
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R17_high_risk_mcc(self, tx, clients, merchants) -> List[Dict]:
        """R17: Transação com MCC de alto risco (cassino, cripto, ATM, quasi-cash)."""
        sev = 2
        if C_MCC not in tx.columns:
            return []

        hits = tx[tx[C_MCC].isin(HIGH_RISK_MCC)]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R17_high_risk_mcc', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'MCC alto risco: {int(r[C_MCC])} — R${r[C_AMOUNT]:,.0f}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R18 — Chargeback de merchant
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R18_chargeback_merchant(self, tx, clients, merchants) -> List[Dict]:
        """R18: Merchant com taxa de chargeback 90d >2%."""
        threshold, sev = 0.02, 2
        if M_CHARGEBACK not in merchants.columns:
            return []

        bad_merchants = merchants[merchants[M_CHARGEBACK] > threshold][M_ID].tolist()
        hits = tx[tx[C_RECV].isin(bad_merchants) & (tx[C_RECV_TYPE] == 'merchant')]

        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            mid = r[C_RECV]
            if mid not in seen:
                seen.add(mid)
                rate = merchants.loc[merchants[M_ID] == mid, M_CHARGEBACK].iloc[0]
                alerts.append({
                    'entity_id': mid, 'entity_type': 'merchant',
                    'rule_id': 'R18_chargeback_merchant', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'Merchant chargeback rate 90d: {rate:.1%} (limiar 2%)',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R19 — Parcelamento atípico
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R19_installments_atypical(self, tx, clients, merchants) -> List[Dict]:
        """R19: Card com ≥12 parcelas em valor baixo (<R$500) ou MCC quasi-cash."""
        min_inst, max_amount, sev = 12, 500, 1
        if C_INSTALLMENTS not in tx.columns:
            return []

        card = tx[tx[C_RAIL] == 'Card'].copy()
        card[C_INSTALLMENTS] = pd.to_numeric(card[C_INSTALLMENTS], errors='coerce')
        hits = card[
            (card[C_INSTALLMENTS] >= min_inst) &
            (
                (card[C_AMOUNT] < max_amount) |
                (card[C_MCC].isin({6051, 6012}) if C_MCC in card.columns else False)
            )
        ]
        alerts = []
        seen: set = set()
        for _, r in hits.iterrows():
            cid = r[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R19_installments_atypical', 'severity': sev,
                    'evidence_ids': [r[C_TXN]],
                    'rule_desc': f'Parcelamento atípico: {int(r[C_INSTALLMENTS])}x R${r[C_AMOUNT]:,.0f}',
                })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R20 — Conta nova com alta atividade
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R20_new_account(self, tx, clients, merchants) -> List[Dict]:
        """R20: Conta com <7 dias de vida no momento da transação com alto volume."""
        age_days_thr, amount_thr, n_tx_thr, sev = 7, 10_000, 5, 2
        if K_REG_DATE not in clients.columns:
            return []

        kc = clients[[K_CUSTOMER, K_REG_DATE]].copy()
        kc[K_REG_DATE] = pd.to_datetime(kc[K_REG_DATE], errors='coerce')
        kc = kc.dropna(subset=[K_REG_DATE])

        m = tx.merge(kc, left_on=C_CLIENT, right_on=K_CUSTOMER, how='inner')
        m['account_age_days'] = (m[C_TS] - m[K_REG_DATE]).dt.days
        new = m[m['account_age_days'] < age_days_thr]

        if new.empty:
            return []

        stats = new.groupby(C_CLIENT).agg(
            total_brl=(C_AMOUNT, 'sum'),
            n_tx=(C_TXN, 'count'),
        ).reset_index()
        flagged = stats[(stats['total_brl'] > amount_thr) | (stats['n_tx'] >= n_tx_thr)]

        alerts = []
        for _, row in flagged.iterrows():
            cid = row[C_CLIENT]
            ev = new[new[C_CLIENT] == cid][C_TXN].tolist()[:5]
            alerts.append({
                'entity_id': cid, 'entity_type': 'client',
                'rule_id': 'R20_new_account', 'severity': sev,
                'evidence_ids': ev,
                'rule_desc': f'Conta nova: {int(row["n_tx"])} tx, R${row["total_brl"]:,.0f} em <{age_days_thr}d',
            })
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R21 — Valores redondos repetidos
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R21_round_values(self, tx, clients, merchants) -> List[Dict]:
        """R21: ≥5 transações com valores redondos (múltiplos de R$500) em 7 dias."""
        k, days, sev = 5, 7, 1
        # Usa round() para lidar com precisão de float
        rnd = tx[(tx[C_AMOUNT].round(0) % 500 == 0) & (tx[C_AMOUNT] >= 500)].copy()
        if rnd.empty:
            return []

        alerts, window_ns = [], _td_ns(days * 24 * 60)
        for cid, grp in rnd.sort_values([C_CLIENT, C_TS]).groupby(C_CLIENT, sort=False):
            if len(grp) < k:
                continue
            ts = grp[C_TS].values
            txids = grp[C_TXN].values
            for i in range(len(ts)):
                mask = (ts >= ts[i]) & (ts < ts[i] + window_ns)
                cnt = int(mask.sum())
                if cnt >= k:
                    alerts.append({
                        'entity_id': cid, 'entity_type': 'client',
                        'rule_id': 'R21_round_values', 'severity': sev,
                        'evidence_ids': txids[mask].tolist(),
                        'rule_desc': f'Valores redondos: {cnt} tx múltiplos de R$1k em {days}d',
                    })
                    break
        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # R22 — Card reuso em múltiplos devices
    # ─────────────────────────────────────────────────────────────────────────
    def rule_R22_card_multidevice(self, tx, clients, merchants) -> List[Dict]:
        """R22: Mesmo sender usa ≥3 devices distintos com cartão no mesmo dia."""
        min_devices, sev = 3, 3
        if C_CARD_BRAND not in tx.columns:
            return []

        card = tx[tx[C_RAIL] == 'Card'].copy()
        card['day'] = card[C_TS].dt.date

        grp = (
            card.groupby([C_CLIENT, C_CARD_BRAND, 'day'])[C_DEVICE].nunique()
            .reset_index(name='n_devices')
        )
        flagged = grp[grp['n_devices'] >= min_devices]

        alerts = []
        seen: set = set()
        for _, row in flagged.iterrows():
            cid = row[C_CLIENT]
            if cid not in seen:
                seen.add(cid)
                ev = card[
                    (card[C_CLIENT] == cid) &
                    (card[C_CARD_BRAND] == row[C_CARD_BRAND]) &
                    (card['day'] == row['day'])
                ][C_TXN].tolist()[:10]
                alerts.append({
                    'entity_id': cid, 'entity_type': 'client',
                    'rule_id': 'R22_card_multidevice', 'severity': sev,
                    'evidence_ids': ev,
                    'rule_desc': f'Card {row[C_CARD_BRAND]} em {int(row["n_devices"])} devices distintos em {row["day"]}',
                })
        return alerts


# ─────────────────────────────────────────────────────────────────────────────
# Build risk ranking + weak label (usado pelo notebook e pelo ML no Dia 4)
# ─────────────────────────────────────────────────────────────────────────────
def build_ranking(alerts: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega alertas por entidade:
      score = Σ severity | n_regras | is_core_label (≥2 regras-core disparadas)
    """
    if alerts.empty:
        return pd.DataFrame(columns=['entity_id', 'entity_type', 'score', 'n_rules',
                                     'rules', 'is_core_label', 'tier'])

    g = (
        alerts.groupby(['entity_id', 'entity_type'])
        .agg(
            score=('severity', 'sum'),
            n_rules=('rule_id', 'nunique'),
            rules=('rule_id', lambda s: ','.join(sorted(set(s)))),
        )
        .reset_index()
        .sort_values('score', ascending=False)
    )

    def _is_core(rules_str: str) -> int:
        fired = set(rules_str.split(','))
        return int(len(fired & CORE_RULES) >= 2)

    g['is_core_label'] = g['rules'].apply(_is_core)

    score_max = g['score'].max() if not g.empty else 1
    g['tier'] = pd.cut(
        g['score'],
        bins=[0, score_max * 0.33, score_max * 0.66, score_max + 1],
        labels=['baixo', 'medio', 'alto'],
        include_lowest=True,
    )
    return g
