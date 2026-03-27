# language: fr
Feature: CLI — Commande export
  En tant qu'utilisateur CLI
  Je veux exporter un ticket dans un format structuré
  Afin de l'utiliser dans un agent DUST ou un outil d'analyse externe

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Export en Markdown (format par défaut)
    When j'exécute "python main.py export 26-083-026025"
    Then la sortie standard contient un document Markdown structuré
    And le document commence par "# Ticket SESAM-Vitale : 26-083-026025"
    And les métadonnées (Titre, Statut, Priorité, Type, Demandeur) sont présentes
    And les messages sont listés sous "## Messages (N)"

  Scenario: Export en JSON
    When j'exécute "python main.py export 26-083-026025 --format json"
    Then la sortie est un objet JSON valide
    And il contient les clés "ticket" et "messages"
    And chaque message contient : direction, objet, contenu, date, pieces_jointes

  Scenario: Export par ID hexadécimal
    When j'exécute "python main.py export 00294000001e8cbd --format markdown"
    Then le document Markdown est généré sans erreur

  Scenario: Messages avec pièces jointes dans l'export
    Given le ticket comporte des messages avec pièces jointes
    When j'exécute "python main.py export 26-083-026025"
    Then chaque pièce jointe est listée sous son message avec l'icône 📎 et son nom

  Scenario: Export redirigé vers un fichier
    When j'exécute "python main.py export 26-083-026025 > ticket.md"
    Then le fichier ticket.md est créé avec le contenu Markdown attendu
