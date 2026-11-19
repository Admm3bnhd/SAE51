# 2. État de l'art et choix techniques

## 2.1 Comment découvrir un équipement ?

Plusieurs techniques complémentaires existent. Aucune n'est suffisante seule :
on les combine.

| Technique | Couche OSI | Principe | Avantages | Limites |
|---|---|---|---|---|
| **Ping (ICMP Echo)** | 3 | On envoie un *Echo Request*, l'hôte répond *Echo Reply* | Simple, universel | Souvent filtré (pare-feu Windows par défaut) |
| **Table ARP** | 2/3 | Pour joindre une IP du même sous-réseau, le noyau doit résoudre sa MAC par ARP. Un hôte qui bloque ICMP **répond quand même à ARP** | Donne l'adresse MAC, contourne le filtrage ICMP | Limité au sous-réseau local (ARP ne traverse pas les routeurs) |
| **Connexion TCP** | 4 | Tentative de connexion (SYN) sur quelques ports connus | Révèle les services (SSH, HTTP, RDP…) | Plus lent ; peut déclencher des alertes IDS |
| **DNS inverse (PTR)** | 7 | Résolution IP → nom | Donne un nom lisible | Dépend de la qualité de la zone DNS |
| **SNMP** | 7 | Interrogation de la MIB de l'équipement (UDP/161) | Informations très riches : nom, description, rôle, voisins | Doit être activé et la communauté/les identifiants connus |
| **LLDP** (IEEE 802.1AB) | 2 | Chaque équipement annonce son identité à ses voisins directs ; ceux-ci la stockent dans la LLDP-MIB | Donne les **liens physiques réels** (port à port) | Doit être activé ; lu via SNMP |
| **CDP** | 2 | Équivalent propriétaire Cisco de LLDP | Activé par défaut sur Cisco | Propriétaire |

### Le cas SNMP

SNMP (*Simple Network Management Protocol*) permet de lire des variables
organisées en arbre (la **MIB**) et identifiées par un **OID**. Les objets
utilisés par ce projet :

| Objet | OID | Utilité |
|---|---|---|
| `sysDescr` | `1.3.6.1.2.1.1.1.0` | Description (OS, version, modèle) |
| `sysObjectID` | `1.3.6.1.2.1.1.2.0` | Identifiant du constructeur/modèle |
| `sysName` | `1.3.6.1.2.1.1.5.0` | Nom de l'équipement |
| `sysServices` | `1.3.6.1.2.1.1.7.0` | Couches OSI assurées (voir ci‑dessous) |
| `lldpLocPortDesc` | `1.0.8802.1.1.2.1.3.7.1.4` | Nom des ports locaux LLDP |
| `lldpRemPortId` | `1.0.8802.1.1.2.1.4.1.1.7` | Port du voisin |
| `lldpRemSysName` | `1.0.8802.1.1.2.1.4.1.1.9` | Nom du voisin |
| `lldpRemManAddrIfSubtype` | `1.0.8802.1.1.2.1.4.2.1.3` | Adresse IP d'administration du voisin (encodée dans l'index) |

**`sysServices`** (RFC 1213) est un entier dont chaque bit indique une
couche assurée par l'équipement : bit 0 → couche 1, bit 1 → couche 2
(commutation), bit 2 → couche 3 (routage), bit 3 → couche 4, bit 6 →
couche 7 (applications). Par exemple :

