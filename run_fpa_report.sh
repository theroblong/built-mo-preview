#!/usr/bin/env bash
# run_fpa_report.sh — Full FP&A report pipeline
#
# !! IMPORTANT: Do NOT run this script without explicit authorization from
# !! an authorized person (Jason, Rob, or Brian). It writes Druid-ingested
# !! parquet files, patches HTML, and modifies docs/ outputs.
#
# Usage:
#   ./run_fpa_report.sh <version>                    # full run
#   ./run_fpa_report.sh <version> --skip-training    # HTML assembly only
#
# Produces:  docs/built_demand_intelligence_report_v<version>.html
#
# ─── PIPELINE MANIFEST ────────────────────────────────────────────────────────
# When adding, removing, or renaming an MO script, update the arrays below.
# The script validates that every declared .py file exists before running.
# Also update memory/project_report_refresh_pipeline.md + wiki/08-roadmap.md.
#
# Phase 1 — sequential (actuals → train → forecast → Druid ingest):
#   MO_25 → MO_26 → MO_27
#
# Phase 2 — independent (rolling metrics):
#   MO_32B
#
# Phase 3 — independent (analysis charts, all read actuals parquet):
#   MO_33, MO_34, MO_35, MO_37
#
# Phase 4 — independent (explainability + event data; MO_40 needs MO_38 first):
#   MO_38 → MO_40  |  MO_43, MO_44, MO_47
#
# Phase 5 — HTML assembly + patch chain (strict order):
#   MO_36 (base) → MO_40 (§14) → MO_41 (§15) → MO_42 (§16)
#                → MO_43 (§17a) → MO_45 (§18) → MO_44 (§17b DAG)
#                → MO_50 (§19) → MO_51 (§20) → MO_52 (§21) → MO_53 (§22) → MO_54 (§23)
#                → MO_56 (§24) → MO_57 (§25) → MO_58 (§26) → MO_49 (§27)
#                → MO_59 (§28) → MO_60 (§29) → MO_61 (§30) → MO_62 (§31)
#
# Final — version-stamp + copy to docs/
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Error: version argument required. Example: ./run_fpa_report.sh 2.1.3"
  exit 1
fi

SKIP_TRAINING=false
if [[ "${2:-}" == "--skip-training" ]]; then
  SKIP_TRAINING=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$SCRIPT_DIR/scripts"
DOCS="$SCRIPT_DIR/docs"
INTERMEDIATE="$SCRIPTS/outputs/built_demand_intelligence_report.html"
DEST="$DOCS/built_demand_intelligence_report_v${VERSION}.html"

# ─── SCRIPT REGISTRY ─────────────────────────────────────────────────────────
# Canonical list of every script this pipeline calls. Update here first.

DATA_PHASE1=(
  MO_25_retailer_sales_actuals
  MO_26_retailer_sales_train
  MO_27_retailer_sales_forecast
  MO_55_portfolio_constraint       # post-forecast: zero-sum BUILT portfolio adjustment
)
DATA_PHASE2=(
  MO_32B_quarterly_rollforward
)
DATA_PHASE3=(
  MO_33_fpa_business_charts
  MO_34_ensemble_trigger
  MO_35_forward_projection
  MO_37_sku_stories
)
DATA_PHASE4=(
  MO_38_model_benchmark
  MO_40_explainability
  MO_43_causal_impact
  MO_44_dag_analysis
  MO_47_event_validation
)
HTML_CHAIN=(
  MO_36_report                    # base HTML
  MO_40_explainability            # §14 SHAP
  MO_41_feature_diagnostic        # §15
  MO_42_quantile_forecast         # §16
  MO_43_causal_impact             # §17a
  MO_45_gru_benchmark             # §18
  MO_44_dag_analysis              # §17b DAG / elasticity
  MO_50_rolling_signal_ablation   # §19 rolling vs. static Mo
  MO_51_regularization_search     # §20 reg search + SHAP pruning + rolling CV
  MO_52_feature_ablation          # §21 MO_25 v4 feature group ablation
  MO_53_individual_feature_ablation  # §22 brand-split donors + TDP change + promo v2
  MO_54_holiday_ablation             # §23 holiday binary flags vs integer code
  MO_56_time_varying_ablation        # §24 time-varying cannibal_rate + elasticity effect
  MO_57_fourier_lag_ablation         # §25 Fourier week encoding + lag2/3 + price bins
  MO_58_base_promo_validation        # §26 base/promo/total coherence audit
  MO_49_promo_gap_chart              # §27 base vs. total units promo gap chart (actuals + forecast)
  MO_59_stl_changepoints             # §28 STL decomposition + PELT changepoint detection
  MO_60_synthetic_control            # §29 synthetic control + DiD causal sensitivity analysis
  MO_61_hte_elasticity               # §30 heterogeneous treatment effects (EconML LinearDML)
  MO_62_foundation_benchmark         # §31 foundation model zero-shot benchmark (Chronos/TimesFM/Moirai/TTM)
)

