"""
fix_report_toc.py — Add TOC + deduplicate sections in the HTML report.

Problems solved:
  1. No table of contents at all (§28-32 are completely unreachable without scrolling)
  2. §21 (MO_52) and §17b (MO_44 DoWhy DAG) each appear twice — those scripts
     used append-to-end without markers, so each pipeline run appended again.
  3. §22-27 (MO_53-49) are outside </body> — their patch_html appended to the
     end of the file rather than before </body>.

Fixes applied:
  A. Deduplicate: for §21 and §17b, remove the FIRST occurrence (keep the second,
     which is from a more recent script run and is slightly larger).
  B. Add id attributes to the first occurrence of each section's h2 heading.
  C. Inject a sticky sidebar TOC via a <script> block appended to the document.
     Uses JS so we don't need to parse/modify the massive base64-image-heavy HTML.

Run from FirstAgent/ root:
    python scripts/fix_report_toc.py
"""

import os, re

HTML_PATH = os.path.join(os.path.dirname(__file__), "outputs",
                         "built_demand_intelligence_report.html")

# ── Step A: Deduplication ─────────────────────────────────────────────────────

def find_h2_positions(html):
    """Return list of (start, end) for each h2 tag."""
    return [(m.start(), m.end()) for m in re.finditer(r'<h2[^>]*>', html)]


def h2_text(html, start):
    """Extract plain text of the h2 element starting at `start`."""
    m = re.search(r'</h2>', html[start:start + 2000])
    if not m:
        return ""
    raw = html[start:start + m.end()]
    return re.sub(r'<[^>]+>', '', raw).strip()


def section_id(text):
    """Map h2 text to a canonical section id. Returns None if unrecognised.

    Patterns must be precise — generic words like 'Validation' appear in
    multiple section titles and will cause false matches.
    """
    t = text
    if 'Executive Summary' in t:                             return 'exec'
    if re.match(r'^1[^0-9]', t) or 'The Challenge: Forecasting' in t: return 's1'
    if re.match(r'^2[^0-9]', t) or 'Domain-Intelligent Ensemble' in t: return 's2'
    if re.match(r'^3[^0-9]', t) or 'How Close Did We Actually Get' in t: return 's3'
    if re.match(r'^4[^0-9]', t) or 'LightGBM Excels vs' in t: return 's4'
    if re.match(r'^5[^0-9]', t) or 'Cost of Not Retraining' in t: return 's5'
    if re.match(r'^6[^0-9]', t) or 'Four Questions We Can Answer' in t: return 's6'
    if re.match(r'^7[^0-9]', t) or 'BUILT Today' in t:      return 's7'
    if re.match(r'^8[^0-9]', t) or 'Real-World Examples: BUILT' in t: return 's8'
    if re.match(r'^9[^0-9]', t) or "Driving Your Growth" in t: return 's9'
    if re.match(r'^10[^0-9]', t) or t.startswith('10ROI'):  return 's10'
    if re.match(r'^11[^0-9]', t) or t.startswith('11Next'):  return 's11'
    if re.match(r'^A[^0-9a-z]', t) or 'Technical Appendix' in t: return 'sa'
    if '14. Model Explainability' in t or t.startswith('§14'): return 's14'
    if '15. Feature Diagnostic' in t or t.startswith('§15'):  return 's15'
    if '16. Quantile' in t or t.startswith('§16'):            return 's16'
    if '17. BSTS' in t or 'CausalImpact' in t:               return 's17'
    if 'DoWhy' in t or ('Causal Price' in t and 'Demand Analysis' in t): return 's17b'
    if t.startswith('§18') or 'GRU Neural' in t:             return 's18'
    if '19 ·' in t or 'Rolling vs. Static Mo' in t:          return 's19'
    if '20 ·' in t or 'Regularization Search' in t:          return 's20'
    if 'Section 21' in t or 'MO_52' in t:                    return 's21'
    if 'Section 22' in t or 'MO_53' in t:                    return 's22'
    if 'Section 23' in t or 'MO_54' in t:                    return 's23'
    if 'Section 24' in t or 'MO_56' in t:                    return 's24'
    if 'Section 25' in t or 'MO_57' in t:                    return 's25'
    if 'Section 26' in t or 'MO_58' in t:                    return 's26'
    if 'Section 27' in t or 'MO_49' in t:                    return 's27'
    if t.startswith('§28') or 'Signal Decomposition' in t:   return 's28'
    if t.startswith('§29') or 'Causal Sensitivity' in t:     return 's29'
    if t.startswith('§30') or 'Heterogeneous Price Elasticity' in t: return 's30'
    if t.startswith('§31') or 'Foundation Model Zero-Shot' in t: return 's31'
    if t.startswith('§32') or 'Rolling Cross-Validation' in t: return 's32'
    return None


