"""
pipeline.py — Pipeline multi-agente AML-FT (Tarefa 4 — CloudWalk Case)
======================================================================
5 agentes especializados + orquestrador, chamados em sequência via Anthropic API.
Cada agente é um PAPEL que o LLM assume via system prompt específico.

Fluxo: Dados → Detecção → Investigação → Reporte(SAR) → Compliance → decisão

Uso:
    python src/agents/pipeline.py [--case C101208]
    python src/agents/pipeline.py --demo   # case demo sem dados reais

Requer: ANTHROPIC_API_KEY no ambiente.
"""

from __future__ import annotations
import os
import json
import argparse
import pathlib
import datetime
from anthropic import Anthropic

SEED = 42
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048
OUT_DIR = pathlib.Path("outputs/sar")

client = Anthropic()


# ---------------------------------------------------------------------------
# Núcleo: chama o LLM com retry em falha de JSON
# ---------------------------------------------------------------------------
def call_agent(system: str, user_payload: dict, temperature: float = 0.1) -> dict:
    def _ask(extra: str = "") -> str:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=system + "\n\nResponda SOMENTE com JSON válido (sem texto fora do JSON, sem cercas markdown).",
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False) + extra,
                }
            ],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    raw = _ask()
    try:
        return json.loads(_strip(raw))
    except json.JSONDecodeError:
        raw = _ask("\n\nSua resposta anterior não era JSON válido. Reenvie SOMENTE o JSON corrigido, sem nenhum texto fora do JSON.")
        return json.loads(_strip(raw))


def _strip(text: str) -> str:
    return text.replace("```json", "").replace("```", "").strip()


# ---------------------------------------------------------------------------
# System prompts — um por agente
# ---------------------------------------------------------------------------
SYS_DADOS = """
Você é o Agente de Dados de um pipeline AML-FT. Recebe um caso com transações e cadastro KYC.

Sua função:
1. Validar esquema e coerência por rail (PIX/Cartão/Wire): parcelas/ECI só fazem sentido em Cartão;
   contraparte obrigatória em PIX e Wire; etc.
2. Sinalizar campos ausentes, tipos errados, valores impossíveis.
3. Enriquecer: calcular razão volume/renda, contar transações por rail, sinalizar países de risco
   (SY=Síria, BY=Bielorrússia, RU=Rússia, YE=Iêmen, IR=Irã, KP=Coreia do Norte).
4. Reportar resumo de qualidade com contagens e alertas de integridade.

NÃO julgue se há fraude — apenas prepare dados confiáveis.

Schema de saída:
{
  "quality_report": {
    "total_transactions": int,
    "rails": {"pix": int, "card": int, "wire": int},
    "issues": [{"field": str, "problem": str, "count": int}],
    "data_quality_score": str
  },
  "rail_coherence": {
    "pix": str, "card": str, "wire": str,
    "notes": [str]
  },
  "enriched_client": {
    "client_id": str,
    "volume_total": float,
    "volume_income_ratio": float,
    "n_cross_border": int,
    "high_risk_countries": [str],
    "sanctions_flag": bool,
    "rails_used": [str]
  }
}
"""

SYS_DETECCAO = """
Você é o Agente de Detecção AML. Avalia as regras acionadas e o score de ML para gerar uma
fila priorizada de alertas.

Regras disponíveis (com severidade):
- R04_income_mismatch (sev 3): volume >= 5x renda anual
- R05_geojump (sev 3): geo-salto com velocidade > 900 km/h entre tx consecutivas
- R10_cash_in_out (sev 3): saída >= 80% entrada em 24h via PIX
- R12_ecom_no_3ds (sev 3): card-not-present sem 3DS em valor alto
- R13_eci_cross_border (sev 3): cross-border + ECI não-autenticado
- R15_sanctions (sev 4): sanctions_screening_hit=Yes
- R17_high_risk_mcc (sev 2): MCC em {6011, 7995, 6051, 4789}

Para cada alerta:
- Liste as regras disparadas e por quê (citando evidências)
- Some a severidade
- Calcule prioridade = severity_sum * (1 + ml_score)
- Alertas de sanção sempre no topo da fila

Schema de saída:
{
  "alerts": [
    {
      "entity_id": str,
      "entity_type": "client",
      "rules_fired": [str],
      "severity_sum": int,
      "ml_score": float,
      "priority": float,
      "evidence_ids": [str],
      "rule_explanations": {"rule_id": str}
    }
  ],
  "queue_order": [str],
  "top_alert_summary": str
}
"""

