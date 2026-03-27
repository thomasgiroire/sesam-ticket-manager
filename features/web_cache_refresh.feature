# language: fr
Feature: Web App — Rafraîchissement du cache
  En tant qu'utilisateur de l'interface web
  Je veux pouvoir rafraîchir manuellement les données affichées
  Afin de voir les tickets mis à jour depuis le dernier chargement sans redémarrer le serveur

  Background:
    Given l'application web est démarrée sur http://localhost:8473

  Scenario: Refresh delta (intelligent)
    When je clique sur le bouton "Refresh" (POST /refresh)
    Then seuls les tickets dont le statut ou updated_at a changé sont re-téléchargés
    And les messages des tickets modifiés sont enrichis
    And le cache mémoire et disque est mis à jour avec la liste consolidée
    And je suis redirigé vers "/" avec le paramètre "?updated=N" (N = nombre de changements)

  Scenario: Refresh complet (force)
    When je clique sur le bouton "Refresh complet" (POST /refresh/full)
    Then le cache mémoire est vidé
    And le fichier .sesam_web_cache.json est supprimé
    And je suis redirigé vers "/" qui recharge toutes les données depuis le portail

  Scenario: Indicateur d'âge du cache
    Given le cache disque a été créé il y a 10 minutes
    When je visite le dashboard
    Then l'indicateur affiche "il y a 10 min"

  Scenario: Cache absent (premier démarrage)
    Given le fichier .sesam_web_cache.json n'existe pas
    When je visite "/"
    Then l'indicateur d'âge du cache est vide ou absent
    And les tickets sont chargés directement depuis le portail

  Scenario: Cache expiré (plus de 1 heure)
    Given le fichier .sesam_web_cache.json a plus de 3600 secondes
    When les données sont demandées via _cached()
    Then le cache disque est ignoré et une requête fraîche est effectuée vers le portail

  Scenario: Affichage du résumé du dernier refresh
    Given le dernier refresh a détecté 2 tickets modifiés
    When je visite "/"
    Then le résumé du dernier refresh est visible avec les codes et anciens/nouveaux statuts
