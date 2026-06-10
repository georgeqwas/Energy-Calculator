# BizNest · Scraper τιμολογίων (ΡΑΑΕΥ / energycost.gr)

Τραβάει τα καταχωρημένα τιμολόγια ρεύματος & αερίου από το **energycost.gr**, κρατάει
τον πιο πρόσφατο μήνα, και γράφει τα δεδομένα που διαβάζει η εφαρμογή:

```
data/tariffs.json   ← canonical
data/tariffs.js     ← window.TARIFFS = {…}  (το φορτώνει το prototype.html)
```

## Εγκατάσταση

```bash
cd scraper
python -m venv .venv && source .venv/bin/activate    # προαιρετικό
pip install -r requirements.txt
```

## Εκτέλεση

```bash
python fetch_tariffs.py            # live από energycost.gr → ενημερώνει data/
python fetch_tariffs.py --all-months   # κράτα όλο το ιστορικό, όχι μόνο τον τελευταίο μήνα
python fetch_tariffs.py --html dump/   # offline: parse τοπικών αρχείων dump/power_home.html κ.λπ.
```

Μετά την εκτέλεση, άνοιξε το `prototype.html` — δείχνει αυτόματα τα νέα δεδομένα.

## Πόσο συχνά

Η ΡΑΑΕΥ ενημερώνει τα τιμολόγια **μηνιαίως**. Τρέξε τον scraper μία φορά τον μήνα.

### Αυτοματισμός με cron (Linux/Mac server)

```cron
# 06:00 στις 2 κάθε μήνα
0 6 2 * *  cd /path/to/Energy\ Calculator/scraper && /usr/bin/python3 fetch_tariffs.py >> sync.log 2>&1
```

### Αυτοματισμός με GitHub Actions

Δες το `.github-workflow-example.yml`. Αντέγραψέ το σε `.github/workflows/tariffs.yml`
στο repo σου· τρέχει την 1η κάθε μήνα και κάνει commit τα ενημερωμένα `data/`.

## Πεδία ανά τιμολόγιο

| πεδίο | περιγραφή |
|---|---|
| `prov` | πάροχος (όπως στη ΡΑΑΕΥ) |
| `name` | ονομασία τιμολογίου |
| `type` | `fixed` / `float` / `special` (από την ονομασία) |
| `fixed` / `rate` | πάγιο €/μήνα · τελική τιμή προμήθειας €/kWh |
| `fixed_disc` / `rate_disc` | πάγιο & τιμή **με** έκπτωση συνέπειας |
| `disc_cond` | προϋπόθεση έκπτωσης |
| `duration` | διάρκεια σύμβασης |
| `notes` | παρατηρήσεις |
| `available` | `false` αν οι παρατηρήσεις λένε «μη εμπορικά διαθέσιμο» |

> Σημ.: Η ΡΑΑΕΥ δίνει **χρέωση προμήθειας**. Το τελικό € σύνολο της εφαρμογής προσθέτει
> εκτίμηση ρυθμιζόμενων χρεώσεων/φόρων (`regulated_estimate_eur_per_kwh`), που είναι
> ~ίδια για όλους τους παρόχους — άρα η **κατάταξη** παραμένει σωστή.

## Logos παρόχων

Βάλε τα PNG στον φάκελο `../providers/<slug>.png` (π.χ. `providers/dei.png`).
Τα slugs ορίζονται στο `providers.json`. Όπου λείπει logo, η εφαρμογή δείχνει monogram.

## Αν ο πίνακας είναι JS-rendered (0 τιμολόγια)

Αν ο scraper βρει 0 γραμμές, η σελίδα φορτώνει τον πίνακα με JavaScript/AJAX. Λύσεις:

1. **Playwright** (render με headless browser):
   ```bash
   pip install playwright && playwright install chromium
   ```
   και άλλαξε το `fetch` ώστε να φορτώνει τη σελίδα με Playwright, να πατά «εμφάνιση όλων»
   και να περνά το `page.content()` στο `parse_html()`.
2. **Χειροκίνητο dump**: άνοιξε κάθε σελίδα στον browser, αποθήκευσέ τη ως `.html` στον
   φάκελο `dump/` (ονόματα `power_home.html`, `power_biz.html`, `gas_home.html`, `gas_biz.html`)
   και τρέξε `python fetch_tariffs.py --html dump/`.

## Νομικό / όροι

Τα δεδομένα ανήκουν στη ΡΑΑΕΥ. Σεβάσου τους όρους χρήσης του energycost.gr, χαμηλή
συχνότητα (1×/μήνα), και ανάφερε την πηγή στην εφαρμογή.
