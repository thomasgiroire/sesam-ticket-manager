# language: fr
Feature: CLI — Commande list
  En tant qu'utilisateur CLI
  Je veux lister les tickets du Portail IRIS depuis le terminal
  Afin de visualiser rapidement l'état de mes demandes de support

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Lister les tickets ouverts (comportement par défaut)
    When j'exécute "python main.py list"
    Then un tableau Rich s'affiche avec les colonnes : Référence, Type, Statut, Priorité, Titre, Demandeur, Mis à jour
    And les tickets sont triés par date de mise à jour décroissante
    And la ligne de récapitulatif indique la page et le nombre de tickets affichés

  Scenario: Filtrer par statut
    When j'exécute "python main.py list --status 'En cours'"
    Then seuls les tickets dont le statut contient "En cours" sont affichés

  Scenario: Filtrer par type Incident
    When j'exécute "python main.py list --type Incident"
    Then seuls les tickets de type "Incident" sont affichés

  Scenario: Afficher uniquement les tickets ouverts
    When j'exécute "python main.py list --open-only"
    Then les tickets clos et résolus sont exclus de la liste

  Scenario: Sortie JSON brut
    When j'exécute "python main.py list --json-output"
    Then la sortie est un tableau JSON valide avec un objet par ticket
    And chaque objet contient les champs : id, code, titre, status, priority, type_ticket

  Scenario: Pagination manuelle
    When j'exécute "python main.py list --limit 10 --page 2"
    Then au maximum 10 tickets de la page 2 sont affichés

  Scenario: Récupération de toutes les pages
    When j'exécute "python main.py list --fetch-all"
    Then tous les tickets sont récupérés en autopaginant jusqu'à hasNextPage=false

  Scenario: Aucun ticket trouvé
    Given aucun ticket ne correspond aux critères de filtre
    When j'exécute "python main.py list --status 'Statut inexistant'"
    Then le message "Aucun ticket trouvé." est affiché en jaune

  Scenario: Erreur d'authentification
    Given SESAM_USERNAME ou SESAM_PASSWORD est incorrect
    When j'exécute "python main.py list"
    Then un message d'erreur rouge "Authentification" est affiché
    And le code de retour est 1
