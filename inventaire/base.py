"""Stockage de l'inventaire dans une base SQLite.

Tables :

- ``equipements`` : un enregistrement par adresse IP découverte ;
- ``voisins``     : liens LLDP déclarés par les équipements interrogés en SNMP ;
- ``reseaux``     : sous-réseaux scannés et leur passerelle ;
- ``scans``       : historique des découvertes lancées ;
- ``evenements``  : journal des changements (nouvel équipement, disparu, réapparu).

Une connexion SQLite ne doit être utilisée que par le thread qui l'a créée :
chaque thread (requête web, scan en arrière-plan) ouvre donc sa propre ``Base``.
"""

import ipaddress
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipements (
    ip            TEXT PRIMARY KEY,
    mac           TEXT,
    constructeur  TEXT,
    nom_dns       TEXT,
    nom_snmp      TEXT,
    description   TEXT,
    type          TEXT,
    raison_type   TEXT,
    ports         TEXT,          -- ports TCP ouverts, ex. "22,80"
    snmp          INTEGER DEFAULT 0,
    reseau        TEXT,
    en_ligne      INTEGER DEFAULT 1,
    premiere_vue  TEXT,
    derniere_vue  TEXT
);

CREATE TABLE IF NOT EXISTS voisins (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_locale        TEXT NOT NULL,  -- équipement qui déclare le voisin
    port_local       TEXT,
    nom_distant      TEXT,
    port_distant     TEXT,
    ip_distante      TEXT,
    chassis_distant  TEXT,           -- souvent l'adresse MAC du voisin
    vu_le            TEXT
);

CREATE TABLE IF NOT EXISTS reseaux (
    reseau        TEXT PRIMARY KEY,
    passerelle    TEXT,
    dernier_scan  TEXT
);

CREATE TABLE IF NOT EXISTS scans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reseau     TEXT,
    debut      TEXT,
    fin        TEXT,
    nb_actifs  INTEGER,
    statut     TEXT,                 -- en_cours, termine, erreur
    message    TEXT
);

CREATE TABLE IF NOT EXISTS evenements (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT,
    ip       TEXT,
    type     TEXT,                   -- nouveau, disparu, reapparu
    message  TEXT
);
"""

# Champs d'un équipement mis à jour à chaque scan
CHAMPS = ["mac", "constructeur", "nom_dns", "nom_snmp", "description",
          "type", "raison_type", "ports", "snmp", "reseau"]
# Champs dont on conserve l'ancienne valeur si le scan ne les a pas obtenus
CHAMPS_CONSERVES = {"mac", "constructeur", "nom_dns", "nom_snmp", "description"}


def horodatage() -> str:
    """Date et heure courantes au format ISO (à la seconde)."""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def nom_affiche(equipement: dict) -> str:
    """Nom le plus parlant d'un équipement : SNMP, puis DNS, puis IP."""
    return equipement.get("nom_snmp") or equipement.get("nom_dns") or equipement["ip"]


