"""
Generate Mo Data Operations Kickoff presentation (.pptx)
Output: mockups/mo_data_ops_kickoff.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
import pptx.oxml.ns as nsmap
from lxml import etree
import copy

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

# ── Slide dimensions (widescreen 16:9) ───────────────────────────────────────
W = Inches(13.333)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

BLANK = prs.slide_layouts[6]  # blank layout

# ── Helper: add textbox ───────────────────────────────────────────────────────
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
    """Multi-paragraph textbox. lines = list of (text, size, bold, color, indent)"""
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    txBox.word_wrap = True
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for item in lines:
        if isinstance(item, str):
            text, size, bold, color, indent = item, default_size, default_bold, default_color, False
        else:
            text = item[0]
            size = item[1] if len(item) > 1 else default_size
            bold = item[2] if len(item) > 2 else default_bold
            color = item[3] if len(item) > 3 else default_color
            indent = item[4] if len(item) > 4 else False
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
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
        1,  # MSO_SHAPE_TYPE.RECTANGLE
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


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)

# Background
rect(slide, 0, 0, 13.333, 7.5, fill=NAVY_DEEP)

# Accent bar (left edge)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

# Mo logo area / eyebrow
tb(slide, 0.5, 0.8, 8, 0.4,
   "MO BY AEVAH  ·  BUILT KICKOFF  ·  AUGUST 2026",
   size=9, color=BLUE_LIGHT, bold=True)

# Main title
tb(slide, 0.5, 1.35, 10, 1.8,
   "How Mo Works\nWith Your Data",
   size=42, bold=True, color=WHITE)

# Subtitle
tb(slide, 0.5, 3.35, 8.5, 1.2,
   "A walkthrough of the process behind each Mo intelligence module — "
   "what data it needs, where that data comes from, what operations are performed, "
   "and what appears on screen.",
   size=14, color=BLUE_LIGHT)

# Divider line
rect(slide, 0.5, 4.75, 6, 0.03, fill=BLUE)

# Five module labels across bottom
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

# Bottom right
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

tb(slide, 0.5, 0.25, 10, 0.6,
   "The End-to-End Process",
   size=24, bold=True, color=WHITE)

tb(slide, 0.5, 1.25, 12, 0.4,
   "Five steps from your SPINS export to decisions on screen — the same sequence runs for every intelligence module.",
   size=12, color=MID_GREY)

# Pipeline steps
steps = [
    ("Step 1", "SPINS Export", "Brian", "Your 214-column weekly\nPOS extract deposited\nto shared storage"),
    ("Step 2", "Data Ingest", "Rob", "Raw SPINS loaded into\nanalytic data store;\nquality gates applied"),
    ("Step 3", "Feature\nEngineering", "Aevah", "Raw rows compressed\ninto business-logic\ntables per module"),
    ("Step 4", "Model Training\n& Scoring", "Aevah", "Focused models trained;\nresults written back\nas queryable tables"),
    ("Step 5", "Mo UI", "BUILT Team", "Two data layers:\nML projections +\nlive context data"),
]

step_w = 2.2
box_h = 2.8
for i, (num, name, who, desc) in enumerate(steps):
    x = 0.4 + i * (step_w + 0.2)
    y = 1.95

    # Step box
    rect(slide, x, y, step_w, box_h, fill=NAVY)

    # Step number
    tb(slide, x + 0.12, y + 0.12, step_w - 0.24, 0.3,
       num.upper(), size=8, bold=True, color=BLUE_LIGHT)

    # Step name
    tb(slide, x + 0.12, y + 0.42, step_w - 0.24, 0.55,
       name, size=13, bold=True, color=WHITE)

    # Who
    tb(slide, x + 0.12, y + 0.95, step_w - 0.24, 0.3,
       who, size=9, color=BLUE_LIGHT, bold=True)

    # Description
    tb(slide, x + 0.12, y + 1.28, step_w - 0.24, 1.3,
       desc, size=9.5, color=RGBColor(0xB0, 0xC8, 0xF0))

    # Arrow (not after last)
    if i < len(steps) - 1:
        ax = x + step_w + 0.02
        tb(slide, ax, y + 1.25, 0.2, 0.35, "→", size=18, bold=True,
           color=BLUE, align=PP_ALIGN.CENTER)

# Key principle box at bottom
rect(slide, 0.4, 5.1, 12.5, 1.1, fill=RGBColor(0xD8, 0xE5, 0xFF))
tb(slide, 0.6, 5.18, 12, 0.3,
   "KEY PRINCIPLE", size=8, bold=True, color=BLUE)
tb(slide, 0.6, 5.48, 12, 0.6,
   "Every Mo screen draws from two distinct sources: model projection tables (what the ML model forecasts) and live context data "
   "(the actual numbers queried at display time). These are kept separate — each has its own query path and lineage.",
   size=11, color=DARK_TEXT)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE TEMPLATE FUNCTION — for each simulation
# ═══════════════════════════════════════════════════════════════════════════════
def add_sim_slide(num_label, name, answer, inputs, operations, ml_outputs, live_outputs):
    slide = prs.slides.add_slide(BLANK)
    rect(slide, 0, 0, 13.333, 7.5, fill=OFF_WHITE)
    rect(slide, 0, 0, 13.333, 1.4, fill=NAVY)
    rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)

    # Header
    tb(slide, 0.5, 0.1, 2, 0.3, num_label, size=9, bold=True, color=BLUE_LIGHT)
    tb(slide, 0.5, 0.38, 7, 0.6, name, size=22, bold=True, color=WHITE)
    # Answer in header right
    tb(slide, 7.8, 0.38, 5.3, 0.8, f'"{answer}"',
       size=11, color=RGBColor(0xC0, 0xD5, 0xFF), italic=True)

    col_margin = 0.35

    # ── LEFT COLUMN: Data Required ──────────────────
    left_x = 0.45
    left_w = 5.0
    y = 1.55

    rect(slide, left_x, y, left_w, 0.28, fill=NAVY)
    tb(slide, left_x + 0.1, y + 0.04, left_w - 0.2, 0.22,
       "DATA REQUIRED", size=8, bold=True, color=BLUE_LIGHT)
    y += 0.28

    # Table header row
    rect(slide, left_x, y, left_w, 0.27, fill=RGBColor(0xD8, 0xE5, 0xFF))
    tb(slide, left_x + 0.1, y + 0.04, 2.4, 0.2, "Field", size=8, bold=True, color=DARK_TEXT)
    tb(slide, left_x + 2.6, y + 0.04, 1.0, 0.2, "Source", size=8, bold=True, color=DARK_TEXT)
    tb(slide, left_x + 3.7, y + 0.04, 1.2, 0.2, "Purpose", size=8, bold=True, color=DARK_TEXT)
    y += 0.27

    row_h = 0.31
    for i, (field, source, purpose) in enumerate(inputs):
        bg = RGBColor(0xF8, 0xFA, 0xFD) if i % 2 == 0 else WHITE
        rect(slide, left_x, y, left_w, row_h, fill=bg, line=0.5,
             line_color=RGBColor(0xCC, 0xD8, 0xEE))
        tb(slide, left_x + 0.08, y + 0.06, 2.4, row_h - 0.06, field,
           size=8.5, bold=True, color=DARK_TEXT)
        tb(slide, left_x + 2.58, y + 0.06, 1.0, row_h - 0.06, source,
           size=8, color=BLUE, bold=True)
        tb(slide, left_x + 3.68, y + 0.06, 1.22, row_h - 0.06, purpose,
           size=7.5, color=MID_GREY)
        y += row_h

    # ── LEFT COLUMN: Operations ──────────────────────
    y += 0.12
    rect(slide, left_x, y, left_w, 0.28, fill=NAVY)
    tb(slide, left_x + 0.1, y + 0.04, left_w - 0.2, 0.22,
       "OPERATIONS PERFORMED", size=8, bold=True, color=BLUE_LIGHT)
    y += 0.28

    for op in operations:
        # bullet
        rect(slide, left_x + 0.1, y + 0.1, 0.08, 0.08,
             fill=BLUE)
        tb(slide, left_x + 0.28, y + 0.02, left_w - 0.38, 0.3,
           op, size=8.5, color=DARK_TEXT)
        y += 0.3

    # ── RIGHT COLUMN ──────────────────────────────────
    right_x = 5.85
    right_w = 7.1
    y_r = 1.55

    # ML Projection block
    rect(slide, right_x, y_r, right_w, 0.3, fill=GREEN)
    tb(slide, right_x + 0.12, y_r + 0.05, right_w, 0.22,
       "FORECAST & PROJECTION — from trained model", size=8, bold=True, color=WHITE)
    y_r += 0.3

    rect(slide, right_x, y_r, right_w, len(ml_outputs) * 0.35 + 0.1, fill=GREEN_LIGHT,
         line=0.5, line_color=RGBColor(0x68, 0xC9, 0xA0))
    for ml_out in ml_outputs:
        tb(slide, right_x + 0.3, y_r + 0.07, right_w - 0.4, 0.28,
           f"›  {ml_out}", size=9.5, color=GREEN)
        y_r += 0.35
    y_r += 0.1

    # Live Context block
    y_r += 0.12
    rect(slide, right_x, y_r, right_w, 0.3, fill=AMBER)
    tb(slide, right_x + 0.12, y_r + 0.05, right_w, 0.22,
       "LIVE CONTEXT DATA — queried at display time", size=8, bold=True, color=WHITE)
    y_r += 0.3

    rect(slide, right_x, y_r, right_w, len(live_outputs) * 0.35 + 0.1,
         fill=AMBER_LIGHT, line=0.5, line_color=RGBColor(0xE8, 0xB8, 0x70))
    for lv_out in live_outputs:
        tb(slide, right_x + 0.3, y_r + 0.07, right_w - 0.4, 0.28,
           f"›  {lv_out}", size=9.5, color=AMBER)
        y_r += 0.35

    # Bottom footnote
    tb(slide, 0.5, 7.2, 12.5, 0.25,
       "Mo by Aevah  ·  BUILT Kickoff  ·  August 2026  ·  Confidential",
       size=8, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDES 3–7 — Simulation modules
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
        "Pair each focal SKU with candidate donors — same flavor, same pack family, same brand, competitor",
        "Measure whether focal demand rose while donor demand fell in the same stores, same window",
        "Flag windows contaminated by promotions, distribution ramps, or supply events",
        "Calculate incremental share: net-new demand vs. demand transferred from a donor SKU",
        "Assign deterministic label (Cannibalizing / Watch / Incremental / Neutral) from observable evidence",
    ],
    ml_outputs=[
        "Risk score + confidence for each focal/donor pair",
        "Status: Cannibalizing · Watch · Incremental · Neutral",
        "Ranked donor SKUs with evidence summary (focal lift, donor decline, distribution delta)",
        "Incremental share — net-new demand vs. transferred demand",
        "Cannibalization rate actuals + 13-week forward projection with confidence bands",
    ],
    live_outputs=[
        "Actual weekly demand trend for focal and donor SKUs",
        "Distribution (TDP) trend — stores stocking each SKU over time",
        "Geography heatmap — which markets show the strongest demand transfer",
        "Launch ramp chart — weeks 1–16 of distribution build vs. category norms",
    ],
)

add_sim_slide(
    num_label="MODULE 02",
    name="Price Elasticity",
    answer="If we change price by X%, how much does demand change — and what's the optimal price point?",
    inputs=[
        ("Average retail price", "SPINS", "Measure price level across accounts and weeks"),
        ("Weekly units sold", "SPINS", "Measure demand response to price changes"),
        ("Base price (non-promo)", "SPINS", "Separate everyday price from promo price"),
        ("Promo discount depth (%)", "SPINS", "Quantify the magnitude of promotional price drops"),
        ("Incremental units (promo-driven)", "SPINS", "Isolate promoted demand from baseline"),
        ("Distribution (TDP)", "SPINS", "Control for distribution changes that mimic price effects"),
        ("Competitor price (same flavor)", "SPINS", "Separate own-price response from competitive pressure"),
    ],
    operations=[
        "Normalize price to price-per-bar so single bars and 12-packs are comparable",
        "Build 13-week regression windows per SKU × account (minimum period for stable estimates)",
        "Separate promotional price changes from everyday price changes",
        "Compare BUILT $/bar vs. same-flavor competitor in the same account and week",
        "Compare $/bar across BUILT's own pack sizes of the same flavor (pack-ladder compression check)",
        "Reject regression windows where price moved >40% in one week — likely a data artifact",
    ],
    ml_outputs=[
        "Own-price elasticity estimate with confidence range (low / mid / high scenario)",
        "Cross-price elasticity — demand response when a competitor changes price",
        "Promo elasticity curve — lift at each discount depth (10% / 20% / 30%+)",
        "What-if demand curves — projected units at alternative price points",
        "Pricing event queue — SKUs with active competitive gaps or pack-ladder compression",
    ],
    live_outputs=[
        "Current $/bar and 52-week price trend by retailer account",
        "Pack price ladder — single / 4pk / 12pk side-by-side in the same account",
        "Competitive price gap chart — BUILT vs. Tier 1 competitor in the same flavor",
        "Category benchmark — BUILT $/bar vs. MULO FOOD category average",
    ],
)

add_sim_slide(
    num_label="MODULE 03",
    name="Promotional Response",
    answer="How much incremental demand does a promotion generate — and what discount depth maximizes return?",
    inputs=[
        ("Incremental units", "SPINS", "SPINS-attributed demand above non-promo baseline"),
        ("Base units (non-promo)", "SPINS", "Denominator for lift ratio calculation"),
        ("% units sold on promotion", "SPINS", "Measure how promo-dependent a SKU is"),
        ("Promo discount depth (%)", "SPINS", "Quantify the price concession driving lift"),
        ("Channel (grocery / mass / c-store)", "SPINS", "Response curves differ by channel"),
        ("Pack count", "SPINS", "12pk cliff behavior differs from single bar"),
        ("Distribution on promo (TDP, Any Promo)", "SPINS", "Separate display support from pure price promotion"),
    ],
    operations=[
        "Calculate promo lift ratio: incremental units ÷ base units, per SKU × account × event week",
        "Group events into discount depth buckets (0–10%, 10–20%, 20–30%, 30%+) — lift response curve",
        "Separate response curves by channel — grocery and c-store show distinct lift profiles",
        "Separate response curves by pack size — single bars and 12-packs have different optimal depths",
        "Identify the discount depth where marginal lift no longer justifies additional margin give-up",
    ],
    ml_outputs=[
        "Expected lift % at each discount depth for this SKU × channel × pack size",
        "Optimal discount depth recommendation — where lift peaks before the cliff",
        "Incremental vs. cannibalized demand breakdown at each discount level",
    ],
    live_outputs=[
        "Historical promo events — discount depth, timing, and observed lift for each past event",
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
        ("Retail account", "SPINS", "Train separate model per account"),
        ("Week end date", "SPINS", "Derive seasonality index and calendar features"),
    ],
    operations=[
        "Normalize velocity to non-zero distribution weeks — eliminate false demand troughs from gaps in shelf presence",
        "Compute rolling averages (4-week, 13-week) to smooth noise while preserving trend signal",
        "Build a 12-month seasonality index from category-level raw monthly averages",
        "Flag promo weeks so the model learns baseline vs. promo-lifted demand separately",
        "Train a separate forecast per SKU × retailer — velocity at Kroger ≠ velocity at Target",
        "Fall back to exponential smoothing for SKUs with fewer than 8 weeks of selling history",
    ],
    ml_outputs=[
        "13-week demand forecast per SKU × retailer account",
        "Confidence bands (low / base / high scenario)",
        "Promo-uplift scenario — projected demand if a promotion is planned in the forecast window",
    ],
    live_outputs=[
        "52-week actual demand trend by SKU and retailer account",
        "Distribution (stores stocking) trend over the same period",
        "Category average velocity — how this SKU compares to the 13-week category norm",
        "Seasonal index overlay — expected seasonal lift or drag on the forecast period",
    ],
)

add_sim_slide(
    num_label="MODULE 05",
    name="Distribution & Launch Monitoring",
    answer="Is this new product ramping as expected — in enough stores, with the right velocity?",
    inputs=[
        ("% of stores selling", "SPINS", "Measure distribution build week over week"),
        ("Total distribution points (TDP)", "SPINS", "Primary ramp metric — store count × shelf presence"),
        ("Avg weekly units per store selling", "SPINS", "Measure velocity independent of distribution level"),
        ("First week selling", "SPINS", "Anchor the ramp monitoring window"),
        ("Number of weeks selling", "SPINS", "Track position in the launch lifecycle"),
    ],
    operations=[
        "Track weeks 1–16 of distribution build and velocity ramp for each new BUILT UPC",
        "Compare each new SKU's ramp trajectory against category norms for the same pack type",
        "Classify new UPCs: new pack size, new flavor, or duplicate/relaunch — determines scoring timeline",
        "Flag underperformance at 4, 8, and 13 weeks post-launch vs. expected ramp curve",
        "Suppress cannibalization scoring during the ramp period — avoids penalizing distribution-driven transfer",
    ],
    ml_outputs=[
        "Launch status at current week: On Track · Watch · Underperforming",
        "Expected ramp curve — where this SKU should be at week 8, 13, and 16",
        "Predicted full-distribution velocity — expected units per store at maturity",
    ],
    live_outputs=[
        "Actual TDP ramp week by week since first week selling",
        "Actual velocity per store — is the product pulling through where it is stocked?",
        "Comparable launch benchmarks — how similar BUILT or category launches ramped in the same retailer",
        "Cannibalization scoring readiness — flag for when this SKU graduates to active scoring",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — Go-Forward / Next Steps
# ═══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, 13.333, 7.5, fill=NAVY_DEEP)
rect(slide, 0, 0, 0.08, 7.5, fill=BLUE)
rect(slide, 0, 0, 13.333, 1.4, fill=RGBColor(0x14, 0x28, 0x50))

tb(slide, 0.5, 0.3, 10, 0.7,
   "Kickoff Agenda & Next Steps",
   size=26, bold=True, color=WHITE)

steps_next = [
    ("Data Handoff",       "Brian confirms 214-column SPINS extract and deposits to MinIO"),
    ("Ingest & QA",        "Rob ingests to spins_full; Aevah validates field coverage and new UPC gate"),
    ("Q-Series Run",       "Aevah runs Q0–Q22 Druid feature engineering; review output table row counts"),
    ("P-Series Training",  "Aevah trains cannibalization, price elasticity, and rate forecast models"),
    ("Scoring & Publish",  "Aevah scores and publishes to Druid; Mo UI connected and verified"),
    ("BUILT Walkthrough",  "Live demo with Brian + Connor — cannibalization + price elasticity suites"),
    ("FP&A Handoff",       "Connor receives forecast outputs; actuals data shared for backtesting"),
]

col1_x, col2_x = 0.5, 4.6
y = 1.65
for step, desc in steps_next:
    rect(slide, col1_x, y, 3.8, 0.55, fill=RGBColor(0x20, 0x40, 0x70))
    tb(slide, col1_x + 0.14, y + 0.12, 3.6, 0.35,
       step, size=11, bold=True, color=BLUE_LIGHT)
    tb(slide, col2_x, y + 0.12, 8.4, 0.35,
       desc, size=11, color=RGBColor(0xB0, 0xC8, 0xF0))
    y += 0.67

tb(slide, 0.5, 7.1, 12.5, 0.3,
   "Mo by Aevah  ·  BUILT Kickoff  ·  August 2026  ·  Confidential",
   size=8, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ─── Save ────────────────────────────────────────────────────────────────────
import os
out_path = os.path.join(os.path.dirname(__file__), "..", "mockups", "mo_data_ops_kickoff.pptx")
out_path = os.path.normpath(out_path)
prs.save(out_path)
print(f"Saved: {out_path}")
