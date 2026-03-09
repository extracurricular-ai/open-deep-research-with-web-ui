# Open Deep Research

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue)](https://ghcr.io/s2thend/open-deep-research-with-ui)

Une réplication open source de [Deep Research d'OpenAI](https://openai.com/index/introducing-deep-research/) avec une interface web moderne — adaptée de [HuggingFace smolagents](https://github.com/huggingface/smolagents/tree/main/examples) avec une configuration simplifiée pour un auto-hébergement facile.

En savoir plus sur l'implémentation originale dans le [billet de blog HuggingFace](https://huggingface.co/blog/open-deep-research).

Cet agent atteint **55% pass@1** sur le jeu de validation GAIA, contre **67%** pour Deep Research d'OpenAI.

---

## Fonctionnalités

- **Recherche parallèle en arrière-plan** — lancez plusieurs tâches de recherche simultanément, surveillez-les indépendamment et consultez les résultats plus tard — même après avoir fermé le navigateur
- **Pipeline de recherche multi-agents** — Manager + sous-agents de recherche avec sortie en streaming en temps réel
- **Interface web moderne** — SPA basée sur Preact avec sections repliables, sélecteur de modèle et prise en charge de la copie
- **Support de modèles flexible** — Tout modèle compatible LiteLLM (OpenAI, Claude, DeepSeek, Ollama, etc.)
- **Moteurs de recherche multiples** — DuckDuckGo (gratuit), SerpAPI, MetaSo avec repli automatique
- **Historique de session** — Stockage de session basé sur SQLite avec support de relecture
- **Trois modes d'exécution** — Live (temps réel), Background (persistant), Auto-kill (one-shot)
- **Découverte automatique de modèles** — Détecte les modèles disponibles des fournisseurs configurés
- **Outils visuels et médias** — Questions-réponses sur images, analyse PDF, transcription audio, transcriptions YouTube
- **Prêt pour la production** — Docker, Gunicorn, multi-worker, vérifications de santé, configurable via JSON

**Captures d'écran :**

<div align="center">
  <img src="imgs/ui_input.png" alt="Interface d'entrée Web UI" width="800"/>
  <p><em>Interface d'entrée épurée avec sélection de modèle</em></p>

  <img src="imgs/ui_tools_plans.png" alt="Plans et outils de l'agent" width="800"/>
  <p><em>Affichage en temps réel du raisonnement de l'agent, des appels d'outils et des observations</em></p>

  <img src="imgs/ui_result.png" alt="Résultats finaux" width="800"/>
  <p><em>Réponse finale mise en évidence avec sections repliables</em></p>
</div>

---

## Recherche parallèle en arrière-plan

Les tâches de recherche approfondie sont lentes — une seule exécution peut prendre 10 à 30 minutes. La plupart des outils bloquent l'interface jusqu'à la fin de la tâche, vous forçant à attendre.

Ce projet adopte une approche différente : **lancez autant de tâches de recherche que vous le souhaitez et laissez-les s'exécuter en arrière-plan — simultanément.**

```
┌─────────────────────────────────────────────────────┐
│  Question A : "Quelles sont les dernières avancées en LLMs ?"  │  ← en cours
│  Question B : "Comparer les meilleures bases de données vectorielles en 2025"  │  ← en cours
│  Question C : "Liste de contrôle de conformité à l'AI Act de l'UE"  │  ← terminé ✓
└─────────────────────────────────────────────────────┘
        Toutes visibles dans la barre latérale. Cliquez sur n'importe laquelle pour inspecter.
```

**Comment ça fonctionne :**

1. Sélectionnez le mode d'exécution **Background** ou **Auto-kill** (par défaut)
2. Soumettez votre première question de recherche — l'agent démarre immédiatement dans un sous-processus
3. L'interface n'est pas bloquée — soumettez une deuxième question, une troisième, autant que nécessaire
4. Chaque agent s'exécute indépendamment, persistant toutes ses étapes de raisonnement et résultats dans SQLite
5. Utilisez la barre latérale pour basculer entre les sessions en cours en temps réel
6. Fermez le navigateur — en mode **Background**, les agents continuent de s'exécuter sur le serveur
7. Revenez plus tard et cliquez sur n'importe quelle session pour relire la trace complète de recherche

**Comparaison des modes d'exécution :**

| Mode | Plusieurs à la fois | Survit à la fermeture du navigateur | Interface bloquée |
|---|---|---|---|
| **Background** | ✅ | ✅ | ✗ |
| **Auto-kill** | ✅ | ✗ (arrêté à la fermeture de l'onglet) | ✗ |
| **Live** | ✗ | ✗ | ✅ |

Particulièrement utile pour :
- Les flux de travail de recherche par lots où vous mettez en file d'attente plusieurs questions liées et examinez les résultats ensemble
- Les requêtes longues où vous ne souhaitez pas maintenir un onglet ouvert
- Les équipes partageant une instance auto-hébergée avec plusieurs utilisateurs simultanés

---

## Pourquoi ce projet ?

Il existe plusieurs alternatives open source à Deep Research. Voici comment ce projet se compare :

| Fonctionnalité | **Ce projet** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / déploiement en une commande** | ✅ Image pré-construite sur GHCR | ✅ Dockerfile | ✅ Docker Compose | ❌ Manuel | ❌ Bibliothèque uniquement |
| **Frontend sans build** | ✅ Preact + htm (pas d'étape de build) | ❌ Build Next.js requis | ❌ Build Next.js requis | ❌ LangGraph Studio | — |
| **Recherche gratuite dès la sortie de la boîte** | ✅ DuckDuckGo (pas de clé requise) | ❌ API Firecrawl requise | ⚠️ Clé recommandée | ⚠️ Configurable | ✅ |
| **Agnostique en modèles** | ✅ Tout modèle LiteLLM | ✅ Fournisseurs AI SDK | ✅ Fournisseurs multiples | ✅ Configurable | ✅ |
| **Support modèles locaux** | ✅ Ollama, LM Studio | ⚠️ Limité | ✅ Ollama/Groq | ✅ | ✅ |
| **Tâches parallèles en arrière-plan** | ✅ Exécutions simultanées multiples | ❌ | ❌ | ❌ | ❌ |
| **Historique / relecture de session** | ✅ Basé sur SQLite | ❌ | ❌ | ❌ | ❌ |
| **Interface streaming** | ✅ SSE, 3 modes d'exécution | ✅ Activité en temps réel | ✅ WebSocket | ✅ Stream type-safe | ❌ |
| **Analyse visuelle / images** | ✅ Captures PDF, QA visuel | ❌ | ⚠️ Limité | ❌ | ⚠️ |
| **Audio / YouTube** | ✅ Transcription, parole | ❌ | ❌ | ❌ | ❌ |
| **Score de référence GAIA** | **55% pass@1** | — | — | — | 55% (original) |

### Avantages clés de ce projet

- **Recherche parallèle en arrière-plan** — la fonctionnalité la plus unique dans cet espace. Démarrez plusieurs tâches de recherche approfondie en même temps — chacune s'exécute comme un sous-processus indépendant, persiste tous les événements dans SQLite, et peut être surveillée ou relue indépendamment. Fermez le navigateur, revenez des heures plus tard, et vos résultats vous attendent. Aucun autre outil de recherche approfondie open source ne supporte ce flux de travail.
- **Déploiement en un seul `docker run`** — l'image pré-construite sur GHCR fonctionne sur n'importe quelle plateforme avec Docker : Linux, macOS, Windows, ARM, VMs cloud, Raspberry Pi.
- **Pas d'étape de build** — le frontend utilise Preact avec des littéraux de gabarit `htm`. Pas de Node.js, pas de `npm install`, pas de webpack. Ouvrez simplement le navigateur.
- **Gratuit par défaut** — la recherche DuckDuckGo ne nécessite pas de clé API, donc l'agent fonctionne immédiatement après l'ajout d'une seule clé API de modèle.
- **Support média plus large** — gère les PDFs, images, fichiers audio et transcriptions YouTube que d'autres projets laissent à l'utilisateur.

---

## Démarrage rapide

### 1. Cloner le dépôt

```bash
git clone https://github.com/S2thend/open-deep-research-with-ui.git
cd open-deep-research-with-ui
```

### 2. Installer les dépendances système

Le projet nécessite **FFmpeg** pour le traitement audio.

- **macOS** : `brew install ffmpeg`
- **Linux** : `sudo apt-get install ffmpeg`
- **Windows** : `choco install ffmpeg` ou télécharger depuis [ffmpeg.org](https://ffmpeg.org/download.html)

Vérifier : `ffmpeg -version`

### 3. Installer les dépendances Python

```bash
python3 -m venv venv
source venv/bin/activate  # Sous Windows : venv\Scripts\activate
pip install -e .
```

### 4. Configurer

Copiez la configuration d'exemple et ajoutez vos clés API :

```bash
cp odr-config.example.json odr-config.json
```

Modifiez `odr-config.json` pour définir votre fournisseur de modèle et vos clés API (voir [Configuration](#configuration) ci-dessous).

### 5. Lancer

```bash
# Interface web (recommandé)
python web_app.py
# Ouvrir http://localhost:5080

# CLI
python run.py --model-id "gpt-4o" "Votre question de recherche ici"
```

---

## Configuration

La configuration est gérée via `odr-config.json` (préféré) ou des variables d'environnement.

### odr-config.json

Copiez `odr-config.example.json` vers `odr-config.json` et personnalisez :

```json
{
  "model": {
    "providers": [
      {
        "name": "openai",
        "api_key": "sk-...",
        "models": ["gpt-4o", "o1", "o3-mini"]
      }
    ],
    "default": "gpt-4o"
  },
  "search": {
    "providers": [
      { "name": "DDGS" },
      { "name": "META_SOTA", "api_key": "your_key" }
    ]
  }
}
```

L'interface inclut un panneau de paramètres intégré pour la configuration côté client. La configuration côté serveur est optionnellement protégée par un mot de passe administrateur.

### Variables d'environnement

Pour Docker ou les environnements où un fichier de configuration n'est pas pratique, vous pouvez utiliser `.env` :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ENABLE_CONFIG_UI` | Activer l'interface de configuration admin via le web (`false` par défaut) |
| `CONFIG_ADMIN_PASSWORD` | Mot de passe pour les modifications de configuration côté serveur |
| `META_SOTA_API_KEY` | Clé API pour la recherche MetaSo |
| `SERPAPI_API_KEY` | Clé API pour la recherche SerpAPI |
| `DEBUG` | Activer la journalisation de débogage (`False` par défaut) |
| `LOG_LEVEL` | Niveau de verbosité des logs (`INFO` par défaut) |

> [!NOTE]
> Les clés API définies dans `odr-config.json` ont priorité sur les variables d'environnement.

### Modèles supportés

Tout modèle [compatible LiteLLM](https://docs.litellm.ai/docs/providers) fonctionne. Exemples :

```bash
python run.py --model-id "gpt-4o" "Votre question"
python run.py --model-id "o1" "Votre question"
python run.py --model-id "claude-sonnet-4-6" "Votre question"
python run.py --model-id "deepseek/deepseek-chat" "Votre question"
python run.py --model-id "ollama/mistral" "Votre question"  # modèle local
```

> [!WARNING]
> Le modèle `o1` nécessite un accès API OpenAI tier-3 : https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### Moteurs de recherche

| Moteur | Clé requise | Notes |
|---|---|---|
| `DDGS` | Non | Par défaut, DuckDuckGo gratuit |
| `META_SOTA` | Oui | MetaSo, souvent meilleur pour les requêtes en chinois |
| `SERPAPI` | Oui | Google via SerpAPI |

Plusieurs moteurs peuvent être configurés avec repli automatique — l'agent les essaie dans l'ordre.

---

## Utilisation

### Interface web

```bash
python web_app.py
# ou avec hôte/port personnalisé :
python web_app.py --port 8000 --host 0.0.0.0
```

Ouvrez `http://localhost:5080` dans votre navigateur.

**Modes d'exécution** (disponibles via le bouton divisé dans l'interface) :

| Mode | Comportement |
|---|---|
| **Live** | Sortie en streaming en temps réel ; la session se termine à la déconnexion |
| **Background** | L'agent s'exécute de manière persistante ; reconnectez-vous à tout moment pour voir les résultats |
| **Auto-kill** | L'agent s'exécute, la session est nettoyée après la fin |

### CLI

```bash
python run.py --model-id "gpt-4o" "Quelles sont les dernières avancées en informatique quantique ?"
```

### Référence GAIA

```bash
# Nécessite HF_TOKEN pour le téléchargement du jeu de données
python run_gaia.py --model-id "o1" --run-name my-run
```

---

## Déploiement

### Docker (Recommandé)

Des **images pré-construites** sont disponibles sur GitHub Container Registry :

```bash
docker pull ghcr.io/s2thend/open-deep-research-with-ui:latest

docker run -d \
  --env-file .env \
  -v ./odr-config.json:/app/odr-config.json \
  -p 5080:5080 \
  --name open-deep-research \
  ghcr.io/s2thend/open-deep-research-with-ui:latest
```

**Docker Compose** (inclut un volume pour les fichiers téléchargés) :

```bash
cp .env.example .env        # configurer les clés API
cp odr-config.example.json odr-config.json  # configurer les modèles
docker-compose up -d
docker-compose logs -f      # suivre les logs
docker-compose down         # arrêter
```

**Construire votre propre image :**

```bash
docker build -t open-deep-research .
docker run -d --env-file .env -p 5080:5080 open-deep-research
```

> [!WARNING]
> Ne jamais committer `.env` ou `odr-config.json` avec de vraies clés API dans git. Toujours passer les secrets à l'exécution.

### Gunicorn (Production)

```bash
pip install -e .
gunicorn -c gunicorn.conf.py web_app:app
```

Le fichier `gunicorn.conf.py` inclus est pré-configuré avec :
- Gestion des processus multi-workers
- Délai d'attente de 300 s pour les tâches d'agent longues
- Journalisation et gestion des erreurs appropriées

---

## Architecture

### Pipeline d'agents

```
Question de l'utilisateur
    │
    ▼
Agent Manager (CodeAgent / ToolCallingAgent)
    │  Planifie une stratégie de recherche en plusieurs étapes
    ├──▶ Sous-Agent de recherche × N
    │       │  Recherche web → navigation → extraction
    │       └──▶ Outils : DuckDuckGo/SerpAPI/MetaSo, VisitWebpage,
    │                   TextInspector, VisualQA, YoutubeTranscript
    │
    └──▶ Synthèse de la réponse finale
```

### Pipeline de streaming

```
run.py  (step_callbacks → JSON-lines sur stdout)
  │
  ▼
web_app.py  (sous-processus → Server-Sent Events)
  │
  ▼
Navigateur  (composants Preact → DOM)
```

**Types d'événements SSE :**

| Événement | Description |
|---|---|
| `planning_step` | Raisonnement et plan de l'agent |
| `code_running` | Code en cours d'exécution |
| `action_step` | Appel d'outil + observation |
| `final_answer` | Résultat de recherche terminé |
| `error` | Erreur avec détails |

### Hiérarchie DOM

```
#output
├── step-container.plan-step       (plan du manager)
├── step-container                 (étape du manager)
│   └── step-children
│       ├── model-output           (raisonnement)
│       ├── Agent Call             (code, replié)
│       └── sub-agent-container
│           ├── step-container.plan-step  (plan du sous-agent)
│           ├── step-container            (étapes du sous-agent)
│           └── sub-agent-result          (aperçu + repliable)
└── final_answer                   (bloc de résultat proéminent)
```

---

## Reproductibilité (Résultats GAIA)

Le résultat 55% pass@1 sur GAIA a été obtenu avec des données augmentées :

- Les PDFs d'une seule page et les fichiers XLS ont été ouverts et capturés en `.png`
- Le chargeur de fichiers vérifie la version `.png` de chaque pièce jointe et la préfère

Le jeu de données augmenté est disponible sur [smolagents/GAIA-annotated](https://huggingface.co/datasets/smolagents/GAIA-annotated) (accès accordé instantanément sur demande).

---

## Développement

```bash
pip install -e ".[dev]"   # inclut les outils de test, linting, vérification de types
python web_app.py         # démarre le serveur de développement avec rechargement automatique
```

Le frontend est une application Preact sans dépendances utilisant `htm` pour les gabarits de type JSX — pas d'étape de build requise. Modifiez les fichiers dans `static/js/components/` et actualisez.

---

## Licence

Sous licence **Apache License 2.0** — la même licence que [smolagents](https://github.com/huggingface/smolagents).

Voir [LICENSE](../LICENSE) pour les détails.

**Remerciements :**
- Implémentation originale de l'agent de recherche par [HuggingFace smolagents](https://github.com/huggingface/smolagents)
- Interface web, gestion de sessions, architecture de streaming et système de configuration ajoutés dans ce fork