- `78` = 2 + 4 + 8 + 64 → couches 2, 3, 4 et 7 → **routeur** (valeur
  typique d'un routeur Cisco) ;
- `6` = 2 + 4 → couches 2 et 3 → **commutateur de niveau 3** ;
- `2` → couche 2 seule → **commutateur** ;
- `72` = 8 + 64 → couches 4 et 7 → **hôte** (valeur par défaut de
  Net-SNMP sous Linux) ;
- `76` = 4 + 8 + 64 → couches 3, 4 et 7 → **hôte** également : c'est la
  valeur annoncée par Windows, qui positionne le bit « couche 3 » parce
  qu'il implémente IP.

C'est un moyen standard de déterminer le rôle d'un équipement, à
condition de ne pas se fier au seul bit « couche 3 » : l'outil exige aussi
le bit « couche 2 » pour conclure à un routeur ou un commutateur (voir
[03-architecture.md § 3.5](03-architecture.md#35-classification-des-équipements)).

**Versions de SNMP** : v1 et v2c utilisent une *communauté* qui circule
**en clair** ; SNMPv3 ajoute authentification (SHA) et chiffrement (AES).
L'outil supporte v2c (simple en TP) et v3 (recommandé en production).

## 2.2 Outils existants

| Outil | Type | Points forts | Pourquoi ne pas l'utiliser tel quel ? |
|---|---|---|---|
| **Nmap** | Scanner en ligne de commande | Référence de la découverte, détection d'OS | Pas d'inventaire persistant ni de topologie physique |
| **NetBox** | Source de vérité (IPAM/DCIM) | Très complet, standard du métier | Inventaire **déclaratif** (saisi à la main), pas de découverte |
| **LibreNMS / Observium** | Supervision SNMP | Découverte auto, cartes LLDP/CDP | Lourds à installer (PHP, MySQL, RRD), dépassent le besoin |
| **Netdisco** | Inventaire L2/L3 | Très bon sur la topologie (LLDP/CDP, tables MAC) | Perl + PostgreSQL, complexe à déployer |
| **Zabbix** | Supervision | Découverte réseau intégrée | Orienté métriques/alertes, pas topologie |

Ces outils montrent que l'approche **ICMP/ARP + SNMP + LLDP** est celle
utilisée par les solutions professionnelles. Notre outil reprend cette
approche avec un périmètre réduit, un déploiement en deux commandes et un
code lisible de bout en bout, ce qui a une vraie valeur pédagogique.

## 2.3 Choix techniques retenus

| Besoin | Choix | Justification |
|---|---|---|
| Langage | **Python 3** | Lisible, très utilisé en automatisation réseau, riche bibliothèque standard (`ipaddress`, `socket`, `sqlite3`, `concurrent.futures`) |
| Ping | Commande système `ping` | Pas besoin des droits root (contrairement aux sockets ICMP brutes / Scapy) |
| ARP | Commande `ip neigh` | Lit directement le cache ARP du noyau Linux |
| SNMP | Outils **Net-SNMP** (`snmpget`, `snmpwalk`) | Les commandes vues en TP ; évite les bibliothèques Python SNMP dont l'API change souvent ; facile à déboguer (on peut relancer la même commande à la main) |
| Parallélisme | `ThreadPoolExecutor` | Les opérations réseau attendent surtout des réponses : les threads suffisent largement |
| Base de données | **SQLite** | Un seul fichier, aucun serveur à installer, intégré à Python |
| Serveur web | **Flask** | Micro-framework simple, gabarits Jinja2 |
| Graphe de topologie | **vis-network** (JavaScript) | Graphe interactif (zoom, déplacement), embarqué localement dans `static/` (pas de CDN) |
| Constructeurs | Fichier OUI de l'IEEE (optionnel) + petite table intégrée | Le préfixe OUI (3 premiers octets de la MAC) identifie le fabricant |
| Tests | **pytest** | Standard Python ; les sorties des commandes sont simulées (*mock*) pour tester sans réseau |

### Pourquoi ne pas simplement appeler Nmap ?

Nmap est excellent, mais l'encapsuler cache le fonctionnement réel des
protocoles. Implémenter soi-même la découverte (ping parallèle, lecture ARP,
connexion TCP, requêtes SNMP) est plus formateur et reste court
(~150 lignes). Nmap pourra être ajouté plus tard comme source
supplémentaire (voir [07-securite-et-limites.md](07-securite-et-limites.md)).
