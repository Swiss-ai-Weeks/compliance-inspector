# Visual Compliance Inspector (Hackathon HPE & NVIDIA)

Le projet consiste à construire un système d'analyse vidéo autonome ("Agent de Conformité") capable de vérifier si un opérateur respecte à la lettre une procédure de maintenance ou d'assemblage. L'outil comprend la temporalité des actions : il valide les étapes réussies, isole les étapes manquées, et horodate chaque événement.

## 1. Ce qui est clair (Le Périmètre)
- **MVP (Livrable des 7 jours)** : Analyse différée sur une tâche d'assemblage simple (dataset IKEA-Manuals-at-Work ou Assembly101). Idéal pour une équipe de 4 personnes.
- **L'expérience utilisateur (La Démo finale)** : L'interface affiche la vidéo synchronisée avec une "checklist" intelligente. Le système coche de manière autonome les étapes : "[✓] Étape 1 complétée (00:15)", "[✗] Étape 2 manquée", et rend un verdict final.
- **Importation automatisée (Le Bonus)** : Un module annexe lit un manuel PDF via un LLM de vision. Il utilise ensuite une **passe d'auto-correction IA (NVIDIA NeMo)** pour garantir que chaque description extraite est strictement unique, préparant un JSON parfait pour l'orchestrateur.

## 2. Architecture Logicielle et Technique (Microservices)
Pour présenter une architecture digne d'une véritable entreprise (Cloud/Edge), le système est divisé en microservices :
- **Backend (FastAPI)** : Un moteur robuste en Python hébergeant la logique métier, la machine à états et les appels API.
- **Frontend (Streamlit)** : Une interface utilisateur web légère communiquant avec le backend via requêtes HTTP.
- **Stack** : Python, OpenCV/VSS, Pydantic, NVIDIA NIM (API compatibles format OpenAI).

## 3. Moteur d'Analyse (Logique Métier)
Pour gérer le traitement séquentiel de la vidéo sans surcharger l'IA, l'architecture repose sur un modèle **"Sliding Window & State Machine Intelligente"** :

- **Le Pipeline Vidéo (VSS)** : Le flux vidéo est découpé en segments (chunks) de 5 à 10 secondes avec un chevauchement (overlap) pour garder le contexte.
- **L'Orchestrateur (Machine à états en Python)** : Suit l'état de chaque étape. Pour gérer les imprévus (désordre, pauses) sans exploser les coûts d'API, il utilise une approche hybride :
  - **Mode Standard** : Demande à Cosmos de choisir parmi les 3 prochaines étapes, ou de détecter une "Pause", ou une "Transition". En cas de "Pause" ou "Transition", il attend patiemment, éliminant les erreurs de double-comptage dues aux chevauchements vidéo.
  - **Mode Recherche Globale (Recovery)** : Si Cosmos détecte une "Action Inconnue", l'orchestrateur met en pause et balaie toutes les étapes par lots de 3 **dans un ordre chronologique strict**. Il s'arrête à la première correspondance pour éviter les conflits d'actions répétées, puis émet un *Warning*.
- **L'Analyse (NVIDIA Cosmos NIM)** : Répond à des prompts à choix multiples très structurés pour maintenir l'orchestrateur synchronisé.
- **Sécurité et Formatage (NeMo Guardrails)** : *(Objectif Bonus)* Le backend utilise NVIDIA NeMo Guardrails pour brider les réponses de Cosmos et garantir la stricte conformité des formats de retour JSON/Enum (Regex/Pydantic en fallback pour assurer le MVP).
- **Confidentialité Industrielle (On-Premise NIMs)** : Le modèle de vision tourne en local sur un serveur NVIDIA RTX PRO Server 6000 (96 Go VRAM) via des conteneurs Docker NIM. **Zéro flux vidéo ne fuite sur le cloud public**, garantissant le secret industriel.
- **Résilience (Buffer Asynchrone)** : L'orchestrateur ne jette jamais de vidéo. En cas de timeout, les segments s'accumulent dans une file d'attente et sont réessayés. Le système garantit 100% de traçabilité légale.
- **Rigueur Industrielle (Enterprise-Grade)** : Le format des procédures (JSON) impose des descriptions uniques et contextualisées (ex: *« visser le 1er pied »* au lieu de *« visser »*). Cela reflète les vraies SOP (Standard Operating Procedures) industrielles et maximise l'efficacité de l'IA spatiale.

## 3. Vision à long terme (Pour le Pitch au Jury)
Ce prototype (Agentic AI) pose les bases d'un système industriel pour :
- **Intervention en temps réel** : Alerter l'opérateur avant qu'il ne fasse une erreur irréversible.
- **Base de Connaissances (RAG) & Validation** : S'intégrer aux RAG documentaires des usines. Les procédures générées par l'IA seront validées par des Ingénieurs Méthodes (Human-in-the-loop) avant déploiement.
- **Supervision Physical AI** : Auditer les actions de robots autonomes (NVIDIA Isaac) sur des chaînes de montage.
- **Contrôle Qualité Fin** : Détecter non seulement la présence d'une action, mais évaluer les défauts d'exécution.
