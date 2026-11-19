"""Tests de l'analyse des réponses SNMP.

Les sorties ci-dessous ont été capturées sur le labo de test (snmpd +
lldpd dans deux namespaces reliés par une paire veth), voir docs/06-tests.md.
"""

from inventaire import snmp
from inventaire.config import ConfigSNMP

WALK_LLDP_REM = """\
.1.0.8802.1.1.2.1.4.1.1.4.10400.6.1 4
.1.0.8802.1.1.2.1.4.1.1.5.10400.6.1 "C6 00 EF A5 29 B7 "
.1.0.8802.1.1.2.1.4.1.1.6.10400.6.1 3
.1.0.8802.1.1.2.1.4.1.1.7.10400.6.1 "C6 00 EF A5 29 B7 "
.1.0.8802.1.1.2.1.4.1.1.8.10400.6.1 "veth-b"
.1.0.8802.1.1.2.1.4.1.1.9.10400.6.1 "sw-labo"
.1.0.8802.1.1.2.1.4.1.1.10.10400.6.1 "Commutateur de test"
"""

WALK_LLDP_MAN_ADDR = """\
.1.0.8802.1.1.2.1.4.2.1.3.10400.6.1.1.4.10.99.0.2 2
.1.0.8802.1.1.2.1.4.2.1.4.10400.6.1.1.4.10.99.0.2 5
"""

WALK_LLDP_LOC_PORT = """\
.1.0.8802.1.1.2.1.3.7.1.2.6 3
.1.0.8802.1.1.2.1.3.7.1.3.6 "DE EF 87 75 1E EF "
.1.0.8802.1.1.2.1.3.7.1.4.6 "veth-a"
"""


def test_options_v2c():
    options = snmp.options_snmp(ConfigSNMP(communaute="labo"))
    assert options[:3] == ["-v2c", "-c", "labo"]


def test_options_v3_authpriv():
    cfg = ConfigSNMP(version="3", utilisateur="admin", niveau="authPriv",
                     auth_motdepasse="motdepasse1", priv_motdepasse="motdepasse2")
    options = snmp.options_snmp(cfg)
    assert options[:5] == ["-v3", "-u", "admin", "-l", "authPriv"]
    assert "-A" in options and "-X" in options


def test_options_v3_sans_chiffrement():
    cfg = ConfigSNMP(version="3", utilisateur="admin", niveau="authNoPriv",
                     auth_motdepasse="motdepasse1")
    assert "-X" not in snmp.options_snmp(cfg)


def test_analyser_walk_valeurs_multilignes_et_absentes():
    texte = (".1.3.6.1.2.1.1.1.0 \"Cisco IOS Software\nTechnical Support\"\n"
             ".1.3.6.1.2.1.1.9.0 No Such Object available on this agent at this OID\n")
    assert snmp.analyser_walk(texte) == [
        ("1.3.6.1.2.1.1.1.0", "Cisco IOS Software\nTechnical Support")]


def test_construire_voisins_lldp():
    voisins = snmp.construire_voisins(snmp.analyser_walk(WALK_LLDP_LOC_PORT),
                                      snmp.analyser_walk(WALK_LLDP_REM),
                                      snmp.analyser_walk(WALK_LLDP_MAN_ADDR))
    assert voisins == [{
        "port_local": "veth-a",
        "nom_distant": "sw-labo",
        "port_distant": "veth-b",
        "ip_distante": "10.99.0.2",
        "chassis_distant": "c6:00:ef:a5:29:b7",
    }]


def test_interroger_sans_reponse(monkeypatch):
    monkeypatch.setattr(snmp, "_executer", lambda commande, cfg: None)
    assert snmp.interroger("192.0.2.1", ConfigSNMP()) is None


def test_interroger_identite(monkeypatch):
    reponses = {
        snmp.OID_SYS_DESCR: '"Cisco IOS Software, C2960 Software"\n',
        snmp.OID_SYS_NAME: '"SW1"\n',
        snmp.OID_SYS_OBJECT_ID: ".1.3.6.1.4.1.9.1.1208\n",
        snmp.OID_SYS_SERVICES: "2\n",
    }
    monkeypatch.setattr(snmp, "_executer", lambda commande, cfg: reponses[commande[-1]])
    assert snmp.interroger("192.0.2.1", ConfigSNMP()) == {
        "description": "Cisco IOS Software, C2960 Software",
        "nom_snmp": "SW1",
        "object_id": ".1.3.6.1.4.1.9.1.1208",
        "services": 2,
    }
