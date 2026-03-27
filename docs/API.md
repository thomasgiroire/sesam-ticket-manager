# API Portail IRIS SESAM-Vitale

## 🎯 Aperçu rapide

**Base URL**: `https://portail-support.sesam-vitale.fr/gsvextranet/api`

**Authentification**: Session cookies JHipster

**Format**: JSON + REST

**Endpoints**: 14 GET (lecture seule), + POST/PUT/PATCH/DELETE à implémenter

---

## 📊 Endpoints par catégorie

### Authentication & Account (1)
| Endpoint | Description |
|----------|------------|
| `GET /account` | Infos utilisateur connecté |

### Tickets (5)
| Endpoint | Description |
|----------|------------|
| `GET /requests/company` | Lister tickets de la société |
| `GET /requests` | Alias de `/requests/company` |
| `GET /requests/{id}` | Détail d'un ticket |
| `PUT /requests/{id}/solve` | Résoudre un ticket |
| `POST /requests` | Créer un ticket ⚠️ À tester |

### Messages (3)
| Endpoint | Description |
|----------|------------|
| `GET /requests/{id}/messages` | Messages d'un ticket |
| `GET /messages/{id}` | Détail d'un message |
| `POST /messages` | Ajouter un commentaire |

### Pièces jointes (4)
| Endpoint | Description |
|----------|------------|
| `GET /requests/{id}/messages/attachments` | Attachments du ticket |
| `GET /messages/{id}/attachments` | Attachments d'un message |
| `POST /requests/{id}/attachments` | Upload fichier ⚠️ À tester |
| `DELETE /messages/{id}/attachments/{id}` | Supprimer ⚠️ À tester |

### Données de référence (3)
| Endpoint | Description |
|----------|------------|
| `GET /refvalues?tableCode=Tt_` | Types de tickets |
| `GET /requests/services` | Services disponibles |
| `GET /requests/qualifications` | Qualifications disponibles |

### Configuration (1)
| Endpoint | Description |
|----------|------------|
| `GET /option?name=...` | Options de configuration |

### Autres (1)
| Endpoint | Description |
|----------|------------|
| `GET /notifications` | Notifications de l'utilisateur |
| `GET /faqs/fromQualif?query=...` | FAQs par qualification |

---

## 🔑 Concepts clés

### IDs
- Format: **Hexadécimal 16 caractères** (ex: `00294000001e8cbd`)
- Utilisés partout (tickets, messages, attachments, qualifications, services)

### Dates
- Format: **ISO 8601** avec timezone (ex: `2026-03-26T17:42:45+01:00`)
- Champs: `createdAt`, `updatedAt`, `closedAt`

### Priorités
```
AVERAGE   Normal
HAUTE     Haute
CRITIQUE  Critique
```

### Types de tickets
```
DEMANDE       Demande
INCIDENT      Incident
PROBLEME      Problème
CHANGEMENT    Changement
REFERENCEMENT Référencement
```

### Structure d'un ticket
```javascript
{
  id: "00294000001e8cbd",           // ID hex
  code: "26-083-026025",            // Référence affichée
  title: null,                      // Toujours null! Regarder description
  description: "...",               // Contenu réel
  status: {code: "ENCOURS", label: "En cours"},
  priority: {code: "AVERAGE", label: "Normal"},
  typeTicket: {code: "INCIDENT", label: "Incident"},
  service: {id: "...", label: "Support technique"},
  qualification: {id: "...", code: "...", label: "..."},
  person: {id: "...", firstName: "Jean", lastName: "Dupont"},
  createdAt: "2026-03-24T14:50:18+01:00",
  updatedAt: "2026-03-26T18:42:45+01:00",
  closedAt: null
}
```

### Structure d'un message
```javascript
{
  id: "00294000001e9058",
  description: "<html>...<p>Contenu</p></html>",  // HTML brut!
  type: {code: "INEXTRANET", label: "Extranet entrant"},
  attachments: [
    {
      id: "00294000001e8cb6",
      name: "image.png",
      contentType: "image/png",
      createdAt: "2026-03-24T14:58:51+01:00"
    }
  ],
  createdAt: "2026-03-24T14:58:51+01:00",
  updatedAt: "2026-03-24T14:58:51+01:00"
}
```

---

## ⚠️ Quirks observés

### 1. Paramètre `nbOfResults` vs `nbOfResult`
- `/requests/company` → `nbOfResults` (AVEC 's')
- `/requests/{id}/messages` → `nbOfResult` (SANS 's')

