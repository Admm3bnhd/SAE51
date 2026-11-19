"""Tests de la construction du graphe de topologie."""

from inventaire.topologie import construire

RESEAUX = [{"reseau": "10.0.0.0/24", "passerelle": "10.0.0.1"}]


def eq(ip, nom="", mac="", type_="poste"):
    return {"ip": ip, "nom_snmp": nom, "nom_dns": "", "mac": mac, "type": type_, "en_ligne": 1}


def voisin(source, nom, ip="", chassis="", port_local="p1", port_distant="p2"):
    return {"ip_locale": source, "nom_distant": nom, "ip_distante": ip,
            "chassis_distant": chassis, "port_local": port_local, "port_distant": port_distant}


def liens_lldp(graphe):
    return [l for l in graphe["liens"] if l["origine"] == "lldp"]


def test_lien_declare_des_deux_cotes_compte_une_fois():
    equipements = [eq("10.0.0.1", "R1", type_="routeur"), eq("10.0.0.2", "SW1")]
    voisins = [voisin("10.0.0.1", "SW1", "10.0.0.2", port_local="Gi0/0", port_distant="Gi0/1"),
               voisin("10.0.0.2", "R1", "10.0.0.1", port_local="Gi0/1", port_distant="Gi0/0")]
    liens = liens_lldp(construire(equipements, voisins, RESEAUX))
    assert len(liens) == 1
    assert {liens[0]["from"], liens[0]["to"]} == {"10.0.0.1", "10.0.0.2"}


def test_liens_paralleles_conserves():
    equipements = [eq("10.0.0.2", "SW1"), eq("10.0.0.3", "SW2")]
    voisins = [voisin("10.0.0.2", "SW2", "10.0.0.3", port_local="Gi0/1"),
               voisin("10.0.0.2", "SW2", "10.0.0.3", port_local="Gi0/2")]
    assert len(liens_lldp(construire(equipements, voisins, RESEAUX))) == 2


def test_correspondance_par_mac_puis_par_nom():
    # L'IP annoncée en LLDP n'est pas dans l'inventaire (autre interface)
    equipements = [eq("10.0.0.2", "SW1"), eq("10.0.0.10", "srv-web", mac="00:50:56:00:00:10"),
                   eq("10.0.0.11", "srv-fichiers")]
    voisins = [voisin("10.0.0.2", "srv-web", "172.16.0.10", chassis="00:50:56:00:00:10"),
               voisin("10.0.0.2", "SRV-FICHIERS.entreprise.lan", "172.16.0.11")]
    cibles = {l["to"] for l in liens_lldp(construire(equipements, voisins, RESEAUX))}
    assert cibles == {"10.0.0.10", "10.0.0.11"}


def test_voisin_hors_inventaire_ajoute_au_graphe():
    graphe = construire([eq("10.0.0.2", "SW1")],
                        [voisin("10.0.0.2", "SEP0011", "10.20.0.15")], RESEAUX)
    noeud = next(n for n in graphe["noeuds"] if n["id"] == "lldp:SEP0011")
    assert noeud["hors_inventaire"]


def test_orphelins_rattaches_au_segment_et_segment_a_la_passerelle():
    equipements = [eq("10.0.0.1", "R1", type_="routeur"), eq("10.0.0.50"), eq("10.0.0.51")]
    graphe = construire(equipements, [], RESEAUX)
    deduits = {(l["from"], l["to"]) for l in graphe["liens"] if l["origine"] == "deduit"}
    assert deduits == {("10.0.0.1", "net:10.0.0.0/24"),
                       ("net:10.0.0.0/24", "10.0.0.50"),
                       ("net:10.0.0.0/24", "10.0.0.51")}


def test_pas_de_segment_si_tout_est_relie_en_lldp():
    equipements = [eq("10.0.0.1", "R1"), eq("10.0.0.2", "SW1")]
    graphe = construire(equipements, [voisin("10.0.0.1", "SW1", "10.0.0.2")], RESEAUX)
    assert not any(n["type"] == "segment" for n in graphe["noeuds"])
