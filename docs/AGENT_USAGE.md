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

## Démarrage de session — base de connaissances

**À chaque début de session**, l'agent doit charger la totalité des tickets :

```bash
sesam list --fetch-all --json-output
```

Cette commande retourne **tous** les tickets (ouverts et clos) depuis le cache
local. Elle constitue la **base de connaissances métier** de l'agent : historique
des demandes, réponses du GIE, précédents de conformité.

- Si le cache est chaud (< 15 min), aucune requête réseau — réponse instantanée.
- Si le cache est froid, les tickets sont rechargés depuis le Portail IRIS et
  mis en cache pour les prochains appels.

> Ne jamais travailler uniquement sur `sesam list` (50 tickets par défaut) —
> utiliser systématiquement `--fetch-all` pour avoir une vue complète.

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

## Installer le skill Claude Code

Pour utiliser `sesam` comme skill natif dans Claude Code (invocation automatique
quand vous mentionnez un ticket GIE) :

```bash
# 1. Générer le guide d'usage
sesam skill-creator > /tmp/sesam-agent-usage.md

# 2. Créer le dossier skill
mkdir -p ~/.claude/skills/sesam

# 3. Générer le SKILL.md à partir du guide
# (coller le contenu dans ~/.claude/skills/sesam/SKILL.md
#  ou demander à Claude de créer le skill depuis ce guide)
```

Le skill est ensuite invoqué automatiquement par Claude quand vous mentionnez
"ticket GIE", "Portail IRIS", ou posez une question du type
"qu'est-ce que le GIE a répondu sur X".

---

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

La CLI partage un cache local avec l'interface web (`.sesam_cache.json`) :

| Donnée | TTL | Invalidation |
|---|---|---|
| Liste complète des tickets | 15 min | Expiré ou `--fetch-all` |
| Messages d'un ticket | 24 h | `updated_at` du ticket change |

**Première exécution** : si aucun ticket n'est encore connu, `sesam list` fait
automatiquement un `--fetch-all` et peuple le cache complet.

Pour forcer un appel API fresh sur la liste, utiliser `--fetch-all` :
```bash
sesam list --fetch-all --json-output
```

`sesam sync --json-output` est recommandé en début de session — il détecte
les nouveaux tickets et met à jour `known_tickets` sans re-fetcher les messages
déjà en cache.

## Stratégie d'accès aux données : JSON direct vs search

L'agent peut accéder aux données de deux façons. Le bon choix dépend du volume.

**Règle simple :**

| Situation | Approche recommandée |
|---|---|
| Début de session / base de connaissances | `sesam list --fetch-all --json-output` |
| Ticket spécifique déjà identifié | `sesam show <ref>` + `sesam messages <ref>` |
| Filtrage sur volume important | Flags CLI (`--open-only`, `--status`, `--type`) |

**Pourquoi `--fetch-all` par défaut :** les tickets clos contiennent les réponses
du GIE sur les précédents de conformité — c'est la mémoire métier. Ne charger
que les tickets ouverts revient à travailler sans historique.

**Cas 1 — Base de connaissances complète (recommandé)**

```bash
# Charger TOUS les tickets (ouverts + clos) — base de connaissances métier
sesam list --fetch-all --json-output
```

L'agent lit la sortie complète et filtre lui-même par raisonnement. Aucun
round-trip supplémentaire.

**Cas 2 — Filtrage CLI (quand le volume est grand)**

```bash
# Ne charger que les incidents en attente
sesam list --type Incident --status "En attente" --json-output

# Limiter à une page
sesam list --limit 20 --page 1 --json-output
```

Les flags réduisent la taille de la réponse avant qu'elle n'entre dans le
contexte.

**Cas 3 — Ticket spécifique (toujours préférer `show`)**

Pour un ticket déjà identifié, ne jamais charger la liste entière :

```bash
sesam show 26-083-026025 --json-output
sesam messages 26-083-026025 --json-output
```

**Note sur les tokens :** `sesam list --fetch-all` peut retourner plusieurs
centaines de tickets. Réserver cet usage à la synchronisation initiale
(`sesam sync`), pas à chaque question de l'utilisateur.

## Limites connues

- `reply` envoie un message dès qu'il est appelé en mode `--json-output` :
  pas de garde-fou côté CLI. À l'agent de confirmer avec l'utilisateur
  avant d'appeler la commande.
- Les pièces jointes ne sont pas encore manipulables via la CLI (lecture
  seule des métadonnées dans la sortie de `messages`).
- Le portail peut renvoyer des erreurs `401` si la session a expiré
  longtemps — relance automatique transparente, sinon `{"ok": false,
  "error": "auth ..."}`.
