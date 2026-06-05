# Guide utilisateur — CLI `sesam`

La commande `sesam` permet de gérer les tickets du Portail IRIS depuis un terminal.
Elle est disponible depuis n'importe où après l'installation (`./install.sh`).

---

## Sommaire

- [Authentification](#authentification)
- [Lister les tickets](#lister-les-tickets)
- [Détail d'un ticket](#détail-dun-ticket)
- [Messages d'un ticket](#messages-dun-ticket)
- [Répondre à un ticket](#répondre-à-un-ticket)
- [Exporter un ticket](#exporter-un-ticket)
- [Synchroniser l'état local](#synchroniser-létat-local)
- [Vérifier la connexion](#vérifier-la-connexion)
- [Cache local](#cache-local)
- [Mode JSON pour les scripts](#mode-json-pour-les-scripts)
- [Dépannage](#dépannage)

---

## Authentification

```bash
sesam login     # Configurer ou mettre à jour vos identifiants Portail IRIS
sesam logout    # Supprimer la session locale (les identifiants sont conservés)
```

> `sesam login` est **interactif uniquement** — le mot de passe ne transite jamais
> en argument. Utilisez-le depuis un terminal après un changement de mot de passe
> ou une session bloquée.

---

## Lister les tickets

```bash
# Tous les tickets (ouverts + clos)
sesam list

# Tickets ouverts uniquement
sesam list --open-only

# Filtrer par statut
sesam list --status "En attente"
sesam list --status "En cours"

# Filtrer par type
sesam list --type Incident
sesam list --type Demande

# Forcer la mise à jour depuis le portail (ignore le cache)
sesam list --refresh
```

**Statuts disponibles :**
`Nouveau` · `En cours` · `En attente` · `Suspendu` · `En expertise` · `Expertise externe` · `Résolu` · `Clos`

---

## Détail d'un ticket

```bash
# Par référence (format XX-YYY-NNNNNN)
sesam show 26-083-026025

# Par ID hexadécimal interne
sesam show 00294000001e8cbd

# Forcer la mise à jour depuis le portail
sesam show 26-083-026025 --refresh
```

Affiche : titre, statut, priorité, service, demandeur, dates, description et les 3 derniers messages.

---

## Messages d'un ticket

```bash
# 20 derniers messages (défaut)
sesam messages 26-083-026025

# Changer la limite
sesam messages 26-083-026025 --limit 50

# Forcer la mise à jour depuis le portail
sesam messages 26-083-026025 --refresh
```

Les messages sont nettoyés (HTML → texte lisible).
Types : `Extranet entrant` (message du demandeur) / `Extranet sortant` (réponse du support).

---

## Répondre à un ticket

```bash
# Mode interactif (prompts)
sesam reply 26-083-026025

# En une ligne
sesam reply 26-083-026025 \
  --title "Complément d'information" \
  --message "Bonjour, voici les éléments demandés : …"

# Sans confirmation (mode script)
sesam reply 26-083-026025 \
  --title "Suivi" \
  --message "Avez-vous pu avancer sur ce point ?" \
  --yes
```

> Le cache du ticket et de ses messages est automatiquement invalidé après l'envoi.

---

## Exporter un ticket

```bash
# Format Markdown (défaut) — idéal pour ingestion par un agent IA
sesam export 26-083-026025

# Format JSON structuré
sesam export 26-083-026025 --format json
```

---

## Synchroniser l'état local

```bash
# Détecter les nouveaux tickets et tickets modifiés
sesam sync

# Traiter tous les tickets (pas seulement les nouveautés)
sesam sync --all

# Simuler sans modifier l'état
sesam sync --dry-run

# Forcer le rechargement complet depuis le portail
sesam sync --refresh
```

`sesam sync` peuple également le **cache partagé** avec les tickets clos en cache permanent.
L'interface web (`sesam-ui`) bénéficie immédiatement de ces données.

---

## Vérifier la connexion

```bash
sesam status
```

Affiche : email connecté, statut du compte, nombre de tickets ouverts par statut.

---

## Cache local

La CLI maintient un cache local dans `.sesam_cache.json` (partagé avec l'interface web) :

| Type de données | Durée de conservation |
|---|---|
| Tickets **clos** (détail + messages) | **Permanent** — jamais expiré |
| Tickets **ouverts** (détail) | 15 minutes |
| Messages d'un ticket ouvert | 5 minutes |
| Liste globale de tickets | 5 minutes |

**Avantages :**
- Zéro requête API pour les tickets clos — source d'information statique pour les agents
- Protège contre le rate limiting du portail (max ~30 requêtes/page)
- `sesam sync` → cache permanent peuplé → `sesam-ui` sert les données immédiatement

**Forcer un rafraîchissement :** ajoutez `--refresh` à n'importe quelle commande.

---

## Mode JSON pour les scripts

Toutes les commandes acceptent `--json-output` pour une sortie machine-readable :

```bash
sesam list --json-output
sesam show 26-083-026025 --json-output
sesam messages 26-083-026025 --json-output
sesam status --json-output
sesam sync --json-output
sesam reply 26-083-026025 \
  --title "Suivi" --message "…" \
  --json-output
```

- **stdout** : uniquement du JSON (pas de logo, pas de décorations)
- **stderr** : logs et warnings (ignorer pour le parsing)
- **Code de sortie** : `0` succès, `1` erreur API/auth, `2` mauvaise utilisation
- **Erreur JSON** : `{"ok": false, "error": "..."}`
- **Auth expirée** : `{"ok": false, "action": "run_login"}` → lancer `sesam login`

Voir [AGENT_USAGE.md](AGENT_USAGE.md) pour le contrat complet.

---

## Dépannage

| Symptôme | Solution |
|---|---|
| `sesam: command not found` | Ajouter `~/.local/bin` au `$PATH` (voir sortie de `./install.sh`) |
| `401 Identifiants incorrects` | `sesam login` pour mettre à jour le mot de passe |
| Session expirée | `sesam logout` puis relancer (re-auth automatique) |
| Données obsolètes | Ajouter `--refresh` à la commande |
| Cache corrompu | Supprimer `.sesam_cache.json` dans le dossier d'installation |
