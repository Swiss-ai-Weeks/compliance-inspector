# Visual Compliance Inspector
**HPE & NVIDIA Agentic AI Hackathon**

## 1. Description du Projet
Le **Visual Compliance Inspector** est un système de contrôle qualité industriel basé sur l'IA Agentique. Il analyse des flux vidéo pour vérifier en temps réel (ou quasi temps réel) si un opérateur respecte scrupuleusement une procédure d'assemblage (SOP). 

Le système est conçu pour être résilient aux anomalies fréquentes : actions dans le désordre, pauses, occlusions visuelles, et chevauchements temporels.

## 2. Architecture Technique (Microservices)

L'application est séparée en deux couches pour refléter une architecture d'entreprise (Cloud/Edge) :

### Backend (Moteur d'Analyse)
- **Framework** : FastAPI (Python)
- **Validation des données** : Pydantic
- **Traitement Vidéo** : OpenCV (cv2) / NVIDIA VSS (découpage en segments avec chevauchement)
- **Orchestrateur** : Machine à états en Python avec file d'attente asynchrone (Buffer) pour la résilience API.
- **Intégration IA** :
  - *NVIDIA Cosmos NIM* : Analyse vidéo (Actions de l'opérateur).
  - *NVIDIA Nemotron Vision* : Extraction du manuel PDF vers JSON.
  - *NVIDIA NeMo Guardrails* (Bonus) : Formatage et sécurité des réponses LLM.

### Frontend (Interface Utilisateur)
- **Framework** : Streamlit (Python)
- **Communication** : Requêtes HTTP (`requests`) vers l'API FastAPI.
- **Fonctionnalités** : Upload de vidéo, checklist dynamique, rapport de conformité final.

## 3. Prérequis
- Python 3.10 ou supérieur
- Clé API NVIDIA (NGC) / Accès Docker pour les NIMs locaux
- `ffmpeg` installé sur la machine
- **Brev.dev CLI** (pour le développement d'équipe)

## 4. Environnement de Développement (Architecture Hybride)
Pour garder un développement rapide et ne pas alourdir l'équipe avec des configurations Docker complexes en local, nous adoptons une approche **Hybride** :

- **Le Cerveau (Machine AWS Brev RTX 6000)** : Cette machine distante ne fait tourner *que* les modèles d'IA (NVIDIA Cosmos et Nemotron) via des conteneurs Docker (NIM). Une fois lancés, ils exposent une API sur le port `57258`.
- **Le Code (Vos PC Windows & Mac)** : Les développeurs codent le Backend (FastAPI) et le Frontend (Streamlit) directement sur leur machine locale en utilisant un simple environnement virtuel Python (`venv`). Pas de Docker en local !
- **Attention (Compatibilité OS)** : Puisque l'équipe est mixte (Windows et Mac), utilisez toujours la librairie Python `pathlib` ou `os.path.join` pour manipuler les chemins des fichiers vidéos, afin d'éviter les bugs liés aux slashs (`/` vs `\`).

## 5. Configuration de l'environnement (Sur votre PC local)

1. **Cloner le projet et créer un environnement virtuel :**
   ```bash
   git clone <votre_repo>
   cd nvidia-hackathon
   python -m venv venv
   ```

2. **Activer l'environnement :**
   - *Windows* : `venv\Scripts\activate`
   - *Linux/Mac* : `source venv/bin/activate`

3. **Installer les dépendances :**
   *(Note : le fichier requirements.txt sera généré lors de la phase d'implémentation)*
   ```bash
   pip install fastapi uvicorn streamlit pydantic opencv-python requests openai
   ```

4. **Variables d'environnement :**
   Créez un fichier `.env` à la racine :
   ```env
   NVIDIA_API_KEY=votre_cle_api_ici
   BACKEND_URL=http://localhost:8000
   ```

## 5. Lancer l'Application

L'architecture nécessite de lancer le backend et le frontend séparément.

**Terminal 1 : Lancer le Backend (FastAPI)**
```bash
# Depuis la racine du projet
uvicorn backend.main:app --reload --port 8000
```
L'API sera disponible sur : `http://localhost:8000` (Documentation Swagger : `http://localhost:8000/docs`)

**Terminal 2 : Lancer le Frontend (Streamlit)**
```bash
# Depuis la racine du projet
streamlit run frontend/app.py
```
L'interface sera disponible sur : `http://localhost:8501`
