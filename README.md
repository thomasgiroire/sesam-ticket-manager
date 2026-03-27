# SESAM Ticket Manager

🎫 **Gestionnaire de tickets** pour le **Portail IRIS** (support GIE SESAM-Vitale)

**CLI Python + API Web** pour gérer vos tickets de support de manière efficace.

---

## 🚀 Quick Start

### Installation

```bash
# Télécharger la dernière version
curl -L -o sesam-ticket-manager.zip \
  https://github.com/thomasgiroire/sesam-ticket-manager/releases/latest/download/sesam-ticket-manager.zip

# Extraire et accéder au dossier
unzip -d sesam-ticket-manager sesam-ticket-manager.zip
cd sesam-ticket-manager

# Rendre les scripts exécutables
chmod +x install.sh start.sh

# Lancer l'installation guidée
./install.sh
```

L'installation va :
- Vérifier/installer Homebrew et Python 3.11+
- Créer un environnement Python dans `run/.venv`
- Installer les dépendances
- Vous demander vos identifiants SESAM
- Configurer le port web

### Démarrer l'application

```bash
./start.sh
```

L'app s'ouvre automatiquement dans votre navigateur sur `http://localhost:8473`

---

## 📖 Documentation

### 👤 Pour les utilisateurs

- **[CLI User Guide](docs/CLI_USER_GUIDE.md)** — Guide complet d'utilisation de la CLI
  - Lister, afficher, répondre à des tickets
  - Filtrer par statut, type, pagination
  - Export JSON

- **[Web App Guide](docs/USER_GUIDE_WEBAPP.md)** — Interface web FastAPI
  - Architecture de la webapp
  - Endpoints disponibles
  - Configuration avancée

### 🔧 Pour les développeurs

- **[API Reverse Engineering Guide](docs/API_REVERSE_ENGINEERING_GUIDE.md)** — Exploration poussée du Portail IRIS
  - 14+ endpoints découverts et documentés
  - Architecture Efficy 11 CRM + JHipster
  - Exemples complets avec requêtes HTTP
  - Quirks et limitations identifiées

- **[API Reference](docs/API.md)** — Démarrage rapide API
  - Vue d'ensemble endpoints
  - Premiers pas d'implémentation
  - Checklist pour ajouter un nouvel endpoint

- **[Examples](docs/EXAMPLES.md)** — Exemples cURL et Python
  - Requêtes pratiques
  - Patterns de filtrage
  - Solutions aux problèmes courants

- **[Architecture](docs/ARCHITECTURE.md)** — Stack technique détaillée
  - Efficy 11 CRM (backend découvert)
  - Authentification JHipster
  - Modèle de données
  - Observations sécurité

---

## 📊 Fonctionnalités

### Web App
- Interface web intuitive
- Listage et recherche de tickets
- Détails ticket + messages
- Réponses directes
- Authentification automatique

**→ Accédée via `./start.sh`**

### CLI (optionnel)
Pour utiliser la CLI avancée :

```bash
# Activer l'environnement Python
source run/.venv/bin/activate

# Commandes disponibles
python main.py list                    # Lister les tickets
python main.py show <ref>              # Détail d'un ticket
python main.py messages <ref>          # Voir les messages
python main.py reply <ref>             # Répondre à un ticket
python main.py status                  # Vérifier la connexion
```

---

## 🏗️ Architecture

```
sesam-ticket-manager/
├── install.sh               # Script d'installation guidée
├── start.sh                 # Script de démarrage
├── main.py                  # CLI Click
├── portal.py                # HTTP Client (authentification + API Portail)
├── web_app.py               # Application web FastAPI
├── config.py                # Configuration centralisée
├── utils.py                 # Utilitaires
├── exceptions.py            # Exceptions personnalisées
├── requirements.txt         # Dépendances Python
├── .env.example             # Template configuration
├── run/                     # Dossier d'exécution (créé par install.sh)
│   ├── .venv/              # Environnement Python
│   ├── .env                # Configuration (généré)
│   └── .sesam_state.json   # État local (cookies, session)
├── docs/
│   ├── CLI_USER_GUIDE.md
│   ├── API_REVERSE_ENGINEERING_GUIDE.md
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── EXAMPLES.md
│   ├── USER_GUIDE_WEBAPP.md
│   └── REVERSE_ENGINEERING.md
└── tests/                   # Tests pytest
```

