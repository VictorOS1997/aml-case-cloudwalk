"""
Modelo de Machine Learning para priorização de risco.
Implementar no Dia 4 com rótulo fraco + XGBoost/RF + Isolation Forest.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.ensemble import IsolationForest


class RiskModel:
    """Modelo de ML para priorização de risco de transações/clientes."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []

    def create_weak_label(
        self, transactions: pd.DataFrame, rule_alerts: pd.DataFrame, core_rules: List[str]
    ) -> pd.Series:
        """
        Cria rótulo fraco baseado em core de regras de alta confiança.
        Positivo fraco = aciona >= 2 rules-core.

        Args:
            transactions: DataFrame de transações
            rule_alerts: DataFrame de alertas (rule_id, transaction_id)
            core_rules: Lista de rule_ids de alta confiança (ex: ['r14_sanctions', 'r16_pep'])

        Returns:
            Series de labels (0/1)
        """
        pass

    def engineer_features(self, transactions: pd.DataFrame, clients: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features para o modelo.
        Mínimo: razão valor/renda, MCC, país, rail, velocidade, reuso IP/device.
        """
        pass

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.3,
        use_temporal_split: bool = True,
    ) -> Dict:
        """
        Treina o modelo com split temporal (passado vs futuro).

        Returns:
            dict com métricas (AUC, PR-AUC, precision, recall, etc)
        """
        pass

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Prediz probabilidade de risco."""
        pass

    def explain_with_shap(self) -> pd.DataFrame:
        """Retorna feature importance via SHAP."""
        pass
