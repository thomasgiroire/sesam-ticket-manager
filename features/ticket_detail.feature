# language: fr
Feature: Détail d'un ticket
  En tant qu'utilisateur
  Je veux consulter le détail complet d'un ticket et ses messages
  Afin de suivre l'historique des échanges avec le support SESAM

  Background:
    Given je suis sur la page de détail d'un ticket

  Scenario: Affichage des métadonnées du ticket
    Then je vois dans le panneau gauche :
      | Champ      | Valeur attendue             |
      | RÉFÉRENCE  | Code du ticket (ex: 26-xxx) |
      | STATUT     | Statut actuel               |
      | PRIORITÉ   | Niveau de priorité          |
      | SERVICE    | Service concerné            |
      | CRÉÉ LE    | Date de création            |
      | MIS À JOUR | Date de dernière MAJ        |

  Scenario: Scroll sur le contenu des messages
    Given le ticket a plusieurs messages
    Then je peux faire défiler la liste des messages vers le bas
    And le dernier message (le plus récent) est visible en bas de page
    And la zone de réponse est accessible après scroll

  Scenario: Affichage des messages dans l'ordre chronologique
    Then les messages sont affichés du plus ancien (haut) au plus récent (bas)
    And les messages client sont affichés à droite (fond bleu)
    And les messages SESAM sont affichés à gauche (fond gris)

  Scenario: Pièces jointes téléchargeables
    Given un message contient une pièce jointe
    Then je vois un bouton de téléchargement avec le nom du fichier
    When je clique sur le lien de la pièce jointe
    Then le téléchargement démarre via le proxy "/tickets/{id}/attachments/{att_id}"

  Scenario: Formulaire de réponse
    Given je suis au bas de la page
    Then je vois un formulaire avec les champs "Titre" et "Message"
    When je remplis le formulaire et je clique sur "Envoyer"
    Then le message est publié sur le portail SESAM
    And je suis redirigé vers la même page de détail

  Scenario: Performance du chargement du détail
    Then la page se charge en moins de 2 secondes (cache chaud)
