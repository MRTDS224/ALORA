# Prompt: Nous reprenons exactement ce projet. Considère ce document comme le contexte de référence pour toutes les réponses suivantes.

# CONTEXTE DU PROJET ALORA (À LIRE AVANT DE CONTINUER)

Nous travaillons sur un projet de recherche personnel appelé **ALORA (Automatic Learning for Oral Resource-poor African Languages)**.

L'objectif à long terme est de développer une méthodologie générale permettant de créer des ressources et des modèles d'IA pour des langues africaines peu dotées, en prenant le **soussou (Guinée)** comme premier cas d'étude.

---

# Vision du projet

Le projet est volontairement découpé en plusieurs phases.

## Phase 1 (été)

Construire les ressources.

Le professeur m'a conseillé de concentrer tout le stage sur :

- collecte
- transcription
- segmentation
- annotation
- préparation des données pour les futures modélisations

L'objectif N'EST PAS de construire un modèle IA cet été.

Le livrable principal doit être un **corpus oral de qualité**, documenté et réutilisable.

---

## Phase 2 (S5)

Début de la modélisation.

Quelques exemples :

- représentations de la parole
- wav2vec2
- HuBERT
- MMS
- clustering
- découverte d'unités phonologiques

---

## Phase 3 (PFE)

Travaux avancés :

- apprentissage de la langue
- induction d'un système d'écriture
- premières applications

---

# Première application

Nous allons développer une plateforme de collecte.

Frontend :

- Flutter

Backend :

- FastAPI

Base de données :

- PostgreSQL

Stockage des audios :

- Object Storage (MinIO ou S3)

Pipeline :

Collecte
→ Validation
→ Transcription
→ Segmentation
→ Annotation
→ Corpus ALORA

---

# Architecture du corpus

Nous voulons nous inspirer du corpus **WAXAL**, sans le copier.

Le corpus devra être compatible avec les futurs outils de Speech AI.

Organisation actuelle :

```
alora-corpus/

audio/
    raw/
    validated/
    segmented/

metadata/
    speakers.csv
    recordings.csv
    prompts.csv
    sessions.csv

transcriptions/
    manual/
    reviewed/
    automatic/

annotations/
    words/
    quality/
    metadata/

exports/
    train/
    validation/
    test/

documentation/
```

---

# Documents déjà réalisés

Nous avons produit un premier document :

Document 0.1

Note de cadrage

Puis nous avons commencé un second document.

Document 0.2

Conception technique de la première phase.

Arborescence actuelle :

```
main.tex

sections/

introduction.tex

objectifs.tex

architecture_technique.tex

architecture_donnees.tex

methodologie.tex

outils.tex

questions.tex

references.bib
```

---

# Philosophie de travail

Nous voulons construire le projet comme dans un laboratoire de recherche.

Cela signifie :

- architecture avant code
- base de données avant backend
- pipeline avant modèles IA
- corpus avant apprentissage

Autrement dit :

Data First.

---

# Ce que ChatGPT m'a conseillé

Ne pas construire simplement une application.

Construire :

- un corpus scientifique
- une architecture robuste
- une méthodologie reproductible

Le corpus est le véritable livrable.

L'application Flutter n'est qu'un moyen de le construire.

---

# Ce qu'il reste à faire

Le document de conception n'est pas terminé.

Il manque encore :

- améliorer les schémas TikZ
- ajouter le schéma UML de la base PostgreSQL
- concevoir entièrement la base de données
- concevoir les API FastAPI
- définir précisément la structure des métadonnées
- étudier réellement WAXAL afin d'en reprendre les bonnes pratiques
- définir les conventions de nommage
- définir les formats d'annotation
- préparer l'implémentation

---

# IMPORTANT

Je ne veux pas que ChatGPT me donne simplement du code.

Je veux qu'il agisse comme un **co-encadrant de recherche**.

Je souhaite qu'il critique mes idées lorsqu'elles sont mauvaises, propose des alternatives plus pertinentes et privilégie les pratiques utilisées dans les laboratoires de recherche plutôt que les solutions les plus simples.

L'objectif est de construire un projet suffisamment solide pour évoluer vers un PFE puis, potentiellement, un doctorat.

Avant toute implémentation importante, je souhaite que l'architecture soit validée et justifiée.