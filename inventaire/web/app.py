"""Interface web (Flask).

Pages :

- ``/``                  tableau de bord + lancement d'un scan
- ``/inventaire``        tableau filtrable des équipements
- ``/equipement/<ip>``   fiche détaillée d'un équipement
- ``/topologie``         graphe interactif

API JSON (utilisée par les pages, réutilisable par d'autres outils) :

- ``GET  /api/equipements``  liste des équipements
- ``GET  /api/topologie``    nœuds et liens du graphe
- ``GET  /api/scan``         état du scan en cours
- ``POST /scan``             lance un scan en arrière-plan

Exports : ``/export.csv`` et ``/export.json``.
"""

import csv
import io
import ipaddress
import os
import threading

from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from .. import __version__, topologie
from ..base import Base, nom_affiche
from ..config import Config
from ..decouverte import lister_hotes
from ..scanner import scanner

COLONNES_EXPORT = ["ip", "nom_snmp", "nom_dns", "type", "mac", "constructeur",
                   "ports", "snmp", "en_ligne", "description", "reseau",
                   "premiere_vue", "derniere_vue"]

# Couleur de chaque type d'équipement (badges et graphe de topologie)
COULEURS = {
    "routeur": "#d9480f",
    "commutateur": "#1971c2",
    "pare-feu": "#c92a2a",
    "serveur": "#2f9e44",
    "poste": "#6741d9",
    "imprimante": "#e67700",
    "point d'accès": "#0c8599",
    "inconnu": "#868e96",
    "segment": "#adb5bd",
}


def creer_application(config: Config) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.urandom(16)  # nécessaire pour les messages flash

    # État du scan lancé depuis l'interface (un seul à la fois)
    etat_scan = {"en_cours": False, "reseau": None, "journal": [], "erreur": None}
    verrou = threading.Lock()

    def base() -> Base:
        """Une connexion SQLite par requête (SQLite n'aime pas le partage entre threads)."""
        if "base" not in g:
            g.base = Base(config.base_de_donnees)
        return g.base

    @app.teardown_appcontext
    def fermer_base(_exception) -> None:
        b = g.pop("base", None)
        if b is not None:
            b.fermer()

    @app.context_processor
    def variables_communes() -> dict:
        return {"version": __version__, "nom_affiche": nom_affiche, "couleurs": COULEURS}

    # ----------------------------------------------------------- pages

    @app.get("/")
    def accueil():
        b = base()
        return render_template("accueil.html", stats=b.statistiques(),
                               evenements=b.lister_evenements(10),
                               scans=b.lister_scans(5), reseaux=b.lister_reseaux(),
                               etat=etat_scan)

    @app.get("/inventaire")
    def inventaire():
        return render_template("inventaire.html", equipements=base().lister_equipements())

    @app.get("/equipement/<ip>")
    def equipement(ip: str):
        b = base()
        eq = b.equipement(ip)
        if eq is None:
            abort(404)
        return render_template("equipement.html", eq=dict(eq),
                               voisins=b.lister_voisins(ip),
                               evenements=b.lister_evenements(20, ip))

    @app.get("/topologie")
    def page_topologie():
        return render_template("topologie.html")

    # ----------------------------------------------------------- scan

    @app.post("/scan")
    def lancer_scan():
        reseau = request.form.get("reseau", "").strip()
        try:
            lister_hotes(reseau)  # valide le format et la taille du réseau
        except ValueError as erreur:
            flash(f"Réseau invalide : {erreur}", "erreur")
            return redirect(url_for("accueil"))

        with verrou:
            if etat_scan["en_cours"]:
                flash("Un scan est déjà en cours.", "erreur")
                return redirect(url_for("accueil"))
            reseau = str(ipaddress.ip_network(reseau, strict=False))
            etat_scan.update(en_cours=True, reseau=reseau, journal=[], erreur=None)

        def tache() -> None:
            b = Base(config.base_de_donnees)
            try:
                scanner(reseau, config, b, journal=etat_scan["journal"].append)
            except Exception as erreur:  # affiché dans l'interface
                etat_scan["erreur"] = str(erreur)
            finally:
                b.fermer()
                etat_scan["en_cours"] = False

        threading.Thread(target=tache, daemon=True).start()
        flash(f"Scan de {reseau} lancé.", "info")
        return redirect(url_for("accueil"))

    # ----------------------------------------------------------- API

    @app.get("/api/scan")
    def api_scan():
        return jsonify(etat_scan)

    @app.get("/api/equipements")
    def api_equipements():
        return jsonify(base().lister_equipements())

    @app.get("/api/topologie")
    def api_topologie():
        b = base()
        return jsonify(topologie.construire(b.lister_equipements(), b.lister_voisins(),
                                            b.lister_reseaux()))

    # ----------------------------------------------------------- exports

    @app.get("/export.json")
    def export_json():
        reponse = jsonify(base().lister_equipements())
        reponse.headers["Content-Disposition"] = "attachment; filename=inventaire.json"
        return reponse

    @app.get("/export.csv")
    def export_csv():
        tampon = io.StringIO()
        # Séparateur « ; » et BOM UTF-8 : ouverture directe dans Excel en français
        ecrivain = csv.DictWriter(tampon, fieldnames=COLONNES_EXPORT, delimiter=";",
                                  extrasaction="ignore")
        ecrivain.writeheader()
        ecrivain.writerows(base().lister_equipements())
        return Response("﻿" + tampon.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=inventaire.csv"})

    return app
