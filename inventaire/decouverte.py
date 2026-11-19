"""Découverte des hôtes actifs (couches 2 à 4).

Techniques utilisées :

1. **Ping ICMP** en parallèle sur toutes les adresses du sous-réseau ;
2. **lecture du cache ARP** du noyau (``ip neigh``) : un hôte qui filtre
   ICMP répond quand même aux requêtes ARP émises pendant le ping, on le
   retrouve donc dans la table avec son adresse MAC ;
3. **DNS inverse** pour obtenir un nom ;
4. **connexion TCP** sur quelques ports connus pour repérer les services.

Les fonctions ``analyser_*`` ne font que du traitement de texte : elles
sont testées unitairement sans réseau.
"""

import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Taille maximale acceptée pour un scan (un /16 = 65 534 hôtes)
TAILLE_MAX = 65_534


def lister_hotes(reseau: str) -> list[str]:
    """Adresses à tester dans un réseau CIDR (sans adresse réseau ni broadcast)."""
    net = ipaddress.ip_network(reseau, strict=False)
    if net.version != 4:
        raise ValueError("Seul IPv4 est pris en charge.")
    if net.num_addresses > TAILLE_MAX + 2:
        raise ValueError(f"Réseau trop grand ({net.num_addresses} adresses), maximum /16.")
    return [str(ip) for ip in net.hosts()]


# --------------------------------------------------------------------- ICMP

def ping(ip: str, delai: int = 1) -> bool:
    """Envoie un seul Echo Request ; vrai si l'hôte répond."""
    try:
        resultat = subprocess.run(
            ["ping", "-c", "1", "-n", "-W", str(delai), ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=delai + 2)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return resultat.returncode == 0


def balayage_ping(ips: list[str], threads: int = 64, delai: int = 1) -> set[str]:
    """Ping de toutes les adresses en parallèle ; renvoie celles qui répondent."""
    with ThreadPoolExecutor(max_workers=threads) as pool:
        reponses = pool.map(lambda ip: ping(ip, delai), ips)
    return {ip for ip, ok in zip(ips, reponses) if ok}


# ---------------------------------------------------------------------- ARP

def normaliser_mac(mac: str) -> str:
    """Met une adresse MAC au format aa:bb:cc:dd:ee:ff.

    Accepte « AA-BB-CC-DD-EE-FF », « aabb.ccdd.eeff » (Cisco) ou
    « AA BB CC DD EE FF » (sortie SNMP). Renvoie "" si ce n'est pas une MAC.
    """
    chiffres = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(chiffres) != 12:
        return ""
    chiffres = chiffres.lower()
    return ":".join(chiffres[i:i + 2] for i in range(0, 12, 2))


def analyser_ip_neigh(texte: str) -> dict[str, str]:
    """Extrait les couples IP → MAC de la sortie de ``ip neigh show``.

    Exemple de ligne : ``192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE``.
    Les entrées sans ``lladdr`` (INCOMPLETE, FAILED) sont ignorées.
    """
    table = {}
    for ligne in texte.splitlines():
        m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s.*\blladdr\s+([0-9a-fA-F:]{17})", ligne)
        if m and "FAILED" not in ligne:
            table[m.group(1)] = normaliser_mac(m.group(2))
    return table


def lire_table_arp() -> dict[str, str]:
    """Cache ARP du noyau Linux."""
    try:
        sortie = subprocess.run(["ip", "-4", "neigh", "show"], capture_output=True,
                                text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    return analyser_ip_neigh(sortie)


def analyser_route_defaut(texte: str) -> str | None:
    """Adresse de la passerelle dans ``ip route show default``."""
    m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", texte)
    return m.group(1) if m else None


def passerelle_par_defaut() -> str | None:
    try:
        sortie = subprocess.run(["ip", "-4", "route", "show", "default"],
                                capture_output=True, text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return analyser_route_defaut(sortie)


def analyser_ip_addr(texte: str) -> dict[str, str]:
    """Couples IP → interface dans ``ip -o -4 addr show``."""
    resultat = {}
    for ligne in texte.splitlines():
        m = re.match(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/", ligne)
        if m:
            resultat[m.group(2)] = m.group(1)
    return resultat


def interfaces_locales() -> dict[str, str]:
    """Adresses IP de la machine qui scanne, avec la MAC de leur interface.

    La machine locale n'apparaît pas dans son propre cache ARP : on lit sa
    MAC dans /sys/class/net/<interface>/address.
    """
    try:
        sortie = subprocess.run(["ip", "-o", "-4", "addr", "show"],
                                capture_output=True, text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    locales = {}
    for ip, interface in analyser_ip_addr(sortie).items():
        try:
            mac = Path(f"/sys/class/net/{interface}/address").read_text().strip()
        except OSError:
            mac = ""
        locales[ip] = normaliser_mac(mac)
    return locales


# --------------------------------------------------------------- DNS / TCP

def nom_dns(ip: str) -> str:
    """Résolution inverse (enregistrement PTR) ; "" si aucune."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, UnicodeError):
        return ""


def port_ouvert(ip: str, port: int, delai: float = 0.5) -> bool:
    """Vrai si une connexion TCP complète aboutit (poignée de main SYN/SYN-ACK/ACK)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(delai)
        return s.connect_ex((ip, port)) == 0


def ports_ouverts(ip: str, ports: list[int], delai: float = 0.5) -> list[int]:
    """Teste plusieurs ports d'un même hôte en parallèle."""
    with ThreadPoolExecutor(max_workers=len(ports) or 1) as pool:
        resultats = pool.map(lambda p: port_ouvert(ip, p, delai), ports)
    return [p for p, ok in zip(ports, resultats) if ok]
