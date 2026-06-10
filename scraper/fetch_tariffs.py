#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizNest · Energy tariff scraper
Πηγή: ΡΑΑΕΥ / energycost.gr (σελίδες «Καταχωρημένα Τιμολόγια»)

Τραβάει τα τιμολόγια ρεύματος & αερίου (οικιακά + επαγγελματικά), κρατάει τον
πιο πρόσφατο μήνα, τα κανονικοποιεί και γράφει:
  ../data/tariffs.json   (canonical)
  ../data/tariffs.js     (window.TARIFFS = {...}  — το φορτώνει το prototype.html)

Χρήση:
  python fetch_tariffs.py                # live από energycost.gr
  python fetch_tariffs.py --html dump/   # offline: parse τοπικών .html (1 ανά κατηγορία)
  python fetch_tariffs.py --all-months   # κράτα όλους τους μήνες, όχι μόνο τον τελευταίο

Σημ.: Η σελίδα ενημερώνεται μηνιαίως. Τρέξε τον scraper 1×/μήνα (δες README.md).
"""
import argparse, json, re, sys, datetime, pathlib
from io import StringIO

try:
    import requests
    import pandas as pd
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Λείπουν εξαρτήσεις. Τρέξε:  pip install -r requirements.txt")

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / "data"
PROVIDERS_FILE = HERE / "providers.json"

# Οι 4 σελίδες «Καταχωρημένα Τιμολόγια» του energycost.gr
SOURCES = {
    "power_home": "https://energycost.gr/καταχωρημένα-τιμολόγια-προμήθειας-η-3/",
    "power_biz":  "https://energycost.gr/καταχωρημένα-τιμολόγια-προμήθειας-η-2/",
    "gas_home":   "https://energycost.gr/καταχωρημένα-τιμολόγια-προμήθειας_gas/",
    "gas_biz":    "https://energycost.gr/καταχωρημένα-τιμολόγια-προμήθειας-ε_gas/",
}

# Εκτίμηση ρυθμιζόμενων χρεώσεων + φόρων (€/kWh) — κοινές ~ για όλους τους παρόχους.
# Δεν επηρεάζουν την ΚΑΤΑΤΑΞΗ, μόνο το τελικό € σύνολο. Προσαρμόσιμο.
REGULATED = {"power": 0.05, "gas": 0.012}

# Αντιστοίχιση κεφαλίδων ΡΑΑΕΥ -> εσωτερικά πεδία
COLMAP = {
    "Πάροχος": "prov",
    "Έτος": "year",
    "Μήνας": "month",
    "Ονομασία Τιμολογίου": "name",
    "Πάγιο (€/μήνα)": "fixed",
    "Τελική Τιμή Προμήθειας (€/ΚWh)": "rate",
    "Πάγιο με Έκπτωση με προϋπόθεση (€/μήνα)": "fixed_disc",
    "Προϋπόθεση Έκπτωσης Παγίου": "disc_cond_fixed",
    "Τελική Τιμή Προμήθειας με Έκπτωση με προϋπόθεση (€/ΚWh)": "rate_disc",
    "Προϋπόθεση Έκπτωσης Βασικής Τιμής Προμήθειας": "disc_cond",
    "Διάρκεια Σύμβασης": "duration",
    "Παρατηρήσεις": "notes",
}

UA = {"User-Agent": "Mozilla/5.0 (BizNest tariff sync; contact: ops@biznest.gr)"}


def fnum(x):
    """Πρώτος αριθμός μέσα στο κελί (αντέχει ανακατεμένο κείμενο, π.χ. διζωνικά)."""
    if x is None:
        return None
    s = str(x).replace("\xa0", " ").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def clean_txt(x):
    s = "" if x is None else str(x).strip()
    return "" if s.lower() in ("nan", "none") else s


def infer_type(name):
    n = (name or "").lower()
    if "κυμαιν" in n:
        return "float"
    if "σταθερ" in n:
        return "fixed"
    if "ειδικ" in n:
        return "special"
    return ""


def _find(cols, must, exclude=()):
    for c in cols:
        cl = str(c)
        if all(m in cl for m in must) and not any(e in cl for e in exclude):
            return c
    return None


# Λογικά όρια τιμής προμήθειας (€/kWh) — πετάμε garbage/μπερδεμένα κελιά.
RATE_MIN, RATE_MAX = 0.005, 1.5


def normalize_table(df):
    """Αναγνωρίζει στήλες με έξυπνο ταίριασμα ονομάτων. Δουλεύει είτε φαίνονται οι
    βασικές στήλες («Πάγιο»/«Τελική Τιμή») είτε μόνο οι «με Έκπτωση»."""
    cols = [str(c) for c in df.columns]
    df = df.copy(); df.columns = cols
    c_prov = _find(cols, ["Πάροχος"])
    if not c_prov:
        return []
    c_year = _find(cols, ["Έτος"]); c_month = _find(cols, ["Μήνας"]); c_name = _find(cols, ["Ονομασία"])
    c_rate_base = _find(cols, ["Τελική Τιμή Προμήθειας"], ["Έκπτωση"])
    c_rate_disc = _find(cols, ["Τελική Τιμή", "Έκπτωση"])
    c_fix_base = _find(cols, ["Πάγιο"], ["Έκπτωση"])
    c_fix_disc = _find(cols, ["Πάγιο", "Έκπτωση"])
    c_cond = _find(cols, ["Προϋπόθεση Έκπτωσης Βασικής"]) or _find(cols, ["Προϋπόθεση Έκπτωσης"])
    c_dur = _find(cols, ["Διάρκεια"]); c_notes = _find(cols, ["Παρατηρήσεις"])
    rate_main = c_rate_base or c_rate_disc          # προτίμησε βασική, αλλιώς «με έκπτωση»
    fix_main = c_fix_base or c_fix_disc
    if not rate_main:
        return []
    have_both_rate = c_rate_base and c_rate_disc
    have_both_fix = c_fix_base and c_fix_disc

    recs = []
    for _, r in df.iterrows():
        prov = clean_txt(r.get(c_prov))
        if not prov:
            continue
        rate = fnum(r.get(rate_main))
        if rate is None or rate < RATE_MIN or rate > RATE_MAX:
            continue
        name = clean_txt(r.get(c_name)) if c_name else ""
        notes = clean_txt(r.get(c_notes)) if c_notes else ""
        recs.append({
            "prov": prov,
            "name": name,
            "type": infer_type(name),
            "fixed": fnum(r.get(fix_main)) if fix_main else None,
            "rate": rate,
            "fixed_disc": (fnum(r.get(c_fix_disc)) if have_both_fix else None),
            "rate_disc": (fnum(r.get(c_rate_disc)) if have_both_rate else None),
            "disc_cond": clean_txt(r.get(c_cond)) if c_cond else "",
            "duration": clean_txt(r.get(c_dur)) if c_dur else "",
            "notes": notes,
            "available": "μη εμπορικά διαθέσιμ" not in notes.lower(),
            "_year": int(fnum(r.get(c_year)) or 0) if c_year else 0,
            "_month": int(fnum(r.get(c_month)) or 0) if c_month else 0,
        })
    return recs


# Σειρά στηλών του πίνακα ΡΑΑΕΥ (όταν το DataTables δίνει body χωρίς κεφαλίδες)
COL_ORDER = ["prov", "year", "month", "name", "fixed", "rate", "fixed_disc",
             "disc_cond_fixed", "rate_disc", "disc_cond", "duration", "notes"]


COLOR_TYPE = {"color_blue": "fixed", "color_yellow": "float", "color_green": "special"}


def _txt(el):
    return el.get_text(strip=True) if el else None


def parse_html(html):
    """Κύριος parser: διαβάζει τον πίνακα του energycost με βάση τις CSS κλάσεις
    των κελιών (αξιόπιστο — δίνει σωστό τύπο τιμολογίου & βασικές/εκπτωτικές τιμές)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="billing_table") or soup.find("table")
    recs = []
    rows = table.select("tbody tr") if table else []
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        name_td = tr.find("td", class_="rae-inv-product-name")
        prov_td = tr.find("td", attrs={"data-filter-value": True})
        prov = _txt(prov_td) or _txt(tds[0])
        if not prov:
            continue
        # τύπος από την κλάση color_* του κελιού ονομασίας
        ttype = ""
        if name_td:
            for cls in name_td.get("class", []):
                if cls in COLOR_TYPE:
                    ttype = COLOR_TYPE[cls]; break
        def cell(c):
            return _txt(tr.find("td", class_=c))
        rate_base = fnum(cell("teliki_timi_promithias"))
        fixed_base = fnum(cell("pagio"))
        rate_disc = fnum(cell("teliki_timi_promithias_meta_apo_ekptoseis_promithias"))
        fixed_disc = fnum(cell("pagio_me_proipotheseis"))
        # καθάρισε garbage εκπτωτικές τιμές
        if rate_disc is not None and (rate_disc < RATE_MIN or rate_disc > RATE_MAX):
            rate_disc = None
        # effective: τιμή με έκπτωση συνέπειας αν ισχύει, αλλιώς βασική
        rate = rate_disc if rate_disc is not None else rate_base
        if rate is None or rate < RATE_MIN or rate > RATE_MAX:
            continue
        fixed = fixed_disc if (rate_disc is not None and fixed_disc is not None) else fixed_base
        has_disc = rate_disc is not None and rate_base is not None and rate_disc < rate_base
        notes = cell("paratiriseis") or ""
        name = _txt(name_td) or ""
        recs.append({
            "prov": prov,
            "name": name,
            "type": ttype or infer_type(name),
            "fixed": fixed,
            "rate": rate,
            "rate_base": rate_base,
            "fixed_base": fixed_base,
            "fixed_disc": fixed_disc if has_disc else None,
            "rate_disc": rate_disc if has_disc else None,
            "has_discount": has_disc,
            "disc_cond": cell("teliki_xreosi_promithias_me_ekptosi_proipothesis_explain") or "",
            "duration": cell("diarkia_simvasis") or "",
            "notes": notes,
            "available": tr.get("data-emporika-diathesimo", "1") != "0",
            "_year": int(fnum(_txt(tds[1])) or 0),
            "_month": int(fnum(_txt(tds[2])) or 0),
        })
    if recs:
        return recs
    return _parse_html_pandas(html)


