# Architecture et Stack Technique

## 🏗️ Stack identifié

### Frontend
- **Framework**: Angular 11+
- **Bundles**:
  - `polyfills.bundle.js` - Polyfills Angular
  - `main.bundle.js` - Code applicatif
  - `global.bundle.js` - Assets globaux

### Backend
- **CRM**: **Efficy 11** (GIE SESAM-Vitale customisé)
- **Framework**: JHipster (backend Java standard)
- **API**: REST + JSON
- **Authentification**: Session cookies JHipster
- **Serveur Web**: Apache

---

## 🔐 Authentification JHipster

### Processus de login

#### 1. Tentative d'accès sans auth
```
GET /api/account
→ 401 Unauthorized (pas de session cookie)
```

#### 2. Authentification
```
POST /api/authenticate
Body: {
  "username": "nom@email",
  "password": "1234567890",
  "rememberMe": false
}
→ 200 OK
→ Définit cookies: JSESSIONID, XSRF-TOKEN
```

#### 3. Vérification
```
GET /api/account
→ 200 OK (maintenant authentifié)
```

### Cookies de session
| Cookie | Type | Usage |
|--------|------|-------|
| `JSESSIONID` | Session | Identifie la session JHipster |
| `XSRF-TOKEN` | CSRF | Protection contre les attaques CSRF |

### Code Python (portal.py)
```python
def authenticate(self):
    """Authentifier via JHipster"""
    response = self.session.post(
        f"{self.base_url}/api/authenticate",
        json={
            "username": self.username,
            "password": self.password,
            "rememberMe": False
        },
        timeout=15
    )
    if response.status_code == 200:
        # Cookies auto-gérés par requests.Session
        self.authenticated = True
        return True
    else:
        raise PortalAuthError(f"Auth failed: {response.status_code}")
```

---

## 🔗 Architecture des endpoints

### Hiérarchie logique

```
/api
├── authenticate              JHipster Auth
├── account                   Profil utilisateur
├── requests                  Tickets/Demandes
│   ├── /company             Tickets de la société
│   ├── /{id}                Détail ticket
│   ├── /{id}/messages       Messages du ticket
│   ├── /{id}/messages/attachments  Pièces jointes
│   ├── /services            Services (métadonnées)
│   └── /qualifications      Qualifications (métadonnées)
├── messages                  Messages (lecture/écriture)
│   ├── /{id}                Détail message
│   └── /{id}/attachments    Pièces jointes message
├── notifications            Notifications utilisateur
├── refvalues                Listes de référence
├── option                   Configuration serveur
├── faqs                     FAQ
└── (À découvrir)            Endpoints non exploités
```

---

## 📊 Modèle de données

### Entités principales

#### Ticket (Request)
```javascript
{
  id: "00294000001e8cbd",        // Hex 16 chars
  code: "26-083-026025",          // Référence GIE
  title: null,                    // Toujours null!
  description: "...",             // Contenu réel
  status: {code: "ENCOURS", label: "..."},
  priority: {code: "AVERAGE", label: "..."},
  typeTicket: {code: "INCIDENT", label: "..."},
  service: {id: "...", label: "..."},
  qualification: {id: "...", label: "..."},
  person: {id: "...", firstName: "...", lastName: "..."},
  createdAt: "2026-03-24T14:50:18+01:00",
  updatedAt: "2026-03-26T18:42:45+01:00",
  closedAt: null
}
```

#### Message
```javascript
{
  id: "00294000001e9058",
  description: "<html>...",      // HTML brut
  type: {code: "INEXTRANET", label: "..."},
  attachments: [
    {
      id: "...",
      name: "file.pdf",
      contentType: "application/pdf",
      createdAt: "..."
    }
  ],
  createdAt: "...",
  updatedAt: "..."
}
```

#### Service
```javascript
{
  id: "00023000004ed02b",
  label: "Support technique",
  qualifs: ["...", "...", "..."]  // IDs des qualifications
}
```

#### Qualification
```javascript
{
  id: "00023000004bef0a",
  code: "APCV-VIDEO",
  label: "La vidéo ne se lance pas",
  description: "Au démarrage...",
  parentQualification: {...},
  topLevelQualification: {...}
}
```

---

## 🛠️ Patterns API observés

### 1. Pagination
```
GET /api/requests/company
  ?fromPageNumber=1
  &nbOfResults=30      ⚠️ Avec 's'
  &orderBy=DmdCrDt
  &orderWay=%20DESC

Response:
{
  objectsList: [...],
  totalSize: 42,
  pageSize: 30
}
```

**Quirk**: `/requests/{id}/messages` utilise `nbOfResult` (SANS 's')!

### 2. Filtrage
```
GET /api/requests/company?notClosed=true
GET /api/requests/company?notClosed=false
```

### 3. Métadonnées
```
GET /api/refvalues?tableCode=Tt_      Types de tickets
GET /api/refvalues?tableCode=Rst      Statuts
GET /api/refvalues?tableCode=Sd_      Domaines
GET /api/refvalues?tableCode=Im_      Impacts
```

### 4. Payload null
```
PUT /api/requests/{id}/solve
null  ⚠️ Payload vide, pas un objet JSON!
```

