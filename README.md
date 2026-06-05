# SESAM Ticket Manager

🎫 **Gestionnaire de tickets** pour le **Portail IRIS** (support GIE SESAM-Vitale)

**CLI Python + API Web** pour gérer vos tickets de support de manière efficace.

---

## 🚀 Quick Start

### Installation

```bash
curl -fsSL https://github.com/thomasgiroire/sesam-ticket-manager/releases/latest/download/setup.sh | bash
```

C'est tout. Le script télécharge la release, extrait les fichiers dans `~/Applications/sesam-ticket-manager` et lance l'installation guidée qui :
- Vérifie Python 3.11+
- Crée un environnement Python isolé dans `run/.venv`
- Vous demande vos identifiants SESAM
- Configure le port web
- **Installe deux commandes globales** : `sesam` (CLI) et `sesam-ui` (interface web)

> **Répertoire personnalisé :** `SESAM_INSTALL_DIR=~/mon-dossier bash <(curl -fsSL ...)`

### Démarrer

```bash
sesam-ui          # interface web — s'ouvre dans votre navigateur
sesam list        # CLI — lister les tickets depuis le terminal
```

### Désinstallation

```bash
curl -fsSL https://github.com/thomasgiroire/sesam-ticket-manager/releases/latest/download/uninstall.sh | bash
```

Supprime les commandes globales (`sesam`, `sesam-ui`), le virtualenv (`run/`), et le fichier de localisation (`~/.sesam/home`). Le code source est conservé.

> Pour supprimer sans confirmation : `curl -fsSL ... | bash -s -- --force`

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

- **[Agent Usage Guide](docs/AGENT_USAGE.md)** — Utiliser `sesam` depuis un agent IA
  - Contrat de sortie JSON (`--json-output`)
  - Schémas des commandes
  - Snippet `CLAUDE.md` prêt à coller

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

### Interface web (`sesam-ui`)
- Dashboard synthétique (compteurs, tickets récents, hot tickets 🔥)
- Liste filtrée par statut, type, recherche textuelle
- Détail ticket + messages chronologiques
- Réponses et résolution directes
- Refresh intelligent : seuls les tickets modifiés sont rechargés

**→ Lancée via `sesam-ui`** depuis n'importe quel terminal.

### CLI (`sesam`)
Une fois `./install.sh` lancé, la commande `sesam` est disponible depuis
n'importe quel terminal :

```bash
sesam login                        # (Re)configurer les identifiants Portail IRIS
sesam logout                       # Supprimer la session locale

sesam list                         # Lister tous les tickets
sesam list --open-only             # Tickets ouverts uniquement
sesam list --status "En attente"   # Filtrer par statut
sesam list --refresh               # Forcer la mise à jour depuis le portail

sesam show <ref>                   # Détail d'un ticket
sesam messages <ref>               # Voir les messages
sesam reply <ref>                  # Répondre à un ticket (interactif)
sesam export <ref>                 # Exporter en Markdown (par défaut) ou JSON

sesam sync                         # Synchroniser l'état local
sesam status                       # Vérifier la connexion
```

