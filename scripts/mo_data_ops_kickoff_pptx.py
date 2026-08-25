"""
Generate Mo Data Operations Kickoff presentation (.pptx)
Output: mockups/mo_data_ops_kickoff.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import os

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY        = RGBColor(0x1B, 0x35, 0x66)
NAVY_DEEP   = RGBColor(0x0C, 0x1A, 0x38)
BLUE        = RGBColor(0x40, 0x78, 0xD0)
BLUE_LIGHT  = RGBColor(0xA0, 0xC0, 0xF0)
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
OFF_WHITE   = RGBColor(0xF0, 0xF4, 0xFA)
LIGHT_BLUE  = RGBColor(0xD8, 0xE5, 0xFF)
MID_GREY    = RGBColor(0x6B, 0x7F, 0xA0)
DARK_TEXT   = RGBColor(0x11, 0x18, 0x27)
GREEN       = RGBColor(0x0E, 0x5E, 0x38)
GREEN_LIGHT = RGBColor(0xD4, 0xF0, 0xE4)
AMBER       = RGBColor(0x8A, 0x48, 0x00)
AMBER_LIGHT = RGBColor(0xFF, 0xF3, 0xD6)
PURPLE      = RGBColor(0x4B, 0x2D, 0x8A)
PURPLE_LIGHT= RGBColor(0xEC, 0xE8, 0xF8)
RED         = RGBColor(0x8B, 0x1A, 0x1A)
RED_LIGHT   = RGBColor(0xFE, 0xF0, 0xF0)

# ── Slide dimensions (widescreen 16:9) ───────────────────────────────────────
W = Inches(13.333)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

BLANK = prs.slide_layouts[6]


# ── Helpers ───────────────────────────────────────────────────────────────────
def tb(slide, left, top, width, height, text, size=12, bold=False, color=DARK_TEXT,
       align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    txBox.word_wrap = wrap
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return txBox


def tb_lines(slide, left, top, width, height, lines, default_size=11,
             default_color=DARK_TEXT, default_bold=False):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    txBox.word_wrap = True
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for item in lines:
        if isinstance(item, str):
            text, size, bold, color, indent = item, default_size, default_bold, default_color, False
        else:
            text  = item[0]
            size  = item[1] if len(item) > 1 else default_size
            bold  = item[2] if len(item) > 2 else default_bold
            color = item[3] if len(item) > 3 else default_color
            indent= item[4] if len(item) > 4 else False
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        if indent:
            p.level = 1
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "Calibri"
    return txBox


def rect(slide, left, top, width, height, fill=NAVY, line=None, line_color=None):
    shape = slide.shapes.add_shape(
        1,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.width = Pt(line)
        if line_color:
            shape.line.color.rgb = line_color
    return shape


def footnote(slide):
    tb(slide, 0.5, 7.2, 12.5, 0.25,
       "Mo by Aevah  ·  BUILT Kickoff  ·  August 2026  ·  Confidential",
       size=8, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=NAVY_DEEP)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

tb(slide, 0.5, 0.8, 10, 0.4,
   "MO BY AEVAH  ·  BUILT KICKOFF  ·  AUGUST 2026",
   size=9, color=BLUE_LIGHT, bold=True)

tb(slide, 0.5, 1.35, 10, 1.8,
   "How Mo Works\nWith Your Data",
   size=42, bold=True, color=WHITE)

tb(slide, 0.5, 3.35, 8.5, 1.2,
   "A walkthrough of the process behind each Mo intelligence module — "
   "what data it needs, where that data comes from, what operations are performed, "
   "and what appears on screen.",
   size=14, color=BLUE_LIGHT)

rect(slide, 0.5, 4.75, 6, 0.03, fill=BLUE)

modules = [
    "Cannibalization Risk",
    "Price Elasticity",
    "Promotional Response",
    "Demand Forecast",
    "Launch Monitoring",
]
col_w = 2.3
for i, mod in enumerate(modules):
    x = 0.5 + i * col_w
    rect(slide, x, 5.1, col_w - 0.12, 0.5, fill=RGBColor(0x20, 0x40, 0x70))
    tb(slide, x + 0.1, 5.15, col_w - 0.22, 0.4,
       mod, size=10, bold=True, color=BLUE_LIGHT, align=PP_ALIGN.CENTER)

tb(slide, 9.0, 6.8, 4, 0.4,
   "aevah.ai  ·  Confidential",
   size=9, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — PIPELINE OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=OFF_WHITE)
rect(slide, 0, 0, 13.333, 1.1, fill=NAVY)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

tb(slide, 0.5, 0.22, 10, 0.6,
   "The End-to-End Process",
   size=24, bold=True, color=WHITE)

tb(slide, 0.5, 1.2, 12.5, 0.4,
   "Five stages from your SPINS export to decisions on screen — Aevah automates stages 2–4 so no manual steps are required once data is deposited.",
   size=11.5, color=MID_GREY)

steps = [
    ("Stage 1", "SPINS Export", "BUILT Data Team",
     "214-column weekly POS extract deposited to shared MinIO storage"),
    ("Stage 2", "Data Ingest", "Aevah — automated",
     "File-watch trigger detects new export; quality gates applied; incremental load only"),
    ("Stage 3", "Feature\nEngineering", "Aevah — automated",
     "Q-series SQL chains compress raw rows into ML-ready feature tables per module"),
    ("Stage 4", "Model Training\n& Scoring", "Aevah — automated",
     "Models retrain on drift/schedule; scores written to Druid; smoke-test gates at each stage"),
    ("Stage 5", "Mo UI", "BUILT Team",
     "Two data layers: ML projections (forecast) + live context data (actuals at render time)"),
]

step_w = 2.2
box_h  = 2.85
for i, (num, name, who, desc) in enumerate(steps):
    x = 0.4 + i * (step_w + 0.2)
    y = 1.88

    rect(slide, x, y, step_w, box_h, fill=NAVY)
    tb(slide, x + 0.12, y + 0.1, step_w - 0.24, 0.28,
       num.upper(), size=8, bold=True, color=BLUE_LIGHT)
    tb(slide, x + 0.12, y + 0.38, step_w - 0.24, 0.55,
       name, size=13, bold=True, color=WHITE)
    tb(slide, x + 0.12, y + 0.92, step_w - 0.24, 0.3,
       who, size=8.5, color=BLUE_LIGHT, bold=True)
    tb(slide, x + 0.12, y + 1.25, step_w - 0.24, 1.4,
       desc, size=9, color=RGBColor(0xB0, 0xC8, 0xF0))

    if i < len(steps) - 1:
        ax = x + step_w + 0.02
        tb(slide, ax, y + 1.2, 0.2, 0.35, "→", size=18, bold=True,
           color=BLUE, align=PP_ALIGN.CENTER)

rect(slide, 0.4, 5.1, 12.5, 1.15, fill=LIGHT_BLUE)
tb(slide, 0.6, 5.17, 12, 0.28, "KEY PRINCIPLE", size=8, bold=True, color=BLUE)
tb(slide, 0.6, 5.45, 12, 0.7,
   "Every Mo screen draws from two distinct sources: ML scoring tables (what the model forecasts, written in Stage 4) "
   "and live Druid queries (actual component data queried at render time). "
   "These have separate lineage and must never be blended. See: mo_decisions_register — COV-04.",
   size=10.5, color=DARK_TEXT)

footnote(slide)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — REFERENCE DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=OFF_WHITE)
rect(slide, 0, 0, 13.333, 1.1, fill=NAVY)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

tb(slide, 0.5, 0.22, 10, 0.6,
   "Reference Documents", size=24, bold=True, color=WHITE)
tb(slide, 0.5, 0.72, 12, 0.32,
   "Four living artifacts — updated as the project evolves. Open any time for the current state of the pipeline, decisions, and automation design.",
   size=11, color=BLUE_LIGHT)

docs = [
    (NAVY,   WHITE,      BLUE_LIGHT,
     "Customer-Facing Overview",
     "mo_data_ops_customer.html",
     "Module-by-module walkthrough for the BUILT team — what data each simulation needs, what operations are performed, and what Mo displays. No implementation detail.",
     [("Audience", "Brian, Connor"),
      ("Format",   "HTML artifact"),
      ("Covers",   "All 5 modules")]),
    (GREEN,  WHITE,      GREEN_LIGHT,
     "Technical Pipeline Reference",
     "mo_data_ops_kickoff.html",
     "Full Q-series and P-series pipeline stages with input/output tables. Source of truth for data lineage, script IDs, and Druid table names.",
     [("Audience", "Rob, Jason"),
      ("Format",   "HTML artifact"),
      ("Covers",   "Q0–Q22, P1–P12")]),
    (BLUE,   WHITE,      LIGHT_BLUE,
     "Pipeline Automation Design",
     "mo_automation_design.html",
     "5-stage automation architecture: trigger layer, per-stage smoke-test gates, rollback guarantee, Druid optimization options, and implementation roadmap (P1–P5).",
     [("Audience", "Rob, Jason"),
      ("Format",   "HTML artifact"),
      ("Covers",   "5-stage, gates, Druid")]),
    (PURPLE, WHITE,      PURPLE_LIGHT,
     "Decisions & Caveats Register",
     "mo_decisions_register.html",
     "48-entry living register: null handling, normalization rules, MULO exclusion, known data anomalies, model guardrails, key formulas, and open items. Updated every session.",
     [("Audience", "Rob, Jason"),
      ("Format",   "HTML artifact — living"),
      ("Covers",   "NUL/NRM/GEO/ANO/GRD/COV/FML/OPN")]),
]

card_w = 3.0
card_h = 5.4
card_y = 1.3

for i, (hdr_color, hdr_text, body_text, title, filename, desc, meta) in enumerate(docs):
    x = 0.42 + i * (card_w + 0.16)

    # Card background
    rect(slide, x, card_y, card_w, card_h, fill=WHITE,
         line=0.75, line_color=RGBColor(0xC0, 0xCC, 0xE4))

    # Header band
    rect(slide, x, card_y, card_w, 0.55, fill=hdr_color)
    tb(slide, x + 0.12, card_y + 0.1, card_w - 0.24, 0.38,
       title, size=11.5, bold=True, color=WHITE)

    # Filename chip
    rect(slide, x + 0.12, card_y + 0.65, card_w - 0.24, 0.28,
         fill=RGBColor(0xEE, 0xF2, 0xFA))
    tb(slide, x + 0.18, card_y + 0.69, card_w - 0.36, 0.22,
       filename, size=8, bold=True, color=NAVY)

    # Description
    tb(slide, x + 0.12, card_y + 1.06, card_w - 0.24, 1.6,
       desc, size=9.5, color=RGBColor(0x3A, 0x4B, 0x6B))

    # Meta rows
    my = card_y + 2.75
    for label, val in meta:
        tb(slide, x + 0.12, my, 0.9, 0.28,
           label + ":", size=8, bold=True, color=MID_GREY)
        tb(slide, x + 1.0, my, card_w - 1.1, 0.28,
           val, size=8, color=DARK_TEXT)
        my += 0.32

    # "All in mockups/" tag at bottom of card
    tb(slide, x + 0.12, card_y + card_h - 0.32, card_w - 0.24, 0.26,
       "mockups/  ·  FirstAgent repo", size=7.5, color=MID_GREY, italic=True)

footnote(slide)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE TEMPLATE FUNCTION — simulation modules
# ═══════════════════════════════════════════════════════════════════════════════
def add_sim_slide(num_label, name, answer, inputs, operations, ml_outputs, live_outputs):
    slide = prs.slides.add_slide(BLANK)
    rect(slide, 0, 0, 13.333, 7.5, fill=OFF_WHITE)
    rect(slide, 0, 0, 13.333, 1.4, fill=NAVY)
    rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

    tb(slide, 0.5, 0.1, 2, 0.3, num_label, size=9, bold=True, color=BLUE_LIGHT)
    tb(slide, 0.5, 0.38, 7, 0.6, name, size=22, bold=True, color=WHITE)
    tb(slide, 7.8, 0.38, 5.3, 0.8, f'"{answer}"',
       size=11, color=RGBColor(0xC0, 0xD5, 0xFF), italic=True)

    left_x = 0.45
    left_w = 5.0
    y = 1.55

    rect(slide, left_x, y, left_w, 0.28, fill=NAVY)
    tb(slide, left_x + 0.1, y + 0.04, left_w - 0.2, 0.22,
       "DATA REQUIRED", size=8, bold=True, color=BLUE_LIGHT)
    y += 0.28

    rect(slide, left_x, y, left_w, 0.27, fill=LIGHT_BLUE)
    tb(slide, left_x + 0.1, y + 0.04, 2.4, 0.2, "Field", size=8, bold=True, color=DARK_TEXT)
    tb(slide, left_x + 2.6, y + 0.04, 1.0, 0.2, "Source", size=8, bold=True, color=DARK_TEXT)
    tb(slide, left_x + 3.7, y + 0.04, 1.2, 0.2, "Purpose", size=8, bold=True, color=DARK_TEXT)
    y += 0.27

    row_h = 0.31
    for i, (field, source, purpose) in enumerate(inputs):
        bg = RGBColor(0xF8, 0xFA, 0xFD) if i % 2 == 0 else WHITE
        rect(slide, left_x, y, left_w, row_h, fill=bg, line=0.5,
             line_color=RGBColor(0xCC, 0xD8, 0xEE))
        tb(slide, left_x + 0.08, y + 0.06, 2.4, row_h - 0.06,
           field, size=8.5, bold=True, color=DARK_TEXT)
        tb(slide, left_x + 2.58, y + 0.06, 1.0, row_h - 0.06,
           source, size=8, color=BLUE, bold=True)
        tb(slide, left_x + 3.68, y + 0.06, 1.22, row_h - 0.06,
           purpose, size=7.5, color=MID_GREY)
        y += row_h

    y += 0.12
    rect(slide, left_x, y, left_w, 0.28, fill=NAVY)
    tb(slide, left_x + 0.1, y + 0.04, left_w - 0.2, 0.22,
       "OPERATIONS PERFORMED", size=8, bold=True, color=BLUE_LIGHT)
    y += 0.28

    for op in operations:
        rect(slide, left_x + 0.1, y + 0.1, 0.08, 0.08, fill=BLUE)
        tb(slide, left_x + 0.28, y + 0.02, left_w - 0.38, 0.3,
           op, size=8.5, color=DARK_TEXT)
        y += 0.3

    right_x = 5.85
    right_w  = 7.1
    y_r = 1.55

    rect(slide, right_x, y_r, right_w, 0.3, fill=GREEN)
    tb(slide, right_x + 0.12, y_r + 0.05, right_w, 0.22,
       "FORECAST & PROJECTION — from trained model (Stage 4)", size=8, bold=True, color=WHITE)
    y_r += 0.3

    rect(slide, right_x, y_r, right_w, len(ml_outputs) * 0.35 + 0.1,
         fill=GREEN_LIGHT, line=0.5, line_color=RGBColor(0x68, 0xC9, 0xA0))
    for ml_out in ml_outputs:
        tb(slide, right_x + 0.3, y_r + 0.07, right_w - 0.4, 0.28,
           f"›  {ml_out}", size=9.5, color=GREEN)
        y_r += 0.35
    y_r += 0.1

    y_r += 0.12
    rect(slide, right_x, y_r, right_w, 0.3, fill=AMBER)
    tb(slide, right_x + 0.12, y_r + 0.05, right_w, 0.22,
       "LIVE CONTEXT DATA — queried at display time (Stage 5)", size=8, bold=True, color=WHITE)
    y_r += 0.3

    rect(slide, right_x, y_r, right_w, len(live_outputs) * 0.35 + 0.1,
         fill=AMBER_LIGHT, line=0.5, line_color=RGBColor(0xE8, 0xB8, 0x70))
    for lv_out in live_outputs:
        tb(slide, right_x + 0.3, y_r + 0.07, right_w - 0.4, 0.28,
           f"›  {lv_out}", size=9.5, color=AMBER)
        y_r += 0.35

    footnote(slide)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDES 4–8 — Simulation modules
# ═══════════════════════════════════════════════════════════════════════════════

add_sim_slide(
    num_label="MODULE 01",
    name="Cannibalization Risk",
    answer="Is this new SKU pulling demand from an existing one, or adding net-new buyers?",
    inputs=[
        ("Weekly units sold", "SPINS", "Measure demand before/after launch"),
        ("Base units (non-promo)", "SPINS", "Separate promo from organic demand"),
        ("Distribution — stores selling", "SPINS", "Distinguish demand drop from distribution loss"),
        ("Average retail price", "SPINS", "Detect whether price changes explain the shift"),
        ("First week selling (launch date)", "SPINS", "Anchor the before/after comparison window"),
        ("Pack count, flavor, brand line", "SPINS", "Identify likely substitute SKUs"),
        ("Weeks on promotion", "SPINS", "Flag confounding promotional periods"),
    ],
    operations=[
        "Build before/after windows (4-week, 13-week, 26-week) around each product launch",
        "Pair each focal SKU with candidate donors — same flavor, same pack family, competitor",
        "Measure whether focal demand rose while donor demand fell in the same stores and window",
        "Flag windows contaminated by promotions, distribution ramps, or supply events",
        "Calculate incremental share: net-new demand vs. demand transferred from a donor SKU",
        "Assign label (Cannibalizing / Watch / Incremental / Neutral) from observable evidence",
    ],
    ml_outputs=[
        "Risk score + confidence for each focal/donor pair",
        "Status: Cannibalizing · Watch · Incremental · Neutral",
        "Ranked donors with evidence summary (focal lift, donor decline, distribution delta)",
        "Incremental share — net-new demand vs. transferred demand  [FML-10]",
        "Cannibalization rate actuals + 13-week forward projection  [FML-09]",
    ],
    live_outputs=[
        "Actual weekly demand trend for focal and donor SKUs",
        "Distribution (TDP) trend — stores stocking each SKU over time  [FML-05]",
        "Geography heatmap — which markets show the strongest demand transfer",
        "Launch ramp chart — weeks 1–16 of distribution build vs. category norms",
    ],
)

add_sim_slide(
    num_label="MODULE 02",
    name="Price Elasticity",
    answer="If we change price by X%, how much does demand change — and what is the optimal price point?",
    inputs=[
        ("Average retail price", "SPINS", "Measure price level across accounts and weeks"),
        ("Weekly units sold", "SPINS", "Measure demand response to price changes"),
        ("Base price (non-promo ARP)", "SPINS", "Separate everyday price from promo price"),
        ("Promo discount depth (%)", "SPINS", "Quantify the magnitude of promotional price drops"),
        ("Incremental units (promo-driven)", "SPINS", "Isolate promoted demand from baseline"),
        ("Distribution (TDP)", "SPINS", "Control for distribution changes that mimic price effects"),
        ("Competitor price (same flavor)", "SPINS", "Separate own-price from competitive pressure"),
    ],
    operations=[
        "Normalize price to $/bar so singles and 12-packs are comparable  [FML-02]",
        "Build 13-week log-log regression windows per SKU × account  [FML-01]",
        "Separate promotional price changes from everyday price changes",
        "Compare BUILT $/bar vs. same-flavor competitor in the same account and week",
        "Compare $/bar across BUILT own pack sizes of the same flavor (pack-ladder check)",
        "Reject windows where price moved >40% in one week — data artifact guardrail  [GRD-01]",
    ],
    ml_outputs=[
        "Own-price elasticity ε with confidence range (q10 / q50 / q90)  [FML-01]",
        "Cross-price elasticity — demand response to competitor price changes",
        "Promo elasticity curve — lift at each discount depth  [FML-04]",
        "What-if demand curves — projected units at alternative price points",
        "Pricing event queue — active competitive gaps or pack-ladder compression",
    ],
    live_outputs=[
        "Current $/bar and 52-week price trend by retailer account",
        "Pack price ladder — single / 4pk / 12pk side-by-side in the same account",
        "Competitive price gap chart — BUILT vs. Tier 1 competitor in the same flavor",
        "Category benchmark — BUILT $/bar vs. MULO FOOD category average  [GEO-01]",
    ],
)

add_sim_slide(
    num_label="MODULE 03",
    name="Promotional Response",
    answer="How much incremental demand does a promotion generate — and what depth maximizes return?",
    inputs=[
        ("Incremental units", "SPINS", "SPINS-attributed demand above non-promo baseline"),
        ("Base units (non-promo)", "SPINS", "Denominator for promo lift ratio  [FML-03]"),
        ("% units sold on promotion", "SPINS", "Measure how promo-dependent a SKU is"),
        ("Promo discount depth (%)", "SPINS", "Quantify the price concession driving lift"),
        ("Channel (grocery / mass / c-store)", "SPINS", "Response curves differ by channel"),
        ("Pack count", "SPINS", "12pk cliff behavior differs from single bar"),
        ("Distribution on promo (TDP, Any Promo)", "SPINS", "Separate display from pure price promo"),
    ],
    operations=[
        "Calculate promo lift ratio: incremental units ÷ base units, per SKU × account × event  [FML-03]",
        "Group events into discount depth buckets (0–10%, 10–20%, 20–30%, 30%+)",
        "Separate response curves by channel — grocery and c-store show distinct lift profiles",
        "Separate response curves by pack size — 12-packs show a 30%+ discount cliff",
        "Identify the depth where marginal lift no longer justifies additional margin give-up",
    ],
    ml_outputs=[
        "Expected lift % at each discount depth for this SKU × channel × pack size",
        "Optimal discount depth recommendation — where lift peaks before the cliff",
        "Incremental vs. cannibalized demand breakdown at each discount level",
    ],
    live_outputs=[
        "Historical promo events — discount depth, timing, and observed lift per event",
        "Lift trend by event type — TPR vs. display vs. feature support",
        "% weeks on promo trend — is this SKU becoming promo-dependent?",
        "Channel comparison — lift curve across grocery / mass / c-store for this SKU",
    ],
)

add_sim_slide(
    num_label="MODULE 04",
    name="Demand Velocity & Forecast",
    answer="What will this SKU sell in the next 13 weeks, by retailer account?",
    inputs=[
        ("52-week weekly units sold", "SPINS", "Training history for demand patterns"),
        ("Distribution (stores selling)", "SPINS", "Normalize velocity to exclude distribution gaps"),
        ("Average retail price", "SPINS", "Capture price-demand relationship in forecast"),
        ("% weeks on promotion", "SPINS", "Separate promoted from non-promoted baseline"),
        ("Retail account", "SPINS", "Train a separate model per account"),
        ("Week end date", "SPINS", "Derive seasonality index and calendar features"),
    ],
    operations=[
        "Normalize to non-zero TDP weeks — eliminate false troughs from shelf-presence gaps  [FML-05]",
        "Compute rolling averages (4-week, 13-week) to smooth noise while preserving trend",
        "Build 12-month seasonality index from category raw monthly averages (not STL)  [FML-08 / NRM-04]",
        "Flag promo weeks so model learns baseline vs. promo-lifted demand separately",
        "Train separate forecast per SKU × retailer — Kroger velocity ≠ Target velocity",
        "Fall back to exponential smoothing (ETS) for SKUs with <8 weeks of history",
    ],
    ml_outputs=[
        "13-week demand forecast per SKU × retailer account",
        "Confidence bands (low / base / high scenario)",
        "Promo-uplift scenario — demand if a promotion is planned in the forecast window",
        "Forecast accuracy benchmark: 4% wMAPE vs. 7–10% industry baseline  [FML-07]",
    ],
    live_outputs=[
        "52-week actual demand trend by SKU and retailer account",
        "Distribution (stores stocking) trend over the same period",
        "Category average velocity — how this SKU compares to 13-week category norm  [FML-06]",
        "Seasonal index overlay — expected lift or drag on the forecast period  [ANO-04]",
    ],
)

add_sim_slide(
    num_label="MODULE 05",
    name="Distribution & Launch Monitoring",
    answer="Is this new product ramping as expected — in enough stores, with the right velocity?",
    inputs=[
        ("% of stores selling", "SPINS", "Measure distribution build week over week"),
        ("Total distribution points (TDP)", "SPINS", "Primary ramp metric — store count × shelf presence"),
        ("Avg weekly units per store selling", "SPINS", "Velocity independent of distribution level  [FML-06]"),
        ("First week selling", "SPINS", "Anchor the ramp monitoring window"),
        ("Number of weeks selling", "SPINS", "Track position in the launch lifecycle"),
    ],
    operations=[
        "Track weeks 1–16 of distribution build and velocity ramp for each new BUILT UPC",
        "Compare each SKU's ramp against category norms for the same pack type",
        "Classify new UPCs: new pack size, new flavor, or duplicate/relaunch  [QS1 gate / GRD-04]",
        "Flag underperformance at 4, 8, and 13 weeks post-launch vs. expected ramp curve",
        "Suppress cannibalization scoring during ramp — avoids penalizing distribution-driven transfer  [GRD-02]",
    ],
    ml_outputs=[
        "Launch status at current week: On Track · Watch · Underperforming",
        "Expected ramp curve — where this SKU should be at weeks 8, 13, 16",
        "Predicted full-distribution velocity — expected units/store at maturity",
        "Cannibalization scoring readiness — flag for when SKU graduates to active scoring",
    ],
    live_outputs=[
        "Actual TDP ramp week by week since first week selling",
        "Actual velocity per store — is the product pulling through where it is stocked?",
        "Comparable launch benchmarks — similar BUILT or category launches in same retailer",
        "Data-maturity status — weeks until QS1 gate clears for active scoring  [GRD-04]",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — AUTOMATION ROADMAP
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=OFF_WHITE)
rect(slide, 0, 0, 13.333, 1.1, fill=NAVY)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

tb(slide, 0.5, 0.22, 10, 0.6,
   "Automation Roadmap", size=24, bold=True, color=WHITE)
tb(slide, 0.5, 0.72, 12, 0.32,
   "Five priorities to remove manual steps from the pipeline — ordered by impact-to-risk ratio. No changes implemented yet; design only.",
   size=11, color=BLUE_LIGHT)

items = [
    (GREEN,  "badge-green",  "P1  ·  Low risk · High impact",
     "Incremental Ingest Watermark",
     "Load only new weeks via OVERWRITE WHERE — never re-process full history. "
     "Requires a watermark metadata store and verification that all Q-series queries are window-safe."),
    (BLUE,   "badge-blue",   "P2  ·  Foundation for P3",
     "Shell Orchestration — run_data_ops.sh",
     "Chain Q-series and P-series scripts with per-stage gate assertions and halt-on-failure logic. "
     "Same pattern as run_fpa_report.sh. Manual execution first; trigger integration added in P3."),
    (BLUE,   "badge-blue",   "P3  ·  Requires P2",
     "File-Watch Trigger — MinIO bucket event",
     "Wire MinIO bucket notification to fire run_data_ops.sh when a new SPINS export lands. "
     "Aevah owns the entire run from deposit to scored output — no manual step required."),
    (PURPLE, "badge-purple", "P4  ·  Testing",
     "Smoke Test Suite — pinned test cases",
     "Define Stage 4 pinned test cases: known UPC × account pairs with expected direction and magnitude bands. "
     "Use FOOD-channel accounts only — never MULO. Assert direction, not exact values.  [GEO-04 / ANO-01]"),
    (AMBER,  "badge-amber",  "P5  ·  Benchmark required first",
     "Druid Segment Tuning",
     "Baseline query-time benchmark on built_filtered_weekly and ml_training_features. "
     "Evaluate segment granularity and partition changes on a copy before touching live specs. "
     "MULO exclusion logic and OVERWRITE WHERE pattern must be preserved.  [GEO-01]"),
]

item_w = 2.3
item_h = 4.7
for i, (color, badge_cls, tag, title, desc) in enumerate(items):
    x = 0.38 + i * (item_w + 0.15)
    y = 1.28

    rect(slide, x, y, item_w, item_h, fill=WHITE,
         line=0.75, line_color=RGBColor(0xC0, 0xCC, 0xE4))
    rect(slide, x, y, item_w, 0.5, fill=color)
    tb(slide, x + 0.1, y + 0.1, item_w - 0.2, 0.32,
       tag, size=8, bold=True, color=WHITE)

    rect(slide, x + 0.12, y + 0.6, item_w - 0.24, 0.06, fill=color)

    tb(slide, x + 0.12, y + 0.74, item_w - 0.24, 0.7,
       title, size=11, bold=True, color=DARK_TEXT)

    tb(slide, x + 0.12, y + 1.48, item_w - 0.24, item_h - 1.58,
       desc, size=8.5, color=MID_GREY)

# Caveat box at bottom
rect(slide, 0.38, 6.22, 12.55, 0.78, fill=LIGHT_BLUE)
tb(slide, 0.55, 6.28, 12.2, 0.28,
   "TESTING PRINCIPLE", size=8, bold=True, color=BLUE)
tb(slide, 0.55, 6.53, 12.2, 0.42,
   "No spec or script changes go live without a before/after benchmark. "
   "New methods run in parallel against the existing method on a copy first. "
   "Any coverage drop >10% from prior run halts and alerts — degenerate output detection runs on every automated run, not just at release.  "
   "See: mo_automation_design.html and mo_decisions_register.html for full gate logic.",
   size=9.5, color=DARK_TEXT)

footnote(slide)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — NEXT STEPS
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=NAVY_DEEP)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)
rect(slide, 0, 0, 13.333, 1.4, fill=RGBColor(0x14, 0x28, 0x50))

tb(slide, 0.5, 0.3, 10, 0.7,
   "Kickoff Agenda & Next Steps", size=26, bold=True, color=WHITE)

steps_next = [
    ("Data Handoff",           "BUILT confirms 214-column SPINS extract and deposits to MinIO — Aevah file-watch triggers ingest"),
    ("Ingest & QA",            "Aevah ingests to spins_full (incremental watermark); validates field coverage and QS1 new-UPC gate"),
    ("Q-Series Feature Eng.",  "Aevah runs Q0–Q22 Druid feature engineering; smoke-test gate checks row counts, null rates, date range"),
    ("P-Series Training",      "Aevah trains cannibalization, price elasticity, and rate forecast models — conditional on drift/schedule"),
    ("Scoring & Publish",      "Aevah scores all combos; Stage 3/4 gates pass; scoring tables promoted to live query path"),
    ("BUILT Walkthrough",      "Live demo with Brian + Connor — cannibalization + price elasticity suites; use FOOD-channel accounts"),
    ("FP&A Handoff",           "Connor receives 13-week forecast outputs; actuals data shared; temporal backtesting initiated"),
    ("Automation P1–P2",       "Implement incremental watermark + run_data_ops.sh orchestration script as next engineering sprint"),
]

col1_x, col2_x = 0.5, 4.6
y = 1.6
for step, desc in steps_next:
    rect(slide, col1_x, y, 3.8, 0.52, fill=RGBColor(0x20, 0x40, 0x70))
    tb(slide, col1_x + 0.14, y + 0.11, 3.6, 0.33,
       step, size=10.5, bold=True, color=BLUE_LIGHT)
    tb(slide, col2_x, y + 0.11, 8.4, 0.33,
       desc, size=10, color=RGBColor(0xB0, 0xC8, 0xF0))
    y += 0.63

tb(slide, 0.5, 7.1, 12.5, 0.3,
   "Mo by Aevah  ·  BUILT Kickoff  ·  August 2026  ·  Confidential",
   size=8, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ─── Save ────────────────────────────────────────────────────────────────────
out_path = os.path.join(os.path.dirname(__file__), "..", "mockups", "mo_data_ops_kickoff.pptx")
out_path = os.path.normpath(out_path)
prs.save(out_path)
print(f"Saved: {out_path}")