### 5. Actions POST
```
POST /api/messages              Ajouter un commentaire
  Body: {
    title: "...",
    description: "...",
    linkedRequest: {id: "..."}
  }

⚠️ POST vers /messages, pas /requests/{id}/messages
```

---

## 🚀 Implémentation dans portal.py

### Initialisation
```python
from portal import PortalClient

client = PortalClient(
    username="email@example.com",
    password="password"
)

# Auto-authentification lors de la première requête
client.authenticate()
```

### Utilisation courante
```python
# Lister les tickets
tickets = client.list_tickets(limit=30)
for ticket in tickets['objectsList']:
    print(f"{ticket['code']}: {ticket['status']['label']}")

# Détail d'un ticket
ticket = client.get_ticket("00294000001e8cbd")
messages = client.get_messages("00294000001e8cbd")

# Ajouter un commentaire
client.add_message(
    ticket_id="00294000001e8cbd",
    title="Réponse",
    description="Contenu"
)

# Résoudre
client.resolve_ticket("00294000001e8cbd")
```

---

## 🔍 Observations de sécurité

### ✅ Positifs
- HTTPS obligatoire (port 443)
- Headers de sécurité présents (CSP, X-Frame-Options, etc.)
- Session cookies sécurisées (JHipster par défaut)
- CORS headers appropriés

### ⚠️ Risques
- **HTML non échappé** dans les descriptions → Risque XSS
- **Données sensibles visibles**: emails, noms complets → Confidentialité
- **Pas de rate limiting observé** → Potentiel DoS
- **Pas de versioning API** → Changements imprévisibles

### 🛡️ Mitigations
- Sanitizer l'HTML des messages avant affichage
- Filtrer les données sensibles si exposé publiquement
- Respecter les limites de requêtes (max 30-100 par page)
- Monitorer les erreurs d'authentification (401, 403)

---

## 📈 Scalabilité & Performance

### Limitations observées
- Max 30-100 résultats par requête (pagination obligatoire)
- Pas de cursors, paging basique (fromPageNumber)
- Pas de bulk endpoints (requêtes individuelles)
- HTML brut dans les descriptions (stockage non optimisé)

### Optimisations possibles
- Cache client des métadonnées (services, qualifications)
- Batch requêtes pour tickets multiples (si endpoint existait)
- Lazy load des messages (paginer par 5)
- Compression des réponses (déjà utilisée)

---

## 🔄 Workflow typique utilisateur

```
1. Login
   POST /api/authenticate

2. Dashboard initial
   GET /api/account                    → Profil
   GET /api/notifications              → Notifications
   GET /api/requests/company?limit=30  → Tickets

3. Voir un ticket
   GET /api/requests/{id}              → Détail
   GET /api/requests/{id}/messages     → Messages
   GET /api/requests/{id}/messages/attachments → Pièces jointes

4. Ajouter un commentaire
   POST /api/messages                  → Nouveau commentaire

5. Résoudre un ticket
   PUT /api/requests/{id}/solve        → Marquer résolu

6. Recherche/Filtrage
   GET /api/refvalues?tableCode=Tt_    → Types
   GET /api/requests/services          → Services
   GET /api/requests/qualifications    → Qualifications
```

---

## 🔗 Ressources externes

### Efficy 11 CRM
- **Documentation**: https://doc.efficy.com/ (si accessible)
- **API Patterns**: Standard JHipster
- **Customisations GIE**: Non documentées (reverse-engineered)

### JHipster
- **Docs**: https://www.jhipster.tech/
- **API Auth**: Session cookies + CSRF tokens
- **Patterns**: REST JSON standard

---

## 📝 Notes techniques

### Version Angular
- Angular 11+ (bundles: polyfills, main, global)
- Pas de SSR (Server-Side Rendering) détecté
- SPA (Single Page App) standard

### Base de données (hypothèse)
- Backend Efficy 11 → Database (probablement Oracle, PostgreSQL, ou SQL Server)
- Schema standard CRM: Requests, Messages, Attachments, Services, Qualifications

### Locale & Timezone
- Français (fr_FR) par défaut
- Timezone: Europe/Paris
- Dates: ISO 8601 avec offset (+01:00)

---

## 🚦 Status d'intégration

| Composant | Status | Notes |
|-----------|--------|-------|
| Authentification | ✅ Implémenté | JHipster standard |
| Lister tickets | ✅ Implémenté | Deux endpoints équivalents |
| Détail ticket | ✅ Implémenté | Format complet |
| Messages | ✅ Implémenté | Avec HTML brut |
| Résoudre ticket | ✅ Implémenté | PUT avec payload null |
| Commentaires | ✅ Implémenté | POST /messages |
| Métadonnées | ✅ Implémenté | Services, qualifications |
| **Upload fichiers** | ❌ À tester | Endpoint format TBD |
| **Modifier ticket** | ❌ À tester | PATCH/PUT TBD |
| **Assigner** | ❌ À tester | Endpoint TBD |
| **Historique** | ❌ À tester | Audit trail TBD |

---

## 🎯 Prochaines étapes

1. ✅ Documenter l'architecture (ce fichier)
2. 🚀 Tester les endpoints manquants
3. 🚀 Implémenter upload de fichiers
4. 🚀 Implémenter modification de tickets
5. 🚀 Générer une documentation Efficy-spécifique