SYS_INVESTIGACAO = """
Você é o Agente de Investigação AML. Recebe um alerta priorizado e os dados completos do caso.
Monte uma análise 360° do cliente suspeito.

Sua entrega:
1. Timeline cronológica das transações mais relevantes (data, valor, rail, receptor, sinais)
2. Rede de conexões identificada (clientes, devices, IPs, merchants, países)
3. Tipologias prováveis com raciocínio passo a passo e evidências citadas por ID
4. O que falta para confirmar / gaps na investigação

Seja factual, investigativo, sem exageros. Cite IDs de transação sempre.

Schema de saída:
{
  "case_id": str,
  "entity_id": str,
  "risk_level": str,
  "typologies": [str],
  "timeline_highlights": [
    {"ts": str, "tx_id": str, "amount": float, "rail": str, "counterparty": str, "signals": [str]}
  ],
  "network_summary": {
    "unique_devices": int, "unique_ips": int, "unique_merchants": int,
    "high_risk_countries": [str], "sanctions_transactions": [str]
  },
  "reasoning": str,
  "key_evidence": [str],
  "gaps": [str]
}
"""

SYS_REPORTE = """
Você é o Agente de Reporte (SAR). Gera o rascunho de Suspicious Activity Report em 7 seções,
baseado EXCLUSIVAMENTE nos fatos do caso investigado. Não invente dados.

Seções obrigatórias:
1. Identificação do Caso (cliente, período, rails, score)
2. Resumo Executivo (1-2 parágrafos: o que aconteceu, por que é suspeito, risco e recomendação)
3. Sinais/Alertas Acionados (tabela: regra, tipologia, severidade, evidências)
4. Análise Detalhada (timeline, valores-chave, geo-saltos, padrões)
5. Base Legal (FATF, Lei 9.613/98, Circular BACEN 3.978/2020, COAF/SISCOAF)
6. Conclusão e Ações Recomendadas (D+0, D+1, D+3)
7. Anexos (IDs de evidência)

Linguagem: clara, objetiva, defensável perante regulador. Português brasileiro.

Schema de saída:
{
  "sar_markdown": str,
  "sar_json": {
    "case_id": str,
    "client_id": str,
    "period": str,
    "summary": str,
    "typologies": [str],
    "alerts": [{"rule": str, "severity": int, "evidence": [str]}],
    "legal_basis": [str],
    "recommended_action": str,
    "risk_level": str
  }
}
"""

SYS_COMPLIANCE = """
Você é o Agente de Compliance. Valida o rascunho de SAR antes de qualquer ação regulatória.

Sua validação:
1. Consistência factual: todos os fatos no SAR estão suportados pelas evidências fornecidas?
2. Completude das 7 seções: alguma seção está vazia ou insuficiente?
3. Checagem de sanções: há transações com sanctions_hit? País de risco nas contrapartes?
4. Aderência regulatória:
   - Lei 9.613/1998 (lavagem) / Lei 13.260/2016 (terrorismo) / Lei 13.810/2019 (sanções ONU)
   - Circular BACEN 3.978/2020 (RBA, KYC, comunicação)
   - COAF/SISCOAF (prazo de comunicação: até 24h após decisão de reporte)
   - FATF 40 Recomendações (Rec. 10 KYC, Rec. 20 reporte)
5. Proporcionalidade da ação: a ação recomendada é proporcional ao risco identificado?

Decida: "approve" (pronto para fila de reporte) ou "revise" (com motivos acionáveis).

Schema de saída:
{
  "decision": "approve",
  "reasons": [str],
  "sanctions_confirmed": bool,
  "regulatory_refs": [str],
  "recommended_action": str,
  "action_timeline": {"D0": str, "D1": str, "D3": str},
  "audit_trail": {
    "agent": "compliance",
    "timestamp": str,
    "case_id": str,
    "model": str
  },
  "sla": str,
  "compliance_notes": str
}
"""


# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------
def orchestrate(case_input: dict, verbose: bool = True) -> dict:
    case_id = case_input.get("case_id", "case_001")
    run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / case_id
    out_path.mkdir(parents=True, exist_ok=True)

    log = []

    def save(stage: str, obj: dict):
        fp = out_path / f"{stage}.json"
        fp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            print(f"  [{stage}] salvo em {fp}")

    def log_step(stage: str, result: dict):
        log.append({"stage": stage, "timestamp": datetime.datetime.now().isoformat(), "keys": list(result.keys())})

    if verbose:
        print(f"\n{'='*60}")
        print(f"[ORQUESTRADOR] Caso: {case_id} | Run: {run_ts}")
        print(f"{'='*60}")

    # Estágio 1 — Dados
    if verbose:
        print("\n[1/5] Agente de DADOS — validação e enriquecimento...")
    dados = call_agent(SYS_DADOS, case_input, temperature=0.0)
    save("01_dados", dados)
    log_step("dados", dados)

    # Estágio 2 — Detecção
    if verbose:
        print("[2/5] Agente de DETECÇÃO — avaliação de regras + score ML...")
    deteccao_input = {
        "case": case_input,
        "enriched_data": dados,
        "ml_score": case_input.get("ml_score", 0.0),
    }
    deteccao = call_agent(SYS_DETECCAO, deteccao_input, temperature=0.0)
    save("02_deteccao", deteccao)
    log_step("deteccao", deteccao)

    # Estágio 3 — Investigação
    if verbose:
        print("[3/5] Agente de INVESTIGAÇÃO — caso 360°, tipologias, evidências...")
    invest_input = {
        "alert": deteccao.get("alerts", [{}])[0] if deteccao.get("alerts") else {},
        "case": case_input,
        "enriched_data": dados,
    }
    invest = call_agent(SYS_INVESTIGACAO, invest_input, temperature=0.2)
    save("03_investigacao", invest)
    log_step("investigacao", invest)

    # Estágio 4 — Reporte (SAR)
    if verbose:
        print("[4/5] Agente de REPORTE — rascunho de SAR...")
    reporte = call_agent(SYS_REPORTE, {"case": invest, "alerts": deteccao.get("alerts", [])}, temperature=0.4)
    save("04_reporte", reporte)
    log_step("reporte", reporte)

    sar_md = reporte.get("sar_markdown", "")
    sar_path = out_path / "sar_agente.md"
    sar_path.write_text(sar_md, encoding="utf-8")
    if verbose:
        print(f"  [04_reporte] SAR markdown → {sar_path}")

    # Estágio 5 — Compliance
    if verbose:
        print("[5/5] Agente de COMPLIANCE — validação regulatória...")
    compliance_input = {
        "sar": reporte,
        "case_id": case_id,
        "sanctions_flag": case_input.get("sanctions_flag", False),
    }
    compliance = call_agent(SYS_COMPLIANCE, compliance_input, temperature=0.0)
    compliance["audit_trail"]["timestamp"] = datetime.datetime.now().isoformat()
    compliance["audit_trail"]["model"] = MODEL
    save("05_compliance", compliance)
    log_step("compliance", compliance)

    # Auditoria geral
    audit = {
        "case_id": case_id,
        "run_timestamp": run_ts,
        "decision": compliance.get("decision"),
        "recommended_action": compliance.get("recommended_action"),
        "typologies": invest.get("typologies", []),
        "sanctions_confirmed": compliance.get("sanctions_confirmed", False),
        "stages_log": log,
        "artifacts_dir": str(out_path),
    }
    save("00_auditoria", audit)

    decision = compliance.get("decision", "revise")
    action = compliance.get("recommended_action", "—")

    if verbose:
        print(f"\n{'='*60}")
        print(f"[ORQUESTRADOR] DECISÃO: {decision.upper()}")
        print(f"  Ação recomendada : {action}")
        print(f"  Tipologias       : {', '.join(invest.get('typologies', []))}")
        print(f"  Sanções          : {compliance.get('sanctions_confirmed', False)}")
        if decision == "revise":
            print(f"  Motivos          : {compliance.get('reasons', [])}")
        print(f"  Artefatos em     : {out_path}")
        print(f"{'='*60}\n")

    return audit