class Base:
    """Accès à la base d'inventaire."""

    def __init__(self, chemin: str):
        self.connexion = sqlite3.connect(chemin, timeout=10)
        self.connexion.row_factory = sqlite3.Row
        self.connexion.executescript(SCHEMA)

    def fermer(self) -> None:
        self.connexion.close()

    # ------------------------------------------------------------------ scans

    def debut_scan(self, reseau: str) -> int:
        with self.connexion:
            curseur = self.connexion.execute(
                "INSERT INTO scans (reseau, debut, statut) VALUES (?, ?, 'en_cours')",
                (reseau, horodatage()))
        return curseur.lastrowid

    def fin_scan(self, scan_id: int, nb_actifs: int, statut: str = "termine",
                 message: str = "") -> None:
        with self.connexion:
            self.connexion.execute(
                "UPDATE scans SET fin = ?, nb_actifs = ?, statut = ?, message = ? WHERE id = ?",
                (horodatage(), nb_actifs, statut, message, scan_id))

    # -------------------------------------------------------- enregistrement

    def enregistrer_resultats(self, reseau: str, passerelle: str | None,
                              equipements: list[dict],
                              voisins: dict[str, list[dict]]) -> dict:
        """Enregistre le résultat d'un scan et détecte les changements.

        ``equipements`` : liste de dictionnaires (clé ``ip`` obligatoire) ;
        ``voisins`` : pour chaque IP interrogée en SNMP, la liste de ses voisins LLDP.

        Renvoie le nombre d'équipements nouveaux, disparus et réapparus.
        """
        maintenant = horodatage()
        reseau_ip = ipaddress.ip_network(reseau, strict=False)
        bilan = {"nouveaux": 0, "disparus": 0, "reapparus": 0}
        vus = set()

        with self.connexion:  # une seule transaction pour tout le scan
            for eq in equipements:
                vus.add(eq["ip"])
                ancien = self.equipement(eq["ip"])
                valeurs = [eq.get(champ) for champ in CHAMPS]

                if ancien is None:
                    self.connexion.execute(
                        f"INSERT INTO equipements (ip, {', '.join(CHAMPS)}, en_ligne,"
                        " premiere_vue, derniere_vue)"
                        f" VALUES (?, {', '.join('?' * len(CHAMPS))}, 1, ?, ?)",
                        [eq["ip"], *valeurs, maintenant, maintenant])
                    self._evenement(maintenant, eq["ip"], "nouveau",
                                    f"Nouvel équipement : {nom_affiche(eq)}")
                    bilan["nouveaux"] += 1
                    continue

                # Équipement déjà connu : on garde l'ancienne valeur si la
                # nouvelle est vide (ex. SNMP qui n'a pas répondu cette fois-ci).
                for i, champ in enumerate(CHAMPS):
                    if champ in CHAMPS_CONSERVES and not valeurs[i]:
                        valeurs[i] = ancien[champ]
                self.connexion.execute(
                    f"UPDATE equipements SET {', '.join(c + ' = ?' for c in CHAMPS)},"
                    " en_ligne = 1, derniere_vue = ? WHERE ip = ?",
                    [*valeurs, maintenant, eq["ip"]])
                if not ancien["en_ligne"]:
                    self._evenement(maintenant, eq["ip"], "reapparu",
                                    f"Équipement de retour : {nom_affiche(dict(ancien))}")
                    bilan["reapparus"] += 1

            # Équipements du réseau scanné qui n'ont pas répondu : hors ligne
            for ancien in self.connexion.execute(
                    "SELECT * FROM equipements WHERE en_ligne = 1").fetchall():
                if ancien["ip"] in vus:
                    continue
                if ipaddress.ip_address(ancien["ip"]) in reseau_ip:
                    self.connexion.execute(
                        "UPDATE equipements SET en_ligne = 0 WHERE ip = ?", (ancien["ip"],))
                    self._evenement(maintenant, ancien["ip"], "disparu",
                                    f"Équipement absent : {nom_affiche(dict(ancien))}")
                    bilan["disparus"] += 1

            # Voisins LLDP : on remplace ceux des équipements interrogés
            for ip_locale, liste in voisins.items():
                self.connexion.execute("DELETE FROM voisins WHERE ip_locale = ?", (ip_locale,))
                for v in liste:
                    self.connexion.execute(
                        "INSERT INTO voisins (ip_locale, port_local, nom_distant, port_distant,"
                        " ip_distante, chassis_distant, vu_le) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (ip_locale, v.get("port_local"), v.get("nom_distant"),
                         v.get("port_distant"), v.get("ip_distante"),
                         v.get("chassis_distant"), maintenant))

            self.connexion.execute(
                "INSERT INTO reseaux (reseau, passerelle, dernier_scan) VALUES (?, ?, ?)"
                " ON CONFLICT(reseau) DO UPDATE SET passerelle = excluded.passerelle,"
                " dernier_scan = excluded.dernier_scan",
                (str(reseau_ip), passerelle, maintenant))

        return bilan

    def _evenement(self, date: str, ip: str, type_: str, message: str) -> None:
        self.connexion.execute(
            "INSERT INTO evenements (date, ip, type, message) VALUES (?, ?, ?, ?)",
            (date, ip, type_, message))

    # --------------------------------------------------------------- lecture

    def equipement(self, ip: str) -> sqlite3.Row | None:
        return self.connexion.execute(
            "SELECT * FROM equipements WHERE ip = ?", (ip,)).fetchone()

    def lister_equipements(self) -> list[dict]:
        lignes = self.connexion.execute("SELECT * FROM equipements").fetchall()
        # Tri par adresse IP « numérique » (10.0.0.2 avant 10.0.0.10)
        return sorted((dict(l) for l in lignes),
                      key=lambda e: ipaddress.ip_address(e["ip"]))

    def lister_voisins(self, ip_locale: str | None = None) -> list[dict]:
        if ip_locale:
            lignes = self.connexion.execute(
                "SELECT * FROM voisins WHERE ip_locale = ? ORDER BY port_local", (ip_locale,))
        else:
            lignes = self.connexion.execute("SELECT * FROM voisins")
        return [dict(l) for l in lignes.fetchall()]

    def lister_reseaux(self) -> list[dict]:
        return [dict(l) for l in self.connexion.execute(
            "SELECT * FROM reseaux ORDER BY reseau").fetchall()]

    def lister_scans(self, limite: int = 10) -> list[dict]:
        return [dict(l) for l in self.connexion.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limite,)).fetchall()]

    def lister_evenements(self, limite: int = 20, ip: str | None = None) -> list[dict]:
        if ip:
            requete = self.connexion.execute(
                "SELECT * FROM evenements WHERE ip = ? ORDER BY id DESC LIMIT ?", (ip, limite))
        else:
            requete = self.connexion.execute(
                "SELECT * FROM evenements ORDER BY id DESC LIMIT ?", (limite,))
        return [dict(l) for l in requete.fetchall()]

    def statistiques(self) -> dict:
        """Chiffres clés pour le tableau de bord."""
        total = self.connexion.execute("SELECT COUNT(*) FROM equipements").fetchone()[0]
        en_ligne = self.connexion.execute(
            "SELECT COUNT(*) FROM equipements WHERE en_ligne = 1").fetchone()[0]
        par_type = {l["type"] or "inconnu": l["nb"] for l in self.connexion.execute(
            "SELECT type, COUNT(*) AS nb FROM equipements GROUP BY type ORDER BY nb DESC")}
        return {"total": total, "en_ligne": en_ligne, "hors_ligne": total - en_ligne,
                "par_type": par_type}
