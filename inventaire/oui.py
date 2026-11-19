"""Identification du constructeur à partir de l'adresse MAC.

Les 3 premiers octets d'une adresse MAC forment l'**OUI** (*Organizationally
Unique Identifier*), attribué par l'IEEE à chaque fabricant.

- Si le fichier officiel ``oui.txt`` de l'IEEE est présent (voir
  ``scripts/telecharger_oui.sh``), il est utilisé.
- Sinon, une petite table intégrée couvre les cas courants en TP
  (machines virtuelles, Raspberry Pi, Cisco).

Cas particulier : si le bit « administré localement » (2e bit de poids
faible du 1er octet) vaut 1, l'adresse n'a pas été attribuée par un
fabricant. C'est le cas des **adresses MAC aléatoires** des smartphones
et ordinateurs portables récents, ou des conteneurs Docker.
"""

import re
from pathlib import Path

OUI_INTEGRES = {
    "00:00:0c": "Cisco",
    "00:0c:29": "VMware",
    "00:50:56": "VMware",
    "08:00:27": "Oracle VirtualBox",
    "52:54:00": "QEMU / KVM",
    "b8:27:eb": "Raspberry Pi",
    "dc:a6:32": "Raspberry Pi",
    "e4:5f:01": "Raspberry Pi",
}

_cache: dict[str, dict[str, str]] = {}


def charger_fichier_oui(chemin: str) -> dict[str, str]:
    """Lit le fichier IEEE (lignes « 00-00-0C   (hex)\t\tCisco Systems, Inc »)."""
    if chemin in _cache:
        return _cache[chemin]
    table = {}
    try:
        with open(chemin, encoding="utf-8", errors="replace") as f:
            for ligne in f:
                m = re.match(r"^([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})\s+\(hex\)\s+(.+)$",
                             ligne.strip())
                if m:
                    table[":".join(m.group(1, 2, 3)).lower()] = m.group(4).strip()
    except OSError:
        pass
    _cache[chemin] = table
    return table


def est_administree_localement(mac: str) -> bool:
    """Vrai si le bit U/L du premier octet est à 1 (MAC non attribuée par l'IEEE)."""
    return bool(int(mac[:2], 16) & 0b10)


def constructeur(mac: str, fichier: str | None = None) -> str:
    """Nom du constructeur d'une MAC normalisée (aa:bb:cc:dd:ee:ff), ou ""."""
    if not mac:
        return ""
    prefixe = mac[:8]
    if prefixe in OUI_INTEGRES:
        return OUI_INTEGRES[prefixe]
    if est_administree_localement(mac):
        return "MAC locale / aléatoire"
    if fichier and Path(fichier).is_file():
        return charger_fichier_oui(fichier).get(prefixe, "")
    return ""
