# 4. Installation

## 4.1 Prérequis

| Élément | Version | Rôle |
|---|---|---|
| Linux (Debian 12, Ubuntu 22.04+ ou équivalent) | – | Commandes `ping` et `ip` |
| Python | 3.11 ou plus | Langage de l'outil |
| Net-SNMP (`snmp`) | 5.9 | Commandes `snmpget` et `snmpwalk` |
| Navigateur web récent | – | Interface |

L'outil **ne demande pas les droits root** : `ping` et `ip neigh`
fonctionnent en utilisateur normal. Seul le labo de test
(`scripts/labo_veth.sh`) a besoin de `sudo`.

## 4.2 Installation pas à pas

```bash
# 1. Paquets système
sudo apt update
sudo apt install -y git python3 python3-venv iputils-ping iproute2 snmp

# 2. Récupération du projet
git clone https://github.com/<compte>/inventaire-reseau.git
cd inventaire-reseau

# 3. Environnement virtuel Python et dépendances
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Configuration (facultative)
cp config.example.ini config.ini
nano config.ini        # communauté SNMP, ports à tester...

# 5. (Facultatif) base officielle des constructeurs IEEE (~6 Mo)
./scripts/telecharger_oui.sh
```

Vérification rapide avec les données de démonstration :

```bash
python -m inventaire demo
python -m inventaire web
```

Puis ouvrir <http://127.0.0.1:5000/> dans un navigateur.

## 4.3 Paquets Debian et `snmp-mibs-downloader`

L'outil utilise uniquement des **OID numériques** (`-On`) : il n'a pas
besoin des fichiers MIB. Le message suivant, parfois affiché par Net-SNMP,
est donc sans conséquence :

```
Cannot find module (SNMPv2-MIB): At line 1 in (none)
```

Pour l'utiliser à la main avec des noms d'objets lisibles
(`snmpwalk ... LLDP-MIB::lldpRemSysName`), installer
`snmp-mibs-downloader` (dépôt *non-free* de Debian) et commenter la ligne
`mibs :` dans `/etc/snmp/snmp.conf`.

## 4.4 Options de configuration

Toutes les options sont facultatives (voir `config.example.ini`).

| Section | Option | Défaut | Description |
|---|---|---|---|
| `general` | `base_de_donnees` | `inventaire.db` | Fichier SQLite |
| `general` | `threads` | `64` | Hôtes interrogés en parallèle |
| `general` | `delai_ping` | `1` | Attente d'une réponse ICMP (s) |
| `general` | `ports_tcp` | `22 23 53 80 443 445 631 3389 8080 9100` | Ports testés |
| `general` | `delai_tcp` | `0.5` | Attente d'une connexion TCP (s) |
| `general` | `fichier_oui` | `data/oui.txt` | Base IEEE des constructeurs |
| `snmp` | `actif` | `oui` | Désactive SNMP si `non` |
| `snmp` | `version` | `2c` | `2c` ou `3` |
| `snmp` | `communaute` | `public` | Communauté SNMP v2c |
| `snmp` | `utilisateur`, `niveau`, `auth_protocole`, `auth_motdepasse`, `priv_protocole`, `priv_motdepasse` | – | Paramètres SNMPv3 (USM) |
| `snmp` | `delai`, `essais` | `1`, `1` | Délai (s) et ré-émissions par requête |

Un autre fichier peut être utilisé avec `-c` :
`python -m inventaire -c /etc/inventaire.ini scan ...`

## 4.5 Lancer l'interface au démarrage (optionnel)

Exemple de service **systemd** (`/etc/systemd/system/inventaire.service`) :

```ini
[Unit]
Description=Inventaire réseau (interface web)
After=network-online.target

[Service]
User=inventaire
WorkingDirectory=/opt/inventaire-reseau
ExecStart=/opt/inventaire-reseau/.venv/bin/python -m inventaire web
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now inventaire
```

Le serveur intégré de Flask suffit pour un usage par un administrateur
sur sa machine. Pour une mise en production, on placerait l'application
derrière un serveur WSGI (Gunicorn) et un proxy HTTPS (Nginx).