# ---------------------------------------------------------------------------
# Caso real C101208 (Dia 3 — SAR)
# ---------------------------------------------------------------------------
CASE_C101208 = {
    "case_id": "C101208",
    "client": {
        "client_id": "C101208",
        "name_alias": "Customer 1209",
        "occupation": "Chef",
        "monthly_income": 1087.25,
        "annual_income": 13047.0,
        "pep_flag": False,
        "kyc_tier": "L1",
        "kyc_score": 51,
        "onboarding_date": "2023-02-17",
        "account_age_days": 868,
        "country": "BR",
    },
    "period": "2025-07-03 to 2025-09-29",
    "ml_score": 0.7973,
    "sanctions_flag": True,
    "rules_fired": [
        "R04_income_mismatch",
        "R05_geojump",
        "R10_cash_in_out",
        "R12_ecom_no_3ds",
        "R13_eci_cross_border",
        "R15_sanctions",
        "R17_high_risk_mcc",
    ],
    "rules_score": 22,
    "transactions": [
        {"tx_id": "T4DEL3OGZ9T5U", "ts": "2025-07-03T17:46", "rail": "pix", "amount": 3443.62, "direction": "cash_out", "counterparty": "C100961", "mcc": "5732", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TRLSHBGRSQGA1", "ts": "2025-07-03T19:35", "rail": "pix", "amount": 2828.01, "direction": "cash_out", "counterparty": "M200059", "mcc": "6051", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TKDIFNLZF949G", "ts": "2025-07-09T09:23", "rail": "card", "amount": 4116.51, "direction": "debit", "counterparty": "M200140", "mcc": "5945", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": False, "sanctions_hit": False},
        {"tx_id": "T5X9879GFHB16", "ts": "2025-07-21T07:25", "rail": "card", "amount": 830.85, "direction": "debit", "counterparty": "M200251", "mcc": "6011", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": False, "sanctions_hit": False},
        {"tx_id": "T2Y9XYZ98FADL", "ts": "2025-07-22T03:28", "rail": "pix", "amount": 1241.06, "direction": "cash_out", "counterparty": "M200526", "mcc": "5999", "country_geo": "PT", "country_ip": "BR", "cross_border": True, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TJZRYWR88WZHJ", "ts": "2025-07-24T11:50", "rail": "pix", "amount": 34398.52, "direction": "cash_out", "counterparty": "C100171", "mcc": "4814", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TVC0AUP1WJ7DN", "ts": "2025-08-02T03:25", "rail": "card", "amount": 3017.79, "direction": "debit", "counterparty": "M200103", "mcc": "5945", "country_geo": "BY", "country_ip": "BR", "cross_border": True, "three_ds": False, "sanctions_hit": False},
        {"tx_id": "TQ0HI60JXN1ZX", "ts": "2025-08-21T18:33", "rail": "card", "amount": 6500.50, "direction": "debit", "counterparty": "M200127", "mcc": "6011", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": False, "sanctions_hit": False},
        {"tx_id": "TNHZDN7D6LYK6", "ts": "2025-08-12T03:37", "rail": "wire", "amount": 2166.18, "direction": "cash_out", "counterparty": "M200815", "mcc": "5999", "country_geo": "SY", "country_ip": "BR", "cross_border": True, "three_ds": None, "sanctions_hit": True},
        {"tx_id": "TA71FJSV7IE3Z", "ts": "2025-08-26T07:12", "rail": "pix", "amount": 3399.10, "direction": "cash_out", "counterparty": "M200339", "mcc": "4789", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TQSBX6QW4LBWX", "ts": "2025-08-29T20:54", "rail": "card", "amount": 1089.07, "direction": "debit", "counterparty": "M200972", "mcc": "5411", "country_geo": "RU", "country_ip": "BR", "cross_border": True, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "T1FPTRX21C46J", "ts": "2025-08-30T21:56", "rail": "card", "amount": 7890.69, "direction": "debit", "counterparty": "M200010", "mcc": "4900", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TOHDJ4A6OYGZA", "ts": "2025-09-08T23:47", "rail": "card", "amount": 6889.49, "direction": "debit", "counterparty": "M200212", "mcc": "7995", "country_geo": "YE", "country_ip": "BR", "cross_border": True, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TIQS2U9KT1J0U", "ts": "2025-09-23T10:09", "rail": "card", "amount": 14011.86, "direction": "debit", "counterparty": "M200637", "mcc": "7995", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "TF9EJQVFQTQJM", "ts": "2025-09-23T23:17", "rail": "pix", "amount": 7718.63, "direction": "cash_out", "counterparty": "M200331", "mcc": "6011", "country_geo": "RU", "country_ip": "BR", "cross_border": True, "three_ds": None, "sanctions_hit": False},
    ],
    "geo_jumps": [
        {"from_tx": "TIQS2U9KT1J0U", "to_tx": "TF9EJQVFQTQJM", "distance_km": 14341.6, "speed_kmh": 1092.0, "from_country": "BR", "to_country": "RU"},
        {"from_tx": "TQSBX6QW4LBWX", "to_tx": "T1FPTRX21C46J", "distance_km": 15907.1, "speed_kmh": 635.4, "from_country": "RU", "to_country": "BR"},
        {"from_tx": "TR1K3PDMT9A1T", "to_tx": "TNHZDN7D6LYK6", "distance_km": 12052.6, "speed_kmh": 225.3, "from_country": "BR", "to_country": "SY"},
    ],
    "volume_summary": {
        "total_volume_brl": 150178.09,
        "volume_income_ratio": 11.5,
        "n_transactions": 29,
        "n_cross_border": 9,
        "n_no_3ds": 5,
        "n_sanctions_hit": 1,
        "n_countries": 8,
        "n_unique_devices": 29,
        "n_unique_ips": 29,
        "rails": {"pix": 15, "card": 12, "wire": 2},
    },
}

# ---------------------------------------------------------------------------
# Caso demo
# ---------------------------------------------------------------------------
CASE_DEMO = {
    "case_id": "case_demo_001",
    "client": {
        "client_id": "C999",
        "occupation": "Estudante",
        "monthly_income": 1500,
        "annual_income": 18000,
        "pep_flag": False,
        "kyc_tier": "L1",
        "country": "BR",
    },
    "ml_score": 0.82,
    "sanctions_flag": False,
    "rules_fired": ["R03_structuring", "R07_device_ring", "R10_cash_in_out"],
    "transactions": [
        {"tx_id": "T1", "ts": "2025-03-01T10:00", "rail": "pix", "amount": 9800, "direction": "cash_in", "counterparty": "X1", "mcc": "5999", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "T2", "ts": "2025-03-01T10:20", "rail": "pix", "amount": 9750, "direction": "cash_in", "counterparty": "X2", "mcc": "5999", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
        {"tx_id": "T3", "ts": "2025-03-01T13:00", "rail": "pix", "amount": 19000, "direction": "cash_out", "counterparty": "X3", "mcc": "5999", "country_geo": "BR", "country_ip": "BR", "cross_border": False, "three_ds": None, "sanctions_hit": False},
    ],
    "volume_summary": {"total_volume_brl": 38550, "volume_income_ratio": 2.14, "n_transactions": 3},
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline multi-agente AML-FT")
    parser.add_argument("--case", default="C101208", help="Case ID: C101208 | demo")
    parser.add_argument("--demo", action="store_true", help="Roda o caso demo")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Defina ANTHROPIC_API_KEY no ambiente antes de rodar.\n"
            "  Windows PowerShell: $env:ANTHROPIC_API_KEY='sk-ant-...'"
        )

    case = CASE_DEMO if args.demo else CASE_C101208
    result = orchestrate(case, verbose=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
