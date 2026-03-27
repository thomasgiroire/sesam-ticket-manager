# Efficy 11 CRM - Patterns standards et implémentation GIE

## 📋 Vue d'ensemble

**Efficy 11 CRM** est le backend du Portail IRIS SESAM-Vitale. Cette page documente:
1. Les patterns standards d'Efficy 11
2. Comment le Portail IRIS les implémente
3. Les customisations spécifiques du GIE

---

## 🏗️ Architecture Efficy 11

### API Standards Efficy 11

Efficy 11 expose deux types d'API:

#### 1. **JSON RPC** (Architecture standard)
- Format: JSON RPC 2.0
- Requêtes: `{"method": "...", "params": {...}}`
- Réponses: Structured JSON
- Authentification: API Key ou User/Password
- Utilisé en backend (Node.js, serveur-à-serveur)

#### 2. **REST API** (Implémentation du GIE)
- Format: REST HTTP + JSON
- Requêtes: GET, POST, PUT, DELETE
- Réponses: JSON standard
- Authentification: Session cookies JHipster
- **Spécifique au Portail IRIS**

### Le Portail IRIS = REST Wrapper
```
┌─────────────────────────────────────────┐
│  Frontend Angular 11+                   │
│  (SPA avec requests HTTP)               │
├─────────────────────────────────────────┤
│  API REST (Portail IRIS)                │
│  - /api/requests                        │
│  - /api/messages                        │
│  - /api/services                        │
│  - /api/qualifications                  │
│  (Customization GIE)                    │
├─────────────────────────────────────────┤
│  Backend Efficy 11 (JSON RPC)           │
│  - Gestion des Requests (tickets)       │
│  - Gestion des Messages (commentaires)  │
│  - Gestion des Services                 │
│  - Gestion des Qualifications           │
├─────────────────────────────────────────┤
│  Database (Oracle/PostgreSQL/SQL Server)│
└─────────────────────────────────────────┘
```

---

## 🔑 Concepts Efficy 11 standards

### Entités principales

| Entité | Code Efficy | Mapping Portail IRIS |
|--------|------------|----------------------|
| Request | `req` | /api/requests → Ticket |
| Message | `msg` | /api/messages → Commentaire |
| Service | `svc` | /api/requests/services |
| Qualification | `qual` | /api/requests/qualifications |
| Contact | `cct` | Personne associée |
| Company | `comp` | Société |

### Patterns d'ID Efficy

**Format**: Hexadécimal 16 caractères
```
00294000001e8cbd
└─ Efficy internal ID (Base de données)
```

Chaque entité Efficy a:
- **ID interne**: Hex 16 chars (clé primaire)
- **Code externe**: Readable code (ex: `26-083-026025` pour les requests)
- **Type**: Code court (ex: `req`, `msg`, `cct`)

### Architecture de données Efficy

```
Request (req)
├── ID (hex)
├── Code (ex: 26-083-026025)
├── Status (ref value)
├── Priority (ref value)
├── Type (ref value: DEMANDE, INCIDENT, etc.)
├── Service (link to svc)
├── Qualification (link to qual)
├── Person (link to cct)
└── Messages (collection of msg)
    └── Message
        ├── ID
        ├── Description (HTML)
        ├── Type (ref value)
        └── Attachments (collection)
```

---

## 🔄 Patterns API standards Efficy

### 1. Recherche (Search)

**JSON RPC standard**:
```json
{
  "method": "search",
  "params": {
    "entity": "req",
    "criteria": "SEARCHFAST",
    "value": "26-083-026025"
  }
}
```

**REST Portail IRIS**:
```
GET /api/requests/company
  ?fromPageNumber=1
  &nbOfResults=30
  &orderBy=DmdCrDt
  &orderWay=%20DESC
```

### 2. Consultation (Consult)

**JSON RPC standard**:
```json
{
  "method": "consult",
  "params": {
    "entity": "req",
    "key": "00294000001e8cbd"
  }
}
```

**REST Portail IRIS**:
```
GET /api/requests/00294000001e8cbd
```

### 3. Édition (Edit)

**JSON RPC standard**:
```json
{
  "method": "edit",
  "params": {
    "entity": "req",
    "key": "00294000001e8cbd",
    "fields": {
      "status": "RESOLU"
    }
  }
}
```

**REST Portail IRIS** (À implémenter):
```
PATCH /api/requests/00294000001e8cbd
  Body: {
    "status": {"code": "RESOLU"}
  }
```

### 4. Valeurs de référence (RefValues)

