"""Détermination du type d'un équipement.

Les règles sont appliquées dans l'ordre, de la plus fiable à la moins
fiable. Chaque décision est accompagnée d'une **raison** affichée dans
l'interface, pour que l'administrateur puisse juger de sa pertinence.

1. ``sysServices`` (SNMP) : bits des couches OSI assurées ;
2. mots-clés dans ``sysDescr`` (SNMP) ;
3. passerelle par défaut du réseau ⇒ routeur ;
4. ports TCP ouverts ;
5. à défaut : « poste » si l'hôte a une MAC, « inconnu » sinon.
"""

import re

TYPES = ["routeur", "commutateur", "pare-feu", "serveur", "poste",
         "imprimante", "point d'accès", "inconnu"]

# Bits de sysServices (RFC 1213) : 2^(couche - 1)
COUCHE_2 = 1 << 1   # 2  : liaison (commutation)
COUCHE_3 = 1 << 2   # 4  : réseau (routage)

# (motif dans sysDescr, type) — insensible à la casse, testés dans l'ordre
MOTS_CLES = [
    (r"printer|laserjet|jetdirect|imprimante|officejet|brother|epson", "imprimante"),
    (r"fortigate|pfsense|opnsense|firewall|\basa\b|palo alto|stormshield", "pare-feu"),
    (r"access point|\bap\b|aironet|unifi ap|wireless", "point d'accès"),
    (r"switch|commutateur|catalyst|ios-?l2|procurve|aruba.*switch|nexus", "commutateur"),
    (r"router|routeur|routeros|mikrotik|ios xe|ios software|\bisr|junos|vyos", "routeur"),
    (r"windows server|ubuntu server|debian|centos|red hat|freebsd", "serveur"),
    (r"windows", "poste"),
]

PORTS_IMPRIMANTE = {9100, 631, 515}       # JetDirect, IPP, LPD
PORTS_SERVEUR = {22, 53, 80, 443, 8080}   # SSH, DNS, web
PORTS_WINDOWS = {445, 3389}               # SMB, bureau à distance


def classifier(eq: dict, passerelle: str | None = None) -> tuple[str, str]:
    """Renvoie (type, raison) pour un équipement.

    ``eq`` peut contenir : ip, mac, description, services (entier sysServices),
    ports (liste d'entiers).
    """
    services = eq.get("services")
    description = eq.get("description") or ""
    ports = set(eq.get("ports") or [])

    # 1. sysServices : un équipement de couche 3 qui n'est pas un simple hôte
    if services:
        if services & COUCHE_3:
            if re.search(r"switch|catalyst|commutateur", description, re.I):
                return "commutateur", f"sysServices={services} (couche 3) et sysDescr de commutateur"
            return "routeur", f"sysServices={services} : routage (couche 3)"
        if services & COUCHE_2:
            return "commutateur", f"sysServices={services} : commutation (couche 2)"

    # 2. Mots-clés dans la description SNMP
    for motif, type_ in MOTS_CLES:
        if re.search(motif, description, re.I):
            return type_, f"sysDescr contient « {re.search(motif, description, re.I).group(0)} »"

    # 3. Passerelle par défaut
    if passerelle and eq.get("ip") == passerelle:
        return "routeur", "passerelle par défaut du réseau"

    # 4. Services TCP
    if ports & PORTS_IMPRIMANTE:
        return "imprimante", f"port d'impression ouvert ({min(ports & PORTS_IMPRIMANTE)})"
    if ports & PORTS_WINDOWS:
        return "poste", f"service Windows ouvert ({min(ports & PORTS_WINDOWS)})"
    if ports & PORTS_SERVEUR:
        return "serveur", f"service réseau ouvert ({min(ports & PORTS_SERVEUR)})"

    # 5. Par défaut
    if description:
        return "serveur", "répond en SNMP sans indice plus précis"
    if eq.get("mac"):
        return "poste", "hôte actif sans service identifié"
    return "inconnu", "aucune information exploitable"