**Typo dans l'API?**

### 2. Le champ `title` est toujours null
La vraie description courte est dans `description`, pas `title`.

### 3. HTML non échappé dans les messages
Les descriptions contiennent du HTML brut:
```html
<html>
<head><title></title></head>
<body>
<p data-mce-style="...">Contenu avec formatting</p>
</body>
</html>
```

**À nettoyer avant affichage!**

### 4. Résolution de ticket avec payload `null`
```bash
PUT /api/requests/{id}/solve
null  # Pas un objet JSON vide!
```

### 5. Upload de pièces jointes: endpoint/format TBD
Pas encore observé. À tester:
- `POST /requests/{id}/attachments` vs `POST /messages/{id}/attachments`
- Format: `multipart/form-data` vs `application/octet-stream`

### 6. Pagination limitée
- Max 30-100 résultats par page
- Pagination de 1 à N (pas de cursor)
- `fromPageNumber` et `nbOfResults` requis

---

## 📖 Documentation détaillée

- **OpenAPI Spec**: Voir `openapi.yaml` pour la spec complète
- **Reverse-Engineering**: Voir `REVERSE_ENGINEERING.md` pour les détails de chaque endpoint
- **Exemples**: Voir `EXAMPLES.md` pour des exemples cURL/Python

---

## 🚀 Statut d'implémentation

### ✅ Implémenté en portal.py
- [x] GET /account
- [x] GET /requests/company
- [x] GET /requests/{id}
- [x] GET /requests/{id}/messages
- [x] GET /messages/{id}
- [x] POST /messages (ajouter commentaire)
- [x] PUT /requests/{id}/solve (résoudre)
- [x] GET /refvalues (métadonnées)
- [x] GET /requests/services
- [x] GET /requests/qualifications

### ❌ À implémenter
- [ ] POST /requests (créer ticket)
- [ ] PATCH /requests/{id} (modifier ticket)
- [ ] PUT /requests/{id} (remplacer ticket)
- [ ] POST /requests/{id}/attachments (upload)
- [ ] DELETE /messages/{id}/attachments/{id} (delete attachment)
- [ ] PUT /requests/{id}/assign (assigner)
- [ ] GET /requests/{id}/history (historique)

---

## 🔐 Authentification

### Cookies de session
- `JSESSIONID` - Session JHipster standard
- `XSRF-TOKEN` - Protection CSRF (optionnel?)

### Non supporté
- ❌ Bearer tokens
- ❌ API keys
- ❌ OAuth

### À implémenter
```python
from portal import PortalClient

client = PortalClient(
    username="email@example.com",
    password="password"
)

# Client automatiquement authentifié pour toutes les requêtes
```

---

## 📝 Utilisation courante

### Lister les tickets
```python
tickets = client.list_tickets(limit=30)
for ticket in tickets['objectsList']:
    print(f"{ticket['code']}: {ticket['status']['label']}")
```

### Voir un ticket et ses messages
```python
ticket = client.get_ticket("00294000001e8cbd")
messages = client.get_messages("00294000001e8cbd")

print(f"Ticket: {ticket['code']}")
print(f"Messages: {messages['totalSize']}")
```

### Ajouter un commentaire
```python
client.add_message(
    ticket_id="00294000001e8cbd",
    title="Réponse",
    description="Contenu du commentaire"
)
```

### Résoudre un ticket
```python
client.resolve_ticket("00294000001e8cbd")
```

---

## 🐛 Debugging

### Voir les requêtes HTTP
```python
import logging
import http.client

http_client.HTTPConnection.debuglevel = 1
logging.basicConfig(level=logging.DEBUG)
```

### Capturer le HAR
```
F12 → Network → Actions → Clic droit → Save all as HAR with content
```

---

## 📞 Support

**Documentation officielle**: Aucune disponible (reverse-engineering seulement)

**Repository**: https://github.com/anthropics/sesam-ticket-manager

**Signaler un bug**: Voir REVERSE_ENGINEERING.md → Suggestions pour le GIE

---

## 📋 Checklist de vérification

- [ ] Authentification fonctionne
- [ ] Lister les tickets fonctionne
- [ ] Détail d'un ticket fonctionne
- [ ] Lister les messages fonctionne
- [ ] Ajouter un commentaire fonctionne
- [ ] Résoudre un ticket fonctionne
- [ ] Tester les uploads de pièces jointes
- [ ] Tester la modification de tickets
- [ ] Implémenter les endpoints manquants
