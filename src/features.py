"""
Feature Store — Agregações e features por entidade.
Implementar no Dia 1-2 conforme EDA.
"""

import pandas as pd
import numpy as np
from datetime import timedelta


def create_feature_store(transactions, clients, merchants):
    """
    Cria feature store agregando dados por cliente, merchant, device, IP.

    Args:
        transactions: DataFrame de transações
        clients: DataFrame de KYC
        merchants: DataFrame de merchants

    Returns:
        dict com feature stores (cliente, merchant, device, IP)
    """
    features = {}

    # TODO: Implementar agregações por cliente
    # - Contagem de transações por período
    # - Soma de valores por período
    # - Velocidade (transações/hora)
    # - Contagem de merchants únicos
    # - etc

    return features


def aggregate_by_client(transactions):
    """Agregações por cliente."""
    pass


def aggregate_by_merchant(transactions):
    """Agregações por merchant."""
    pass


def aggregate_by_device(transactions):
    """Agregações por device."""
    pass


def aggregate_by_ip(transactions):
    """Agregações por IP."""
    pass
