"""
Pipeline multi-agente AML-FT.
5 agentes orquestrados em sequência via Anthropic API.
Implementar no Dia 5.
"""

from anthropic import Anthropic
import json


class AMLPipeline:
    """Orquestrador do pipeline de 5 agentes AML."""

    def __init__(self, api_key: str):
        self.client = Anthropic()
        self.conversation_history = []

    def run(self, case_data: Dict) -> Dict:
        """
        Executa o pipeline completo sobre um caso.

        Fluxo:
        1. Dados → Detecção
        2. Detecção → Investigação
        3. Investigação → Reporte (SAR)
        4. Reporte → Compliance
        5. Compliance → Decisão (approve/revise)

        Args:
            case_data: dict com transações e cliente do caso

        Returns:
            dict com saída de cada estágio + decisão final
        """
        pass

    def agent_detector(self, case_data: Dict) -> Dict:
        """Agente 1: Detecção de anomalias."""
        pass

    def agent_investigator(self, detection_result: Dict) -> Dict:
        """Agente 2: Investigação aprofundada."""
        pass

    def agent_reporter(self, investigation_result: Dict) -> Dict:
        """Agente 3: Geração de SAR."""
        pass

    def agent_compliance(self, sar_draft: Dict) -> Dict:
        """Agente 4: Verificação de conformidade."""
        pass

    def agent_decision(self, compliance_result: Dict) -> Dict:
        """Agente 5: Decisão final (approve/revise)."""
        pass


if __name__ == "__main__":
    # TODO: Implementar script de teste com 1-2 casos reais
    pass
