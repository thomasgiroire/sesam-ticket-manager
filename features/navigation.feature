# language: fr
Feature: Navigation principale
  En tant qu'utilisateur
  Je veux pouvoir naviguer entre les sections de l'outil
  Afin d'accéder rapidement aux informations

  Scenario: Accéder au Dashboard depuis n'importe quelle page
    Given je suis sur n'importe quelle page de l'outil
    When je clique sur le lien "Dashboard" dans la navigation
    Then je suis redirigé vers la page "/"
    And je vois les statistiques globales (tickets ouverts, clos, total)

  Scenario: Accéder à la liste des tickets
    Given je suis sur le Dashboard
    When je clique sur le lien "Tickets" dans la navigation
    Then je suis redirigé vers "/tickets"
    And je vois un tableau avec les colonnes Référence, Titre, Statut, JIRA, Auteur, Mis à jour

  Scenario: Retour au Dashboard depuis la liste des tickets
    Given je suis sur la page "/tickets"
    When je clique sur le lien "Dashboard" dans la navigation
    Then je suis redirigé vers "/"

  Scenario: Retour à la liste depuis le détail d'un ticket
    Given je suis sur la page de détail d'un ticket
    When je clique sur le lien "← Tickets" ou le bouton retour
    Then je suis redirigé vers "/tickets"
