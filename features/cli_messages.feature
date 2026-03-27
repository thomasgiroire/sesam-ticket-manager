# language: fr
Feature: CLI — Commande messages
  En tant qu'utilisateur CLI
  Je veux lire tous les messages d'un ticket dans le terminal
  Afin de suivre l'historique de la conversation sans accéder au portail web

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Afficher les messages d'un ticket par référence
    When j'exécute "python main.py messages 26-083-026025"
    Then le nombre de messages est affiché dans l'en-tête
    And chaque message est affiché dans un panneau Rich avec son type et sa date

  Scenario: Distinguer messages entrants et sortants
    Given le ticket comporte des messages de type INEXTRANET et INTRANET
    When j'exécute "python main.py messages 26-083-026025"
    Then les messages entrants (INEXTRANET) ont une bordure bleue
    And les messages sortants (INTRANET) ont une bordure grise

  Scenario: Afficher les messages par ID hexadécimal
    When j'exécute "python main.py messages 00294000001e8cbd"
    Then les messages sont affichés sans étape de résolution d'ID

  Scenario: Limiter le nombre de messages
    When j'exécute "python main.py messages 26-083-026025 --limit 5"
    Then au maximum 5 messages sont récupérés et affichés

  Scenario: Indiquer les pièces jointes
    Given un message comporte une pièce jointe
    When j'exécute "python main.py messages 26-083-026025"
    Then l'en-tête du message affiche "📎 1 pièce(s)"

  Scenario: Sortie JSON brut
    When j'exécute "python main.py messages 26-083-026025 --json-output"
    Then la sortie est un tableau JSON contenant chaque message avec id, title, body, type_code, created_at, attachments

  Scenario: Ticket sans message
    Given le ticket n'a pas encore de message
    When j'exécute "python main.py messages 26-083-026025"
    Then le message "Aucun message sur ce ticket." est affiché en jaune
