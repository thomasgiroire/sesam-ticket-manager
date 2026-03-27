# language: fr
Feature: CLI — Commande reply
  En tant qu'utilisateur CLI
  Je veux envoyer un message de réponse sur un ticket depuis le terminal
  Afin de communiquer avec le support SESAM-Vitale sans passer par le portail web

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Répondre avec titre et message passés en options
    When j'exécute "python main.py reply 26-083-026025 --title 'Suivi' --message 'Merci pour votre retour'"
    Then un récapitulatif est affiché avec le ticket, le titre et le message
    And après confirmation, le message est envoyé sur le portail
    And la sortie affiche "✅ Message envoyé"

  Scenario: Saisie interactive du titre et du message
    When j'exécute "python main.py reply 26-083-026025" sans passer --title ni --message
    Then le CLI demande le titre via une invite "📝 Titre du message"
    And le CLI demande le message via une invite "✉️  Votre message"

  Scenario: Annuler l'envoi à la confirmation
    Given le récapitulatif est affiché
    When je réponds "N" à la question "Envoyer ce message ?"
    Then le message "Annulé." est affiché en jaune
    And aucun message n'est envoyé sur le portail

  Scenario: Message vide refusé
    When j'exécute la commande reply avec un message vide
    Then le message "Message vide, annulé." est affiché en jaune
    And aucun appel API n'est effectué

  Scenario: Répondre par ID hexadécimal
    When j'exécute "python main.py reply 00294000001e8cbd --title 'Test' --message 'Bonjour'"
    Then l'ID est utilisé directement sans résolution de code
    And le message est envoyé avec succès
