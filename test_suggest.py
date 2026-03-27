"""
Script de validation de l'algorithme de suggestion service/qualification.
Utilise un dictionnaire de synonymes basé sur l'analyse des mots-clés par qualification.
"""
import json
import math
import re
from collections import Counter

STOPWORDS = {
    "je", "un", "une", "des", "les", "est", "en", "de", "du", "la", "le",
    "et", "ou", "sur", "pour", "avec", "par", "au", "aux", "il", "elle",
    "ils", "elles", "nous", "vous", "mon", "ma", "mes", "son", "sa", "ses",
    "ce", "cet", "cette", "ces", "qui", "que", "quoi", "dont", "où", "à",
    "pas", "ne", "plus", "bien", "aussi", "très", "lors", "si", "car",
    "mais", "donc", "or", "ni", "lors", "tout", "tous", "toute", "non",
    "par", "lors", "etc", "vs", "via", "chez", "cas", "dans", "sont",
    "bonjour", "cordialement", "merci", "avons", "notre", "leur", "nos",
}

# Mots-clés → parties de labels de qualifications
# Basé sur l'analyse tf-idf des tickets historiques
SYNONYMS: dict[str, list[str]] = {
    # === Package FSV ===
    "fsv": ["Package FSV"],
    "cica": ["Package FSV"],
    "ssv": ["Package FSV", "J'ai une erreur SSV"],
    "adm": ["Package FSV"],
    "installeur": ["Package FSV"],
    "str": ["Package FSV"],

    # === J'ai une erreur SSV ===
    "0x": ["J'ai une erreur SSV"],
    "fse": ["J'ai une erreur SSV"],

    # === Support ARL Négatif ===
    "arl": ["Support ARL"],
    "lot": ["Support ARL"],
    "lots": ["Support ARL"],
    "invérifiable": ["Support ARL"],
    "invérifiables": ["Support ARL"],
    "signature": ["Support ARL", "J'ai une erreur SSV"],

    # === Support CCAM ===
    "ccam": ["Support CCAM"],
    "c2s": ["Support CCAM"],
    "optam": ["Support CCAM", "Evolutions Règlementaires"],
    "tarification": ["Support CCAM"],

    # === Tables de l'annexe 2bis ===
    "annexe": ["Tables de l'annexe"],
    "majoration": ["Tables de l'annexe"],
    "ameli": ["Tables de l'annexe"],

    # === Package Tables d'Exploitation ===
    "srt": ["Package Tables"],
    "sts": ["Package Tables"],
    "plafonds": ["Package Tables"],

    # === Facturation ApCV (NFC/iPhone) ===
    "nfc": ["Facturation avec l'Appli"],
    "iphone": ["Facturation avec l'Appli"],
    "ios": ["Facturation avec l'Appli"],
    "apple": ["Facturation avec l'Appli"],
    "android": ["Facturation avec l'Appli"],

    # === Erreur apcv_xxx ===
    "apcv": ["Erreur apcv", "Facturation avec l'Appli"],
    "usb": ["Erreur apcv"],
    "hid": ["Erreur apcv"],
    "décodage": ["Erreur apcv"],

    # === Flux SV en production ===
    "mgen": ["Flux SV en phase de production"],
    "triptyque": ["Flux SV en phase de production"],
    "migration": ["Flux SV en phase de production"],
    "rejet": ["Flux SV", "Demande d'accompagnement"],
    "rejets": ["Flux SV", "Demande d'accompagnement"],
    "lot": ["Flux SV"],
    "télétransmission": ["Flux SV"],
    "télétransmissions": ["Flux SV"],

    # === Flux SV en phase de développement ===
    "4005": ["Flux SV en phase de développement"],

    # === Problème d'accès ===
    "404": ["Problème d'accès"],
    "finess": ["Problème d'accès"],
    "siret": ["Problème d'accès"],
    "mot passe": ["Problème d'accès"],
    "identifiant": ["Problème d'accès"],
    "connexion": ["Problème d'accès"],
    "industriels": ["Problème d'accès"],

    # === Evolutions Règlementaires ===
    "avenant": ["Evolutions Règlementaires", "j'ai une question concernant la documentation"],
    "réglementaire": ["Evolutions Règlementaires"],
    "reglementaire": ["Evolutions Règlementaires"],
    "frmt": ["Evolutions Règlementaires"],
    "valorisation": ["Evolutions Règlementaires"],
    "revalorisation": ["Evolutions Règlementaires"],
    "revalorisation": ["Evolutions Règlementaires"],

    # === Veille conventionnelle ===
    "coefficients": ["Veille conventionnelle"],
    "coefficient": ["Veille conventionnelle"],

    # === Support / question documentation ===
    "mcdc": ["j'ai une question concernant la documentation"],
    "cahier": ["j'ai une question concernant la documentation"],
    "scor": ["j'ai une question concernant la documentation"],
    "te2": ["j'ai une question concernant la documentation"],

    # === J'ai une question sur documentation/livrable ===
    "livrable": ["J'ai une question sur la documentation"],
    "mutuelle": ["J'ai une question sur la documentation"],
    "harmonie": ["J'ai une question sur la documentation"],
    "catégorie": ["J'ai une question sur la documentation"],

    # === J'ai une demande technique ou fonctionnelle ===
    "nir": ["J'ai une demande technique"],
    "annuaire": ["J'ai une demande technique"],
    "lps": ["J'ai une demande technique"],
    "ati": ["J'ai une demande technique"],
    "adri": ["J'ai une demande technique"],

    # === J'ai besoin d'aide en phase de développement ===
    "clc": ["J'ai besoin d'aide en phase de développement"],
    "etudes": ["J'ai besoin d'aide en phase de développement"],
    "éditeur": ["J'ai besoin d'aide en phase de développement", "J'ai une demande technique"],
    "intégration": ["J'ai besoin d'aide en phase de développement"],
    "integration": ["J'ai besoin d'aide en phase de développement"],
    "test": ["J'ai besoin d'aide en phase de développement"],
    "tests": ["J'ai besoin d'aide en phase de développement"],
    "développement": ["J'ai besoin d'aide en phase de développement", "Flux SV en phase de développement"],
    "developpement": ["J'ai besoin d'aide en phase de développement", "Flux SV en phase de développement"],

    # === Demande d'accompagnement ===
    "rsp": ["Demande d'accompagnement"],
    "meusrec": ["Demande d'accompagnement"],
    "entité": ["Demande d'accompagnement"],

    # === Installation composants ===
    "composant": ["à l'installation des composants"],
    "composants": ["à l'installation des composants"],
    "télécharger": ["à l'installation des composants"],
    "diagam": ["à l'installation des composants"],

    # === Autre sujet lié à la facturation ===
    "salarié": ["Autre sujet lié à la facturation"],
    "salarie": ["Autre sujet lié à la facturation"],
    "msp": ["Autre sujet lié à la facturation"],
    "selas": ["Autre sujet lié à la facturation"],
    "honoraires": ["Autre sujet lié à la facturation"],

    # === Je rencontre un dysfonctionnement ===
    "dysfonctionnement": ["Je rencontre un dysfonctionnement"],
    "anomalie": ["Je rencontre un dysfonctionnement"],
    "bug": ["Je rencontre un dysfonctionnement"],
    "ordonnance": ["Je rencontre un dysfonctionnement"],
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zàâäéèêëîïôùûüç0-9]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_cache(path: str) -> list[dict]:
    with open(path) as f:
        raw = json.load(f)
    return raw["data"].get("tickets:all", [])


