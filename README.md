# BizNest · Σύγκριση Ενέργειας

Εσωτερικό εργαλείο σύγκρισης τιμολογίων **ρεύματος & φυσικού αερίου** για τους
υπαλλήλους της BizNest. Δεδομένα από τη **ΡΑΑΕΥ** (energycost.gr), παρουσίαση σε
στυλ καρτών με τιμή κιλοβατώρας, πάγιο/μήνα και εκτιμώμενο μηνιαίο κόστος.

> Στάδιο: prototype (research preview). Επόμενο βήμα: customer-facing έκδοση.

## Γρήγορη εκκίνηση

Άνοιξε το `prototype.html` σε έναν browser (διπλό κλικ). Δεν χρειάζεται build.

## Δομή

```
prototype.html        # η εφαρμογή (single-file, χωρίς build)
data/
  tariffs.json        # τα τιμολόγια (canonical)
  tariffs.js          # window.TARIFFS = {...}  ← το φορτώνει το prototype.html
scraper/
  fetch_tariffs.py    # τραβάει τα τιμολόγια από energycost.gr (ΡΑΑΕΥ)
  providers.json      # registry παρόχων (slug, χρώμα, domain)
  README.md           # οδηγίες scraper + αυτοματισμός
providers/            # logos παρόχων  <slug>.png  (+ monogram fallback)
logo/                 # logos BizNest
ΟΔΗΓΙΕΣ.md            # runbook για μη-τεχνικούς
```

## Ενημέρωση δεδομένων (μηνιαία)

```bash
cd scraper
pip install -r requirements.txt
python fetch_tariffs.py --browser      # χρειάζεται playwright· δες scraper/README.md
```

Τα `data/tariffs.json` & `data/tariffs.js` ενημερώνονται αυτόματα.

## Δημοσίευση για τους συνεργάτες (GitHub Pages)

Η εφαρμογή είναι στατική, οπότε φιλοξενείται δωρεάν σε GitHub Pages:
Settings → Pages → Branch `main` → φάκελος `/ (root)`. Μετά θα είναι διαθέσιμη σε
`https://<user>.github.io/<repo>/prototype.html`.

## Άδεια

Proprietary — δες [LICENSE](LICENSE). Τα δεδομένα τιμολογίων ανήκουν στη ΡΑΑΕΥ.