# ─── VALIDATION ──────────────────────────────────────────────────────────────
echo "Validating pipeline scripts …"
ALL_SCRIPTS=("${DATA_PHASE1[@]}" "${DATA_PHASE2[@]}" "${DATA_PHASE3[@]}" "${DATA_PHASE4[@]}" "${HTML_CHAIN[@]}")
MISSING=()
for s in "${ALL_SCRIPTS[@]}"; do
  [[ -f "$SCRIPTS/${s}.py" ]] || MISSING+=("${s}.py")
done
# Deduplicate (scripts appear in both DATA and HTML arrays)
if [[ ${#MISSING[@]} -gt 0 ]]; then
  MISSING=($(printf '%s\n' "${MISSING[@]}" | sort -u))
fi
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "Error: missing scripts — update run_fpa_report.sh registry:"
  printf '  %s\n' "${MISSING[@]}"
  exit 1
fi
echo "  All scripts present."

cd "$SCRIPTS"

log() { echo; echo "━━━━━  $*  ━━━━━"; }

if [[ "$SKIP_TRAINING" == "false" ]]; then
  log "Phase 1: Actuals → Train → Forecast"
  for s in "${DATA_PHASE1[@]}"; do python "${s}.py"; done

  log "Phase 2: Rolling metrics"
  for s in "${DATA_PHASE2[@]}"; do python "${s}.py"; done

  log "Phase 3: Analysis charts"
  for s in "${DATA_PHASE3[@]}"; do python "${s}.py"; done

  log "Phase 4: Explainability + event data"
  python MO_38_model_benchmark.py
  python MO_40_explainability.py        # needs MO_38 CSV
  python MO_43_causal_impact.py
  python MO_44_dag_analysis.py
  python MO_47_event_validation.py
fi

# ── Phase 5: HTML assembly + patch chain ─────────────────────────────────────
log "Phase 5: HTML assembly + patch chain"
for s in "${HTML_CHAIN[@]}"; do
  echo "  → ${s}.py"
  python "${s}.py"
done

# ── Final: version-stamp + copy to docs/ ─────────────────────────────────────
log "Versioning → v${VERSION}"
if [[ ! -f "$INTERMEDIATE" ]]; then
  echo "Error: intermediate HTML not found at $INTERMEDIATE"
  exit 1
fi

python - <<PYEOF
import re, shutil, os

src  = "$INTERMEDIATE"
dest = "$DEST"
ver  = "$VERSION"

with open(src, "r", encoding="utf-8") as f:
    html = f.read()

html = re.sub(r'v\d+\.\d+\.\d+', f'v{ver}', html)
html = re.sub(r'Version \d+\.\d+\.\d+', f'Version {ver}', html)

with open(dest, "w", encoding="utf-8") as f:
    f.write(html)

size_mb = os.path.getsize(dest) / 1_048_576
print(f"  → {dest}  ({size_mb:.1f} MB)")
PYEOF

echo
echo "━━━━━  DONE  ━━━━━"
echo "Report: $DEST"
echo
echo "If MO_27 ran: re-ingest Druid with appendToExisting:false."
