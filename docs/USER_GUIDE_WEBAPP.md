# Guide utilisateur — Interface Web SESAM Ticket Manager

## Prérequis

Avant de lancer l'interface web, assurez-vous que :

1. Votre fichier `.env` contient au minimum :
   ```
   SESAM_USERNAME=votre@email.fr
   SESAM_PASSWORD=votre_mot_de_passe
   ```
2. Les dépendances Python sont installées :
   ```bash
   pip install -r requirements.txt
   ```

---

## Lancement de l'application

```bash
uvicorn web_app:app --reload --port 8473
```

L'interface est accessible à l'adresse : **http://localhost:8473**

> Le flag `--reload` active le rechargement automatique lors de modifications du code (pratique en développement). En production, omettez-le.

---

## Pages disponibles

### 1. Dashboard — `GET /`

La page d'accueil affiche une synthèse de vos tickets :

| Zone | Description |
|------|-------------|
| **Compteurs** | Nombre total, ouverts et clos |
| **Répartition par statut** | Histogramme des statuts, trié par fréquence |
| **Activité récente** | Les 15 derniers tickets modifiés ou actifs |
| **Indicateur de cache** | Âge du cache disque (ex: "il y a 5 min") |
| **Résumé du dernier refresh** | Tickets détectés comme modifiés lors du dernier refresh |

**Hot tickets** : les tickets mis à jour dans les dernières 24 heures sont marqués 🔥.

---

### 2. Liste des tickets — `GET /tickets`

Affiche tous les tickets (ouverts et clos) avec des options de filtrage.

#### Colonnes du tableau

| Colonne | Description |
|---------|-------------|
| Référence | Code du ticket (ex: 26-083-026025) |
| Titre | Titre tronqué |
| Statut | Badge coloré selon l'état |
| Priorité | Badge coloré selon l'urgence |
| Auteur | Prénom Nom du demandeur |
| Mis à jour | Date de dernière modification |
| 🔥 | Indicateur hot ticket (< 24h) |

#### Filtres disponibles

- **Filtre par statut** : cliquer sur un badge de statut dans la colonne gauche
- **Filtre par type** : sélectionner "Incident" ou "Demande"
- **Recherche textuelle** (`?q=`) : recherche dans le titre, la référence, l'auteur et le service
- **Effacer les filtres** : bouton "✕ Effacer les filtres"

#### Exemple d'URL avec filtres

```
http://localhost:8473/tickets?status=En+cours&type=Incident&q=SESAM
```

---

### 3. Détail d'un ticket — `GET /tickets/{ticket_id}`

Affiche les informations complètes d'un ticket.

#### Panneau de métadonnées

- Référence, Type, Statut, Priorité
- Service, Qualification
- Demandeur
- Dates de création, mise à jour et clôture

#### Historique des messages

Les messages sont affichés chronologiquement (du plus ancien au plus récent).

- **Messages du client** (INEXTRANET) : bulles alignées à droite, fond bleu
- **Messages du support** (INTRANET) : bulles alignées à gauche, fond gris

Chaque message affiche :
- La date d'envoi
- Le contenu texte (HTML nettoyé)
- Les pièces jointes avec leur nom et type MIME

#### Pièces jointes

Cliquer sur le nom d'une pièce jointe lance le téléchargement via le proxy intégré.
Cliquer sur l'icône 👁 (si disponible) ouvre la pièce jointe directement dans le navigateur.

#### Export

Bouton **"Exporter"** disponible en haut de la page de détail :
- `?fmt=markdown` (défaut) : document Markdown structuré pour agents DUST
- `?fmt=json` : JSON normalisé

URL directe : `GET /tickets/{id}/export?fmt=markdown`

---

### 4. Créer un ticket — `GET /tickets/create`

Formulaire de création d'une nouvelle demande de support.

#### Champs

| Champ | Obligatoire | Description |
|-------|-------------|-------------|
| **Titre** | ✅ | Titre court et descriptif |
| **Description** | ✅ | Détail du problème ou de la demande |
| **Service** | Non | Service concerné (liste chargée depuis le portail) |
| **Qualification** | Non | Catégorie de la demande |
| **Priorité** | Non | AVERAGE (défaut), HIGH, URGENT |

