# ALORA — Brief de travail pour Codex / agents de développement

## 1. Contexte du projet

ALORA signifie **Automatic Learning for Oral Resource-poor African Languages**.

Le projet est un projet de recherche personnel visant à développer une méthodologie générale pour construire des ressources et, à terme, des modèles d'IA pour des langues africaines peu dotées. Le **soussou (Guinée)** est le premier cas d'étude.

Le livrable scientifique principal n'est pas l'application elle-même : c'est un **corpus oral de qualité, documenté, reproductible et réutilisable**.

Le principe directeur est :

> **Data First**
>
> Architecture avant code, base de données avant backend, pipeline avant modèles IA, corpus avant apprentissage.

La première phase est consacrée à :
- collecte ;
- validation ;
- transcription ;
- segmentation ;
- annotation ;
- préparation des données pour les futures modélisations.

Il ne faut donc pas construire prématurément un modèle d'IA.

---

# 2. Décision actuelle sur la stack

La première idée était Flutter pour le frontend.

**Cette décision est abandonnée.**

La plateforme de collecte sera une application web simple :

- **HTML**
- **CSS**
- JavaScript minimal lorsque nécessaire
- **FastAPI**
- **PostgreSQL**
- **MinIO / S3** pour les fichiers audio
- **Jinja2** pour rendre les pages HTML côté serveur
- SQLAlchemy pour l'accès à PostgreSQL
- Alembic pour les migrations

Architecture :

```text
                    Navigateur
                        |
                   HTML/CSS/JS
                        |
                        v
                     FastAPI
                    /       \
                   /         \
                  v           v
             PostgreSQL     MinIO/S3
             métadonnées    fichiers audio
```

Le navigateur ne doit pas communiquer directement avec PostgreSQL.

---

# 3. Objectif immédiat

Le délai est très court.

Le site de collecte doit être fonctionnel **au plus tard le 10 septembre**.

Il faut donc privilégier :

1. une architecture correcte ;
2. un MVP fonctionnel ;
3. la collecte réelle ;
4. la robustesse des données ;

avant :
- animations ;
- design sophistiqué ;
- fonctionnalités secondaires ;
- abstractions inutiles.

Le site doit permettre de réaliser le parcours complet :

```text
Locuteur
   ↓
Session
   ↓
Prompt
   ↓
Enregistrement audio
   ↓
Upload
   ↓
Stockage MinIO
   ↓
Métadonnées PostgreSQL
   ↓
Validation
   ↓
Transcription
   ↓
Révision
```

---

# 4. Architecture scientifique du corpus

Le modèle conceptuel retenu est :

```text
Speaker
   1
   |
   N
Session
   1
   |
   N
Recording
   N
   |
   1
Prompt
```

Un enregistrement peut ensuite avoir :

```text
Recording
   |
   +---- Transcriptions
   |
   +---- Quality annotations
   |
   +---- Segments
   |
   +---- Word annotations
```

Le schéma PostgreSQL initial comporte donc **8 tables principales** :

```text
speakers
sessions
prompts
recordings
transcriptions
quality_annotations
segments
word_annotations
```

---

# 5. Table `speakers`

Représente un locuteur participant au corpus.

Champs prévus :

```text
id
speaker_code
age_group
gender
region
location
native_language
other_languages
consent_status
created_at
updated_at
```

Contraintes :

- `id` : UUID, clé primaire
- `speaker_code` : unique, non nul
- ne pas stocker inutilement le nom complet ou les coordonnées personnelles dans le corpus scientifique
- utiliser un identifiant pseudonymisé tel que `SPK_000001`

Exemple :

```text
speaker_code    = SPK_000001
age_group       = 18-25
gender          = female
region          = Kindia
native_language = Susu
consent_status  = granted
```

---

# 6. Table `sessions`

Une session correspond à une séance de collecte.

Champs :

```text
id
session_code
speaker_id
recorded_at
location
environment
device
collector
notes
created_at
```

Relation :

```text
speakers 1 ---- N sessions
```

