"""Chargement de la configuration.

La configuration est lue dans un fichier INI (``config.ini`` par défaut).
Toutes les options ont une valeur par défaut : le fichier est facultatif.
Voir ``config.example.ini`` pour la liste commentée des options.
"""

import configparser
from dataclasses import dataclass, field
from pathlib import Path

PORTS_PAR_DEFAUT = [22, 23, 53, 80, 443, 445, 631, 3389, 8080, 9100]


@dataclass
class ConfigSNMP:
    """Paramètres d'accès SNMP (v2c ou v3)."""

    actif: bool = True
    version: str = "2c"            # "2c" ou "3"
    communaute: str = "public"     # SNMP v2c uniquement
    # Paramètres SNMPv3 (USM)
    utilisateur: str = ""
    niveau: str = "authPriv"       # noAuthNoPriv, authNoPriv ou authPriv
    auth_protocole: str = "SHA"
    auth_motdepasse: str = ""
    priv_protocole: str = "AES"
    priv_motdepasse: str = ""
    # Réseau
    delai: float = 1.0             # secondes d'attente par requête
    essais: int = 1                # nombre de ré-émissions


@dataclass
class Config:
    """Configuration générale de l'outil."""

    base_de_donnees: str = "inventaire.db"
    threads: int = 64              # requêtes réseau menées en parallèle
    delai_ping: int = 1            # secondes
    ports_tcp: list[int] = field(default_factory=lambda: list(PORTS_PAR_DEFAUT))
    delai_tcp: float = 0.5         # secondes
    fichier_oui: str = "data/oui.txt"
    snmp: ConfigSNMP = field(default_factory=ConfigSNMP)


def charger_config(chemin: str | Path = "config.ini") -> Config:
    """Lit le fichier de configuration s'il existe, sinon renvoie les valeurs par défaut."""
    config = Config()
    lecteur = configparser.ConfigParser()
    if not lecteur.read(chemin, encoding="utf-8"):
        return config

    if lecteur.has_section("general"):
        g = lecteur["general"]
        config.base_de_donnees = g.get("base_de_donnees", config.base_de_donnees)
        config.threads = g.getint("threads", config.threads)
        config.delai_ping = g.getint("delai_ping", config.delai_ping)
        config.delai_tcp = g.getfloat("delai_tcp", config.delai_tcp)
        config.fichier_oui = g.get("fichier_oui", config.fichier_oui)
        if "ports_tcp" in g:
            config.ports_tcp = [int(p) for p in g["ports_tcp"].replace(",", " ").split()]

    if lecteur.has_section("snmp"):
        s = lecteur["snmp"]
        c = config.snmp
        c.actif = s.getboolean("actif", c.actif)
        c.version = s.get("version", c.version)
        c.communaute = s.get("communaute", c.communaute)
        c.utilisateur = s.get("utilisateur", c.utilisateur)
        c.niveau = s.get("niveau", c.niveau)
        c.auth_protocole = s.get("auth_protocole", c.auth_protocole)
        c.auth_motdepasse = s.get("auth_motdepasse", c.auth_motdepasse)
        c.priv_protocole = s.get("priv_protocole", c.priv_protocole)
        c.priv_motdepasse = s.get("priv_motdepasse", c.priv_motdepasse)
        c.delai = s.getfloat("delai", c.delai)
        c.essais = s.getint("essais", c.essais)

    return config
