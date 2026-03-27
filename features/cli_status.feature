# language: fr
Feature: CLI — Commande status
  En tant qu'utilisateur CLI
  Je veux vérifier l'état de la connexion au portail IRIS et obtenir un résumé du compte
  Afin de diagnostiquer rapidement les problèmes de configuration

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Connexion réussie
    When j'exécute "python main.py status"
    Then le message "✅ Connexion réussie" est affiché en vert
    And les informations du compte sont affichées : Email, Statut, Dernière connexion

  Scenario: Afficher le nombre de tickets ouverts par statut
    When j'exécute "python main.py status"
    Then le nombre total de tickets ouverts est affiché
    And la répartition par statut est affichée, triée par nombre décroissant
    And chaque statut est coloré selon son style (ex: "En cours" en bleu)

  Scenario: Erreur d'authentification
    Given SESAM_USERNAME ou SESAM_PASSWORD est incorrect
    When j'exécute "python main.py status"
    Then un message d'erreur rouge est affiché
    And le code de retour est 1

  Scenario: Mode verbose (--verbose)
    When j'exécute "python main.py --verbose status"
    Then les logs DEBUG sont activés et affichent les appels HTTP en cours
