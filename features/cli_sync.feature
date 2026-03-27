# language: fr
Feature: CLI — Commande sync
  En tant qu'utilisateur CLI
  Je veux détecter les tickets nouveaux ou modifiés depuis la dernière synchronisation
  Afin de mettre à jour l'état local sans traiter des tickets déjà connus

  Background:
    Given les variables d'environnement SESAM_USERNAME et SESAM_PASSWORD sont définies

  Scenario: Synchronisation standard (nouveaux et modifiés seulement)
    Given l'état local contient des tickets connus
    When j'exécute "python main.py sync"
    Then le nombre de tickets récupérés est affiché
    And seuls les tickets nouveaux ou dont updated_at a changé sont listés dans le tableau
    And ces tickets sont marqués comme synchronisés dans .sesam_state.json

  Scenario: Tout est à jour
    Given tous les tickets sont déjà connus avec le même updated_at
    When j'exécute "python main.py sync"
    Then le message "✅ Tout est à jour, rien à synchroniser." est affiché en vert

  Scenario: Synchroniser tous les tickets (--all)
    When j'exécute "python main.py sync --all"
    Then la ligne "Traitement de tous les tickets" est affichée
    And tous les tickets (nouveaux et connus) sont inclus dans le tableau

  Scenario: Mode dry-run — simulation sans modification
    When j'exécute "python main.py sync --dry-run"
    Then l'avertissement "Mode DRY-RUN" est affiché en jaune
    And le tableau des tickets à synchroniser est affiché
    And le fichier .sesam_state.json n'est pas modifié
    And la sortie se termine par "DRY-RUN : aucune action effectuée."

  Scenario: Inclure les tickets clos (--closed)
    When j'exécute "python main.py sync --closed"
    Then les tickets avec le statut "Résolu" ou "Clôturé" sont inclus dans l'analyse

  Scenario: Erreur d'authentification pendant la sync
    Given SESAM_USERNAME ou SESAM_PASSWORD est incorrect
    When j'exécute "python main.py sync"
    Then un message d'erreur est affiché
    And le code de retour est 1
    And l'état local n'est pas modifié
