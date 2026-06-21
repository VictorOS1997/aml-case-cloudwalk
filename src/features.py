"""
Feature Store — Agregações por entidade para regras e ML.
Colunas reais da base (EDA Dia 1):
  sender_id, amount_brl, transaction_type, device_fingerprint, ip_address,
  cross_border (Yes/No), ip_anomaly (Yes/No), device_rooted (Yes/No),
  sanctions_screening_hit (Yes/No), receiver_id, receiver_entity_type, status
"""

from __future__ import annotations
import numpy as np
import pandas as pd

SEED = 42
np.random.seed(SEED)

# Colunas reais da base
C_CLIENT = 'sender_id'
C_RECEIVER = 'receiver_id'
C_RECV_TYPE = 'receiver_entity_type'
C_AMOUNT = 'amount_brl'
C_TS = 'timestamp'
C_TXN_ID = 'transaction_id'
C_CROSS = 'cross_border'
C_IP_ANOMALY = 'ip_anomaly'
C_DEVICE_ROOTED = 'device_rooted'
C_SANCTIONS = 'sanctions_screening_hit'
C_DEVICE = 'device_fingerprint'
C_IP = 'ip_address'
C_RAIL = 'transaction_type'
C_STATUS = 'status'
C_MCC = 'mcc'
C_AUTH3DS = 'auth_3ds'
C_CAPTURE = 'capture_method'


def _yes(series: pd.Series) -> pd.Series:
    return series == 'Yes'


def create_feature_store(
    transactions: pd.DataFrame,
    clients: pd.DataFrame,
    merchants: pd.DataFrame
) -> dict:
    """Cria feature store completo para todas as entidades."""
    return {
        'client': aggregate_by_client(transactions, clients),
        'merchant': aggregate_by_merchant(transactions, merchants),
        'device': aggregate_by_device(transactions),
        'ip': aggregate_by_ip(transactions),
    }


def aggregate_by_client(
    transactions: pd.DataFrame,
    clients: pd.DataFrame | None = None
) -> pd.DataFrame:
    """
    Agregações por cliente:
    - perspectiva de envio (sender_id)
    - perspectiva de recebimento (receiver_id onde entity='customer')
    - join opcional com KYC para renda/PEP/kyc_score
    """
    yes = lambda s: (s == 'Yes').sum()

    # Perspectiva de envio
    sent = transactions.groupby(C_CLIENT).agg(
        total_brl_sent=(C_AMOUNT, 'sum'),
        media_brl_sent=(C_AMOUNT, 'mean'),
        max_brl_sent=(C_AMOUNT, 'max'),
        n_tx_sent=(C_TXN_ID, 'count'),
        n_receivers_uniq=(C_RECEIVER, 'nunique'),
        n_cross_border=(C_CROSS, yes),
        n_ip_anomaly=(C_IP_ANOMALY, yes),
        n_device_rooted=(C_DEVICE_ROOTED, yes),
        n_sanctions=(C_SANCTIONS, yes),
        n_devices_uniq=(C_DEVICE, 'nunique'),
        n_ips_uniq=(C_IP, 'nunique'),
    ).reset_index().rename(columns={C_CLIENT: 'customer_id'})

    # Merchants únicos para onde enviou
    merch_sent = (
        transactions[transactions[C_RECV_TYPE] == 'merchant']
        .groupby(C_CLIENT)[C_RECEIVER].nunique()
        .reset_index(name='n_merchants_uniq')
        .rename(columns={C_CLIENT: 'customer_id'})
    )

    # Perspectiva de recebimento (customer como destinatário)
    recv = (
        transactions[transactions[C_RECV_TYPE] == 'customer']
        .groupby(C_RECEIVER)
        .agg(
            total_brl_recv=(C_AMOUNT, 'sum'),
            n_tx_recv=(C_TXN_ID, 'count'),
        )
        .reset_index()
        .rename(columns={C_RECEIVER: 'customer_id'})
    )

    result = (
        sent
        .merge(recv, on='customer_id', how='left')
        .merge(merch_sent, on='customer_id', how='left')
    )
    result['total_brl_recv'] = result['total_brl_recv'].fillna(0)
    result['n_tx_recv'] = result['n_tx_recv'].fillna(0).astype(int)
    result['n_merchants_uniq'] = result['n_merchants_uniq'].fillna(0).astype(int)

    # Razão pass-through (quanto do recebido é repassado)
    result['cash_through_ratio'] = np.where(
        result['total_brl_recv'] > 0,
        (result['total_brl_sent'] / result['total_brl_recv']).clip(0, 20),
        0
    )

    if clients is not None and len(clients) > 0:
        kc = clients[[
            'customer_id', 'annual_income_brl', 'pep',
            'registration_date', 'sanctions_list_hit', 'kyc_risk_score'
        ]].copy()
        kc['monthly_income'] = kc['annual_income_brl'] / 12
        result = result.merge(kc, on='customer_id', how='left')
        result['income_tx_ratio'] = np.where(
            result['monthly_income'].fillna(0) > 0,
            result['max_brl_sent'] / result['monthly_income'],
            0
        )

    return result.round(2)


