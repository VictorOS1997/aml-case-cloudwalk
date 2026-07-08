"""
simulate_case.py — Simula o pipeline de 5 agentes AML-FT para QUALQUER caso, sem chamar a API.
=================================================================================================
Ao contrário de notebooks/05_agentes_pipeline.py (que só tem uma narrativa fixa para C101208),
este script lê as evidências reais de outputs/alertas.csv, outputs/ranking_risco.csv,
outputs/04_ml_scores.csv e data/processed/sender_features.csv para QUALQUER entity_id, e
reproduz deterministicamente a mesma lógica que os 5 agentes (Dados, Detecção, Investigação,
Reporte, Compliance) aplicariam — útil para validar a arquitetura sem custo de API.

Uso:
    python scripts/simulate_case.py --case C101919
"""
import argparse
import csv
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
SEVERITY_RULES = {
    "R04_income_mismatch": 3, "R05_geojump": 3, "R10_cash_in_out": 3,
    "R12_ecom_no_3ds": 3, "R13_eci_cross_border": 3, "R15_sanctions": 4,
    "R17_high_risk_mcc": 2,
}
TYPOLOGY_MAP = {
    "R02_burst_value": "Burst de valor / velocidade",
    "R04_income_mismatch": "Renda incompatível",
    "R05_geojump": "Geo-salto",
    "R10_cash_in_out": "Cash-in → Cash-out",
    "R12_ecom_no_3ds": "E-commerce sem 3DS",
    "R13_eci_cross_border": "Cross-border + ECI não-autenticado",
    "R14_cross_border_high": "Cross-border alto valor",
    "R15_sanctions": "Sanctions screening hit",
    "R16_pep": "PEP (Pessoa Exposta Politicamente)",
    "R17_high_risk_mcc": "MCC de alto risco",
}


def load_case(case_id: str) -> dict:
    alerts = []
    with open(ROOT / "outputs/alertas.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["entity_id"] == case_id:
                alerts.append(row)
    if not alerts:
        raise SystemExit(f"Nenhum alerta encontrado para {case_id} em outputs/alertas.csv")

    ranking = {}
    with open(ROOT / "outputs/ranking_risco.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["entity_id"] == case_id:
                ranking = row
                break

    ml = {}
    with open(ROOT / "outputs/04_ml_scores.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["customer_id"] == case_id:
                ml = row
                break

    volume = {}
    with open(ROOT / "data/processed/sender_features.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["entity_id"] == case_id:
                volume = row
                break

    return {"case_id": case_id, "alerts": alerts, "ranking": ranking, "ml": ml, "volume": volume}


def simulate(case_id: str, verbose: bool = True) -> dict:
    data = load_case(case_id)
    alerts, ranking, ml, volume = data["alerts"], data["ranking"], data["ml"], data["volume"]

    rules_fired = [a["rule_id"] for a in alerts]
    severity_sum = int(ranking.get("score", sum(SEVERITY_RULES.get(r, 2) for r in rules_fired)))
    ml_score = float(ml.get("final_score", 0.0))
    sanctions_fired = "R15_sanctions" in rules_fired
    priority = round(severity_sum * (1 + ml_score), 1)

    if verbose:
        print("=" * 60)
        print(f"[ORQUESTRADOR SIMULADO] Caso: {case_id}  (fonte: outputs agregados, sem API)")
        print("=" * 60)

        print("\n[1/5] Agente de DADOS — validação e enriquecimento...")
        print(f"  → {volume.get('n_transacoes', '?')} transações | volume total R$ {volume.get('total_brl', '?')}")
        print(f"  → Cross-border: {volume.get('n_cross_border', '?')} | device rooted: {volume.get('n_device_rooted', '?')} | sanções: {volume.get('n_sanctions', '?')}")

        print("\n[2/5] Agente de DETECÇÃO — avaliação de regras + score ML...")
        print(f"  → {len(rules_fired)} regras disparadas: {', '.join(rules_fired)}")
        print(f"  → Severity sum: {severity_sum} | ML score (final_score): {ml_score:.4f} | risk_tier_ml: {ml.get('risk_tier_ml', '?')}")
        print(f"  → Priority: {priority}{'  (SANÇÃO no topo da fila)' if sanctions_fired else ''}")

        print("\n[3/5] Agente de INVESTIGAÇÃO — caso 360°...")
        typologies = [TYPOLOGY_MAP.get(r, r) for r in rules_fired]
        print(f"  → Risk level (regras): {ranking.get('tier', '?')} | Risk level (ML): {ml.get('risk_tier_ml', '?')}")
        print(f"  → Tipologias: {' · '.join(typologies)}")
        for a in alerts:
            print(f"    - [{a['rule_id']}] {a['rule_desc']}  (evid: {a['evidence_ids']})")

        print("\n[4/5] Agente de REPORTE — rascunho de SAR...")
        print(f"  → SAR draft gerado com 7 seções (baseado em {len(alerts)} regras + score ML)")

        print("\n[5/5] Agente de COMPLIANCE — validação regulatória...")
        decision = "approve" if (sanctions_fired or severity_sum >= 15) else "revise"
        action = "report_coaf" if decision == "approve" else "monitor"
        print(f"  → Sanções confirmadas: {sanctions_fired}")
        print(f"  → Decisão: {decision.upper()} | Ação recomendada: {action}")

        print("\n" + "=" * 60)
        print(f"[ORQUESTRADOR] DECISÃO: {decision.upper()}")
        print(f"  Ação recomendada : {action}")
        print(f"  Tipologias       : {', '.join(typologies)}")
        print(f"  Sanções          : {sanctions_fired}")
        print(f"  Nota             : divergência regra(alto/{ranking.get('tier')}) x ML({ml.get('risk_tier_ml')}) — trade-off precisão x cobertura")
        print("=" * 60)

    return {
        "case_id": case_id,
        "decision": "approve" if (sanctions_fired or severity_sum >= 15) else "revise",
        "recommended_action": "report_coaf" if (sanctions_fired or severity_sum >= 15) else "monitor",
        "typologies": [TYPOLOGY_MAP.get(r, r) for r in rules_fired],
        "sanctions_confirmed": sanctions_fired,
        "rules_tier": ranking.get("tier"),
        "ml_tier": ml.get("risk_tier_ml"),
        "mode": "SIMULADO — reconstruído de outputs agregados, sem chamadas à API",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simula o pipeline multi-agente para um caso, sem API")
    parser.add_argument("--case", required=True, help="entity_id do caso, ex.: C101919")
    args = parser.parse_args()
    import json
    resultado = simulate(args.case)
    print("\nResultado final:")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
