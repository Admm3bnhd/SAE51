"""Interrogation SNMP des équipements (identité et voisins LLDP).

On s'appuie sur les commandes Net-SNMP ``snmpget`` et ``snmpwalk``
(paquet Debian ``snmp``) : ce sont les outils vus en TP, et une requête
qui pose problème peut être rejouée à la main pour la déboguer.

Options Net-SNMP utilisées :

- ``-Oqv`` : n'affiche que la valeur (pour ``snmpget``) ;
- ``-On -Oq`` : OID numérique suivi de la valeur (pour ``snmpwalk``).
"""

import shutil
import subprocess

from .config import ConfigSNMP
from .decouverte import normaliser_mac

# MIB-II, groupe system (RFC 1213)
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_SERVICES = "1.3.6.1.2.1.1.7.0"

# LLDP-MIB (IEEE 802.1AB)
OID_LLDP_LOC_PORT = "1.0.8802.1.1.2.1.3.7.1"     # lldpLocPortTable
OID_LLDP_REM = "1.0.8802.1.1.2.1.4.1.1"          # lldpRemTable
OID_LLDP_REM_MAN_ADDR = "1.0.8802.1.1.2.1.4.2.1"  # lldpRemManAddrTable

# Colonnes utiles des tables LLDP
LOC_PORT_ID, LOC_PORT_DESC = 3, 4
REM_CHASSIS_ID, REM_PORT_ID, REM_PORT_DESC, REM_SYS_NAME = 5, 7, 8, 9


def snmp_disponible() -> bool:
    """Vrai si les outils Net-SNMP sont installés."""
    return shutil.which("snmpget") is not None and shutil.which("snmpwalk") is not None


def options_snmp(cfg: ConfigSNMP) -> list[str]:
    """Arguments d'authentification et de délai communs à toutes les commandes."""
    if cfg.version == "3":
        options = ["-v3", "-u", cfg.utilisateur, "-l", cfg.niveau]
        if cfg.niveau in ("authNoPriv", "authPriv"):
            options += ["-a", cfg.auth_protocole, "-A", cfg.auth_motdepasse]
        if cfg.niveau == "authPriv":
            options += ["-x", cfg.priv_protocole, "-X", cfg.priv_motdepasse]
    else:
        options = ["-v2c", "-c", cfg.communaute]
    return options + ["-t", str(cfg.delai), "-r", str(cfg.essais)]


def _executer(commande: list[str], cfg: ConfigSNMP) -> str | None:
    """Lance une commande Net-SNMP ; None en cas d'échec (pas de réponse...)."""
    attente_max = cfg.delai * (cfg.essais + 1) + 5
    try:
        resultat = subprocess.run(commande, capture_output=True, text=True,
                                  timeout=attente_max)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if resultat.returncode != 0:
        return None
    return resultat.stdout


def nettoyer_valeur(valeur: str) -> str:
    """Retire les guillemets et espaces autour d'une valeur Net-SNMP."""
    valeur = valeur.strip()
    if len(valeur) >= 2 and valeur[0] == valeur[-1] == '"':
        valeur = valeur[1:-1]
    return valeur.strip()


def valeur_absente(valeur: str) -> bool:
    """Net-SNMP répond « No Such Object/Instance » quand l'OID n'existe pas."""
    return valeur.startswith(("No Such", "No more variables"))


def snmp_get(ip: str, oid: str, cfg: ConfigSNMP) -> str | None:
    """Valeur d'un OID, ou None si l'équipement ne répond pas / n'a pas cet OID."""
    sortie = _executer(["snmpget", *options_snmp(cfg), "-On", "-Oqv", ip, oid], cfg)
    if sortie is None:
        return None
    valeur = nettoyer_valeur(sortie)
    return None if valeur_absente(valeur) else valeur


def analyser_walk(texte: str) -> list[tuple[str, str]]:
    """Découpe la sortie de ``snmpwalk -On -Oq`` en couples (OID, valeur).

    Une valeur peut s'étendre sur plusieurs lignes (ex. sysDescr Cisco) :
    une ligne qui ne commence pas par « . » prolonge la précédente.
    """
    resultats: list[tuple[str, str]] = []
    for ligne in texte.splitlines():
        if ligne.startswith("."):
            oid, _, valeur = ligne.partition(" ")
            resultats.append((oid.lstrip("."), valeur))
        elif resultats:
            oid, valeur = resultats[-1]
            resultats[-1] = (oid, valeur + "\n" + ligne)
    return [(oid, nettoyer_valeur(v)) for oid, v in resultats if not valeur_absente(v)]