Une même personne peut avoir plusieurs sessions.

Exemple :

```text
SPK_000001
    |
    +-- SES_000001
    |      +-- REC_000001
    |      +-- REC_000002
    |
    +-- SES_000002
           +-- REC_000003
```

---

# 7. Table `prompts`

Un prompt est le stimulus donné au locuteur.

Champs :

```text
id
prompt_code
prompt_type
title
description
content
language
topic
difficulty
active
created_at
```

Types de prompts envisagés :

```text
image
question
topic
sentence
story
free_speech
```

Ne pas sur-normaliser ces valeurs immédiatement. Le système doit rester suffisamment flexible pendant les premières collectes.

L'objectif est d'éviter de limiter ALORA à la simple lecture de phrases.

Le corpus doit pouvoir contenir :
- parole lue ;
- parole semi-dirigée ;
- parole spontanée ;
- descriptions ;
- réponses à des questions ;
- récits ;
- conversations ou productions plus naturelles à terme.

---

# 8. Table `recordings`

C'est la table centrale.

Champs :

```text
id
recording_code
session_id
prompt_id
audio_object_key
duration_seconds
sample_rate
channels
format
file_size_bytes
recording_status
created_at
updated_at
```

Contraintes :

- `recording_code` unique ;
- `session_id` obligatoire ;
- `prompt_id` peut être nullable pour certains types de parole libre ;
- `audio_object_key` obligatoire après upload ;
- durée et caractéristiques audio doivent être enregistrées lorsque disponibles.

Exemple :

```text
recording_code = REC_000001
session_id     = SES_000001
prompt_id      = PRM_000012

audio_object_key =
raw/2026/09/03/REC_000001.wav
```

---

# 9. Stockage des audios

**Ne jamais stocker les fichiers audio binaires dans PostgreSQL.**

PostgreSQL conserve :

```text
audio_object_key
```

MinIO/S3 conserve le fichier.

Architecture :

```text
PostgreSQL
    |
    | audio_object_key
    v
MinIO
    |
    +-- raw/...
    +-- validated/...
    +-- segmented/...
```

Organisation cible :

```text
alora-storage/
|
+-- raw/
|   +-- YYYY/
|       +-- MM/
|           +-- DD/
|               +-- REC_000001.wav
|
+-- validated/
|   +-- REC_000001.wav
|
+-- segmented/
|   +-- REC_000001_SEG_0001.wav
|
+-- exports/
```

Important :

Le déplacement physique d'un fichier ne doit pas être utilisé comme source de vérité pour son état.

**L'état d'un enregistrement appartient à PostgreSQL.**

MinIO contient les objets.
PostgreSQL contient leur état et leurs métadonnées.

---

# 10. Statut des recordings

Workflow initial :

```text
uploaded
   ↓
validating
   ↓
validated
   ↓
transcribed
   ↓
reviewed
   ↓
accepted
```

Avec possibilité de :

```text
rejected
```

Le statut permet de savoir où se trouve chaque donnée dans le pipeline.

---

# 11. Table `transcriptions`

Une transcription peut avoir plusieurs versions.

Champs :

```text
id
recording_id
text
language
transcription_type
transcription_status
transcriber
reviewer
confidence
version
created_at
updated_at
```

Relation :

```text
recording 1 ---- N transcriptions
```

Exemple :

```text
REC_000001

v1 → automatic
v2 → manual
v3 → reviewed
v4 → final
```

Il faut conserver l'historique plutôt que d'écraser systématiquement la transcription précédente.

Contrainte :

```text
UNIQUE(recording_id, version)
```

---

# 12. Table `quality_annotations`

La qualité audio doit être indépendante de la transcription.

Champs :

```text
id
recording_id
audio_quality
noise_level
clipping
speech_present
multiple_speakers
reviewer
notes
created_at
```

Exemple :

```text
audio_quality     = good
noise_level       = low
clipping          = false
speech_present    = true
multiple_speakers = false
```

