# Portail IRIS – Gestionnaire de tickets SESAM-Vitale

CLI Python pour gérer les tickets du **Portail IRIS** (support GIE SESAM-Vitale) et les synchroniser vers **Jira** et **Slack**.

---

## Sommaire

- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Intégration Jira](#intégration-jira)
- [Intégration Slack](#intégration-slack)
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

# ── Jira (optionnel) ──────────────────────────────
JIRA_URL=https://votre-org.atlassian.net
JIRA_EMAIL=votre.email@domaine.com
JIRA_API_TOKEN=votre_api_token          # https://id.atlassian.com/manage/api-tokens
JIRA_PROJECT_KEY=SUP                    # Clé du projet Jira cible
JIRA_ISSUE_TYPE=Task                    # Type d'issue (Task, Bug, Story…)

# ── Slack (optionnel) ─────────────────────────────
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
# OU (token bot)
SLACK_BOT_TOKEN=xoxb-votre-token
SLACK_CHANNEL=#support-sesam
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

# Avec notification Slack
python main.py reply 26-001-000001 \
  --title "Mise à jour" \
  --message "Ticket résolu côté éditeur." \
  --notify-slack
```

---

### Synchroniser vers Jira + Slack

```bash
# Sync des nouveautés uniquement (recommandé en usage quotidien)
python main.py sync

# Sync de tous les tickets (premier lancement)
python main.py sync --all

# Simuler sans rien créer
python main.py sync --dry-run

# Inclure les tickets clos
python main.py sync --closed

# Jira uniquement
python main.py sync --no-slack

# Slack uniquement
python main.py sync --no-jira
```

La commande `sync` :
1. Récupère les tickets depuis le portail
2. Détecte les nouveaux et les modifiés depuis la dernière synchro (via `.sesam_state.json`)
3. Crée ou met à jour les issues Jira correspondantes
4. Envoie les notifications Slack
5. Mémorise l'état pour la prochaine synchro

---

## Intégration Jira

### Prérequis

1. Générer un **API Token** : https://id.atlassian.com/manage/api-tokens
2. Renseigner dans `.env` : `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`

### Comportement

- Chaque ticket SESAM crée une issue Jira avec le label `sesam-vitale`
- Le titre Jira est `[SESAM-26-001-000001] Titre du ticket`
- Si l'issue existe déjà (même référence), elle est **mise à jour** (pas de doublon)
- La description Jira contient : métadonnées, lien vers le portail, description, derniers messages
- Mapping des priorités : `Normal → Medium`, `Haute → High`, `Critique → Highest`

---

## Intégration Slack

### Option A : Webhook (recommandé)

1. https://api.slack.com/apps → Create App → Incoming Webhooks → Activate
2. "Add New Webhook to Workspace" → choisir le channel
3. Copier l'URL dans `SLACK_WEBHOOK_URL`

### Option B : Bot Token

1. Créer une app Slack avec le scope `chat:write`
2. Installer dans le workspace
3. Renseigner `SLACK_BOT_TOKEN` et `SLACK_CHANNEL`

### Notifications envoyées

| Événement | Contenu |
|-----------|---------|
| Nouveau ticket | Titre, référence, statut, priorité, service, demandeur, lien portail + Jira |
| Ticket mis à jour | Référence, nouveau statut, date de mise à jour |
| Résumé synchro | Nombre de tickets créés / mis à jour / en erreur |
| Nouveau message | Extrait du message, lien vers le ticket |

---

## Architecture

```
sesam-ticket-manager/
├── main.py           # CLI Click (list, show, messages, reply, sync, status)
├── portal.py         # Client HTTP Portail IRIS (auth + parsing + cache)
├── jira_client.py    # Intégration Jira (création/MAJ issues)
├── slack_client.py   # Intégration Slack (webhooks + Block Kit)
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
        │
   ┌────┴────┐
   ▼         ▼
jira_client  slack_client
(REST API)   (Webhooks / SDK)
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
| Jira : `401` | Vérifier que `JIRA_API_TOKEN` est un token API (pas le mot de passe) |
| Slack : message non reçu | Vérifier que le webhook est actif et l'URL complète dans `.env` |

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
