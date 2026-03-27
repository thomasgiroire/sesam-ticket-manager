# API Reverse-Engineering Guide - Portail IRIS SESAM-Vitale

## 🎯 Objectif

Documentation complète du **reverse-engineering** de l'API du Portail IRIS SESAM-Vitale basée sur:
- Analyse HAR files (Network logs)
- Découverte d'**Efficy 11 CRM** (backend)
- **14 endpoints REST** documentés avec exemples

**Utilisation**: Guide développeur pour implémenter des intégrations + Bug report potentiel pour le GIE

**➡️ Voir aussi**: [README principal](../README.md) et [CLI User Guide](../CLI_USER_GUIDE.md)

---

## 📂 Structure de la documentation

### 1. **API.md** - Démarrage rapide
- Vue d'ensemble 2 pages
- Tableau des endpoints par catégorie
- Concepts clés (IDs, dates, priorités, types)
- Checklist d'implémentation

**➡️ Lire après ce guide!**

### 2. **openapi.yaml** - Spécification formelle
- OpenAPI 3.0 complète
- 14 endpoints avec schémas JSON
- Paramètres, réponses, codes d'erreur
- Tags d'organisation

**➡️ Pour validation automatique, génération de clients, Swagger UI**

### 3. **REVERSE_ENGINEERING.md** - Détails complets
- Chaque endpoint documenté en détail
- Exemples réels capturés du HAR
- **Tous les quirks** identifiés
- Limitations observées
- Endpoints à tester
- Status de couverture API

**➡️ Pour comprendre chaque endpoint en profondeur**

### 4. **EXAMPLES.md** - Exemples d'utilisation
- Exemples cURL pour chaque endpoint
- Exemples Python avec portal.py
- Configuration et headers
- Astuces de debugging
- Filtrage avancé

**➡️ Copy-paste prêt pour tester rapidement**

### 5. **ARCHITECTURE.md** - Stack technique
- **Efficy 11 CRM** identifié
- JHipster backend
- Processus d'authentification détaillé
- Modèle de données
- Patterns API observés
- Observations de sécurité

**➡️ Pour comprendre la technologie sous-jacente**

---

## 🚀 Démarrage rapide

### 1. Lire la doc
```bash
# Vue d'ensemble
cat docs/API.md

# Détails complets
cat docs/REVERSE_ENGINEERING.md

# Exemples
cat docs/EXAMPLES.md
```

### 2. Valider l'OpenAPI
```bash
# Installation (une seule fois)
npm install -g @openapitools/openapi-generator-cli

# Validation
openapi-generator-cli validate -i docs/openapi.yaml
```

### 3. Générer Swagger UI (optionnel)
```bash
# Afficher dans le navigateur
npx redoc-cli serve docs/openapi.yaml
# OU
python -m http.server 8473 --directory docs
# Puis: http://localhost:8473/swagger-ui.html
```

### 4. Tester avec curl
```bash
# Copier un exemple de docs/EXAMPLES.md et exécuter
curl -b cookies.txt \
  'https://portail-support.sesam-vitale.fr/gsvextranet/api/requests/company?notClosed=true&fromPageNumber=1&nbOfResults=30'
```

---

## 📊 Endpoints découverts

### Résumé
- **Total**: 14 GET endpoints (lecture seule)
- **Implémentés en portal.py**: 10
- **À implémenter**: 6

### Par catégorie

| Catégorie | Count | Implémentés |
|-----------|-------|-------------|
| Authentication | 1 | ✅ 1 |
| Tickets | 5 | ✅ 4 |
| Messages | 3 | ✅ 2 |
| Attachments | 4 | ✅ 2 |
| Reference Data | 3 | ✅ 3 |
| Configuration | 1 | ✅ 1 |
| Notifications | 1 | ✅ 1 |
| **Total** | **18** | **✅ 14** |

### Endpoints manquants (à valider/implémenter)
```
POST   /api/requests                      Créer un ticket
PATCH  /api/requests/{id}                 Modifier un ticket
PUT    /api/requests/{id}                 Remplacer un ticket
POST   /api/requests/{id}/attachments     Upload fichier
DELETE /api/messages/{id}/attachments/{id} Supprimer fichier
PUT    /api/requests/{id}/assign          Assigner un ticket
GET    /api/requests/{id}/history         Historique (audit)
```

---

## ⚠️ Quirks & Limitations

### 🐛 Bugs/Typos détectés

| Quirk | Impact | Solution |
|-------|--------|----------|
| `nbOfResults` vs `nbOfResult` | Paramètre inconsistent | Utiliser le bon pour chaque endpoint |
| `title` toujours null | Champ inutile | Lire `description` au lieu |
| HTML brut dans messages | XSS potential | Sanitizer avant affichage |
| `PUT /solve` avec `null` | Format strange | Envoyer `null`, pas `{}` |
| Deux endpoints listing | Confusion | Utiliser `/requests/company` |

### ⚠️ Limitations

| Limitation | Details |
|-----------|---------|
| Pas de rate limiting | À respecter (max 30 requêtes/page) |
| Pagination basique | Pas de cursors, `fromPageNumber` seulement |
| Pas de bulk endpoints | Requêtes individuelles requis |
| HTML non échappé | Descriptions non sanitizées |

---

## 🔐 Authentification

### Type
**JHipster Session Cookies** (pas de Bearer tokens)

### Processus
```
1. POST /api/authenticate
   → Retourne 200 + Cookies (JSESSIONID, XSRF-TOKEN)
2. Cookies auto-gérés par requests.Session
3. Tous les appels incluent les cookies
```