Cette table permet de documenter pourquoi un enregistrement est accepté ou rejeté.

---

# 13. Table `segments`

Un `recording` n'est pas forcément un segment.

Exemple :

```text
REC_000001.wav
        |
        +-- SEG_000001
        +-- SEG_000002
        +-- SEG_000003
```

La table doit au minimum permettre de stocker :

```text
id
recording_id
segment_code
start_time
end_time
audio_object_key
created_at
updated_at
```

La segmentation appartient au pipeline de traitement, pas au formulaire de collecte initial.

---

# 14. Table `word_annotations`

Version minimale initiale.

Champs :

```text
id
recording_id
transcription_id
word
start_time
end_time
normalized_form
annotation_type
value
annotator
created_at
```

Cette structure doit rester flexible.

Exemples futurs :

```text
annotation_type = POS
value           = noun
```

ou :

```text
annotation_type = language
value           = fr
```

ou :

```text
annotation_type = code_switch
value           = true
```

Ne pas essayer de construire dès maintenant un système complet d'annotation phonétique, morphologique, syntaxique, etc.

---

# 15. Identifiants

Utiliser des UUID comme identifiants techniques PostgreSQL.

En parallèle, utiliser des codes lisibles pour le corpus :

```text
SPK_000001
SES_000001
PRM_000001
REC_000001
SEG_000001
```

Les UUID servent à la base et aux relations internes.

Les codes servent à l'identification humaine et aux exports.

---

# 16. Index PostgreSQL minimum

Créer au minimum des index sur :

```text
sessions.speaker_id
recordings.session_id
recordings.prompt_id
recordings.recording_status
transcriptions.recording_id
quality_annotations.recording_id
segments.recording_id
word_annotations.recording_id
```

---

# 17. Architecture FastAPI

Arborescence recommandée :

```text
alora/
|
+-- app/
|   |
|   +-- main.py
|   |
|   +-- core/
|   |   +-- config.py
|   |   +-- database.py
|   |
|   +-- models/
|   |   +-- speaker.py
|   |   +-- session.py
|   |   +-- prompt.py
|   |   +-- recording.py
|   |   +-- transcription.py
|   |   +-- quality.py
|   |   +-- segment.py
|   |   +-- annotation.py
|   |
|   +-- schemas/
|   |   +-- speaker.py
|   |   +-- session.py
|   |   +-- prompt.py
|   |   +-- recording.py
|   |   +-- transcription.py
|   |
|   +-- routers/
|   |   +-- speakers.py
|   |   +-- sessions.py
|   |   +-- prompts.py
|   |   +-- recordings.py
|   |   +-- transcriptions.py
|   |   +-- quality.py
|   |
|   +-- services/
|   |   +-- storage.py
|   |   +-- recording.py
|   |   +-- transcription.py
|   |
|   +-- templates/
|       +-- base.html
|       +-- dashboard.html
|       +-- speakers/
|       +-- sessions/
|       +-- recordings/
|       +-- transcriptions/
|
+-- static/
|   +-- css/
|   +-- js/
|
+-- migrations/
|
+-- docker-compose.yml
+-- requirements.txt
+-- .env
```

Jinja2 doit être utilisé pour les pages HTML côté serveur.

---

# 18. Pages MVP

Ne pas créer trop de pages.

## Dashboard

Afficher au minimum :

```text
Nombre de locuteurs
Nombre de sessions
Nombre d'enregistrements
Nombre d'enregistrements validés
Nombre à transcrire
Nombre rejetés
```

---

## Gestion des locuteurs

Page :

```text
/speakers
```

Fonctions :

- liste ;
- recherche ;
- création ;
- consultation.

Formulaire :

```text
speaker_code
age_group
gender
region
location
native_language
other_languages
consent_status
```

---

## Gestion des sessions

Page :

```text
/sessions
```

Fonctions :

- créer une session ;
- associer un locuteur ;
- renseigner les conditions de collecte ;
- voir les enregistrements de la session.

---

## Gestion des prompts

Page :

```text
/prompts
```