**JSON RPC standard**:
```json
{
  "method": "refvalues",
  "params": {
    "tableCode": "Tt_"
  }
}
```

**REST Portail IRIS**:
```
GET /api/refvalues?tableCode=Tt_
```

---

## 🔐 Authentification

### JSON RPC Efficy (Standard)
```javascript
// API Key
const auth = {
  "X-API-Key": "your-api-key"
};

// OU User/Password
const auth = {
  "Authorization": "Basic " + base64(user:pass)
};

// OU POST login
POST /json
{
  "method": "login",
  "params": {"user": "...", "pwd": "..."}
}
```

### REST Portail IRIS (Customisé)
```
POST /api/authenticate
{
  "username": "email@example.com",
  "password": "password",
  "rememberMe": false
}
→ Retourne 200 + Cookies (JSESSIONID)
```

**Différence**: Le GIE utilise JHipster Session Auth au lieu des API Keys d'Efficy.

---

## 📊 Structures de données

### Request (Ticket)
**Efficy standard**:
```javascript
{
  // Identifiants
  "id": "00294000001e8cbd",           // Clé primaire
  "code": "26-083-026025",            // Code affiché

  // Status & Priority
  "status": "ENCOURS",                // Valeur ref
  "priority": "AVERAGE",              // Valeur ref
  "type": "INCIDENT",                 // Valeur ref

  // Associations
  "service": "00023000004ed02b",      // Lien à Service
  "qualification": "00023000004bef0a",// Lien à Qualification
  "person": "0002300001661d4b",       // Lien à Contact

  // Contenu
  "title": null,                      // Toujours null (bug?)
  "description": "...",               // Contenu réel

  // Audit
  "createdAt": "2026-03-24T14:50:18+01:00",
  "updatedAt": "2026-03-26T18:42:45+01:00",
  "closedAt": null
}
```

### Service
**Efficy standard**:
```javascript
{
  "id": "00023000004ed02b",
  "label": "Support technique",
  "code": "SUP",                      // Code interne

  // Hiérarchie
  "parentService": null,

  // Associations
  "qualifications": [                // IDs des qualifications
    "00023000007eb20a",
    "0002300000928aa7",
    "..."
  ]
}
```

### Message
**Efficy standard**:
```javascript
{
  "id": "00294000001e9058",

  // Contenu
  "description": "<html>...",         // HTML from RichText
  "title": "...",                     // Optional

  // Type
  "type": "INEXTRANET",               // Valeur ref

  // Attachments
  "attachments": [
    {
      "id": "...",
      "name": "file.pdf",
      "contentType": "application/pdf",
      "size": 12345
    }
  ],

  // Associations
  "request": "00294000001e8cbd",      // Link back to Request

  // Audit
  "createdAt": "2026-03-24T14:58:51+01:00",
  "updatedAt": "2026-03-24T14:58:51+01:00"
}
```

---

## 🎯 Customisations du GIE SESAM-Vitale

### 1. REST API Wrapper
Le GIE a wrappé la JSON RPC d'Efficy 11 dans une REST API moderne pour:
- ✅ Faciliter l'intégration frontend (Angular)
- ✅ Simplifier les clients
- ✅ Standardiser l'authentification (JHipster sessions)
- ✅ Ajouter des endpoints custom

### 2. Métadonnées SESAM-Vitale
Endpoints spécifiques au GIE:
```
GET /api/refvalues?tableCode=Tt_       Types SESAM (DEMANDE, INCIDENT, etc.)
GET /api/refvalues?tableCode=Rst       Statuts SESAM
GET /api/refvalues?tableCode=Sd_       Domaines SESAM
GET /api/refvalues?tableCode=Im_       Impacts SESAM
```

Ces tableCodes sont des conventions Efficy, mais les valeurs sont customisées par le GIE.

### 3. Champs customisés
Le GIE a potentiellement ajouté des champs ou des validations spécifiques:
- ✅ Types de tickets (DEMANDE, INCIDENT, PROBLEME, CHANGEMENT, REFERENCEMENT)
- ✅ Services SESAM-Vitale
- ✅ Qualifications spécifiques (ex: "APCV-VIDEO")
- ✅ Workflows SESAM

### 4. Authentification customisée
Au lieu de l'auth API Key d'Efficy:
- ✅ Portail IRIS utilise **JHipster Session Cookies**
- ✅ Endpoint `/api/authenticate` standard JHipster
- ✅ Gestion des sessions côté backend

---

## 🔗 Mapping Efficy → Portail IRIS

### Endpoints

