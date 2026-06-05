# SESAM Ticket Manager — Guide pour agent IA

Ce document décrit comment un agent (Claude Code, Claude Desktop, script
LLM…) peut consommer SESAM Ticket Manager via la commande globale `sesam`.

## Installation préalable

L'agent doit pouvoir exécuter `sesam` dans un shell. Vérifier :

```bash
sesam --help          # doit lister les sous-commandes
sesam status --json-output
```

Une commande complémentaire `sesam-ui` lance l'interface web.
Elle n'est pas destinée à l'agent — c'est un raccourci utilisateur —
mais l'agent peut la suggérer si l'utilisateur préfère naviguer dans l'UI.

Si la commande n'est pas trouvée, l'utilisateur doit relancer `./install.sh`
depuis le répertoire d'installation et accepter l'étape « Commande globale ».
Le wrapper résout son installation via `~/.sesam/home` ou la variable
`$SESAM_HOME`.

## Contrat de sortie

Toutes les sous-commandes utiles à un agent acceptent `--json-output`.

- **stdout** contient **uniquement** du JSON (une ligne ou un objet/array
  indenté). Aucune décoration, pas de prompt, pas de logo.
- **stderr** peut contenir des logs (auth, warnings réseau) — à ignorer pour
  le parsing.
- Code de sortie : `0` = succès, `1` = erreur API/auth, `2` = mauvaise
  utilisation (argument manquant, message vide…).
- En cas d'erreur avec `--json-output`, stdout contient :
  `{"ok": false, "error": "<message>"}`.
- Si l'erreur est due à un défaut d'authentification (identifiants
  manquants, session expirée, mot de passe changé), la sortie inclut
  aussi `"action": "run_login"` et `"hint": "Lancez `sesam login`…"`.
  **L'agent doit alors interrompre son action et demander à l'utilisateur
  d'exécuter `sesam login` dans un terminal**, puis réessayer.

## Authentification

`sesam login` et `sesam logout` sont **strictement interactifs** : pas de
flags `--username`/`--password`, pas de mode JSON. C'est volontaire — le
mot de passe ne doit jamais transiter par les arguments de ligne de
commande (visibles dans `ps`, l'historique shell, les logs d'agent).

Si l'agent reçoit `{"ok": false, "action": "run_login"}`, il doit
**répondre à l'utilisateur** quelque chose comme :

> Je ne peux pas accéder au Portail IRIS — les identifiants sont
> manquants ou la session a expiré. Lancez `sesam login` dans un
> terminal, puis redemandez-moi.

et **ne pas tenter** d'invoquer `sesam login` lui-même.

## Sous-commandes

### `sesam list [--open-only] [--status <s>] [--type Incident|Demande] [--limit N] [--page N] [--fetch-all] [--refresh] --json-output`

Liste les tickets. Sortie : `array<Ticket>`.

```bash
sesam list --json-output
sesam list --open-only --type Incident --json-output
sesam list --fetch-all --json-output
```

### `sesam show <code|id> --json-output`

Détail d'un ticket, incluant la description et les derniers messages.
La référence accepte le format `XX-YYY-NNNNNN` (ex: `26-083-026025`) ou
l'ID hexadécimal interne.

```bash
sesam show 26-083-026025 --json-output
```

### `sesam messages <code|id> [--limit N] --json-output`

Tous les messages d'un ticket. Sortie : `array<Message>`.

```bash
sesam messages 26-083-026025 --limit 50 --json-output
```

### `sesam reply <code|id> --title "..." --message "..." --json-output`

Ajoute un message à un ticket. **Non-interactif** : `--title` et `--message`
sont obligatoires ; `--json-output` implique l'absence de prompt de
confirmation.

Sortie : `{"ok": true, "message_id": "...", "ticket": "..."}`.

```bash
sesam reply 26-083-026025 \
  --title "Suivi" \
  --message "Bonjour, pourriez-vous nous tenir informés de l'avancement ?" \
  --json-output
```

### `sesam sync [--all] [--dry-run] --json-output`

Détecte les nouveaux tickets (ou tous avec `--all`) et met à jour l'état
local. `--dry-run` simule sans rien marquer.

Sortie :
```json
{
  "ok": true,
  "synced": 3,
  "dry_run": false,
  "tickets": [ { "code": "...", "status": "...", ... } ]
}
```

### `sesam status --json-output`

Vérifie l'authentification et compte les tickets ouverts par statut.

```json
{
  "ok": true,
  "account": { "email": "...", "status": "Validé", "last_login": "..." },
  "open_tickets": 31,
  "by_status": { "En cours": 1, "En attente": 6, ... }
}
```

### `sesam export <code|id> [--format markdown|json]`

Export d'un ticket complet, optimisé pour ingestion par un autre agent
(format Markdown structuré par défaut).

## Exemple de bloc à coller dans un `CLAUDE.md`

```markdown
## Outils disponibles : SESAM Ticket Manager

Tu disposes de la commande `sesam` pour interagir avec les tickets
SESAM-Vitale (Portail IRIS). Utilise systématiquement `--json-output`
pour parser la sortie.

Commandes utiles :
- `sesam status --json-output` — vérifier la connexion
- `sesam list --open-only --json-output` — tickets ouverts
- `sesam show <ref> --json-output` — détail d'un ticket
- `sesam messages <ref> --json-output` — historique des échanges
- `sesam reply <ref> --title "..." --message "..." --json-output` — répondre

Les références ont la forme `26-083-026025`. Ne réponds JAMAIS sur un
ticket sans avoir d'abord lu `sesam messages` pour comprendre le contexte.
```

## Cache et performance

La CLI maintient un cache local partagé avec l'interface web :

- **Tickets clos** : conservés indéfiniment — zéro requête API, source stable pour l'agent
- **Tickets ouverts** : rafraîchis toutes les 15 minutes
- **Liste globale** : rafraîchie toutes les 5 minutes

Pour forcer un appel API fresh, ajouter `--refresh` :
```bash
sesam show 26-083-026025 --refresh --json-output
sesam list --refresh --json-output
```

`sesam sync --json-output` est recommandé en début de session — il peuple le cache
complet (tickets clos en permanent) sans surcharger le portail.

## Limites connues

- `reply` envoie un message dès qu'il est appelé en mode `--json-output` :
  pas de garde-fou côté CLI. À l'agent de confirmer avec l'utilisateur
  avant d'appeler la commande.
- Les pièces jointes ne sont pas encore manipulables via la CLI (lecture
  seule des métadonnées dans la sortie de `messages`).
- Le portail peut renvoyer des erreurs `401` si la session a expiré
  longtemps — relance automatique transparente, sinon `{"ok": false,
  "error": "auth ..."}`.
