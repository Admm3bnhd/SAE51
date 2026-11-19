"""Données de démonstration : un petit réseau d'entreprise fictif.

Permet de présenter l'interface sans réseau réel (soutenance, tests).
Les données passent par les **mêmes fonctions** qu'un vrai scan
(classification, enregistrement, détection des changements) : seule la
collecte sur le réseau est simulée.

Topologie simulée (192.168.10.0/24) ::

                      R1-CORE (.1, passerelle)
                         | Gi0/0/1
                         | Gi1/0/24
                      SW-CORE (.2) ---- srv-web (.10), srv-fichiers (.11)
                      /          \\
               SW-ETAGE1 (.3)   SW-ETAGE2 (.4) ---- SEP0011... (téléphone IP,
                    |                                autre VLAN, hors inventaire)
              AP-ETAGE1 (.30)

    + postes, imprimante, sonde Raspberry Pi et smartphone sans LLDP.
"""

from pathlib import Path

from .base import Base
from .classification import classifier
from .oui import constructeur

RESEAU = "192.168.10.0/24"
PASSERELLE = "192.168.10.1"


def _eq(ip, mac, nom_dns="", nom_snmp="", description="", services=None, ports=()):
    return {"ip": ip, "mac": mac, "nom_dns": nom_dns, "nom_snmp": nom_snmp,
            "description": description, "services": services, "ports": list(ports),
            "snmp": 1 if description else 0}


def _v(port_local, nom, port_distant, ip="", chassis=""):
    return {"port_local": port_local, "nom_distant": nom, "port_distant": port_distant,
            "ip_distante": ip, "chassis_distant": chassis}


EQUIPEMENTS = [
    _eq("192.168.10.1", "00:00:0c:9f:f0:01", "r1-core.entreprise.lan", "R1-CORE",
        "Cisco IOS XE Software, ISR4331 Software (X86_64_LINUX_IOSD-UNIVERSALK9-M), "
        "Version 17.9.4", 78, [22, 443]),
    _eq("192.168.10.2", "00:00:0c:a1:00:02", "sw-core.entreprise.lan", "SW-CORE",
        "Cisco IOS Software, Catalyst L3 Switch Software (CAT9K_IOSXE), Version 17.9.4",
        6, [22]),
    _eq("192.168.10.3", "00:00:0c:b2:00:03", "", "SW-ETAGE1",
        "Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 15.2(7)E8",
        2, [22]),
    _eq("192.168.10.4", "00:00:0c:b2:00:04", "", "SW-ETAGE2",
        "Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 15.2(7)E8",
        2, [22]),
    _eq("192.168.10.10", "00:50:56:8a:10:10", "srv-web.entreprise.lan", "srv-web",
        "Linux srv-web 6.1.0-28-amd64 #1 SMP Debian 6.1.119-1 x86_64", 72, [22, 80, 443]),
    _eq("192.168.10.11", "00:50:56:8a:10:11", "srv-fichiers.entreprise.lan", "SRV-FICHIERS",
        "Hardware: Intel64 Family 6 Model 85 - Software: Windows Server 2022 Standard",
        76, [53, 445, 3389]),
    _eq("192.168.10.20", "3c:2a:f4:20:20:20", "imp-accueil.entreprise.lan", "IMP-ACCUEIL",
        "HP ETHERNET MULTI-ENVIRONMENT,ROM none,JETDIRECT,JD153,EEPROM JSI24090012 - "
        "HP LaserJet Pro M404dn", None, [80, 443, 631, 9100]),
    _eq("192.168.10.30", "00:00:0c:c3:00:30", "", "AP-ETAGE1",
        "Cisco AP Software, Aironet 2800 Series, Version 8.10.185.0", None, [22, 443]),
    _eq("192.168.10.50", "a4:bb:6d:50:00:50", "pc-compta-01.entreprise.lan", ports=[445, 3389]),
    _eq("192.168.10.51", "a4:bb:6d:50:00:51", "pc-compta-02.entreprise.lan", ports=[445]),
    _eq("192.168.10.52", "a4:bb:6d:50:00:52", "pc-rh-01.entreprise.lan", ports=[445, 3389]),
    _eq("192.168.10.53", "a4:bb:6d:50:00:53", "pc-direction.entreprise.lan", ports=[445]),
    _eq("192.168.10.60", "dc:a6:32:60:60:60", "sonde-temp.entreprise.lan", ports=[22]),
    _eq("192.168.10.101", "a6:5f:1e:77:01:01"),  # smartphone : MAC aléatoire
]

VOISINS = {
    "192.168.10.1": [_v("Gi0/0/1", "SW-CORE", "Gi1/0/24", "192.168.10.2")],
    "192.168.10.2": [
        _v("Gi1/0/24", "R1-CORE", "Gi0/0/1", "192.168.10.1"),
        _v("Gi1/0/1", "SW-ETAGE1", "Gi0/1", "192.168.10.3"),
        _v("Gi1/0/2", "SW-ETAGE2", "Gi0/1", "192.168.10.4"),
        _v("Gi1/0/10", "srv-web", "ens18", chassis="00:50:56:8a:10:10"),
        _v("Gi1/0/11", "SRV-FICHIERS.entreprise.lan", "Ethernet0"),
    ],
    "192.168.10.3": [
        _v("Gi0/1", "SW-CORE", "Gi1/0/1", "192.168.10.2"),
        _v("Fa0/5", "AP-ETAGE1", "Gi0", "192.168.10.30"),
    ],
    "192.168.10.4": [
        _v("Gi0/1", "SW-CORE", "Gi1/0/2", "192.168.10.2"),
        # Téléphone IP dans le VLAN voix (10.20.0.0/24, non scanné)
        _v("Fa0/3", "SEP001122334455", "Port 1", "10.20.0.15"),
    ],
    "192.168.10.10": [_v("ens18", "SW-CORE", "Gi1/0/10", "192.168.10.2")],
}

# Équipement présent au premier scan seulement (pour montrer un « disparu »)
ANCIEN_POSTE = _eq("192.168.10.54", "a4:bb:6d:50:00:54", "pc-stagiaire.entreprise.lan",
                   ports=[445])


def _preparer(eq: dict) -> dict:
    eq = dict(eq, reseau=RESEAU, constructeur=constructeur(eq["mac"]))
    eq["type"], eq["raison_type"] = classifier(eq, PASSERELLE)
    eq["ports"] = ",".join(map(str, eq["ports"]))
    return eq


def remplir_demo(chemin: str) -> None:
    """Crée une base de démonstration (écrase la base existante)."""
    Path(chemin).unlink(missing_ok=True)
    base = Base(chemin)
    voisins_snmp = {ip: v for ip, v in VOISINS.items()}

    # Scan n°1 : sans le smartphone, avec le poste du stagiaire
    premier = [e for e in EQUIPEMENTS if e["ip"] != "192.168.10.101"] + [ANCIEN_POSTE]
    scan = base.debut_scan(RESEAU)
    base.enregistrer_resultats(RESEAU, PASSERELLE, [_preparer(e) for e in premier], voisins_snmp)
    base.fin_scan(scan, len(premier))

    # Scan n°2 : le smartphone apparaît, le poste du stagiaire a disparu
    scan = base.debut_scan(RESEAU)
    base.enregistrer_resultats(RESEAU, PASSERELLE, [_preparer(e) for e in EQUIPEMENTS],
                               voisins_snmp)
    base.fin_scan(scan, len(EQUIPEMENTS))
    base.fermer()