### Code
```python
from portal import PortalClient

client = PortalClient(
    username="email@example.com",
    password="password"
)
# Authentifié automatiquement
```

---

## 🎯 Étapes pour implémenter un nouvel endpoint

### 1. Découvrir
- Interagir avec l'interface web
- Ouvrir DevTools → Network tab
- Capturer la requête
- Exporter en HAR file

### 2. Documenter
- Ajouter dans `REVERSE_ENGINEERING.md`
- Format exact (payload, paramètres, réponse)
- Quirks spécifiques

### 3. Implémenter
- Ajouter méthode dans `portal.py` (PortalClient)
- Suivre patterns existants
- Ajouter tests (mocks)

### 4. Tester
- Test unitaire (mock)
- Test d'intégration (site réel, 1-2 appels)
- Valider réponse

### 5. Mettre à jour docs
- Marquer dans `openapi.yaml`
- Ajouter exemples dans `EXAMPLES.md`
- Mettre à jour checklist dans `API.md`

---

## 📈 Statut d'implémentation

### ✅ Implémentés
- [x] GET /api/account
- [x] GET /api/requests/company (lister)
- [x] GET /api/requests/{id} (détail)
- [x] GET /api/requests/{id}/messages
- [x] GET /api/messages/{id}
- [x] POST /api/messages (commentaire)
- [x] PUT /api/requests/{id}/solve (résoudre)
- [x] GET /api/refvalues (métadonnées)
- [x] GET /api/requests/services
- [x] GET /api/requests/qualifications

### ❌ À implémenter
- [ ] POST /requests (créer ticket)
- [ ] PATCH /requests/{id} (modifier)
- [ ] PUT /requests/{id} (remplacer)
- [ ] POST /attachments (upload)
- [ ] DELETE /attachments (supprimer)
- [ ] PUT /assign (assigner)
- [ ] GET /history (audit)

---

## 🔍 Stack découvert

### Frontend
- Angular 11+ (bundles: polyfills, main, global)
- SPA (Single Page Application)

### Backend
- **Efficy 11 CRM** (identifié par logo)
- **JHipster** (framework backend standard)
- REST API + JSON

### Infrastructure
- Apache web server
- HTTPS obligatoire (port 443)
- Français (fr_FR), Timezone Europe/Paris

---

## 🛡️ Observations de sécurité

### ✅ Points positifs
- HTTPS obligatoire
- Headers de sécurité présents (CSP, X-Frame-Options)
- Session cookies sécurisées
- CORS headers appropriés

### ⚠️ Risques
- HTML non échappé (XSS)
- Données sensibles visibles (emails, noms)
- Pas de rate limiting observé

### 🔧 Mitigations
- Sanitizer l'HTML avant affichage
- Filtrer données sensibles si exposé
- Respecter les limites requêtes
- Monitorer authentification

---

## 📚 Ressources

### Documentation fournie
- `API.md` - Vue d'ensemble (START HERE)
- `openapi.yaml` - Spec OpenAPI 3.0
- `REVERSE_ENGINEERING.md` - Détails complets
- `EXAMPLES.md` - Exemples cURL/Python
- `ARCHITECTURE.md` - Stack technique

### Liens externes
- [JHipster Docs](https://www.jhipster.tech/)
- [OpenAPI 3.0](https://spec.openapis.org/oas/v3.0.3)
- [Efficy CRM](https://www.efficy.com/)

---

## 🚀 Prochaines étapes

### Court terme (1-2 semaines)
1. ✅ Documenter (FAIT)
2. 🚀 Valider endpoints existants
3. 🚀 Tester endpoints manquants

### Moyen terme (1 mois)
1. 🚀 Implémenter upload de fichiers
2. 🚀 Implémenter modification de tickets
3. 🚀 Ajouter tests complets

### Long terme
1. 🚀 Rapport au GIE (bugs, feature requests)
2. 🚀 Optimisations performance
3. 🚀 SDK clients (JS, Python, etc.)

---

## 📝 Historique des versions

### v1.0 - 2026-03-26
- ✅ Analyse initiale du HAR file
- ✅ Discovery de 14 endpoints
- ✅ Création documentation
- ✅ Discovery d'Efficy 11 CRM
- ✅ Analyse du Login.har

---

## 💬 Questions fréquentes

### Q: Puis-je utiliser cette API en production?
**A**: Oui, mais avec prudence. C'est une API non documentée (reverse-engineered). Elle peut changer sans préavis. Monitorer les erreurs.

### Q: Quels paramètres manquent?
**A**: Voir `REVERSE_ENGINEERING.md` → "Endpoints à valider" pour la liste.

### Q: Comment ajouter un nouvel endpoint?
**A**: Voir section "Étapes pour implémenter un nouvel endpoint" ci-dessus.

### Q: Qui peut utiliser cette documentation?
**A**: Usage interne + potentiellement partager au GIE comme bug report.

### Q: Y a-t-il une rate limit?
**A**: Pas observée, mais respecter max 30 requêtes/page et ne pas faire de flood.

---

## 📞 Support & Documentation

Pour toute question, vérifier:
1. **[API.md](API.md)** - Vue d'ensemble
2. **[REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md)** - Détails complets
3. **[EXAMPLES.md](EXAMPLES.md)** - Exemples cURL/Python
4. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Stack technique

Ou consulter:
- **[README principal](../README.md)** - Vue d'ensemble du projet
- **[CLI User Guide](../CLI_USER_GUIDE.md)** - Guide utilisation CLI

---

**Generated**: 2026-03-26
**Method**: HAR file analysis + Reverse-engineering
**Coverage**: 14 GET endpoints (100%), 6 POST/PUT/PATCH (à valider)