def remove_duplicate_sections(html):
    """
    For any section that appears more than once, remove all but the LAST
    occurrence. The last occurrence is from the most recent script run and
    is the canonical version.
    """
    # Collect all (position, section_id) pairs
    h2_positions = [m.start() for m in re.finditer(r'<h2[^>]*>', html)]
    all_h2_ends  = [m.end()   for m in re.finditer(r'<h2[^>]*>', html)]
    n = len(h2_positions)

    # For each h2, compute the section span: from h2 start to next h2 start
    # (or end of document for the last one)
    sections = []
    for i, pos in enumerate(h2_positions):
        end = h2_positions[i + 1] if i + 1 < n else len(html)
        text = h2_text(html, pos)
        sid  = section_id(text)
        sections.append((pos, end, sid, text[:60]))

    # Find duplicate section_ids
    from collections import defaultdict
    sid_occurrences = defaultdict(list)
    for i, (pos, end, sid, label) in enumerate(sections):
        if sid:
            sid_occurrences[sid].append(i)

    # Collect index ranges to remove (all but the last occurrence)
    to_remove = []
    for sid, idxs in sid_occurrences.items():
        if len(idxs) > 1:
            print(f"  Duplicate section '{sid}': {len(idxs)} copies — keeping last at pos {sections[idxs[-1]][0]:,}")
            for i in idxs[:-1]:  # remove all but last
                s, e, _, label = sections[i]
                to_remove.append((s, e))
                print(f"    Removing first copy at pos {s:,}–{e:,}: '{label}'")

    if not to_remove:
        print("  No duplicates found.")
        return html

    # Remove in reverse order so positions don't shift
    to_remove.sort(reverse=True)
    for start, end in to_remove:
        html = html[:start] + html[end:]
    print(f"  Removed {len(to_remove)} duplicate section(s). New size: {len(html):,} chars")
    return html


# ── Step B: Add id attributes ─────────────────────────────────────────────────

def add_section_ids(html):
    """
    Add id="toc-{sid}" to the first h2 of each recognised section.
    Skips h2 elements that already have an id attribute.
    """
    seen = set()
    count = 0

    def replacer(m):
        nonlocal count
        tag  = m.group(0)
        pos  = m.start()
        text = h2_text(html, pos)
        sid  = section_id(text)
        if sid and sid not in seen:
            seen.add(sid)
            if 'id=' not in tag:
                new_tag = tag[:-1] + f' id="toc-{sid}">'
                count += 1
                return new_tag
        return tag

    html = re.sub(r'<h2[^>]*>', replacer, html)
    print(f"  Added id attributes to {count} h2 headings.")
    return html


# ── Step C: Inject TOC script ─────────────────────────────────────────────────