def suggest(
    titre: str, description: str, qualifications: list[str], qual_freq: Counter
) -> tuple[str | None, float]:
    tokens = tokenize(titre + " " + description)
    if not tokens:
        return None, 0.0

    scores: dict[str, float] = {ql: 0.0 for ql in qualifications}
    token_set = set(tokens)

    # 1. Boost via synonymes (score +0.4 par hit)
    for token in token_set:
        if token in SYNONYMS:
            for partial_label in SYNONYMS[token]:
                for ql in qualifications:
                    if partial_label.lower() in ql.lower():
                        scores[ql] += 0.4

    # 2. Jaccard sur les tokens des labels de qualification (avec boost popularité)
    for ql in qualifications:
        qt = set(tokenize(ql))
        j = jaccard(token_set, qt)
        freq = qual_freq.get(ql, 0)
        scores[ql] += j * (1 + 0.1 * math.log(1 + freq))

    best_label = max(scores, key=lambda k: scores[k])
    best_score = scores[best_label]

    # Seuil minimum pour proposer une suggestion
    if best_score < 0.15:
        return None, 0.0

    return best_label, best_score


def main():
    cache_path = ".sesam_web_cache.json"
    tickets = load_cache(cache_path)

    with_qual = [t for t in tickets if t.get("qualification")]
    qual_freq = Counter(t["qualification"] for t in with_qual)
    qualifications = list(qual_freq.keys())

    print(f"Tickets avec qualification : {len(with_qual)} | Qualifications uniques : {len(qualifications)}\n")

    correct = 0
    no_suggestion = 0
    total = 0
    rows = []

    for t in with_qual:
        titre = t.get("titre", "")
        desc = t.get("description", "") or ""
        real_qual = t.get("qualification", "")

        predicted, score = suggest(titre, desc, qualifications, qual_freq)

        if predicted is None:
            no_suggestion += 1
            is_correct = False
        else:
            is_correct = predicted == real_qual
            if is_correct:
                correct += 1
        total += 1
        rows.append((
            t["code"], titre[:48], real_qual[:42],
            (predicted or "— (pas de suggestion)") [:42],
            round(score, 3), is_correct, predicted is None
        ))

    # Affichage : erreurs + succès mélangés (20 exemples)
    wrong_rows = [r for r in rows if not r[5] and not r[6]]
    correct_rows = [r for r in rows if r[5]]
    sample = wrong_rows[:10] + correct_rows[:10]
    sample.sort(key=lambda r: r[0])

    header = f"{'Ticket':<20} {'Titre':<50} {'Réelle':<44} {'Suggérée':<44} {'Score':<7} OK?"
    print(header)
    print("-" * len(header))
    for code, titre, real, pred, score, ok, no_sug in sample:
        ok_str = "✓" if ok else ("~" if no_sug else "✗")
        print(f"{code:<20} {titre:<50} {real:<44} {pred:<44} {score:<7} {ok_str}")

    suggested = total - no_suggestion
    print(f"""
Résultats :
  Total tickets évalués    : {total}
  Suggestion proposée      : {suggested} ({suggested/total*100:.0f}%)
  Pas de suggestion        : {no_suggestion} ({no_suggestion/total*100:.0f}%)
  Correctes (sur suggérées): {correct}/{suggested} = {correct/suggested*100:.1f}%
  Précision globale        : {correct}/{total} = {correct/total*100:.1f}%
""")

    # Quelques exemples naturels pour valider le bon sens
    print("=== Test sur des phrases en langage naturel ===\n")
    examples = [
        ("Dysfonctionnement lors de la facturation", "J'ai une erreur lors de la facturation des actes, depuis ce matin"),
        ("Question sur l'avenant 30", "Bonjour, je voudrais savoir si l'avenant 30 s'applique aux kinésithérapeutes"),
        ("Aide pour intégration SESAM", "Nous développons un logiciel et avons besoin d'aide pour l'intégration"),
        ("Problème accès portail industriels", "Je n'arrive pas à me connecter, mot de passe refusé"),
        ("CCAM acte non reconnu", "L'acte CCAM référence XXX n'est pas reconnu dans le logiciel"),
        ("FSV CICA version 2.0 bug", "Erreur lors de l'installation du package FSV CICA 2.0"),
    ]
    for titre_ex, desc_ex in examples:
        pred, score = suggest(titre_ex, desc_ex, qualifications, qual_freq)
        print(f"  Titre : \"{titre_ex}\"")
        print(f"  Desc  : \"{desc_ex[:70]}\"")
        print(f"  → {pred or '(pas de suggestion)'} (score {score:.3f})\n")


if __name__ == "__main__":
    main()
