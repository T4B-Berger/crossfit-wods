# AGENTS.md

## Mission
Construire un projet Python simple et maintenable pour collecter, parser, enrichir et explorer l’historique des WODs CrossFit.

## Priorités
1. Robustesse du scraping incrémental
2. Reprise sur incident
3. Qualité du parsing
4. Normalisation métrique
5. Interface Streamlit simple
6. Préparation d’une future brique d’aide à la programmation

## Contraintes
- Outils gratuits prioritairement
- Pas de scraping en production
- Batch offline uniquement pour la collecte
- Streamlit lit un dataset figé
- SQLite = source de vérité
- Parquet/CSV = exports
- Code Python simple, modulaire, lisible

## Règles de données
- Conserver les données source brutes
- Conserver les unités source
- Calculer en plus la version SI
- Ne jamais inventer une donnée source absente
- Toute inférence doit indiquer méthode + confiance

## Référentiels métier
- Unités SI : kg, m, s
- Filières énergétiques :
  - aérobie
  - anaérobie lactique
  - anaérobie alactique
  - mixte
  - indéterminée

## Statuts
- fetch_status : pending, success, not_found, timeout, http_error, network_error
- page_type : wod, rest_day, editorial_only, not_found, unknown
- record_status : valid_wod, valid_rest_day, missing_page, editorial_ignored, needs_review

## Anti-objectifs
- Pas d’infra complexe
- Pas de backend séparé tant que non nécessaire
- Pas de LLM au cœur du scraping
- Pas d’agent autonome tant que le pipeline de données n’est pas fiable

## Cadre de modification
Quand tu modifies le code :
- privilégie les petits changements testables
- ajoute ou ajuste les tests si pertinent
- documente brièvement les choix structurants
- garde les scripts exécutables dans Colab et localement
