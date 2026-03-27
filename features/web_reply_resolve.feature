# language: fr
Feature: Web App — Répondre et résoudre un ticket
  En tant qu'utilisateur de l'interface web
  Je veux envoyer des messages de réponse et résoudre des tickets depuis la page de détail
  Afin de gérer la communication avec le support sans quitter l'application

  Background:
    Given l'application web est démarrée sur http://localhost:8473
    And je suis sur la page de détail d'un ticket ouvert "/tickets/{id}"

  Scenario: Affichage du formulaire de réponse
    Then un formulaire de réponse est visible en bas de la page de détail
    And le champ de saisie du message est présent

  Scenario: Envoyer un message de réponse
    When je saisit un message dans le champ de réponse
    And je clique sur le bouton "Envoyer"
    Then le message est posté sur le portail via POST /messages
    And le cache des messages du ticket est invalidé
    And je suis redirigé vers la page de détail du même ticket

  Scenario: Répondre et résoudre en une seule action
    When je saisit un message de réponse
    And je clique sur le bouton "Envoyer et résoudre"
    Then le message est envoyé sur le portail
    And le ticket est résolu via PUT /requests/{id}/solve
    And le cache global des tickets est invalidé
    And je suis redirigé vers la page de détail du ticket

  Scenario: Résoudre un ticket sans envoyer de message
    When je clique sur le bouton "Résoudre le ticket" (POST /resolve)
    Then le ticket est résolu sur le portail
    And le cache des messages et des tickets est invalidé
    And je suis redirigé vers la page de détail du ticket

  Scenario: Message vide non autorisé
    When je soumet le formulaire de réponse avec un message vide
    Then la validation HTML5 empêche la soumission du formulaire

  Scenario: Erreur API lors de l'envoi
    Given le portail retourne une erreur 503 lors de l'ajout de message
    When je soumet le formulaire de réponse
    Then la page d'erreur est affichée avec le message d'erreur API
