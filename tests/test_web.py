"""Tests de l'interface web, sur les données de démonstration."""

import pytest

from inventaire.config import Config
from inventaire.demo import remplir_demo
from inventaire.web.app import creer_application


@pytest.fixture
def client(tmp_path):
    chemin = str(tmp_path / "demo.db")
    remplir_demo(chemin)
    application = creer_application(Config(base_de_donnees=chemin))
    application.config["TESTING"] = True
    return application.test_client()


@pytest.mark.parametrize("url", ["/", "/inventaire", "/topologie", "/equipement/192.168.10.1"])
def test_pages(client, url):
    reponse = client.get(url)
    assert reponse.status_code == 200
    assert "Inventaire réseau" in reponse.get_data(as_text=True)


def test_equipement_inconnu(client):
    assert client.get("/equipement/192.0.2.99").status_code == 404


def test_api_topologie(client):
    graphe = client.get("/api/topologie").get_json()
    ids = {n["id"] for n in graphe["noeuds"]}
    assert {"192.168.10.1", "192.168.10.2", "net:192.168.10.0/24"} <= ids
    assert any(l["origine"] == "lldp" for l in graphe["liens"])


def test_export_csv(client):
    texte = client.get("/export.csv").get_data(as_text=True)
    lignes = texte.lstrip("﻿").splitlines()
    assert lignes[0].startswith("ip;nom_snmp;")
    assert len(lignes) == 1 + 15


def test_scan_refuse_un_reseau_invalide(client):
    reponse = client.post("/scan", data={"reseau": "n'importe quoi"}, follow_redirects=True)
    assert "Réseau invalide" in reponse.get_data(as_text=True)