Fonctions :

- créer ;
- modifier ;
- activer/désactiver ;
- consulter.

---

## Collecte

Page :

```text
/record
```

C'est la page la plus importante.

Elle doit :

1. sélectionner un locuteur/session ;
2. afficher un prompt ;
3. permettre l'enregistrement depuis le navigateur ;
4. afficher la durée ;
5. permettre d'arrêter/reprendre si nécessaire ;
6. envoyer l'audio à FastAPI ;
7. créer le recording ;
8. stocker l'audio dans MinIO ;
9. enregistrer les métadonnées dans PostgreSQL ;
10. afficher clairement le succès ou l'échec.

---

## Validation

Page :

```text
/recordings
/recordings/{id}
```

Permettre :

- écouter l'audio ;
- consulter les métadonnées ;
- évaluer la qualité ;
- valider ;
- rejeter ;
- ajouter une note.

---

## Transcription

Page :

```text
/transcriptions/{recording_id}
```

Permettre :

- écouter l'audio ;
- saisir une transcription ;
- sauvegarder ;
- modifier ;
- conserver les versions ;
- marquer comme reviewed/final.

---

# 19. API minimale

Prévoir des routes similaires à :

```text
GET  /api/speakers
POST /api/speakers
GET  /api/speakers/{id}

GET  /api/sessions
POST /api/sessions
GET  /api/sessions/{id}

GET  /api/prompts
POST /api/prompts
GET  /api/prompts/{id}

GET  /api/recordings
POST /api/recordings
GET  /api/recordings/{id}

POST /api/recordings/{id}/validate
POST /api/recordings/{id}/reject

GET  /api/transcriptions/{recording_id}
POST /api/transcriptions
PUT  /api/transcriptions/{id}

POST /api/quality
```

Les noms exacts peuvent être adaptés, mais garder une séparation claire entre ressources.

---

# 20. Workflow de collecte réel

Le workflow cible est :

```text
1. Créer / sélectionner un speaker
             ↓
2. Créer une session
             ↓
3. Sélectionner un prompt
             ↓
4. Enregistrer l'audio
             ↓
5. Upload vers FastAPI
             ↓
6. Stocker dans MinIO
             ↓
7. Créer le recording PostgreSQL
             ↓
8. Vérifier automatiquement les caractéristiques
             ↓
9. Validation humaine
             ↓
10. Transcription
             ↓
11. Révision
             ↓
12. Export corpus
```

Ce workflow doit fonctionner avant de travailler sur le design.

---

# 21. Audio

Pour le MVP, privilégier un format adapté au corpus, idéalement :

```text
WAV
mono
16 kHz
```

Mais ne pas détruire ou réencoder aveuglément l'original.

Le système doit distinguer le fichier brut de ses éventuelles versions validées/traitées.

Si le navigateur produit un autre format, prévoir une étape explicite de conversion/normalisation plutôt que de prétendre que le fichier est déjà conforme.

---

# 22. Sécurité et données personnelles

Le corpus scientifique doit être pseudonymisé.

Ne pas afficher ou exporter inutilement :

- noms complets ;
- numéros de téléphone ;
- adresses personnelles ;
- informations sensibles.

Le consentement doit être enregistré avant l'utilisation scientifique de la donnée.

Pour le MVP, ne pas construire un système complexe de gestion d'identité si ce n'est pas nécessaire au fonctionnement immédiat, mais ne jamais concevoir la base en supposant que les données personnelles doivent être mélangées au corpus public.

---

# 23. Ce qu'il NE faut PAS faire

Ne pas :

- recréer une architecture Flutter ;
- construire un SPA React/Vue/etc. sans nécessité ;
- mettre les audios en `BYTEA` dans PostgreSQL ;
- mettre toute la logique dans `main.py` ;
- mélanger modèles SQLAlchemy et logique métier ;
- écraser les transcriptions précédentes ;
- considérer les noms de fichiers comme source de vérité ;
- commencer par les animations/UI ;
- construire un modèle IA maintenant ;
- construire immédiatement un système d'annotation linguistique complet ;
- multiplier les tables sans besoin scientifique clair ;
- ajouter de la complexité uniquement parce qu'elle est techniquement possible.

