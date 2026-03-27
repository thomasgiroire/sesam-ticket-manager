# language: fr
Feature: Web App — Créer un ticket
  En tant qu'utilisateur de l'interface web
  Je veux créer un nouveau ticket de demande depuis le formulaire web
  Afin de soumettre une demande de support sans passer par le portail IRIS

  Background:
    Given l'application web est démarrée sur http://localhost:8473
    And je suis connecté au portail IRIS via les variables d'environnement

  Scenario: Affichage du formulaire
    When je visite "/tickets/create"
    Then un formulaire est affiché avec les champs : Titre, Description, Service, Qualification, Priorité

  Scenario: Les listes de services et qualifications sont chargées
    When je visite "/tickets/create"
    Then la liste déroulante "Service" contient les services disponibles du portail
    And la liste déroulante "Qualification" contient les qualifications disponibles

  Scenario: Créer un ticket avec succès
    When je remplis le formulaire avec un titre et une description valides
    And je soumet le formulaire
    Then le cache de la liste des tickets est invalidé
    And je suis redirigé vers la page de détail du nouveau ticket "/tickets/{id}"

  Scenario: Champs obligatoires manquants
    When je soumet le formulaire sans renseigner le titre
    Then le formulaire est réaffiché avec un message d'erreur de validation

  Scenario: Erreur API lors de la création
    Given le portail retourne une erreur lors de la création
    When je soumet le formulaire avec des données valides
    Then le formulaire est réaffiché avec le message d'erreur API
    And les valeurs précédemment saisies sont conservées dans le formulaire

  Scenario: Sélection de la priorité
    When je sélectionne la priorité "URGENT" dans le formulaire
    And je soumet le formulaire avec les autres champs remplis
    Then le ticket est créé avec la priorité "URGENT" sur le portail
