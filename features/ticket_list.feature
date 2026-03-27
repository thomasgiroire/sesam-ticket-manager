# language: fr
Feature: Liste des tickets
  En tant qu'utilisateur
  Je veux voir tous les tickets GIE SESAM-Vitale
  Afin de gérer mes demandes de support

  Background:
    Given je suis sur la page "/tickets"

  Scenario: Affichage de la liste complète
    Then je vois un tableau avec au moins un ticket
    And les tickets sont triés par date de mise à jour décroissante
    And chaque ligne affiche : référence, titre, statut, priorité, auteur, date

  Scenario: Filtrer par statut
    When je sélectionne le filtre "En cours"
    Then seuls les tickets avec le statut "En cours" sont affichés
    And le compteur de résultats est mis à jour

  Scenario: Rechercher par mot-clé
    When je tape "SESAM" dans le champ de recherche
    Then seuls les tickets dont le titre ou la référence contient "SESAM" sont affichés

  Scenario: Effacer les filtres
    Given j'ai appliqué un filtre de statut
    When je clique sur "✕ Effacer les filtres"
    Then tous les tickets sont à nouveau affichés

  Scenario: Navigation vers le détail depuis la liste
    When je clique sur une ligne de ticket
    Then je suis redirigé vers la page de détail de ce ticket "/tickets/{id}"

  Scenario: Performance du chargement de la liste
    Then la page se charge en moins de 3 secondes (cache chaud)
    And la page se charge en moins de 10 secondes (premier chargement)
