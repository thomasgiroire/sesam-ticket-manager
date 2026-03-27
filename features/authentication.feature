# language: fr
Feature: Authentification au portail IRIS
  En tant qu'utilisateur du CLI ou de la web app
  Je veux être authentifié automatiquement auprès du portail IRIS
  Afin que mes requêtes soient autorisées sans saisie manuelle d'identifiants

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies dans .env

  Scenario: Login réussi à la première requête
    Given aucun cookie de session n'est sauvegardé dans .sesam_state.json
    When le client effectue sa première requête API
    Then POST /api/authenticate est appelé avec username et password
    And les cookies de session sont sauvegardés dans .sesam_state.json
    And la requête API initiale est exécutée avec succès

  Scenario: Réutilisation des cookies de session existants
    Given des cookies valides sont sauvegardés dans .sesam_state.json
    When le client effectue une requête API
    Then GET /api/account est appelé pour vérifier la validité de la session
    And POST /api/authenticate n'est pas appelé
    And la requête API est exécutée directement

  Scenario: Session expirée — reconnexion automatique
    Given des cookies expirés sont sauvegardés dans .sesam_state.json
    When GET /api/account retourne 401
    Then les cookies sont effacés de la session HTTP et de l'état
    And POST /api/authenticate est appelé pour obtenir une nouvelle session
    And la requête API originale est relancée

  Scenario: Identifiants incorrects
    Given SESAM_PASSWORD est incorrect dans .env
    When le client tente de se connecter
    Then POST /api/authenticate retourne 401
    And une AuthError est levée avec le message "Identifiants incorrects"
    And le code de retour CLI est 1

  Scenario: Retry avec backoff exponentiel en cas d'erreur réseau
    Given le portail IRIS est temporairement inaccessible (timeout)
    When le client tente de se connecter
    Then jusqu'à 3 tentatives sont effectuées avec un délai croissant (1s, 2s)
    And si toutes les tentatives échouent, une LoginError est levée

  Scenario: Variables d'environnement manquantes
    Given SESAM_USERNAME est absent du fichier .env
    When une commande CLI est exécutée
    Then une AuthError est levée avec le message indiquant les variables manquantes
    And aucun appel réseau n'est effectué
