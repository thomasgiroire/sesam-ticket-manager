# Reverse-Engineering du Portail IRIS SESAM-Vitale

## 📋 Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Endpoints découverts](#endpoints-découverts)
3. [Authentification](#authentification)
4. [Quirks et limitations](#quirks-et-limitations)
5. [Structures de données](#structures-de-données)
6. [Notes de sécurité](#notes-de-sécurité)

---

## Vue d'ensemble

**Site**: https://portail-support.sesam-vitale.fr/gsvextranet/
**API Base**: https://portail-support.sesam-vitale.fr/gsvextranet/api

### Découverte initiale
- **Méthode**: Analyse de HAR file (Network logs du navigateur)
- **Date**: 2026-03-26
- **Endpoints trouvés**: 14 GET endpoints (lecture seule)
- **Endpoints manquants**: POST/PUT/PATCH/DELETE (à tester)

### Technology Stack identifié
- **Frontend**: Angular 11+ (bundles détectés: polyfills.bundle.js, main.bundle.js, global.bundle.js)
- **Backend**: JHipster (authentification par session cookies)
- **API Format**: JSON + REST

---

## Endpoints découverts

### Niveau de validation
- ✅ **Validé**: Endpoint confirmé dans HAR file, réponse JSON complète capturée
- ⚠️ **À valider**: Endpoint hypothétique basé sur patterns
- ❌ **Non observé**: Non présent dans HAR file

### 1. Authentication & Account

#### GET /api/account ✅
Récupère les informations de l'utilisateur actuellement authentifié.

**Réponse exemple**:
```json
{
  "id": "0002400001661d4b",
  "email": "nom@mail.com",
  "applicationLanguage": {
    "id": "0002300000002ee4",
    "code": "fr_FR",
    "label": "Français"
  },
  "timeZone": {
    "id": "0002400000003f4c",
    "code": "Europe/Paris",
    "label": "Europe/Paris"
  },
  "status": {
    "id": "...",
    "label": "Actif"
  }
}
```

**Quirks**:
- Pas de paramètres requêtes
- Retourne toujours le compte connecté
- Utilisé pour valider la session

---

### 2. Tickets

#### GET /api/requests/company ✅
Liste les tickets de la société. **Endpoint principal pour lister**.

**Paramètres**:
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `notClosed` | boolean | true | Filtrer les tickets fermés |
| `fromPageNumber` | int | 1 | Numéro de la page |
| `nbOfResults` | int | 30 | Résultats par page ⚠️ Avec 's' (not 'nbOfResult') |
| `orderBy` | string | DmdCrDt | Champ de tri |
| `orderWay` | string | " DESC" | Direction de tri |

**Réponse**:
```json
{
  "objectsList": [
    {
      "id": "00294000001e8cbd",
      "code": "26-083-026025",
      "title": null,
      "description": "...",
      "status": {
        "code": "ENCOURS",
        "label": "En cours"
      },
      "priority": {
        "code": "AVERAGE",
        "label": "Normal"
      },
      "typeTicket": {
        "code": "INCIDENT",
        "label": "Incident"
      },
      "service": {
        "id": "...",
        "label": "Support technique"
      },
      "qualification": {
        "id": "...",
        "code": "...",
        "label": "..."
      },
      "person": {
        "id": "...",
        "firstName": "Jean",
        "lastName": "Dupont"
      },
      "createdAt": "2026-03-24T14:50:18+01:00",
      "updatedAt": "2026-03-26T18:42:45+01:00",
      "closedAt": null
    }
  ],
  "totalSize": 42,
  "pageSize": 30
}
```

**Quirks**:
- `title` peut être `null` (le "titre" est en fait dans `description`)
- `description` contient du HTML + texte formaté
- Ordre de tri par défaut: `DmdCrDt DESC` (date création descendant)
- Max 30 résultats par requête (pagination obligatoire)

---

#### GET /api/requests ✅
Équivalent de `/requests/company`. Mêmes paramètres.

**Quirks**: Deux endpoints pour la même chose (alias).

---

#### GET /api/requests/{id} ✅
Détail d'un ticket spécifique.

**Paramètres**:
- `id` (path): ID du ticket au format hex (16 caractères)

**Exemple**: `/api/requests/00294000001e8cbd`

**Réponse**: Identique à l'objet ticket dans le listing (voir structure ci-dessus).

---

### 3. Messages & Commentaires

#### GET /api/requests/{id}/messages ✅
Liste les messages/commentaires d'un ticket.

**Paramètres**:
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `fromPageNumber` | int | 1 | Page |
| `nbOfResult` | int | 5 | Résultats par page ⚠️ SANS 's' (not 'nbOfResults') |

**Quirk majeur**: Le paramètre est `nbOfResult` (SANS 's'), tandis que `/requests/company` utilise `nbOfResults` (AVEC 's'). Typo dans l'API?

**Réponse**:
```json
{
  "objectsList": [
    {
      "id": "00294000001e9058",
      "description": "<html>...<p>Contenu du message</p></html>",
      "type": {
        "code": "INEXTRANET",
        "label": "Extranet entrant"
      },
      "attachments": [
        {
          "id": "00294000001e8cb6",
          "name": "image (5).png",
          "description": "Saisie praticien",
          "contentType": "image/png",
          "createdAt": "2026-03-24T14:58:51+01:00",
          "updatedAt": "2026-03-24T14:58:51+01:00"
        }
      ],
      "createdAt": "2026-03-24T14:58:51+01:00",
      "updatedAt": "2026-03-24T14:58:51+01:00"
    }
  ],
  "totalSize": 15,
  "pageSize": 5
}
```

**Quirks**:
- `description` contient du HTML brut (nécessite sanitization)
- Les attachments sont inclus dans l'objet Message
- Types de messages: `INEXTRANET` observé (d'autres types probablement: INTERNE, SORTANT, etc.)

---

#### GET /api/requests/{id}/messages/attachments ✅
Récupère TOUS les attachments des messages d'un ticket, organisés par message ID.

**Réponse**:
```json
{
  "00294000001e8ced": [
    {
      "id": "00294000001e8cb6",
      "name": "image (5).png",
      "description": "Saisie praticien",
      "contentType": "image/png",
      "createdAt": "2026-03-24T14:58:51+01:00",
      "updatedAt": "2026-03-24T14:58:51+01:00"
    },
    {
      "id": "00294000001e8cb7",
      "name": "Capture d'écran 2026-03-24 à 14.58.10.png",
      "contentType": "image/png",
      "createdAt": "2026-03-24T14:58:51+01:00",
      "updatedAt": "2026-03-24T14:58:51+01:00"
    }
  ]
}
```

**Quirks**:
- Clés = Message IDs (hex)
- Valeurs = Arrays de pièces jointes
- Structure différente de celle retournée par `/messages/{id}/messages` (pas directement dans Message.attachments)

---

#### GET /api/messages/{messageId} ✅
Détail d'un message spécifique.

**Réponse**: Identique à un objet dans `objectsList` de `/requests/{id}/messages`.

---

#### GET /api/messages/{messageId}/attachments ✅
Pièces jointes d'un message spécifique (en array simple, pas par message).

**Réponse**:
```json
[
  {
    "id": "00294000001e8cb6",
    "name": "image (5).png",
    "description": "Saisie praticien",
    "contentType": "image/png",
    "createdAt": "2026-03-24T14:58:51+01:00",
    "updatedAt": "2026-03-24T14:58:51+01:00"
  }
]
```

---

### 4. Données de référence

#### GET /api/refvalues ✅
Récupère les listes de valeurs de référence (types, statuts, etc.).

**Paramètres**:
- `tableCode` (query): Code de la table

**Codes supportés**:
| Code | Description | Exemple de valeurs |
|------|-------------|-------------------|
| `Tt_` | Types de tickets | DEMANDE, INCIDENT, PROBLEME, CHANGEMENT, REFERENCEMENT |
| `Rst` | Statuts | ENCOURS, RESOLU, ... |
| `Sd_` | Domaines/Catégories | (à découvrir) |
| `Im_` | Impacts | (à découvrir) |

**Réponse pour Tt_**:
```json
[
  {
    "id": "0002300000033a2f",
    "code": "DEMANDE",
    "label": "Demande",
    "nu1": true,
    "pos": 10
  },
  {
    "id": "0002300000070c8d",
    "code": "INCIDENT",
    "label": "Incident",
    "nu1": true,
    "pos": 20
  }
]
```

---

#### GET /api/requests/services ✅
Liste des services disponibles.

**Réponse**:
```json
[
  {
    "id": "00023000004ed02b",
    "label": "Support technique",
    "qualifs": [
      "00023000007eb20a",
      "0002300000928aa7",
      "00023000007eb279",
      "..."
    ]
  }
]
```

**Quirks**:
- `qualifs` = Array d'IDs de qualifications associées au service

---

#### GET /api/requests/qualifications ✅
Liste des qualifications disponibles.

**Paramètres**:
- `all` (boolean, default true): Récupérer toutes les qualifications

**Réponse**:
```json
[
  {
    "id": "00023000004bef0a",
    "code": "APCV-VIDEO",
    "label": "La vidéo ne se lance pas",
    "description": "Au démarrage de la vidéo, message d'erreur",
    "masque": null,
    "requestFieldIds": null,
    "faqIds": null,
    "parentQualification": {
      "id": "00023000004beec3",
      "code": null,
      "label": "Audiovisuel"
    },
    "topLevelQualification": {
      "id": "00023000004beec3",
      "code": null,
      "label": "Audiovisuel"
    }
  }
]
```

**Quirks**:
- Hiérarchie: `parentQualification` et `topLevelQualification`
- Peut contenir des qualifications "conteneurs" avec labels nulles

---

### 5. Configuration & Options

#### GET /api/option ✅
Récupère une option de configuration.

**Paramètres**:
- `name` (query): Nom de l'option

**Exemples capturés**:
- `MaxUploadSize` - Taille max upload
- `Security.UploadExtensionWhiteList` - Extensions autorisées

**Réponse pour Security.UploadExtensionWhiteList**:
```json
{
  "id": null,
  "name": "Security.UploadExtensionWhiteList",
  "type": "00023000000034df",
  "valueList": null,
  "value": "arl;b2;bin;cfg;csr;csv;css;data;doc;docm;docx;dotm;dotx;eml;html;ics;in;ini;jpg;json;log;msg;noe;oft;olm;out;p12;pdf;png;ppsx;pptx;rsp;rtf;srt;ssv;staging;sts;sys;txt;xls;xlsm;xlsx;xml;zip;"
}
```

**Quirks**:
- Valeur = chaîne délimitée par des `;`
- ID peut être null pour certaines options

---

### 6. Notifications

#### GET /api/notifications ✅
Liste les notifications de l'utilisateur.

**Paramètres**:
| Param | Type | Default |
|-------|------|---------|
| `isRead` | boolean | false |
| `offset` | int | 0 |
| `nbOfResult` | int | 20 |

**Réponse**:
```json
{
  "notificationsByHourMap": {
    "2": [
      {
        "id": "00294000001ead9d",
        "channel": null,
        "createdAt": "2026-03-26T17:42:45+01:00",
        "updatedAt": "2026-03-26T17:42:45+01:00",
        "dateTime": "2026-03-26T17:42:45+01:00",
        "isRead": false,
        "readStatusId": null,
        "objectId": "00294000001df..."
      }
    ]
  }
}
```

---

### 7. FAQs

#### GET /api/faqs/fromQualif ⚠️
Récupère les FAQs pour une qualification.

**Paramètres**:
- `query` (string): Code ou ID de qualification

**Exemples capturés**:
- `/api/faqs/fromQualif?query=RIENDUTOUT`

**Note**: Endpoint peu documenté, réponse observée limitée.

---

## Authentification

### Type
**Session cookies JHipster** (pas de Bearer tokens)

### Cookies observés
- `JSESSIONID` - Cookie de session standard
- `XSRF-TOKEN` - Potentiellement pour la protection CSRF

### Validation
- Tous les appels incluent les cookies de session
- Absence de session = réponse 401 (non observée)
- Session expirée = revalidation nécessaire (à tester)

### À implémenter en portal.py
```python
# Lors de l'authentification
response = session.post('/api/authenticate', json={
    'username': email,
    'password': password,
    'rememberMe': False
})
# Les cookies de session sont automatiquement gérés par requests.Session
```

---

## Quirks et limitations

### 1. ⚠️ Paramètre inconsistent: nbOfResults vs nbOfResult
- `/requests/company` utilise `nbOfResults` (AVEC 's')
- `/requests/{id}/messages` utilise `nbOfResult` (SANS 's')
- Probablement une typo/bug dans le backend

### 2. ⚠️ `title` du ticket est toujours null
La vraie "description courte" est dans le champ `description`, pas `title`.

### 3. ⚠️ HTML dans description des messages
Les descriptions des messages contiennent du HTML brut et doivent être sanitizées avant affichage:
```html
<html>
<head><title></title></head>
<body>
<p data-mce-style="...">Contenu</p>
</body>
</html>
```

### 4. ✅ Deux endpoints pour lister les tickets
`/requests` et `/requests/company` font exactement la même chose. Probablement un alias.

### 5. ⚠️ Upload/Download de pièces jointes non observés
Les requêtes pour uploader ou télécharger les pièces jointes n'ont pas été capturées dans le HAR.
À tester:
- `POST /api/requests/{id}/attachments` - Upload
- `GET /api/messages/{messageId}/attachments/{attachmentId}/download` - Download (hypothétique)
- `DELETE /api/messages/{messageId}/attachments/{attachmentId}` - Delete

### 6. ⚠️ Modification de tickets non testée
Les endpoints PUT/PATCH pour modifier un ticket n'ont pas été observés:
- `PUT /api/requests/{id}` - Modification complète
- `PATCH /api/requests/{id}` - Modification partielle

### 7. ✅ Postings de messages
L'endpoint POST pour ajouter un commentaire n'a pas été capturé mais est implémenté en portal.py:
```python
POST /api/messages
{
  "title": "...",
  "description": "...",
  "linkedRequest": {"id": "..."}
}
```

### 8. ✅ Résolution de ticket
L'endpoint pour résoudre un ticket:
```python
PUT /api/requests/{id}/solve
null  # Payload vide!
```

---

## Structures de données

### ID Format
Tous les IDs sont des **hexadécimales de 16 caractères**:
```
00294000001e8cbd
^16 caractères hex
```

### Dates
Format: **ISO 8601 avec timezone**
```
2026-03-26T17:42:45+01:00
```

### Types de tickets
```
DEMANDE
INCIDENT
PROBLEME
CHANGEMENT
REFERENCEMENT
```

### Priorités
```
AVERAGE    (Normal)
HAUTE      (Haute)
CRITIQUE   (Critique)
```

### Statuts
```
ENCOURS    (En cours)
RESOLU     (Résolu)
(autres à découvrir)
```

---

## Notes de sécurité

### ⚠️ Données sensibles observées
- Emails des utilisateurs
- Noms complets (firstName, lastName)
- Descriptions de tickets contenant potentiellement des données sensibles

### ⚠️ HTML non échappé
Les descriptions des messages contiennent du HTML brut. Risque XSS si affiché sans sanitization.

### ✅ HTTPS obligatoire
Tous les appels utilisent HTTPS (port 443).

### ✅ CORS headers
Présence de headers CORS appropriés (Vary, Access-Control-*).

### ⚠️ Pas de rate limiting observé
Les logs n'indiquent pas de rate limiting (à confirmer).

---

## Status de la couverture API

### ✅ Endpoints implémentés en portal.py
1. GET /api/authenticate
2. GET /api/account
3. GET /api/requests/company
4. GET /api/requests/{id}
5. GET /api/requests/{id}/messages
6. POST /api/messages (ajouter un commentaire)
7. PUT /api/requests/{id}/solve (résoudre)
8. Métadonnées (refvalues, services, qualifications)

### ❌ Endpoints non implémentés
- [ ] `POST /api/requests` - Créer un ticket
- [ ] `PATCH /api/requests/{id}` - Modifier un ticket
- [ ] `PUT /api/requests/{id}` - Remplacer un ticket
- [ ] `POST /api/requests/{id}/attachments` - Upload fichier
- [ ] `DELETE /api/messages/{id}/attachments/{attId}` - Supprimer pièce jointe
- [ ] `PUT /api/requests/{id}/assign` - Assigner un ticket

### ⚠️ Endpoints à valider
- [ ] Modification de tickets (PUT/PATCH)
- [ ] Upload de pièces jointes (formats, limits)
- [ ] Authentification complète (logout, expiration)
- [ ] Pagination au-delà de la page 3
- [ ] Filtres avancés sur les tickets

---

## Prochaines étapes

1. ✅ Documenter les endpoints observés
2. 🚀 Tester upload de pièces jointes
3. 🚀 Tester modification de tickets
4. 🚀 Implémenter les endpoints manquants en portal.py
5. 🚀 Générer tests unitaires avec mocks