TOC_INJECTION = """
<!-- fix_report_toc.py TOC START -->
<style>
  #rpt-toc {
    position: fixed;
    right: 12px;
    top: 60px;
    width: 196px;
    max-height: calc(100vh - 80px);
    overflow-y: auto;
    background: #fff;
    border: 1px solid #c5cae9;
    border-radius: 8px;
    padding: 12px 10px;
    font-size: 11.5px;
    line-height: 1.45;
    box-shadow: 0 2px 14px rgba(0,0,0,.13);
    z-index: 9999;
  }
  #rpt-toc-hd {
    font-weight: 700;
    color: #0d47a1;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .8px;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 2px solid #e3f2fd;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  #rpt-toc-hd button {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    color: #90a4ae;
    padding: 0 2px;
    line-height: 1;
  }
  #rpt-toc a {
    display: block;
    color: #546e7a;
    text-decoration: none;
    padding: 2px 0 2px 8px;
    border-left: 2px solid transparent;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    border-radius: 2px;
  }
  #rpt-toc a:hover  { color: #0d47a1; border-left-color: #0d47a1; background: #f5f7ff; }
  #rpt-toc a.active { color: #0d47a1; border-left-color: #1565c0; font-weight: 600; background: #e8eeff; }
  #rpt-toc a.missing { opacity: 0.35; pointer-events: none; }
  #rpt-toc .toc-sep { border-top: 1px solid #e3f2fd; margin: 5px 0; }
  #rpt-toc .toc-grp { font-size: 9px; color: #90a4ae; text-transform: uppercase;
                      letter-spacing: .5px; margin: 5px 0 2px 8px; }
  /* Show toggle button always; hide sidebar by default on narrow screens */
  #rpt-toc-btn {
    position: fixed;
    right: 12px;
    top: 20px;
    background: #0d47a1;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    z-index: 10000;
    letter-spacing: .3px;
  }
  #rpt-toc-btn:hover { background: #1565c0; }
  @media (max-width: 1320px) { #rpt-toc { display: none; } }
</style>

<script>
(function () {
  var SECTIONS = [
    // [toc_label, id_suffix, is_separator, group_label]
    ['Main Report', null, false, 'group'],
    ['★ Executive Summary',         'exec',  false, null],
    ['§1 — The Challenge',          's1',    false, null],
    ['§2 — Our Approach',           's2',    false, null],
    ['§3 — Validation',             's3',    false, null],
    ['§4 — LightGBM vs. ETS',       's4',    false, null],
    ['§5 — Cost of Not Retraining', 's5',    false, null],
    ['§6 — FP&A Decision Tools',    's6',    false, null],
    ['§7 — July 2026 Projection',   's7',    false, null],
    ['§8 — Real-World Examples',    's8',    false, null],
    ['§9 — Growth Drivers',         's9',    false, null],
    ['§10 — ROI Calculation',       's10',   false, null],
    ['§11 — Next Steps',            's11',   false, null],
    ['§A — Technical Appendix',     'sa',    false, null],
    [null, null, true, null],
    ['Accuracy & Explainability', null, false, 'group'],
    ['§14 — Explainability',        's14',   false, null],
    ['§15 — Feature Diagnostic',    's15',   false, null],
    ['§16 — Quantile Forecast',     's16',   false, null],
    ['§17 — CausalImpact',          's17',   false, null],
    ['§17b — DoWhy DAG',            's17b',  false, null],
    ['§18 — GRU Benchmark',         's18',   false, null],
    [null, null, true, null],
    ['Feature Engineering', null, false, 'group'],
    ['§19 — Rolling Mo Signals',    's19',   false, null],
    ['§20 — Regularization',        's20',   false, null],
    ['§21 — Feature Ablation v4',   's21',   false, null],
    ['§22 — Individual Ablation',   's22',   false, null],
    ['§23 — Holiday Re-Encoding',   's23',   false, null],
    ['§24 — Time-Varying Signals',  's24',   false, null],
    ['§25 — Fourier/Lag Ablation',  's25',   false, null],
    ['§26 — Base/Promo Validation', 's26',   false, null],
    ['§27 — Promo Gap Chart',       's27',   false, null],
    [null, null, true, null],
    ['Advanced Analytics', null, false, 'group'],
    ['§28 — STL Decomposition',     's28',   false, null],
    ['§29 — Causal Sensitivity',    's29',   false, null],
    ['§30 — HTE Elasticity',        's30',   false, null],
    ['§31 — Foundation Models',     's31',   false, null],
    ['§32 — Rolling Cross-Val',     's32',   false, null],
  ];

  function buildToc() {
    var nav = document.createElement('nav');
    nav.id = 'rpt-toc';

    var hd = document.createElement('div');
    hd.id = 'rpt-toc-hd';
    hd.innerHTML = '<span>Contents</span>';
    var closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.title = 'Close';
    closeBtn.onclick = function() { nav.style.display = 'none'; };
    hd.appendChild(closeBtn);
    nav.appendChild(hd);

    SECTIONS.forEach(function(s) {
      var label = s[0], sid = s[1], isSep = s[2], grp = s[3];
      if (isSep) {
        var d = document.createElement('div');
        d.className = 'toc-sep';
        nav.appendChild(d);
        return;
      }
      if (grp === 'group') {
        var g = document.createElement('div');
        g.className = 'toc-grp';
        g.textContent = label;
        nav.appendChild(g);
        return;
      }
      var a = document.createElement('a');
      a.href = '#toc-' + sid;
      a.textContent = label;
      a.dataset.sid = sid;
      var target = document.getElementById('toc-' + sid);
      if (!target) a.classList.add('missing');
      nav.appendChild(a);
    });

    document.body.appendChild(nav);

    // Toggle button
    var btn = document.createElement('button');
    btn.id = 'rpt-toc-btn';
    btn.textContent = '☰ Contents';
    btn.onclick = function() {
      var n = document.getElementById('rpt-toc');
      n.style.display = n.style.display === 'none' ? 'block' : 'none';
    };
    document.body.appendChild(btn);

    // Scroll-based active link highlighting
    var links = nav.querySelectorAll('a[data-sid]');
    window.addEventListener('scroll', function() {
      var scrollY = window.scrollY || window.pageYOffset;
      var current = '';
      document.querySelectorAll('[id^="toc-"]').forEach(function(el) {
        if (el.getBoundingClientRect().top < 130) current = el.id;
      });
      links.forEach(function(a) {
        a.classList.toggle('active', !!current && a.getAttribute('href') === '#' + current);
      });
    }, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildToc);
  } else {
    buildToc();
  }
})();
</script>
<!-- fix_report_toc.py TOC END -->
"""

