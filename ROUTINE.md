# Routine quotidienne d'analyse (5 h, heure de Luxembourg)

Cette routine est exécutée chaque matin par une tâche Claude planifiée. Elle passe
après la collecte de la GitHub Action (02:30 UTC) et prend une quinzaine de minutes.

## 1. Récupérer la collecte

```bash
cd /home/user/KeepMePosted
git fetch origin claude/wizardly-bohr-o7znla
git checkout claude/wizardly-bohr-o7znla
git merge --ff-only FETCH_HEAD
```

Ouvrir `data/status.json`. Si aucune source n'a été vérifiée dans les 6 dernières
heures, la collecte planifiée n'a pas tourné (GitHub retarde ou saute parfois les
déclenchements planifiés) : la lancer avec l'outil GitHub `actions_run_trigger`
(`run_workflow`, `collect.yml`, ref `claude/wizardly-bohr-o7znla`), attendre le commit
« Collecte du … » sur la branche, puis refaire la fusion ci-dessus.

## 2. Analyser les nouveaux éléments

```bash
python3 scripts/pending.py 80
```

Lire `referentiel/part-is.yaml`, puis, pour chaque élément, produire :

| Champ | Contenu |
|---|---|
| `resume` | 2 à 3 phrases en français, factuelles, sans reprendre le titre |
| `tags` | 2 à 5 parmi : Réglementation, Menace, Incident, Vulnérabilité, Acteur LU, Fournisseur, GNSS, Drones, NIS2, Part-IS, Supply chain, Ransomware, Gouvernance, Contexte |
| `exigences` | 0 à 3 codes du référentiel, seulement si le lien est réel (ex. `IS.I.OR.230` pour une notification d'incident, `IS.I.OR.235` pour un prestataire) |
| `perimetre` | `DAC`, `Entités`, `Les deux` ou `Contexte` |
| `score` | 0 à 100, voir le barème |
| `action` | `Rien`, `Lire`, `Suivre`, `Informer le CISO`, `Alerter une entité`, `Ajuster la supervision` |
| `pourquoi` | Une phrase : en quoi cela concerne (ou pas) la mission Part-IS de la DAC |
| `doublon_de` | Facultatif : identifiant de l'élément principal quand plusieurs articles traitent du même sujet (la page les regroupe sous lui) |

Barème du score :
- 80 à 100 : touche directement une entité luxembourgeoise supervisée, la DAC, ou
  modifie Part-IS ou NIS2 (texte, AMC/GM, transposition luxembourgeoise).
- 60 à 79 : incident ou vulnérabilité chez un acteur ou fournisseur utilisé au
  Luxembourg ; consultation EASA ouverte ; publication ENISA ou CERT-EU sur l'aviation.
- 40 à 59 : menace ou incident aviation en Europe, sans lien direct identifié.
- 20 à 39 : contexte international utile.
- 0 à 19 : hors sujet (faux positif d'un mot-clé). Action `Rien`.

Les sources sont publiques : ne jamais ajouter d'information interne à la DAC ou
aux entités supervisées. Ne pas inventer de lien avec une entité : en cas de doute,
`Suivre`, et le dire dans `pourquoi`.

S'il reste plus de 80 éléments, traiter d'abord les plus récents, puis relancer
`pending.py` jusqu'à épuisement (les anciens peuvent recevoir une analyse courte).

## 3. Rédiger la synthèse du jour

- `synthese` : 3 à 5 phrases sur ce qui compte aujourd'hui pour l'ISO, en commençant
  par ce qui demande une action.
- `une` : les 5 à 10 éléments à retenir parmi ceux des 72 dernières heures, chacun
  avec une `note` d'une ligne qui dit quoi faire.

Écrire le lot dans un fichier du scratchpad :

```json
{
  "analyses": {"<id>": {"resume": "…", "tags": ["…"], "exigences": ["…"], "perimetre": "…",
                         "score": 75, "action": "…", "pourquoi": "…"}},
  "digest": {"date": "AAAA-MM-JJ", "synthese": "…", "une": [{"id": "…", "note": "…"}]}
}
```

```bash
python3 scripts/save_analyses.py <lot.json>
python3 scripts/build.py
```

Corriger les avertissements éventuels de `save_analyses.py`.

## 4. Enregistrer et publier

```bash
git add data/analyses.json data/digests.json
git commit -m "Analyse du AAAA-MM-JJ"
git push -u origin claude/wizardly-bohr-o7znla
```

Publier l'artifact privé : `file_path` = `dist/index.html`, `files` =
`{"data.json": "dist/data.json"}`, avec `url` = https://claude.ai/artifact/Fi1qZJEUHgFhvZeyjppCSM.

## 5. Sources en erreur

Si une source est en erreur deux jours de suite (`data/status.json`), chercher la
bonne URL et corriger `sources.yaml` dans le même commit, en le signalant dans la synthèse.
