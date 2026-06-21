"""
Dia 5 — Pipeline Multi-Agente AML-FT (Tarefa 4)
================================================
Demonstra a execução do pipeline de 5 agentes sobre o caso real C101208.
Requer: ANTHROPIC_API_KEY no ambiente.

Execução:
    python notebooks/05_agentes_pipeline.py
ou, via módulo:
    python -m src.agents.pipeline --case C101208
"""

import sys
import os
import io
import json
import pathlib

# Força UTF-8 no stdout do Windows (evita UnicodeEncodeError em cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# garante import do módulo local
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.agents.pipeline import orchestrate, CASE_C101208, CASE_DEMO

# -----------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------
SEED = 42

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("[AVISO] ANTHROPIC_API_KEY não definida.")
    print("  Defina com: $env:ANTHROPIC_API_KEY='sk-ant-...'")
    print("  Rodando no modo SIMULADO (sem chamadas reais à API).\n")
    SIMULATE = True
else:
    SIMULATE = False

# -----------------------------------------------------------------------
# Execução principal
# -----------------------------------------------------------------------
if __name__ == "__main__":
    if SIMULATE:
        # Saída simulada para demonstração sem API key
        print("=" * 60)
        print("[ORQUESTRADOR SIMULADO] Caso: C101208")
        print("=" * 60)
        print("\n[1/5] Agente de DADOS — validação e enriquecimento...")
        print("  → 15 transações validadas | Rails: PIX=7, Card=6, Wire=2")
        print("  → Países de risco: SY, RU, YE, BY")
        print("  → Ratio volume/renda: 11.5x")
        print("  → Qualidade: OK (sem campos críticos ausentes)")

        print("\n[2/5] Agente de DETECÇÃO — avaliação de regras + score ML...")
        print("  → 7 regras disparadas: R04, R05, R10, R12, R13, R15, R17")
        print("  → Severity sum: 21 | ML score: 0.797")
        print("  → Priority: 39.6 (SANÇÃO no topo da fila)")

        print("\n[3/5] Agente de INVESTIGAÇÃO — caso 360°...")
        print("  → Risk level: CRÍTICO")
        print("  → Tipologias: Renda incompatível · Geo-salto · Cash-in→out")
        print("               E-com sem 3DS · Cross-border · Sanções · MCC risco")
        print("  → Geo-jump mais grave: 14.341 km em 13h (1.092 km/h) BR→RU")
        print("  → Sanctions TX: TNHZDN7D6LYK6 → M200815 (SY)")

        print("\n[4/5] Agente de REPORTE — rascunho de SAR...")
        print("  → SAR draft gerado com 7 seções")
        print("  → Resumo: layering via 3 rails + cross-border + sanção")
        print("  → Base legal: Lei 9.613/98, BACEN 3.978/2020, COAF/SISCOAF, FATF Rec. 20")

        print("\n[5/5] Agente de COMPLIANCE — validação regulatória...")
        print("  → Sanção confirmada: SY (Síria — lista ONU)")
        print("  → SAR: completo e factualmente consistente")
        print("  → Ação proporcional ao risco CRÍTICO")

        print("\n" + "=" * 60)
        print("[ORQUESTRADOR] DECISÃO: APPROVE")
        print("  Ação recomendada : report_coaf")
        print("  Tipologias       : Renda incompatível, Geo-salto, Cash-in→out,")
        print("                     E-com sem 3DS, Cross-border, Sanções, MCC risco")
        print("  Sanções          : True")
        print("  SLA              : D+3 (prazo legal de comunicação ao COAF)")
        print("=" * 60)

        resultado_simulado = {
            "case_id": "C101208",
            "run_timestamp": "20260621_120000",
            "decision": "approve",
            "recommended_action": "report_coaf",
            "typologies": [
                "Renda incompatível (11.5× renda anual)",
                "Geo-salto (1.092 km/h BR→RU)",
                "Cash-in → Cash-out PIX",
                "E-commerce sem 3DS",
                "Cross-border + ECI não-autenticado",
                "Sanctions screening hit (SY)",
                "MCC de alto risco (6011, 7995, 4789)",
            ],
            "sanctions_confirmed": True,
            "mode": "SIMULADO — sem chamadas reais à API",
        }
        print("\nResultado final:")
        print(json.dumps(resultado_simulado, ensure_ascii=False, indent=2))

    else:
        # Execução real com a API
        print("Rodando pipeline real com ANTHROPIC_API_KEY...")
        resultado = orchestrate(CASE_C101208, verbose=True)
        print("\nResultado final:")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
