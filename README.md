# KeepMePosted

Veille cyber-aviation quotidienne pour l'ISO de la Direction de l'Aviation Civile
(Luxembourg) : Part-IS, NIS2, acteurs luxembourgeois, menaces et fournisseurs critiques.

Sources **publiques uniquement (OSINT)**. Aucune donnée interne de la DAC ni des
entités supervisées ne doit entrer dans ce dépôt.

## Fonctionnement

| Heure (Luxembourg) | Étape | Où |
|---|---|---|
| 03:30 (hiver) / 04:30 (été) | Collecte des sources → `data/items.json` | GitHub Action `collect.yml` |
| 05:00 environ | Analyse (résumé FR, tags, exigences Part-IS, score, action), synthèse du jour, publication | Tâche Claude planifiée, sur l'abonnement, voir `ROUTINE.md` |

La page se consulte dans un artifact claude.ai privé : https://claude.ai/artifact/Fi1qZJEUHgFhvZeyjppCSM Tu peux la partager quand tu le décides.

## Fichiers

- `sources.yaml` : registre des sources (RSS, nouveaux liens d'une page, page surveillée)
- `calendar.yaml` : calendrier réglementaire, tenu à la main
- `referentiel/part-is.yaml` : exigences Part-IS et articles NIS2 utilisés par l'analyse
- `scripts/collect.py` : collecte (`python scripts/collect.py [id_source…]`)
- `scripts/pending.py` : éléments à analyser
- `scripts/save_analyses.py` : enregistre un lot d'analyses et la synthèse du jour
- `scripts/build.py` : construit `dist/index.html` et `dist/data.json`
- `web/index.html` : la page
- `data/` : données produites (ne pas modifier à la main)

## Ajouter une source

Ajouter une entrée à `sources.yaml`, puis lancer l'Action « Collecte quotidienne »
à la main (onglet Actions → Run workflow). L'état de chaque source est affiché en bas de la page.

## À vérifier

Les intitulés des exigences dans `referentiel/part-is.yaml` sont des résumés de travail
à confronter aux textes officiels (règlements 2022/1645 et 2023/203).
