"""Orchestration d'une découverte complète sur un sous-réseau.

Étapes (voir le diagramme de séquence dans docs/03-architecture.md) :

1. balayage ICMP de toutes les adresses ;
2. lecture du cache ARP → hôtes qui filtrent ICMP + adresses MAC ;
3. pour chaque hôte actif, en parallèle : constructeur, DNS inverse,
   ports TCP, SNMP (identité + voisins LLDP), classification ;
4. enregistrement en base et détection des changements.
"""

import ipaddress
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import decouverte, oui, snmp
from .base import Base
from .classification import classifier
from .config import Config


def analyser_hote(ip: str, mac: str, config: Config, passerelle: str | None,
                  avec_snmp: bool) -> tuple[dict, list[dict]]:
    """Collecte toutes les informations sur un hôte actif."""
    eq = {
        "ip": ip,
        "mac": mac,
        "constructeur": oui.constructeur(mac, config.fichier_oui),
        "nom_dns": decouverte.nom_dns(ip),
        "ports": decouverte.ports_ouverts(ip, config.ports_tcp, config.delai_tcp),
        "snmp": 0,
    }
    voisins: list[dict] = []
    if avec_snmp:
        identite = snmp.interroger(ip, config.snmp)
        if identite:
            eq.update(identite, snmp=1)
            voisins = snmp.voisins_lldp(ip, config.snmp)

    eq["type"], eq["raison_type"] = classifier(eq, passerelle)
    eq["ports"] = ",".join(map(str, eq["ports"]))  # stockage texte en base
    return eq, voisins


def scanner(reseau: str, config: Config, base: Base,
            journal: Callable[[str], None] = print) -> dict:
    """Découvre le réseau, enregistre le résultat et renvoie un bilan."""
    net = ipaddress.ip_network(reseau, strict=False)
    ips = decouverte.lister_hotes(str(net))
    scan_id = base.debut_scan(str(net))
    debut = time.monotonic()

    try:
        # 1. ICMP
        journal(f"Ping de {len(ips)} adresses sur {net}...")
        actifs = decouverte.balayage_ping(ips, config.threads, config.delai_ping)
        journal(f"  {len(actifs)} hôte(s) ont répondu au ping")

        # 2. ARP (le ping a forcé la résolution ARP de chaque adresse)
        table_arp = {ip: entree for ip, entree in decouverte.lire_table_arp().items()
                     if ipaddress.ip_address(ip) in net}
        # La machine qui scanne n'est pas dans son propre cache ARP
        locales = {ip: mac for ip, mac in decouverte.interfaces_locales().items()
                   if ipaddress.ip_address(ip) in net}
        macs = {ip: mac for ip, (mac, _etat) in table_arp.items()} | locales
        actifs |= set(locales)

        # Hôtes présents dans le cache ARP mais muets en ICMP : à confirmer
        candidats = set(table_arp) - actifs
        if candidats:
            journal(f"  Vérification ARP de {len(candidats)} hôte(s) muet(s) en ICMP...")
            silencieux = decouverte.confirmer_par_arp(candidats)
            if silencieux:
                journal(f"  {len(silencieux)} hôte(s) supplémentaire(s) trouvé(s) par ARP "
                        "(ICMP filtré)")
            actifs |= set(silencieux)

        passerelle = decouverte.passerelle_par_defaut()
        if passerelle and ipaddress.ip_address(passerelle) not in net:
            passerelle = None

        # 3. Analyse détaillée de chaque hôte
        avec_snmp = config.snmp.actif and snmp.snmp_disponible()
        if config.snmp.actif and not avec_snmp:
            journal("  Attention : outils Net-SNMP absents (apt install snmp), SNMP ignoré")
        journal(f"Analyse de {len(actifs)} hôte(s) (DNS, ports TCP, SNMP)...")
        with ThreadPoolExecutor(max_workers=config.threads) as pool:
            resultats = list(pool.map(
                lambda ip: analyser_hote(ip, macs.get(ip, ""), config, passerelle, avec_snmp),
                sorted(actifs, key=ipaddress.ip_address)))

        equipements = [dict(eq, reseau=str(net)) for eq, _ in resultats]
        voisins = {eq["ip"]: v for eq, v in resultats if eq["snmp"]}

        # 4. Enregistrement
        bilan = base.enregistrer_resultats(str(net), passerelle, equipements, voisins)
        bilan.update(reseau=str(net), actifs=len(equipements),
                     snmp=sum(eq["snmp"] for eq in equipements),
                     liens_lldp=sum(len(v) for v in voisins.values()),
                     duree=round(time.monotonic() - debut, 1))
        base.fin_scan(scan_id, len(equipements))
        journal(f"Terminé en {bilan['duree']} s : {bilan['actifs']} actif(s), "
                f"{bilan['snmp']} en SNMP, {bilan['liens_lldp']} lien(s) LLDP, "
                f"{bilan['nouveaux']} nouveau(x), {bilan['disparus']} disparu(s)")
        return bilan

    except Exception as erreur:
        base.fin_scan(scan_id, 0, "erreur", str(erreur))
        raise
