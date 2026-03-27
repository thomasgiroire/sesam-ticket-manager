# language: fr
Feature: Web App — Dashboard
  En tant qu'utilisateur de l'interface web
  Je veux voir un tableau de bord synthétique au chargement de l'application
  Afin d'avoir une vue d'ensemble immédiate de mes tickets SESAM-Vitale

  Background:
    Given l'application web est démarrée sur http://localhost:8473
    And je suis connecté au portail IRIS via les variables d'environnement

  Scenario: Affichage des compteurs globaux
    When je visite "/"
    Then je vois le nombre total de tickets
    And je vois le nombre de tickets ouverts
    And je vois le nombre de tickets clos

  Scenario: Répartition des tickets par statut
    When je visite "/"
    Then un bloc "Répartition par statut" liste les statuts et leur nombre
    And les statuts sont triés par fréquence décroissante

  Scenario: Tickets récents (hot tickets)
    When je visite "/"
    Then la section "Activité récente" affiche jusqu'à 15 tickets
    And les tickets mis à jour dans les dernières 24h sont marqués 🔥

  Scenario: Indicateur d'âge du cache
    Given le cache disque existe
    When je visite "/"
    Then l'âge du cache est affiché (ex: "il y a 5 min")

  Scenario: Résultat du dernier refresh affiché
    Given un refresh a été déclenché et a détecté 3 tickets modifiés
    When je suis redirigé vers "/" avec le paramètre "?updated=3"
    Then un bandeau indique "3 ticket(s) mis à jour"

  Scenario: Erreur de connexion au portail
    Given le portail IRIS est inaccessible
    When je visite "/"
    Then la page d'erreur 503 est affichée avec le message d'erreur
