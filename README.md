# Stage Finder

Outil local de recherche rapide de **stages Data en Île-de-France** (6 mois, Paris / IDF).
Il interroge plusieurs sites, déduplique, filtre (pas d'alternance / CDI, uniquement IDF) et
**classe les offres selon ton profil** (SQL/PostgreSQL, Python, pandas, NumPy, Matplotlib, ML, QA, anglais…).

Sources (sans compte ni clé API) :

| Source | Méthode |
|---|---|
| LinkedIn | recherche publique « guest » + page détail |
| Welcome to the Jungle | index Algolia public du site |
| HelloWork | page de recherche + JSON-LD de l'offre |
| France Travail *(optionnel)* | API officielle, clé gratuite sur https://francetravail.io → `FT_CLIENT_ID` / `FT_CLIENT_SECRET` |

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate   # optionnel
pip install -r requirements.txt
```

## Utilisation

```bash
python run.py web           # http://127.0.0.1:5000 → bouton « Actualiser les offres »
python run.py search        # tout en console, top 30
python run.py export out.csv
```

Dans l'interface : score et raisons du score (tags), filtres (statut / source / score min / texte),
boutons **Sauver / Candidaté / Masquer**, notes personnelles, export CSV.
Les offres déjà vues sont mémorisées dans `data/jobs.db` : à chaque actualisation seules les **nouvelles** sont marquées « NEW ».

## Personnaliser le profil

Tout est dans `config.json` :

- `queries` — les recherches lancées sur chaque site ;
- `skills` / `boosts` / `penalties` — mots-clés et poids (un mot dans le **titre** compte `title_weight` fois plus) ;
- `exclude_title_terms` — titres éliminés d'office (alternance, CDI, senior…) ;
- `location` — zone géographique par source.

Le score n'est qu'un tri : une offre à 40+ coche beaucoup de cases (SQL, Python, 6 mois…), une offre à 5 n'en coche presque aucune.