| Portail IRIS | Efficy Backend | Fonction |
|--------------|----------------|----------|
| GET /requests | `search("req")` | Chercher les requests |
| GET /requests/{id} | `consult("req")` | Voir une request |
| PATCH /requests/{id} | `edit("req")` | Modifier une request |
| PUT /requests/{id}/solve | `edit("req", {status})` | Résoudre (statut=RESOLU) |
| POST /messages | `edit("msg")` | Ajouter un message |
| GET /messages/{id} | `consult("msg")` | Voir un message |
| GET /services | `consult("svc")` | Services disponibles |
| GET /qualifications | `consult("qual")` | Qualifications |

### Opérations

| Portail IRIS | JSON RPC Efficy | Description |
|--------------|-----------------|-------------|
| GET (list) | search() | Rechercher entités |
| GET (single) | consult() | Consulter une entité |
| POST | edit() + new | Créer entité |
| PATCH/PUT | edit() + update | Modifier entité |
| DELETE | delete() | Supprimer entité |

---

## ⚠️ Quirks & Incompatibilités

### 1. `title` toujours null
- **Efficy standard**: Title peut être utilisé
- **Portail IRIS**: Title est null, description contient le contenu
- **Cause**: Probablement une customisation/bug du GIE

### 2. HTML brut dans descriptions
- **Efficy standard**: RichText storé en HTML
- **Portail IRIS**: HTML retourné tel quel (non sanitizé)
- **Risque**: XSS si affiché sans sanitization

### 3. Deux endpoints list
- `GET /requests` et `GET /requests/company` (alias)
- Efficy standard n'expose pas de doublon
- **Personnalisation du GIE**

### 4. Paramètres inconsistants
- `nbOfResults` vs `nbOfResult` (typo)
- Inconsistance entre endpoints
- **Bug dans la REST API du GIE**

### 5. Payload `null` pour resolve
- `PUT /requests/{id}/solve` + body `null`
- Efficy standard utiliserait `{status: "RESOLU"}`
- **Wrapper REST du GIE**

---

## 📈 Capacités Efficy 11 non explorées

D'après la doc Efficy, il y a d'autres capacités non utilisées dans Portail IRIS:

| Capacité Efficy | Status Portail | Potentiel |
|-----------------|----------------|-----------|
| Workflows | Non utilisé | Automatisation possible |
| Categories | Non utilisé | Optionnels avancés |
| Documents | Non utilisé | Gestion de fichiers |
| Relations | Non utilisé | Liens entités |
| Permissions | Utilisé | Déjà dans auth |
| Notifications | Partiellement | GET /notifications existe |
| Custom Fields | Potentiellement | À explorer |

---

## 🚀 Opportunités d'amélioration

### Court terme
1. ✅ Documenter les endpoints existants (FAIT)
2. 🚀 Standardiser les noms paramètres
3. 🚀 Corriger le bug `title` null

### Moyen terme
1. 🚀 Implémenter endpoints manquants (upload, modify)
2. 🚀 Sanitizer l'HTML des descriptions
3. 🚀 Ajouter support des workflows

### Long terme
1. 🚀 Générer doc OpenAPI officielle
2. 🚀 Créer SDK clients (JS, Python, etc.)
3. 🚀 Intégrations tiers (Slack, Jira, etc.)

---

## 📚 Ressources

### Documentation Efficy 11 officielle
- [Efficy Enterprise API - GitHub](https://github.com/Pauwris/efficy-enterprise-api)
- [Efficy Enterprise API Docs](https://pauwris.github.io/efficy-enterprise-api/)
- [Efficy Developer Network](https://help.efficy.io/edn/)
- [API Tracker - Efficy](https://apitracker.io/a/efficy)

### Stack du Portail IRIS
- **Backend**: Efficy 11 CRM + JHipster
- **Frontend**: Angular 11+
- **Protocol**: HTTP/HTTPS JSON REST
- **Auth**: JHipster Session Cookies

---

## 📝 Résumé

**Efficy 11 CRM** fournit:
- ✅ Modèle de données CRM complet
- ✅ JSON RPC API standard
- ✅ Gestion des entités (Requests, Messages, Services, etc.)
- ✅ Authentification et autorisations

**Portail IRIS** ajoute:
- ✅ REST API wrapper (facilite l'intégration)
- ✅ Frontend Angular SPA
- ✅ Authentification JHipster customisée
- ✅ Métadonnées SESAM-Vitale spécifiques

**Résultat**: Une API REST moderne pour gérer les tickets SESAM-Vitale, basée sur Efficy 11 CRM.

---

Generated: 2026-03-26
Based on: Efficy 11 official docs + reverse-engineering