---

# 24. Priorités absolues

Ordre de travail :

```text
PRIORITÉ 1
PostgreSQL + modèles + migrations

PRIORITÉ 2
FastAPI + connexion DB

PRIORITÉ 3
MinIO + service de stockage

PRIORITÉ 4
Speaker / Session / Prompt

PRIORITÉ 5
Recording + upload audio

PRIORITÉ 6
Validation

PRIORITÉ 7
Transcription

PRIORITÉ 8
Dashboard

PRIORITÉ 9
UI / CSS / amélioration visuelle
```

---

# 25. Principe de développement

Chaque implémentation importante doit être justifiée par rapport au corpus.

Toujours se demander :

> Est-ce que cette décision améliore la qualité, la traçabilité, la reproductibilité ou la réutilisabilité du corpus ?

Si non, elle n'est probablement pas prioritaire.

L'application est un outil de production de données scientifiques.

Le corpus est le produit principal.

---

# 26. Premier objectif technique

Le premier jalon doit être :

```text
docker compose up
        ↓
PostgreSQL fonctionne
        ↓
MinIO fonctionne
        ↓
Alembic fonctionne
        ↓
tables créées
        ↓
FastAPI démarre
        ↓
création d'un speaker
        ↓
création d'une session
        ↓
création/sélection d'un prompt
        ↓
enregistrement audio
        ↓
upload MinIO
        ↓
recording PostgreSQL
        ↓
lecture audio
```

Une fois ce parcours fonctionnel, le reste devient principalement du développement incrémental.

---

# 27. Niveau d'exigence

Le projet doit être développé comme un prototype de recherche sérieux, pas comme une simple application CRUD.

Les décisions doivent rester compatibles avec :

- constitution d'un corpus scientifique ;
- reproductibilité ;
- traçabilité ;
- évolution vers des expériences Speech AI ;
- export de datasets ;
- séparation train/validation/test ;
- futures annotations linguistiques ;
- évolution vers le PFE et éventuellement des travaux de recherche plus avancés.

Mais le délai impose une règle :

> **Construire aujourd'hui uniquement les fondations nécessaires pour ne pas bloquer ces évolutions demain.**

Ne pas sur-architecturer.

---

# 28. Travail demandé à l'agent

Commencer par inspecter le dépôt existant.

Ne pas réécrire inutilement ce qui existe déjà.

Avant de modifier une architecture importante :

1. identifier ce qui existe ;
2. vérifier les dépendances ;
3. vérifier les fichiers de configuration ;
4. vérifier le schéma de base existant ;
5. proposer les modifications ;
6. implémenter ;
7. tester.

Si une décision existante contredit ce document, signaler explicitement le conflit avant de la remplacer.

Les décisions scientifiques concernant le schéma de données ne doivent pas être changées silencieusement.

---

# 29. Definition of Done du MVP

Le MVP est considéré comme fonctionnel lorsque l'on peut effectuer entièrement :

```text
Créer un locuteur
      ↓
Créer une session
      ↓
Choisir un prompt
      ↓
Enregistrer une phrase / production orale
      ↓
Uploader l'audio
      ↓
Stocker l'audio dans MinIO
      ↓
Enregistrer ses métadonnées dans PostgreSQL
      ↓
Retrouver l'enregistrement
      ↓
Lire l'audio
      ↓
Valider / rejeter
      ↓
Ajouter une transcription
      ↓
Réviser la transcription
```

Et que les données restent cohérentes après redémarrage de l'application.

---

# 30. Philosophie finale

ALORA n'est pas simplement :

```text
une application qui enregistre des voix.
```

C'est :

```text
une infrastructure légère permettant de construire
un corpus oral scientifique pour une langue africaine peu dotée.
```

Toute décision technique doit garder cette finalité en tête.

**Data First.**