def aggregate_by_merchant(
    transactions: pd.DataFrame,
    merchants: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Agregações por merchant (receiver quando receiver_entity_type=='merchant')."""
    yes = lambda s: (s == 'Yes').sum()
    merch_recv = transactions[transactions[C_RECV_TYPE] == 'merchant']

    agg = (
        merch_recv.groupby(C_RECEIVER).agg(
            total_brl=(C_AMOUNT, 'sum'),
            media_brl=(C_AMOUNT, 'mean'),
            max_brl=(C_AMOUNT, 'max'),
            n_tx=(C_TXN_ID, 'count'),
            n_senders_uniq=(C_CLIENT, 'nunique'),
            n_cross_border=(C_CROSS, yes),
            n_ip_anomaly=(C_IP_ANOMALY, yes),
            n_chargebacks=(C_STATUS, lambda x: (x == 'Chargeback').sum()),
        )
        .reset_index()
        .rename(columns={C_RECEIVER: 'merchant_id'})
    )
    agg['chargeback_rate_tx'] = (agg['n_chargebacks'] / agg['n_tx'].clip(1)).round(4)

    if merchants is not None and len(merchants) > 0:
        mc = merchants[[
            'merchant_id', 'mcc', 'owner_customer_id',
            'merchant_chargeback_ratio_90d', 'merchant_high_risk_flag', 'mcc_risk'
        ]].copy()
        agg = agg.merge(mc, on='merchant_id', how='left')

    return agg.round(2)


def aggregate_by_device(transactions: pd.DataFrame) -> pd.DataFrame:
    """Agregações por device_fingerprint."""
    yes = lambda s: (s == 'Yes').sum()
    agg = (
        transactions.groupby(C_DEVICE).agg(
            n_clients_uniq=(C_CLIENT, 'nunique'),
            n_tx=(C_TXN_ID, 'count'),
            total_brl=(C_AMOUNT, 'sum'),
            n_sanctions=(C_SANCTIONS, yes),
            n_rooted=(C_DEVICE_ROOTED, yes),
        )
        .reset_index()
        .rename(columns={C_DEVICE: 'device_fingerprint'})
    )
    agg['is_device_ring'] = agg['n_clients_uniq'] >= 6
    return agg.sort_values('n_clients_uniq', ascending=False)


def aggregate_by_ip(transactions: pd.DataFrame) -> pd.DataFrame:
    """Agregações por ip_address."""
    yes = lambda s: (s == 'Yes').sum()
    agg = (
        transactions.groupby(C_IP).agg(
            n_clients_uniq=(C_CLIENT, 'nunique'),
            n_tx=(C_TXN_ID, 'count'),
            total_brl=(C_AMOUNT, 'sum'),
            n_anomaly=(C_IP_ANOMALY, yes),
        )
        .reset_index()
        .rename(columns={C_IP: 'ip_address'})
    )
    agg['is_ip_ring'] = agg['n_clients_uniq'] >= 6
    return agg.sort_values('n_clients_uniq', ascending=False)