TOC_START = "<!-- fix_report_toc.py TOC START -->"
TOC_END   = "<!-- fix_report_toc.py TOC END -->"


def inject_toc(html):
    """Inject the TOC before </body> (or append if absent). Idempotent via markers."""
    if TOC_START in html and TOC_END in html:
        # Replace between markers, preserving content outside them
        s = html.index(TOC_START)
        e = html.index(TOC_END) + len(TOC_END)
        html = html[:s] + html[e:]
        print("  Removed prior TOC injection (re-injecting fresh).")

    # Insert before </body> if present; otherwise append
    close = html.rfind("</body>")
    if close != -1:
        html = html[:close] + "\n" + TOC_INJECTION + "\n" + html[close:]
        print("  TOC script injected before </body>.")
    else:
        html = html + "\n" + TOC_INJECTION
        print("  TOC script appended (no </body> found).")
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("fix_report_toc.py")
    print("=" * 50)

    print(f"\nReading {HTML_PATH} …")
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    orig_size = len(html)
    print(f"  Original size: {orig_size / 1_048_576:.1f} MB ({orig_size:,} chars)")

    print("\n[A] Deduplicating sections …")
    html = remove_duplicate_sections(html)

    print("\n[B] Adding section id attributes …")
    html = add_section_ids(html)

    print("\n[C] Injecting TOC sidebar …")
    html = inject_toc(html)

    print(f"\nWriting {HTML_PATH} …")
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    new_size = len(html)
    print(f"  New size: {new_size / 1_048_576:.1f} MB ({new_size:,} chars)")
    print(f"  Delta: {(new_size - orig_size):+,} chars")
    print("\nDone. Open the report in a browser to verify the sidebar.")


if __name__ == "__main__":
    main()
