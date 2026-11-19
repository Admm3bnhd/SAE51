"""Tests de la détermination du type d'équipement."""

import pytest

from inventaire.classification import classifier


@pytest.mark.parametrize("eq, attendu", [
    # sysServices
    ({"services": 78, "description": "Cisco IOS XE Software, ISR4331"}, "routeur"),
    ({"services": 6, "description": "Cisco IOS Software, Catalyst L3 Switch"}, "commutateur"),
    ({"services": 2, "description": "Cisco IOS Software, C2960"}, "commutateur"),
    # Windows Server annonce 76 (couches 3, 4, 7) : ce n'est pas un routeur
    ({"services": 76, "description": "Software: Windows Server 2022"}, "serveur"),
    ({"services": 72, "description": "Linux srv 6.1.0 Debian"}, "serveur"),
    # Mots-clés
    ({"description": "HP LaserJet Pro M404dn JETDIRECT"}, "imprimante"),
    ({"description": "Cisco AP Software, Aironet 2800"}, "point d'accès"),
    ({"description": "FortiGate-60F v7.2"}, "pare-feu"),
    ({"description": "Hardware: Intel64 - Software: Windows Version 10.0"}, "poste"),
    # Ports TCP
    ({"ports": [9100], "mac": "x"}, "imprimante"),
    ({"ports": [445, 3389], "mac": "x"}, "poste"),
    ({"ports": [22, 80], "mac": "x"}, "serveur"),
    # Défaut
    ({"mac": "aa:bb:cc:dd:ee:ff"}, "poste"),
    ({}, "inconnu"),
])
def test_classifier(eq, attendu):
    type_, raison = classifier(eq)
    assert type_ == attendu
    assert raison  # une justification est toujours fournie


def test_passerelle_est_un_routeur():
    assert classifier({"ip": "192.168.1.1", "mac": "x"}, "192.168.1.1")[0] == "routeur"


def test_snmp_prioritaire_sur_la_passerelle():
    # Un pare-feu qui sert de passerelle reste un pare-feu
    eq = {"ip": "192.168.1.1", "description": "pfSense 2.7"}
    assert classifier(eq, "192.168.1.1")[0] == "pare-feu"
