# CloudWalk AML-FT Case

**Detecção de lavagem de dinheiro e financiamento ao terrorismo (PIX, Cartão, Wire)**

> Projeto desenvolvido para o case AML-FT da CloudWalk, combinando **regras de alertas**, **machine learning** e **sistema multi-agente com LLM** para detecção, investigação e reporte de atividades suspeitas.

---

## 📋 Visão Geral

Este repositório implementa um **produto AML (Anti-Money Laundering) completo** que vai da detecção à recomendação de ação, integrando:

- **Tarefa 1:** Identificação de suspeitos + 1 SAR completo
- **Tarefa 2:** Sistema de alertas (≥15 regras)
- **Tarefa 3:** Modelo de Machine Learning para priorização de risco
- **Tarefa 4:** Pipeline multi-agente com LLM para orquestração

**Prazo:** 5 dias | **Escopo:** ≤30 clientes e/ou transações

---

## 🎯 Critérios de Avaliação

1. ✅ **Raciocínio investigativo, explicável e reprodutível**
2. ✅ **Qualidade técnica** — limpeza, coerência por rail, métricas reais
3. ✅ **Integração de múltiplos sinais** — KYC, transações, device, geo, MCC
4. ✅ **Orquestração ponta a ponta** — detecção → ação (congelar/monitorar/reportar)
5. ✅ **Clareza de comunicação** — relatório e apresentação acessíveis

---

## 📁 Estrutura do Projeto

```
cloudwalk-aml-ft/
├── README.md                  # Este arquivo
├── requirements.txt           # Dependências (versões fixas)
├── .gitignore                 # Arquivos ignorados no Git
├── config/
│   └── rules.yaml             # Limiares parametrizáveis das regras
├── data/
│   ├── raw/                   # Base original (gitignored)
│   └── processed/             # Feature store, alertas, scores
├── notebooks/
│   ├── 01_eda_qualidade.ipynb
│   ├── 02_regras_alertas.ipynb
│   ├── 03_suspeitos_sar.ipynb
│   └── 04_modelo_ml.ipynb
├── src/
│   ├── rules_engine.py        # Motor de regras
│   ├── features.py            # Feature store
│   ├── model.py               # Treino/avaliação ML
│   └── agents/                # Pipeline multi-agente
│       ├── pipeline.py
│       └── prompts/
├── outputs/
│   ├── alertas/               # Alertas gerados
│   ├── figuras/               # Gráficos para relatório e deck
│   └── sar/                   # SARs (Suspicious Activity Reports)
├── relatorio/                 # Relatório final (DOCX/PDF)
└── apresentacao/              # Deck (Google Slides)
```

---

## 🚀 Quick Start

### Pré-requisitos
- Python 3.9+
- Git
- Chave de API da Anthropic (para agentes LLM)

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/VictorOS1997/aml-case-cloudwalk.git
cd aml-case-cloudwalk

# 2. Criar ambiente virtual
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env e adicionar chave da Anthropic API
```

### Executar

```bash
# 1. Exploração de dados (Dia 1)
jupyter notebook notebooks/01_eda_qualidade.ipynb

# 2. Sistema de regras (Dia 2)
jupyter notebook notebooks/02_regras_alertas.ipynb

# 3. Suspeitos + SAR (Dia 3)
jupyter notebook notebooks/03_suspeitos_sar.ipynb

# 4. Modelo ML (Dia 4)
jupyter notebook notebooks/04_modelo_ml.ipynb

# 5. Multi-agente (Dia 5)
python src/agents/pipeline.py
```

---

## 📅 Plano de 5 Dias

| Dia | Tarefa | Entrega |
|-----|--------|---------|
| **1** | Fundação & Dados | Notebook 01 + dicionário de dados + schema map |
| **2** | Regras & Tipologias | Motor de regras + ≥15 regras + alertas (Sheets) |
| **3** | Suspeitos & SAR | Lista de suspeitos + 1 SAR completo + grafo/mapa |
| **4** | Machine Learning | Modelo de risco + métricas + SHAP + ranking (Sheets) |
| **5** | Multi-agente + Relatório | Pipeline de 5 agentes + relatório DOCX + deck Slides |

---

## 📚 Referências

- **Balizador mestre:** [SKILL.md](./SKILL.md) (seção 0 sobre como usar)
- **Arquitetura (3 camadas):** [ARQUITETURA.md](./ARQUITETURA.md)
- **Catálogo de 22 regras:** `referencias/catalogo-regras.md`
- **Template SAR:** `referencias/template-sar.md`
- **Sistema multi-agente:** `referencias/agentes-aml.md`
- **Esqueletos de código:** 
  - `scripts/rules_engine_skeleton.py` (Tarefa 2)
  - `scripts/aml_agents_skeleton.py` (Tarefa 4)

---

## 🔑 Tipologias AML Cobertas

| Tipologia | Sinal | Regras |
|-----------|-------|--------|
| **Structuring** | Valores abaixo de limiar | R03, R21 |
| **Bursts/Velocidade** | Muitas transações rápido | R01, R02, R20 |
| **Geo-salto** | Distância impossível | R05, R06 |
| **PEP/MCC alto risco** | Pessoa/categoria sensível | R16, R17 |
| **Device/IP ring** | Reuso entre clientes | R07, R08, R22 |
| **Self-merchant** | Cliente paga merchant próprio | R09 |
| **Cash-in → cash-out** | Entrada rápida = saída | R10, R11 |
| **E-commerce sem 3DS** | CNP sem autenticação forte | R12, R13 |
| **País/sanções** | Contraparte em lista | R14, R15 |
| **Renda incompatível** | Valor vs renda | R04 |
| **Chargeback** | Merchant com alta taxa | R18 |

---

## 📊 Reprodutibilidade

- ✅ **Seeds fixas:** `SEED = 42` em todos os módulos
- ✅ **Ambiente documentado:** `requirements.txt` com versões
- ✅ **Coerência por rail:** Validação PIX/Card/Wire no Notebook 01
- ✅ **Dados:** Descrição do schema em `data/README.md` (criar no Dia 1)

---

## 🔒 Segurança

- 🚫 Dados sensíveis (CSVs) no `.gitignore`
- 🔑 Credenciais em `.env` (nunca comitar)
- 📋 Apenas amostra de dados no repositório (se necessário)

---

## 📝 Entregáveis Finais

- **Relatório:** 5–10 páginas (DOCX/PDF)
  - Resumo executivo
  - Achados + SAR
  - Regras de alertas
  - Modelo ML + métricas
  - Arquitetura multi-agente

- **Apresentação:** Google Slides (~10 slides)
  - Objetivo & escopo
  - Raciocínio & método
  - Casos suspeitos
  - Sistema de alertas
  - Modelo ML + resultados
  - Multi-agente
  - Conclusões & melhorias

- **Repositório:** Código reprodutível, README claro, sementes fixas

---

## 📞 Dúvidas?

Consulte a **skill `cloudwalk-aml-case`** no Claude Code:
- Seção 3 → Specs dos entregáveis
- Seção 6 → MVP de cada etapa
- Seção 11 → FAQ
- Seção 8 → Tipologias AML

---

## 📄 Licença

MIT License — veja [LICENSE](./LICENSE)

---

**Status:** 🚀 Em desenvolvimento | **Última atualização:** 2026-06-20