def snmp_walk(ip: str, oid: str, cfg: ConfigSNMP) -> list[tuple[str, str]]:
    sortie = _executer(["snmpwalk", *options_snmp(cfg), "-On", "-Oq", ip, oid], cfg)
    return analyser_walk(sortie) if sortie else []


def _index(oid: str, base: str) -> list[int]:
    """Partie de l'OID qui suit la base, sous forme d'entiers.

    Ex. : _index("1.0.8802.1.1.2.1.4.1.1.9.0.6.1", OID_LLDP_REM) → [9, 0, 6, 1]
    """
    return [int(x) for x in oid[len(base) + 1:].split(".") if x]


# ------------------------------------------------------------- identité

def interroger(ip: str, cfg: ConfigSNMP) -> dict | None:
    """Identité SNMP d'un équipement, ou None s'il ne répond pas en SNMP."""
    description = snmp_get(ip, OID_SYS_DESCR, cfg)
    if description is None:
        return None
    services = snmp_get(ip, OID_SYS_SERVICES, cfg)
    return {
        "description": description,
        "nom_snmp": snmp_get(ip, OID_SYS_NAME, cfg) or "",
        "object_id": snmp_get(ip, OID_SYS_OBJECT_ID, cfg) or "",
        "services": int(services) if services and services.isdigit() else None,
    }


# ------------------------------------------------------------- voisins LLDP

def construire_voisins(locaux: list[tuple[str, str]], distants: list[tuple[str, str]],
                       adresses: list[tuple[str, str]]) -> list[dict]:
    """Assemble les tables LLDP en une liste de voisins.

    - ``lldpLocPortTable``, indexée par numéro de port local ;
    - ``lldpRemTable``, indexée par (TimeMark, port local, index du voisin) ;
    - ``lldpRemManAddrTable``, indexée par (TimeMark, port local, index,
      type d'adresse, longueur, octets de l'adresse) : l'adresse IP du
      voisin est **dans l'index**, pas dans la valeur.
    """
    # Nom des ports locaux : description si présente, sinon identifiant
    noms_ports: dict[int, str] = {}
    for oid, valeur in locaux:
        colonne, port = _index(oid, OID_LLDP_LOC_PORT)[:2]
        if colonne == LOC_PORT_DESC and valeur:
            noms_ports[port] = valeur
        elif colonne == LOC_PORT_ID and valeur:
            noms_ports.setdefault(port, valeur)

    # Une entrée par (port local, index du voisin)
    voisins: dict[tuple[int, int], dict] = {}
    for oid, valeur in distants:
        colonne, _timemark, port, index = _index(oid, OID_LLDP_REM)[:4]
        v = voisins.setdefault((port, index), {})
        if colonne == REM_CHASSIS_ID:
            v["chassis_distant"] = normaliser_mac(valeur) or valeur
        elif colonne == REM_PORT_ID:
            v["port_id"] = normaliser_mac(valeur) or valeur
        elif colonne == REM_PORT_DESC:
            v["port_desc"] = valeur
        elif colonne == REM_SYS_NAME:
            v["nom_distant"] = valeur

    # Adresse d'administration IPv4 (type 1, longueur 4)
    for oid, _valeur in adresses:
        idx = _index(oid, OID_LLDP_REM_MAN_ADDR)
        if len(idx) >= 10 and idx[4] == 1 and idx[5] == 4:
            cle = (idx[2], idx[3])
            if cle in voisins:
                voisins[cle].setdefault("ip_distante", ".".join(map(str, idx[6:10])))

    resultat = []
    for (port, _index_voisin), v in sorted(voisins.items()):
        resultat.append({
            "port_local": noms_ports.get(port, str(port)),
            "nom_distant": v.get("nom_distant", ""),
            "port_distant": v.get("port_desc") or v.get("port_id", ""),
            "ip_distante": v.get("ip_distante", ""),
            "chassis_distant": v.get("chassis_distant", ""),
        })
    return resultat


def voisins_lldp(ip: str, cfg: ConfigSNMP) -> list[dict]:
    """Voisins LLDP déclarés par l'équipement (liste vide si LLDP absent)."""
    distants = snmp_walk(ip, OID_LLDP_REM, cfg)
    if not distants:
        return []
    locaux = snmp_walk(ip, OID_LLDP_LOC_PORT, cfg)
    adresses = snmp_walk(ip, OID_LLDP_REM_MAN_ADDR, cfg)
    return construire_voisins(locaux, distants, adresses)