Après soumission réussie, vous êtes redirigé vers la page de détail du nouveau ticket.

> **Note** : le formulaire crée toujours une demande de type `DEMANDE`. Pour les incidents, utilisez la CLI : `python main.py` (création d'incident non exposée dans la web app).

---

### 5. Répondre à un ticket — `POST /tickets/{id}/reply`

Depuis la page de détail, un formulaire de réponse est disponible en bas de page.

#### Options

- **"Envoyer"** : envoie le message sans modifier le statut du ticket
- **"Envoyer et résoudre"** : envoie le message ET passe le ticket en statut Résolu en une seule action

Le cache des messages du ticket est invalidé automatiquement après envoi.

---

### 6. Résoudre un ticket — `POST /tickets/{id}/resolve`

Bouton **"Résoudre le ticket"** sur la page de détail (sans message).

Cette action :
1. Appelle `PUT /api/requests/{id}/solve` sur le portail IRIS
2. Invalide le cache des messages et le cache global des tickets
3. Redirige vers la page de détail (ticket désormais résolu)

---

### 7. Rafraîchissement du cache

Le cache (mémoire + disque) a une durée de vie de **1 heure** par défaut.

Deux boutons de rafraîchissement sont disponibles sur le dashboard :

#### Refresh intelligent (delta) — `POST /refresh`

Comportement :
1. Récupère la liste complète des tickets (métadonnées uniquement)
2. Compare avec le cache existant pour détecter les changements de statut ou `updated_at`
3. Télécharge les messages uniquement pour les tickets modifiés
4. Met à jour le cache mémoire et disque
5. Redirige vers `/` avec `?updated=N` (N = nombre de tickets modifiés)

Recommandé pour une utilisation régulière — beaucoup plus rapide que le refresh complet.

#### Refresh complet — `POST /refresh/full`

- Vide le cache mémoire et supprime `.sesam_web_cache.json`
- Force le rechargement de toutes les données depuis le portail au prochain accès

À utiliser si les données semblent incohérentes ou corrompues.

---

## API JSON

L'application expose un endpoint JSON pour les intégrations :

### `GET /api/tickets`

Retourne la liste des tickets filtrée au format JSON.

**Paramètres query string :**
| Paramètre | Description |
|-----------|-------------|
| `status` | Filtre exact sur le statut |
| `type` | Filtre sur le type ("Incident" ou "Demande") |
| `q` | Recherche textuelle dans le titre et la référence |

**Exemple :**
```bash
curl "http://localhost:8473/api/tickets?status=En+cours&q=SESAM"
```

**Réponse :**
```json
{
  "tickets": [
    {
      "id": "00294000001e8cbd",
      "code": "26-083-026025",
      "titre": "Problème connexion SESAM",
      "status": "En cours",
      "priority": "Normal",
      "type_ticket": "Incident",
      ...
    }
  ]
}
```

### `GET /api/tickets/{id}/messages/raw`

Debug uniquement : retourne les données brutes des messages avec la structure des pièces jointes.

---

## Fichier de cache disque

Le fichier `.sesam_web_cache.json` est créé dans le répertoire de travail.
Il persiste entre les redémarrages du serveur pendant 1 heure maximum.

Pour supprimer le cache manuellement :
```bash
rm .sesam_web_cache.json
```

---

## Dépannage

| Symptôme | Solution |
|----------|----------|
| Page d'erreur 503 au démarrage | Vérifier SESAM_USERNAME et SESAM_PASSWORD dans .env |
| Données périmées affichées | Cliquer sur "Refresh" ou "Refresh complet" |
| Pièces jointes non téléchargeables | Session expirée — cliquer sur "Refresh" pour renouveler la session |
| Erreur lors de la création de ticket | Vérifier que les champs Titre et Description sont remplis |
| Lenteur au premier chargement | Normal — les données sont récupérées depuis le portail (10-30s selon le volume) |
