"""Construction du graphe de topologie.

Deux sortes de liens :

- **LLDP** (trait plein) : lien physique réel, déclaré par l'équipement
  lui-même via LLDP. On connaît les ports aux deux extrémités.
- **déduit** (pointillés) : l'équipement n'a déclaré aucun voisin LLDP ;
  on sait seulement qu'il appartient à tel sous-réseau. Il est rattaché à
  un nœud « segment » représentant ce sous-réseau, lui-même relié à la
  passerelle quand elle est connue.

Pour retrouver dans l'inventaire l'équipement désigné par un voisin LLDP,
on compare dans l'ordre : son adresse IP d'administration, sa MAC de
châssis, puis son nom (l'IP annoncée n'est pas forcément celle du réseau
scanné, voir docs/03-architecture.md).
"""

import ipaddress
from collections import defaultdict

from .base import nom_affiche


def _nom_court(nom: str) -> str:
    """« sw1.labo.local » → « sw1 » (comparaison des noms insensible au domaine)."""
    return (nom or "").split(".")[0].lower()


def _trouver(voisin: dict, par_ip: dict, par_mac: dict, par_nom: dict) -> str | None:
    """IP (identifiant du nœud) de l'équipement correspondant à un voisin LLDP."""
    if voisin.get("ip_distante") in par_ip:
        return voisin["ip_distante"]
    if voisin.get("chassis_distant") in par_mac:
        return par_mac[voisin["chassis_distant"]]
    return par_nom.get(_nom_court(voisin.get("nom_distant")))


def construire(equipements: list[dict], voisins: list[dict],
               reseaux: list[dict]) -> dict:
    """Renvoie ``{"noeuds": [...], "liens": [...]}`` prêt à être affiché."""
    par_ip = {e["ip"]: e for e in equipements}
    par_mac = {e["mac"]: e["ip"] for e in equipements if e.get("mac")}
    par_nom = {}
    for e in equipements:
        for nom in (e.get("nom_snmp"), e.get("nom_dns")):
            if nom:
                par_nom.setdefault(_nom_court(nom), e["ip"])

    noeuds = {e["ip"]: {
        "id": e["ip"],
        "label": nom_affiche(e),
        "type": e.get("type") or "inconnu",
        "en_ligne": bool(e.get("en_ligne", 1)),
        "ip": e["ip"],
        "mac": e.get("mac") or "",
        "constructeur": e.get("constructeur") or "",
    } for e in equipements}

    # --- 1. Liens LLDP -------------------------------------------------
    # Un lien A–B est souvent déclaré deux fois (par A et par B). On regroupe
    # les déclarations par paire d'équipements et on garde celles de
    # l'équipement qui en déclare le plus (gère les liens parallèles).
    declarations: dict[frozenset, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for v in voisins:
        source = v["ip_locale"]
        if source not in noeuds:
            continue
        cible = _trouver(v, par_ip, par_mac, par_nom)
        if cible is None:
            # Voisin hors inventaire (autre réseau, équipement sans IP...) :
            # on l'ajoute quand même au graphe pour ne pas perdre l'information.
            nom = v.get("nom_distant") or v.get("chassis_distant") or "voisin inconnu"
            cible = f"lldp:{nom}"
            noeuds.setdefault(cible, {"id": cible, "label": nom, "type": "inconnu",
                                      "en_ligne": True, "ip": v.get("ip_distante") or "",
                                      "mac": "", "constructeur": "", "hors_inventaire": True})
        if cible == source:
            continue
        declarations[frozenset((source, cible))][source].append(v)

    liens = []
    for paire, par_source in declarations.items():
        source, liste = max(par_source.items(), key=lambda item: len(item[1]))
        for v in liste:
            cible = next(iter(paire - {source}))
            liens.append({
                "from": source, "to": cible, "origine": "lldp",
                "label": f"{v.get('port_local') or '?'} ↔ {v.get('port_distant') or '?'}",
            })

    # --- 2. Liens déduits pour les équipements sans voisin LLDP --------
    relies = {l["from"] for l in liens} | {l["to"] for l in liens}
    for r in reseaux:
        reseau = ipaddress.ip_network(r["reseau"], strict=False)
        orphelins = [ip for ip, n in noeuds.items()
                     if ip not in relies and not n.get("hors_inventaire")
                     and ipaddress.ip_address(ip) in reseau]
        if not orphelins:
            continue
        segment = f"net:{reseau}"
        noeuds[segment] = {"id": segment, "label": str(reseau), "type": "segment",
                           "en_ligne": True, "ip": "", "mac": "", "constructeur": ""}
        passerelle = r.get("passerelle")
        if passerelle in noeuds:
            liens.append({"from": passerelle, "to": segment, "origine": "deduit",
                          "label": "passerelle"})
        for ip in orphelins:
            if ip != passerelle:
                liens.append({"from": segment, "to": ip, "origine": "deduit", "label": ""})

    return {"noeuds": list(noeuds.values()), "liens": liens}
