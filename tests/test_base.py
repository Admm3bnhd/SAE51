"""Tests de l'enregistrement en base et de la détection des changements."""

RESEAU = "10.0.0.0/24"


def eq(ip, **champs):
    return {"ip": ip, "mac": "", "type": "poste", "ports": "", "snmp": 0, **champs}


def types_evenements(base):
    return sorted((e["ip"], e["type"]) for e in base.lister_evenements(100))


def test_premier_scan_cree_des_evenements_nouveau(base):
    bilan = base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1"), eq("10.0.0.2")], {})
    assert bilan == {"nouveaux": 2, "disparus": 0, "reapparus": 0}
    assert base.statistiques()["en_ligne"] == 2


def test_equipement_absent_puis_de_retour(base):
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1"), eq("10.0.0.2")], {})

    bilan = base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1")], {})
    assert bilan["disparus"] == 1
    assert base.equipement("10.0.0.2")["en_ligne"] == 0

    bilan = base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1"), eq("10.0.0.2")], {})
    assert bilan["reapparus"] == 1
    assert ("10.0.0.2", "reapparu") in types_evenements(base)


def test_un_scan_ne_touche_pas_les_autres_reseaux(base):
    base.enregistrer_resultats("10.0.1.0/24", None, [eq("10.0.1.5")], {})
    bilan = base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1")], {})
    assert bilan["disparus"] == 0
    assert base.equipement("10.0.1.5")["en_ligne"] == 1


def test_les_informations_connues_sont_conservees(base):
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1", nom_snmp="SW1", ports="22")], {})
    # Au scan suivant, SNMP ne répond pas et le port 22 est fermé
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.1", nom_snmp="", ports="")], {})
    ligne = base.equipement("10.0.0.1")
    assert ligne["nom_snmp"] == "SW1"   # identité conservée
    assert ligne["ports"] == ""         # état des services mis à jour


def test_voisins_remplaces_a_chaque_scan(base):
    v1 = {"port_local": "Gi0/1", "nom_distant": "R1"}
    v2 = {"port_local": "Gi0/2", "nom_distant": "SW2"}
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.2")], {"10.0.0.2": [v1]})
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.2")], {"10.0.0.2": [v2]})
    assert [v["nom_distant"] for v in base.lister_voisins("10.0.0.2")] == ["SW2"]


def test_tri_numerique_des_adresses(base):
    base.enregistrer_resultats(RESEAU, None, [eq("10.0.0.10"), eq("10.0.0.9")], {})
    assert [e["ip"] for e in base.lister_equipements()] == ["10.0.0.9", "10.0.0.10"]
