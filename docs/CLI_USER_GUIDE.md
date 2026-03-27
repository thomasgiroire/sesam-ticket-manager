# Portail IRIS – Gestionnaire de tickets SESAM-Vitale

CLI Python pour gérer les tickets du **Portail IRIS** (support GIE SESAM-Vitale).

---

## Sommaire

- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Dépannage](#dépannage)

---

## Installation

**Prérequis :** Python 3.11+

```bash
cd sesam-ticket-manager/

# Créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

# Installer les dépendances
pip install -r requirements.txt
```

Avec **uv** (plus rapide) :
```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
```

Éditez `.env` :

```env
# ── Portail IRIS ──────────────────────────────────
SESAM_USERNAME=votre.email@domaine.com
SESAM_PASSWORD=votre_mot_de_passe
```

Vérifier la connexion :
```bash
python main.py status
```

---

## Utilisation

### Vérifier la connexion

```bash
python main.py status
```
Affiche l'email connecté, le statut du compte et un résumé des tickets ouverts par statut.

---

### Lister les tickets

```bash
# Tous les tickets ouverts (défaut : 50)
python main.py list

# Avec les tickets clos
python main.py list --closed

# Filtrer par statut
python main.py list --status "En attente"
python main.py list --status "Expertise externe"

# Filtrer par type
python main.py list --type Incident
python main.py list --type Demande

# Pagination
python main.py list --limit 100 --page 2

# Export JSON brut (pour scripting)
python main.py list --json-output > tickets.json
```

**Statuts disponibles :**
`Nouveau` · `En cours` · `En attente` · `Suspendu` · `En expertise` · `Expertise externe` · `Résolu`

---

### Détail d'un ticket

```bash
# Par référence (format XX-YYY-NNNNNN)
python main.py show 26-001-000001

# Par ID hexadécimal interne
python main.py show 00000000000000ab

# Export JSON
python main.py show 26-001-000001 --json-output
```

Affiche : titre, statut, priorité, service, demandeur, dates, description et les 3 derniers messages.

---

### Voir les messages d'un ticket

```bash
python main.py messages 26-001-000001
python main.py messages 26-001-000001 --limit 50
python main.py messages 26-001-000001 --json-output
```

Les messages sont nettoyés (HTML → texte lisible). Types affichés : `Extranet entrant` (message du demandeur) / `Extranet sortant` (réponse du support).

---

### Répondre à un ticket

```bash
# Mode interactif
python main.py reply 26-001-000001

# En une ligne
python main.py reply 26-001-000001 \
  --title "Complément d'information" \
  --message "Voici les logs demandés : …"
```

---

## Architecture

```
sesam-ticket-manager/
├── main.py           # CLI Click (list, show, messages, reply, status)
├── portal.py         # Client HTTP Portail IRIS (auth + parsing + cache)
├── requirements.txt  # Dépendances Python
├── .env.example      # Template de configuration
├── .env              # ⚠ Ne pas committer
└── .sesam_state.json # État local (session, tickets connus) — auto-généré
```

### Flux de données

```
Portail IRIS (JHipster Angular 11)
        │
        │  POST /api/authenticate  (cookie session)
        │  GET  /api/requests/company
        │  GET  /api/requests/{id}
        │  GET  /api/requests/{id}/messages?nbOfResult=N
        │  POST /api/requests/{id}/messages
        ▼
   portal.py  ──── .sesam_state.json (cookies + état synchro)
```

### Authentification

Le portail utilise **JHipster** avec authentification par **cookie de session** (pas de Bearer token).
Flux : `POST /api/authenticate` → cookies HttpOnly → réutilisés pour tous les appels suivants.
Les cookies sont sauvegardés dans `.sesam_state.json` et réutilisés entre les sessions.

---

## API Reference

### Endpoints confirmés

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/authenticate` | Login `{username, password, rememberMe}` |
| `GET` | `/api/account` | Infos utilisateur connecté |
| `GET` | `/api/requests/company` | Liste des tickets société |
| `GET` | `/api/requests/{id}` | Détail ticket (ID hex) |
| `GET` | `/api/requests/{id}/messages` | Messages d'un ticket (`nbOfResult` sans 's') |
| `POST` | `/api/requests/{id}/messages` | Ajouter un message `{title, description}` |
| `GET` | `/api/requests/{id}/messages/attachments` | Pièces jointes |
| `GET` | `/api/requests/services` | Services disponibles |
| `GET` | `/api/requests/qualifications` | Qualifications |
| `GET` | `/api/refvalues?tableCode=Rst` | Statuts |
| `GET` | `/api/refvalues?tableCode=Tt_` | Types de tickets |

### Structure d'un ticket

```json
{
  "id": "00000000000000ab",
  "code": "26-001-000001",
  "titre": "Titre du ticket",
  "status": { "code": "EXPEXT", "label": "Expertise externe" },
  "priority": { "code": "AVERAGE", "label": "Normal" },
  "typeTicket": { "code": "INCIDENT", "label": "Incident" },
  "service": { "id": "00023000004ecba5", "qualifs": [...] },
  "person": { "firstName": "Jean", "lastName": "DUPONT" },
  "createdAt": "2026-03-24T14:58:51",
  "updatedAt": "2026-03-24T17:09:46",
  "description": "..."
}
```

> **Note :** Le champ du titre est `titre` (français), pas `title`.
> Le label du service n'est pas dans l'objet ticket — il est résolu via `/api/requests/services`.

### Paramètres de liste

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| `notClosed` | Masquer les clos | `true` |
| `fromPageNumber` | Page (commence à 1) | `1` |
| `nbOfResults` | Résultats par page | `50` |
| `orderBy` | Champ de tri | `DmdCrDt` (création), `DmdUpDt` (MAJ) |
| `orderWay` | Sens du tri | ` DESC` ou ` ASC` |

---

## Dépannage

| Symptôme | Solution |
|----------|----------|
| `401 Identifiants incorrects` | Vérifier `SESAM_USERNAME` (email complet) et `SESAM_PASSWORD` dans `.env` |
| `Service : —` dans `show` | Mettre à jour `portal.py` (résolution via cache `/api/requests/services`) |
| Messages en HTML brut | Mettre à jour `portal.py` (parser HTML intégré) |
| Session expirée | Supprimer `.sesam_state.json` pour forcer une reconnexion |
| `ModuleNotFoundError` | Activer le venv : `source .venv/bin/activate` |

---

## Développement

```bash
# Export JSON pour inspecter les données brutes
python main.py list --json-output | python3 -m json.tool | head -100
python main.py show 26-001-000001 --json-output

# Tester la synchro sans rien créer
python main.py sync --dry-run

# Réinitialiser l'état de synchro
rm .sesam_state.json
```
