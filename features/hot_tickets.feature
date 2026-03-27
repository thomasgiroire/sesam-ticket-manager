# language: fr
Feature: Tickets "chauds" (modifiés dans les 24 dernières heures)
  En tant qu'utilisateur
  Je veux identifier visuellement les tickets qui ont évolué récemment
  Afin de prioriser mes actions sans avoir à lire toutes les dates

  Scenario: Affichage du 🔥 dans la liste des tickets
    Given je suis sur la page "/tickets"
    And au moins un ticket a été modifié dans les dernières 24 heures
    Then ce ticket affiche l'emoji 🔥 dans la colonne dédiée à droite de la date
    And les tickets non modifiés dans les 24h n'ont pas d'emoji

  Scenario: Affichage du 🔥 sur le Dashboard
    Given je suis sur la page "/"
    And au moins un ticket actif a été modifié dans les dernières 24 heures
    Then ce ticket affiche l'emoji 🔥 à côté de son titre dans la liste des tickets récents

  Scenario: Cohérence avec les données réelles
    Given le ticket "26-057-025204" a reçu un message aujourd'hui
    Then il affiche 🔥 dans la liste
    And sa colonne "Mis à jour" affiche la date d'aujourd'hui

  Scenario: Pas de faux positifs
    Given un ticket a été modifié il y a plus de 24 heures
    Then il n'affiche pas 🔥

  Scenario: Critère temporel
    The filter "is_hot" is based on the "updated_at" field
    And a ticket is considered "hot" if updated_at > now - 24h (UTC)
