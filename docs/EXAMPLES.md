# Exemples d'utilisation de l'API Portail IRIS

## 📚 Table des matières
1. [Configuration](#configuration)
2. [Authentification](#authentification)
3. [Lister les tickets](#lister-les-tickets)
4. [Détail d'un ticket](#détail-dun-ticket)
5. [Messages d'un ticket](#messages-dun-ticket)
6. [Ajouter un commentaire](#ajouter-un-commentaire)
7. [Données de référence](#données-de-référence)

---

## Configuration

### Base URL
```
https://portail-support.sesam-vitale.fr/gsvextranet/api
```

### Headers communs
```
Accept: application/json
Content-Type: application/json
X-Requested-With: XMLHttpRequest
Cookie: JSESSIONID=<your-session-id>
```

---

## Authentification

### Python (avec portal.py existant)
```python
from portal import PortalClient

client = PortalClient(
    username="nom@mail.com",
    password="your_password"
)

# Client automatiquement authentifié
user_info = client.get_account()
print(user_info['email'])
```

### cURL direct
```bash
curl -X POST https://portail-support.sesam-vitale.fr/gsvextranet/api/authenticate \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nom@mail.com",
    "password": "your_password",
    "rememberMe": false
  }' \
  -c cookies.txt

# Cookies sauvegardés dans cookies.txt pour les appels suivants
```

---

## Lister les tickets

### Python
```python
# Avec portal.py existant
tickets = client.list_tickets(page=1, limit=30)

print(f"Total: {tickets['totalSize']}")
for ticket in tickets['objectsList']:
    print(f"{ticket['code']} - {ticket['status']['label']}")
    print(f"  Priorité: {ticket['priority']['label']}")
    print(f"  Service: {ticket['service']['label']}")
```

### cURL
```bash
# Lister les 30 premiers tickets non fermés
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?notClosed=true&fromPageNumber=1&nbOfResults=30&orderBy=DmdCrDt&orderWay=%20DESC' \
  -H "Accept: application/json"

# Avec jq pour formatter
curl -s -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?notClosed=true&fromPageNumber=1&nbOfResults=30&orderBy=DmdCrDt&orderWay=%20DESC' \
  | jq '.objectsList[] | {code: .code, status: .status.label, priority: .priority.label}'
```

### Paramètres
```
notClosed=true          # Filtrer tickets fermés
fromPageNumber=1        # Première page
nbOfResults=30          # 30 résultats par page ⚠️ Avec 's'!
orderBy=DmdCrDt         # Tri par date création
orderWay=%20DESC        # Descendant (note: espace encodé)
```

---

## Détail d'un ticket

### Python
```python
# Récupérer un ticket spécifique
ticket_id = "00294000001e8cbd"
ticket = client.get_ticket(ticket_id)

print(f"Code: {ticket['code']}")
print(f"Titre: {ticket['title']}")
print(f"Description: {ticket['description'][:200]}...")
print(f"Status: {ticket['status']['label']}")
print(f"Priorité: {ticket['priority']['label']}")
print(f"Service: {ticket['service']['label']}")
print(f"Créé le: {ticket['createdAt']}")
print(f"Modifié le: {ticket['updatedAt']}")
if ticket['closedAt']:
    print(f"Fermé le: {ticket['closedAt']}")
```

### cURL
```bash
ticket_id="00294000001e8cbd"

curl -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id" \
  -H "Accept: application/json" | jq '.'

# Afficher juste les infos principales
curl -s -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id" \
  | jq '{
      code: .code,
      status: .status.label,
      priority: .priority.label,
      createdAt: .createdAt,
      updatedAt: .updatedAt
    }'
```

### Réponse exemple
```json
{
  "id": "00294000001e8cbd",
  "code": "26-083-026025",
  "title": null,
  "description": "OTP : | Nom AMC : CCSP...",
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
    "id": "00023000004ed02b",
    "label": "Support technique"
  },
  "createdAt": "2026-03-24T14:50:18+01:00",
  "updatedAt": "2026-03-26T18:42:45+01:00",
  "closedAt": null
}
```

---

## Messages d'un ticket

### Python
```python
ticket_id = "00294000001e8cbd"

# Récupérer les messages (paginator par 5)
messages = client.get_messages(ticket_id, page=1, limit=5)

print(f"Total messages: {messages['totalSize']}")
for msg in messages['objectsList']:
    print(f"\n[{msg['createdAt']}] {msg['type']['label']}")
    # Description contient du HTML, à nettoyer
    print(f"Contenu: {msg['description'][:100]}...")

    if msg.get('attachments'):
        print(f"  Pièces jointes: {len(msg['attachments'])}")
        for att in msg['attachments']:
            print(f"    - {att['name']} ({att['contentType']})")
```

### cURL
```bash
ticket_id="00294000001e8cbd"

# Récupérer les 5 premiers messages ⚠️ Paramètre: nbOfResult (SANS 's')
curl -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id/messages?fromPageNumber=1&nbOfResult=5" \
  -H "Accept: application/json" | jq '.'

# Afficher juste les résumés
curl -s -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id/messages?fromPageNumber=1&nbOfResult=5" \
  | jq '.objectsList[] | {date: .createdAt, type: .type.label, attachments: (.attachments | length)}'
```

### Récupérer toutes les pièces jointes d'un ticket
```python
ticket_id = "00294000001e8cbd"

# Pièces jointes organisées par message ID
attachments_by_msg = client.get_attachments_for_ticket(ticket_id)

for msg_id, attachments in attachments_by_msg.items():
    print(f"Message {msg_id}:")
    for att in attachments:
        print(f"  - {att['name']} ({att['contentType']}, {att['createdAt']})")
```

### cURL
```bash
ticket_id="00294000001e8cbd"

curl -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id/messages/attachments" \
  -H "Accept: application/json" | jq '.'
```

---

## Ajouter un commentaire

### Python
```python
ticket_id = "00294000001e8cbd"

# Ajouter un commentaire
response = client.add_message(
    ticket_id=ticket_id,
    title="Réponse du support",
    description="Merci pour votre demande. Nous avons bien reçu..."
)

print(f"Commentaire ajouté: {response.get('id')}")
```

### cURL
```bash
ticket_id="00294000001e8cbd"

curl -X POST https://portail-support.sesam-vitale.fr/gsvextranet/api/messages \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Réponse du support",
    "description": "Merci pour votre demande. Nous avons bien reçu...",
    "linkedRequest": {
      "id": "'$ticket_id'"
    }
  }'
```

⚠️ **Note**: POST vers `/api/messages`, pas `/api/requests/{id}/messages`!

---

## Données de référence

### Types de tickets
```python
# Python
types = client.get_ticket_types()
for t in types:
    print(f"{t['code']}: {t['label']}")

# Output:
# DEMANDE: Demande
# INCIDENT: Incident
# PROBLEME: Problème
# CHANGEMENT: Changement
# REFERENCEMENT: Référencement
```

### cURL
```bash
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/refvalues?tableCode=Tt_' \
  -H "Accept: application/json" | jq '.[] | {code, label}'
```

### Statuts
```python
# Python
statuses = client.get_statuses()
for s in statuses:
    print(f"{s['code']}: {s['label']}")
```

### Services
```python
# Python
services = client.get_services()
for svc in services:
    print(f"{svc['id']}: {svc['label']}")
```

### Qualifications
```python
# Python
qualifications = client.get_qualifications()
for qual in qualifications:
    print(f"{qual['code']}: {qual['label']}")
    if qual.get('parentQualification'):
        parent = qual['parentQualification']
        print(f"  Parent: {parent['label']}")
```

### cURL
```bash
# Services
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/services' \
  -H "Accept: application/json" | jq '.[] | {id, label}'

# Qualifications
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/qualifications?all=true' \
  -H "Accept: application/json" | jq '.[] | {code, label, parent: .parentQualification.label}'
```

---

## Filtrage avancé (à tester)

### Lister seulement les tickets fermés
```bash
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?notClosed=false&fromPageNumber=1&nbOfResults=30' \
  | jq '.objectsList[] | select(.closedAt != null)'
```

### Filtrer par service
```bash
# À implémenter (paramètre à tester)
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?service=00023000004ed02b'
```

### Filtrer par priorité
```bash
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?priority=CRITIQUE'
```

---

## Résoudre un ticket ✅

### Python
```python
ticket_id = "00294000001e8cbd"
response = client.resolve_ticket(ticket_id)
print("Ticket résolu")
```

### cURL
```bash
ticket_id="00294000001e8cbd"

curl -X PUT https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id/solve \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d 'null'
```

⚠️ **Note**: Payload = `null` (vide), pas un objet JSON!

---

## ⚠️ Endpoints à tester

### Modifier un ticket
```bash
# À implémenter et tester
curl -X PATCH https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Nouveau titre",
    "priority": {"code": "HAUTE"}
  }'
```

### Uploader une pièce jointe
```bash
# Format et endpoint à confirmer
curl -X POST https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/$ticket_id/attachments \
  -b cookies.txt \
  -F "file=@/path/to/file.pdf"
```

### Télécharger une pièce jointe
```bash
# Endpoint à valider
message_id="00294000001e9058"
attachment_id="00294000001e8cb6"

curl -b cookies.txt \
  "https://portail-support.sesam-vitale.fr/gsvextranet/api/messages/$message_id/attachments/$attachment_id/download" \
  -o downloaded_file
```

---

## Astuces & Debugging

### Afficher toutes les requêtes HTTP
```python
import logging
import http.client as http_client

http_client.HTTPConnection.debuglevel = 1

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

# Ensuite vos appels HTTP afficheront les détails
```

### Capturer le trafic réseau (Chrome)
```
F12 → Network tab → Effectuer actions → Clic droit → Save all as HAR with content
```

### Nettoyer le HTML des descriptions
```python
from html import unescape
from html.parser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return unescape(s.get_data())

# Utilisation
raw_html = "<html>...<p>Contenu</p></html>"
clean_text = strip_tags(raw_html)
```

---

## Limites observées

- Max 30-100 résultats par requête (pagination obligatoire)
- Pas de rate limiting observé (à respecter)
- Descriptions longues peuvent être tronquées
- Données sensibles non filtrées (email, noms complets)