def _parse_html_pandas(html):
    """Fallback parser (παλιός, με pandas) αν αλλάξει το markup."""
    try:
        tables = pd.read_html(StringIO(html))  # χρειάζεται lxml/bs4
    except ValueError:
        return []  # «No tables found» → JS-rendered, δες --browser ή --html
    # 1) με βάση τις κεφαλίδες
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        if "Πάροχος" in cols and any("Τελική Τιμή" in c for c in cols):
            recs = normalize_table(t)
            if recs:
                return recs
    # 2) fallback: το DataTables συχνά δίνει body-πίνακα ΧΩΡΙΣ κεφαλίδες.
    #    Παίρνουμε τον πίνακα με τις περισσότερες γραμμές & ~12 στήλες και
    #    αντιστοιχίζουμε με βάση τη ΣΕΙΡΑ των στηλών.
    cand = [t for t in tables if len(t.columns) >= 11 and len(t) > 0]
    cand.sort(key=len, reverse=True)
    for t in cand:
        t = t.copy()
        n = min(len(t.columns), len(COL_ORDER))
        t = t.iloc[:, :n]
        t.columns = COL_ORDER[:n]
        recs = normalize_table(t)
        if recs:
            return recs
    return []


def render_with_playwright(url, log=print):
    """Ανοίγει τη σελίδα σε headless Chromium, δείχνει όλες τις γραμμές και
    επιστρέφει λίστα HTML (μία ανά σελίδα pagination)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Λείπει το Playwright. Τρέξε:  pip install playwright && playwright install chromium")
    htmls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # «domcontentloaded» αντί για «networkidle»: το energycost κρατάει polling
        # συνδέσεις ανοιχτές και δεν φτάνει ποτέ σε networkidle.
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        for sel in ["text=Αποδοχή", "text=ΑΠΟΔΟΧΗ", "text=Accept", "#cookie-accept", ".cookie-accept"]:
            try:
                page.click(sel, timeout=1200)
                break
            except Exception:
                pass
        # περίμενε να εμφανιστεί ο πίνακας ΜΕ δεδομένα (όχι μόνο <table>)
        try:
            page.wait_for_selector("#billing_table tbody tr td, table tbody tr td", timeout=75000)
            page.wait_for_timeout(2500)  # δώσε χρόνο να γεμίσουν όλες οι γραμμές
        except Exception:
            log("  [warn] ο πίνακας δεν γέμισε σε 75s — δοκίμασε τον χειροκίνητο τρόπο (--html)")
            page.wait_for_timeout(1500)
        # δείξε όσο το δυνατόν περισσότερες γραμμές ανά σελίδα
        try:
            sel = page.query_selector("select[name$='_length'], .dataTables_length select, select")
            if sel:
                vals = [o.get_attribute("value") for o in sel.query_selector_all("option")]
                vals = [v for v in vals if v]
                best = "-1" if "-1" in vals else (max([v for v in vals if v.lstrip("-").isdigit()], key=lambda v: int(v), default=None))
                if best:
                    sel.select_option(best)
                    page.wait_for_timeout(2500)
        except Exception as e:
            log(f"  [warn] length select: {e}")
        # μάζεψε όλες τις σελίδες pagination
        guard = 0
        while True:
            htmls.append(page.content())
            guard += 1
            nxt = page.query_selector("a.paginate_button.next, .dataTables_paginate .next, li.next a")
            cls = (nxt.get_attribute("class") or "") if nxt else ""
            if not nxt or "disabled" in cls or guard > 300:
                break
            try:
                nxt.click()
                page.wait_for_timeout(1200)
            except Exception:
                break
        browser.close()
    log(f"  [browser] {len(htmls)} σελίδα(ες) pagination")
    return htmls


def dedup(recs):
    seen, out = set(), []
    for r in recs:
        key = (r["prov"], r["name"], r.get("_year"), r.get("_month"), r["rate"])
        if key in seen:
            continue
        seen.add(key); out.append(r)
    return out


def keep_latest(recs, all_months=False):
    if not recs:
        return recs
    if all_months:
        out = recs
    else:
        ym = max((r["_year"], r["_month"]) for r in recs)
        out = [r for r in recs if (r["_year"], r["_month"]) == ym]
    for r in out:
        r.pop("_year", None); r.pop("_month", None)
    return out


def load_providers():
    if PROVIDERS_FILE.exists():
        return json.load(open(PROVIDERS_FILE, encoding="utf-8"))
    return {}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "provider"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="φάκελος με τοπικά <key>.html για offline parse")
    ap.add_argument("--browser", action="store_true", help="render με Playwright (για JS-rendered πίνακα)")
    ap.add_argument("--all-months", action="store_true")
    args = ap.parse_args()

    providers = load_providers()
    categories = {}
    seen = set()

    for key, url in SOURCES.items():
        if args.html:
            fp = pathlib.Path(args.html) / f"{key}.html"
            if not fp.exists():
                print(f"  [skip] {key}: λείπει {fp}")
                categories[key] = []
                continue
            recs = parse_html(fp.read_text(encoding="utf-8"))
        elif args.browser:
            print(f"  [get ] {key} ← {url}  (browser)")
            recs = []
            pages = render_with_playwright(url)
            if pages:  # αποθήκευσε το 1ο rendered HTML για debug/χειροκίνητο parse
                dbg = HERE / "_debug"; dbg.mkdir(exist_ok=True)
                (dbg / f"{key}.html").write_text(pages[0], encoding="utf-8")
            for h in pages:
                recs += parse_html(h)
        else:
            print(f"  [get ] {key} ← {url}")
            resp = requests.get(url, headers=UA, timeout=60)
            resp.raise_for_status()
            recs = parse_html(resp.text)
        recs = keep_latest(dedup(recs), args.all_months)
        for r in recs:
            seen.add(r["prov"])
        categories[key] = recs
        print(f"  [ok  ] {key}: {len(recs)} τιμολόγια")

    # συμπλήρωσε registry για νέους παρόχους
    for p in sorted(seen):
        if p not in providers:
            providers[p] = {"slug": slugify(p), "color": "#5b5b64", "domain": ""}
            print(f"  [new ] πάροχος χωρίς registry: {p} -> slug {providers[p]['slug']}")

    out = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "ΡΑΑΕΥ / energycost.gr",
        "is_sample": False,
        "regulated_estimate_eur_per_kwh": REGULATED,
        "providers": providers,
        "categories": categories,
    }
    total = sum(len(v) for v in categories.values())
    if total == 0:
        # ΜΗΝ σβήνεις τα υπάρχοντα καλά δεδομένα με άδειο αποτέλεσμα.
        print("\n⚠  0 τιμολόγια — ΔΕΝ έγραψα τίποτα (κράτησα τα προηγούμενα δεδομένα).")
        if args.browser:
            print("   Το rendered HTML αποθηκεύτηκε στο scraper/_debug/ για έλεγχο.")
        print("   Δοκίμασε τον χειροκίνητο τρόπο:  python3 fetch_tariffs.py --html dump/")
        print("   (δες ΟΔΗΓΙΕΣ.md / README.md). Αν συνεχίσει, στείλε μου ένα _debug/*.html.")
        return

    DATA.mkdir(exist_ok=True)
    (DATA / "tariffs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "tariffs.js").write_text("window.TARIFFS = " + json.dumps(out, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    PROVIDERS_FILE.write_text(json.dumps(providers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Γράφτηκαν {total} τιμολόγια σε data/tariffs.json & data/tariffs.js")


if __name__ == "__main__":
    main()
