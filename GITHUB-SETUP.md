# Πώς να το ανεβάσεις στο GitHub & να το μοιραστείς

Βήμα-βήμα (Mac, Terminal). Χρόνος: ~5 λεπτά.

## 1. Λογαριασμός & Git
- Αν δεν έχεις λογαριασμό: φτιάξε στο https://github.com
- Έλεγξε ότι έχεις git: στο Terminal γράψε `git --version`. Αν λείπει, τρέξε `xcode-select --install`.

## 2. Φτιάξε κενό repository στο GitHub
- Πήγαινε https://github.com/new
- Repository name: `biznest-energy`  (ή ό,τι θες)
- Διάλεξε **Private** (ιδιωτικό — μόνο εσύ & όσοι προσκαλέσεις)
- ΜΗΝ προσθέσεις README/.gitignore (τα έχουμε ήδη) → **Create repository**

## 3. Ανέβασε τον κώδικα (από τον φάκελο του project)
Στο Terminal:
```
cd ~/Claude/Projects/"Energy Calculator"
git init
git add .
git commit -m "BizNest energy comparison — initial"
git branch -M main
git remote add origin https://github.com/<ΤΟ-USERNAME-ΣΟΥ>/biznest-energy.git
git push -u origin main
```
(Την πρώτη φορά θα σου ζητήσει σύνδεση στο GitHub — ακολούθησε τον σύνδεσμο.)

## 4. Πρόσκαλεσε συνεργάτες
GitHub repo → **Settings → Collaborators → Add people** → βάλε τα usernames/emails τους.

## 5. (Προαιρετικό) Δημοσίευση online με GitHub Pages
Ώστε οι συνεργάτες να το ανοίγουν με ένα link, χωρίς να κατεβάζουν τίποτα:
- repo → **Settings → Pages**
- Source: **Deploy from a branch** → Branch `main` → φάκελος `/(root)` → **Save**
- Σε ~1 λεπτό θα είναι live στο:
  `https://<username>.github.io/Energy-Calculator/`

> Προσοχή: στο GitHub Pages ο κώδικας είναι **δημόσια ορατός** (το Pages δεν δουλεύει σε
> private repos στο δωρεάν πλάνο). Αν θες να μείνει ιδιωτικό, μοίρασέ το ως private repo
> (βήμα 4) και οι συνεργάτες ανοίγουν τοπικά το `index.html`, ή χρησιμοποίησε
> ιδιωτικό hosting. Μπορώ να σε βοηθήσω να διαλέξεις.

## Κάθε φορά που αλλάζει κάτι
```
cd ~/Claude/Projects/"Energy Calculator"
git add .
git commit -m "περιγραφή αλλαγής"
git push
```
