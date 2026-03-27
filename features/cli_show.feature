# language: fr
Feature: CLI — Commande show
  En tant qu'utilisateur CLI
  Je veux consulter le détail complet d'un ticket par sa référence ou son ID
  Afin d'avoir toutes les informations nécessaires sans passer par le portail web

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Afficher un ticket par sa référence
    When j'exécute "python main.py show 26-083-026025"
    Then un panneau Rich affiche le titre du ticket en gras
    And les métadonnées sont visibles : Référence, Type, Statut, Priorité, Service, Demandeur, Créé le, Mis à jour

  Scenario: Afficher un ticket par son ID hexadécimal
    When j'exécute "python main.py show 00294000001e8cbd"
    Then le même ticket est affiché sans étape de résolution d'ID

  Scenario: Afficher la description du ticket
    Given le ticket possède une description non vide
    When j'exécute "python main.py show 26-083-026025"
    Then un panneau "Description" est affiché sous les métadonnées

  Scenario: Afficher les derniers messages
    Given le ticket possède des messages
    When j'exécute "python main.py show 26-083-026025"
    Then les 3 derniers messages sont affichés avec leur type et leur date

  Scenario: Sortie JSON brut
    When j'exécute "python main.py show 26-083-026025 --json-output"
    Then la sortie est un objet JSON valide représentant le ticket complet

  Scenario: Ticket introuvable par référence
    When j'exécute "python main.py show 99-999-999999"
    Then le message "Ticket 99-999-999999 introuvable." est affiché en rouge
    And le code de retour est 1