---

## 🔐 Authentification

Le Portail IRIS utilise **JHipster avec cookies de session** (pas de Bearer tokens).

Les identifiants SESAM sont configurés lors de `./install.sh` et stockés dans `run/.env`.

Les sessions sont automatiquement gérées et persistées dans `run/.sesam_state.json`.

---

## 🛠️ Dépendances

- **Python 3.11+**
- **FastAPI** — Web framework
- **Click** — CLI framework
- **requests** — HTTP client
- **pytest** — Tests

Voir `requirements.txt` pour la liste complète.

---

## 📋 État d'implémentation

| Fonctionnalité | Statut |
|--|--|
| Authentification | ✅ Implémentée |
| Lister tickets | ✅ Implémentée |
| Afficher ticket | ✅ Implémentée |
| Voir messages | ✅ Implémentée |
| Répondre | ✅ Implémentée |
| Web API | ✅ Implémentée |
| Créer tickets | ✅ Implémentée |
| Upload fichiers | ✅ Implémentée |
| Modifier tickets | 🚀 À faire |

---

## ⚠️ Limitations & Quirks

- **Sans rate limiting** — Respecter max 30 requêtes/page
- **HTML non échappé** — Sanitizer avant affichage
- **Pas de bulk operations** — Requêtes individuelles
- **Pagination simple** — Pas de cursors, numérotation par page

Pour plus de détails → [API Reverse Engineering Guide](docs/API_REVERSE_ENGINEERING_GUIDE.md#quirks--limitations)

---

## 🧪 Tests

```bash
pytest                      # Lancer tous les tests
pytest -v                   # Verbose
pytest --cov               # Coverage report
```

---

## 🐛 Dépannage

| Symptôme | Solution |
|--|--|
| `401 Identifiants incorrects` | Vérifier email + password demandés par `./install.sh` |
| Service : — manquant | Mettre à jour le cache des services (CLI) |
| Session expirée | Supprimer `run/.sesam_state.json` |
| Port 8473 déjà utilisé | `./install.sh` trouvera un port libre automatiquement |
| `ModuleNotFoundError` | Activer l'env via `source run/.venv/bin/activate` |
| L'app n'ouvre pas le navigateur | Accédez manuellement à `http://localhost:8473` |

Pour plus d'aide CLI → [CLI User Guide - Dépannage](docs/CLI_USER_GUIDE.md#dépannage)

---

## 📚 Ressources

- [OpenAPI Specification](docs/openapi.yaml) — Spec 3.0 formelle (14+ endpoints)
- [Efficy 11 Patterns](docs/EFFICY_11_PATTERNS.md) — Patterns identifiés du backend
- [Reverse Engineering Details](docs/REVERSE_ENGINEERING.md) — Analyse complète HAR file

---

## 📝 Licence

[À définir]

---

## 💬 Questions?

1. **Utilisation CLI** → Voir [CLI User Guide](docs/CLI_USER_GUIDE.md)
2. **Développement d'API** → Voir [API Reverse Engineering Guide](docs/API_REVERSE_ENGINEERING_GUIDE.md)
3. **Exemples** → Voir [Examples](docs/EXAMPLES.md)
4. **Architecture** → Voir [Architecture](docs/ARCHITECTURE.md)

---

**Généré pour le Portail IRIS du GIE SESAM-Vitale**

Stack découvert: **Efficy 11 CRM** + **JHipster** + **Angular 11**
