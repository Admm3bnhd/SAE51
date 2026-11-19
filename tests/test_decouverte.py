"""Tests de l'analyse des sorties système et de l'identification des constructeurs."""

import pytest

from inventaire import decouverte, oui

SORTIE_IP_NEIGH = """\
192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE
192.168.1.20 dev eth0 lladdr AA:BB:CC:DD:EE:FF STALE
192.168.1.30 dev eth0  INCOMPLETE
192.168.1.40 dev eth0  FAILED
"""


def test_lister_hotes_exclut_reseau_et_broadcast():
    hotes = decouverte.lister_hotes("192.168.1.0/30")
    assert hotes == ["192.168.1.1", "192.168.1.2"]


def test_lister_hotes_accepte_une_adresse_hote():
    # « 192.168.1.17/24 » est accepté et ramené au réseau 192.168.1.0/24
    assert len(decouverte.lister_hotes("192.168.1.17/24")) == 254


@pytest.mark.parametrize("reseau", ["10.0.0.0/8", "fe80::/64", "pas-un-reseau"])
def test_lister_hotes_refuse_les_reseaux_invalides(reseau):
    with pytest.raises(ValueError):
        decouverte.lister_hotes(reseau)


def test_analyser_ip_neigh_ignore_les_entrees_incompletes():
    table = decouverte.analyser_ip_neigh(SORTIE_IP_NEIGH)
    assert table == {
        "192.168.1.1": ("00:11:22:33:44:55", "REACHABLE"),
        "192.168.1.20": ("aa:bb:cc:dd:ee:ff", "STALE"),
    }


def test_confirmer_par_arp_ecarte_les_entrees_perimees(monkeypatch):
    # 1re lecture : les deux entrées sont en cours de vérification ;
    # 2e lecture : .20 a répondu (REACHABLE), .30 a échoué (FAILED → absente)
    lectures = iter([
        {"192.168.1.20": ("aa:aa:aa:aa:aa:20", "DELAY"),
         "192.168.1.30": ("aa:aa:aa:aa:aa:30", "PROBE")},
        {"192.168.1.20": ("aa:aa:aa:aa:aa:20", "REACHABLE")},
    ])
    monkeypatch.setattr(decouverte, "lire_table_arp", lambda: next(lectures))
    monkeypatch.setattr(decouverte.time, "sleep", lambda s: None)
    confirmes = decouverte.confirmer_par_arp({"192.168.1.20", "192.168.1.30"})
    assert confirmes == {"192.168.1.20": "aa:aa:aa:aa:aa:20"}


def test_analyser_route_defaut():
    texte = "default via 192.168.1.254 dev eth0 proto dhcp metric 100\n"
    assert decouverte.analyser_route_defaut(texte) == "192.168.1.254"
    assert decouverte.analyser_route_defaut("") is None


def test_analyser_ip_addr():
    texte = ("1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever\n"
             "2: eth0    inet 192.168.1.42/24 brd 192.168.1.255 scope global eth0\n")
    assert decouverte.analyser_ip_addr(texte) == {"127.0.0.1": "lo", "192.168.1.42": "eth0"}


@pytest.mark.parametrize("entree", [
    "00:1A:2B:3C:4D:5E", "00-1a-2b-3c-4d-5e", "001a.2b3c.4d5e", '"00 1A 2B 3C 4D 5E "',
])
def test_normaliser_mac(entree):
    assert decouverte.normaliser_mac(entree) == "00:1a:2b:3c:4d:5e"


def test_normaliser_mac_rejette_ce_qui_nest_pas_une_mac():
    assert decouverte.normaliser_mac("veth-b") == ""
    assert decouverte.normaliser_mac("") == ""


def test_constructeur_table_integree():
    assert oui.constructeur("00:50:56:aa:bb:cc") == "VMware"
    assert oui.constructeur("b8:27:eb:00:00:01") == "Raspberry Pi"


def test_constructeur_mac_aleatoire():
    # 2e bit de poids faible du 1er octet à 1 (0xa6 = 1010 0110)
    assert oui.est_administree_localement("a6:5f:1e:77:01:01")
    assert oui.constructeur("a6:5f:1e:77:01:01") == "MAC locale / aléatoire"


def test_constructeur_fichier_ieee(tmp_path):
    fichier = tmp_path / "oui.txt"
    fichier.write_text("3C-2A-F4   (hex)\t\tBrother Industries, LTD.\n"
                       "3C2AF4     (base 16)\t\tBrother Industries, LTD.\n")
    assert oui.constructeur("3c:2a:f4:20:20:20", str(fichier)) == "Brother Industries, LTD."
    assert oui.constructeur("3c:2a:f4:20:20:20") == ""  # sans fichier : inconnu


def test_port_ouvert_sur_un_serveur_local():
    import socket
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen()
    port = serveur.getsockname()[1]
    try:
        assert decouverte.ports_ouverts("127.0.0.1", [port], 0.5) == [port]
    finally:
        serveur.close()
    assert decouverte.ports_ouverts("127.0.0.1", [port], 0.5) == []