> `sesam login` et `sesam logout` sont **strictement interactifs**
> (le mot de passe n'est jamais passé en argument). Utilisez-les depuis
> un terminal pour changer de compte ou réinitialiser une session bloquée.

**Cache local intelligent** : les tickets clos sont conservés indéfiniment
(source statique pour les agents). Les tickets ouverts sont rafraîchis
automatiquement. `sesam sync` peuple le cache — l'interface web bénéficie
immédiatement des données sans appel API supplémentaire.

Toutes les commandes acceptent `--json-output` pour une sortie structurée,
exploitable par un script ou un agent IA. Voir [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md).

> Si `sesam` n'est pas trouvée, c'est que `~/.local/bin` n'est pas dans
> votre `$PATH` — `./install.sh` affiche la ligne `export` à ajouter à
> votre `~/.zshrc`.

### 🤖 Usage par un agent IA

Le tool est conçu pour être appelable par un agent type Claude depuis le
poste de travail. La commande `sesam` est globale, non-interactive en
mode `--json-output`, et chaque sortie est un objet JSON stable.

Exemple minimal de configuration dans un `CLAUDE.md` (ou prompt système) :

```markdown
Tu disposes de la commande `sesam` pour interagir avec les tickets
SESAM-Vitale. Utilise toujours `--json-output`.

- `sesam status --json-output`
- `sesam list --open-only --json-output`
- `sesam show <ref> --json-output`
- `sesam messages <ref> --json-output`
- `sesam reply <ref> --title "..." --message "..." --json-output`

Si une commande retourne `{"ok": false, "action": "run_login"}`,
NE TENTE PAS de te connecter toi-même. Demande à l'utilisateur de
lancer `sesam login` dans un terminal, puis réessaie.
```

Le contrat complet (stdout JSON, stderr logs, codes de sortie, schémas)
est documenté dans **[docs/AGENT_USAGE.md](docs/AGENT_USAGE.md)**.

---

## 🏗️ Architecture

```
sesam-ticket-manager/
├── main.py                  # CLI Click (exposition terminal)
├── web_app.py               # Interface web FastAPI (exposition HTTP)
├── ticket_store.py          # Couche domaine partagée CLI + WebUI
├── cache.py                 # Moteur cache : disque atomique + LRU mémoire
├── portal.py                # HTTP Client (auth + API Portail IRIS)
├── config.py                # Configuration centralisée
├── utils.py                 # Utilitaires
├── exceptions.py            # Exceptions personnalisées
├── requirements.txt         # Dépendances Python
├── .env.example             # Template configuration
├── bin/                     # Wrappers globaux (installés par install.sh)
│   ├── sesam                # Commande CLI globale
│   └── sesam-ui             # Lance l'interface web
├── run/                     # Dossier d'exécution (créé par install.sh)
│   ├── .venv/               # Environnement Python
│   ├── .env                 # Configuration (identifiants, port)
│   ├── .sesam_state.json    # Session (cookies)
│   └── .sesam_cache.json    # Cache partagé CLI + WebUI
├── docs/
│   ├── AGENT_USAGE.md       # Contrat CLI pour agent IA
│   ├── CLI_USER_GUIDE.md
│   ├── USER_GUIDE_WEBAPP.md
│   ├── API_REVERSE_ENGINEERING_GUIDE.md
│   ├── ARCHITECTURE.md
│   └── EXAMPLES.md
└── tests/                   # Tests pytest (127 tests)
```

**Cache partagé** : `ticket_store.py` est la couche commune entre CLI et WebUI.
Les deux interfaces lisent et écrivent le même `.sesam_cache.json` —
un `sesam sync` en terminal se reflète immédiatement dans l'interface web.

> `~/.sesam/home` contient le chemin d'installation, lu par les wrappers
> `sesam` et `sesam-ui`. La variable `$SESAM_HOME` peut l'override explicitement.

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

- **Rate limiting** — Le portail accepte max ~30 requêtes/page ; le cache local protège contre les appels répétitifs
- **HTML non échappé** — Sanitizer intégré avant affichage
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
| `401 Identifiants incorrects` | `sesam login` pour les mettre à jour |
| Données obsolètes | `sesam list --refresh` ou `sesam sync --refresh` pour forcer l'API |
| Session expirée | `sesam logout` puis relancer une commande (re-auth automatique) |
| Port 8473 déjà utilisé | `./install.sh` trouvera un port libre automatiquement |
| L'app n'ouvre pas le navigateur | Accédez manuellement à `http://localhost:8473` |
| `sesam: command not found` | Ajouter `~/.local/bin` au `$PATH` (voir sortie de `./install.sh`) ou relancer `./install.sh` |
| Wrapper pointe sur mauvais dossier | Vérifier `cat ~/.sesam/home`, ou définir `export SESAM_HOME=/chemin/install` |

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
