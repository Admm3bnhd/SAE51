# 1. Cahier des charges

## 1.1 Contexte

Dans une entreprise ou un établissement, le parc réseau évolue en permanence :
ajout de postes, remplacement de commutateurs, imprimantes déplacées,
équipements personnels branchés sans autorisation… Maintenir un inventaire
à la main (tableur) devient vite faux et chronophage.

Un administrateur réseau a besoin de répondre rapidement à des questions
comme :

- *Quels équipements sont actuellement présents sur le réseau ?*
- *Quelle est l'adresse MAC, le nom, le type de tel équipement ?*
- *Comment les commutateurs et routeurs sont-ils reliés entre eux ?*
- *Un nouvel équipement est-il apparu depuis hier ? Un autre a-t-il disparu ?*

## 1.2 Objectif

Concevoir un outil qui :

1. **découvre** automatiquement les équipements d'un ou plusieurs
   sous-réseaux IP ;
2. **inventorie** ces équipements (adresse IP, MAC, constructeur, nom,
   type, services) dans une base de données ;
3. **affiche** l'inventaire et la **topologie** dans une interface web.

## 1.3 Périmètre

| Inclus | Exclus |
|---|---|
| Réseaux IPv4 locaux (LAN, labo GNS3, salle de TP) | IPv6 (piste d'amélioration) |
| Équipements répondant à ICMP, ARP ou TCP | Équipements totalement silencieux |
| Identification fine via SNMP v2c/v3 | Configuration des équipements (outil en lecture seule) |
| Liens physiques via LLDP (IEEE 802.1AB) | CDP propriétaire Cisco (piste d'amélioration) |
| Interface web consultable sur le poste de l'admin | Gestion multi-utilisateurs / authentification |

## 1.4 Besoins fonctionnels

| ID | Besoin | Priorité |
|---|---|---|
| F1 | Lancer une découverte sur un sous-réseau donné en notation CIDR (ex. `192.168.1.0/24`) | Indispensable |
| F2 | Détecter les hôtes actifs (ping ICMP + table ARP) | Indispensable |
| F3 | Récupérer l'adresse MAC et en déduire le constructeur (OUI) | Indispensable |
| F4 | Récupérer le nom (DNS inverse, puis SNMP `sysName`) | Indispensable |
| F5 | Détecter quelques services ouverts (SSH, HTTP, RDP, impression…) | Souhaitable |
| F6 | Interroger les équipements en SNMP (description, rôle) | Indispensable |
| F7 | Déterminer automatiquement le **type** d'équipement (routeur, commutateur, serveur, poste, imprimante…) | Indispensable |
| F8 | Construire la topologie à partir des voisins LLDP | Indispensable |
| F9 | Stocker l'inventaire de façon persistante (historique première/dernière vue) | Indispensable |
| F10 | Détecter les changements : nouvel équipement, équipement disparu, réapparu | Souhaitable |
| F11 | Afficher l'inventaire sous forme de tableau filtrable | Indispensable |
| F12 | Afficher la topologie sous forme de graphe interactif | Indispensable |
| F13 | Lancer un scan depuis l'interface web | Souhaitable |
| F14 | Exporter l'inventaire (CSV, JSON) | Souhaitable |
| F15 | Mode démonstration (données fictives) pour présenter l'outil sans réseau | Souhaitable |

## 1.5 Besoins non fonctionnels

| ID | Besoin |
|---|---|
| NF1 | **Simplicité** : installation en quelques commandes sur une machine Linux (Debian/Ubuntu) |
| NF2 | **Performance** : scan d'un /24 en moins d'une minute environ (parallélisation) |
| NF3 | **Non intrusif** : uniquement des requêtes en lecture (ping, ARP, connexion TCP, SNMP GET/WALK) |
| NF4 | **Fonctionnement hors ligne** : l'interface web ne dépend d'aucun CDN (salle de TP sans Internet) |
| NF5 | **Maintenabilité** : code Python commenté, découpé en modules, testé (pytest) |
| NF6 | **Sécurité** : interface web écoutant par défaut uniquement en local, secrets SNMP hors du dépôt |

## 1.6 Contraintes

- Langage : **Python 3.11+** (bibliothèque standard autant que possible).
- Système cible : **Linux** (utilisation des commandes `ping`, `ip` et des
  outils Net-SNMP).
- Durée : un semestre, projet réalisable par un petit groupe d'étudiants.
- Cadre légal : un scan réseau ne doit être effectué **que sur un réseau
  dont on a l'autorisation** (art. 323-1 et suivants du Code pénal).

## 1.7 Livrables

- Le code source versionné (ce dépôt Git).
- La documentation technique (dossier `docs/`).
- Un jeu de tests automatisés (`tests/`).
- Une maquette de test (topologie GNS3 décrite dans [06-tests.md](06-tests.md)).
