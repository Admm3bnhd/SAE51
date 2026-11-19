# 7. Sécurité, limites et perspectives

## 7.1 Cadre légal

Scanner un réseau revient à sonder des systèmes qui ne nous appartiennent
pas forcément. En France, accéder ou tenter d'accéder frauduleusement à
un système de traitement automatisé de données est puni par
l'**article 323-1 du Code pénal**.

- N'utiliser l'outil **que sur un réseau dont on est administrateur** ou
  avec une autorisation écrite (salle de TP, maquette, réseau personnel).
- Prévenir l'équipe sécurité : un scan peut déclencher des alertes de
  détection d'intrusion (IDS), ce qui est normal.
- L'inventaire contient des **données à caractère personnel** au sens du
  RGPD (noms de postes nominatifs comme `pc-dupont`, adresses MAC liées à
  un utilisateur). La base doit être protégée et conservée pour une durée
  limitée.

## 7.2 Mesures de sécurité de l'outil

| Risque | Mesure prise |
|---|---|
| Action non voulue sur le réseau | L'outil est en **lecture seule** : ping, ARP, connexion TCP, SNMP GET/WALK. Aucune écriture SNMP (SET), aucune connexion SSH/Telnet |
| Accès à l'interface par un tiers | Écoute par défaut sur **127.0.0.1** ; l'ouverture au réseau (`--hote 0.0.0.0`) est un choix explicite |
| Fuite de la communauté SNMP | `config.ini` est exclu du dépôt Git (`.gitignore`) ; seul `config.example.ini` est versionné |
| Communauté SNMP lisible sur le réseau | SNMPv3 `authPriv` (SHA + AES) pris en charge |
| Injection de commande | Les commandes sont lancées avec `subprocess.run([...])` sous forme de **liste** (jamais via un shell) et le réseau saisi est validé par le module `ipaddress` |
| Injection SQL | Requêtes **paramétrées** (`?`) uniquement |
| Injection HTML (XSS) via un `sysName` malveillant | Échappement automatique de Jinja2 ; infobulles du graphe en texte brut |
| Scan démesuré | Taille limitée à un /16 ; un seul scan à la fois depuis l'interface |

### Points de vigilance restants

- **SNMP v2c** : la communauté circule **en clair** (UDP 161). Toute
  personne qui capture le trafic (Wireshark) peut la lire. Il faut la
  limiter à la lecture (`RO`) et à l'adresse de la machine d'inventaire
  (ACL), ou passer en SNMPv3.
- Les mots de passe SNMPv3 sont passés en arguments à `snmpget` : ils sont
  visibles par les autres utilisateurs de la machine via `ps`. Sur une
  machine partagée, laisser les mots de passe vides dans `config.ini` et
  les placer dans `~/.snmp/snmp.conf` (`chmod 600`), que Net-SNMP lit
  automatiquement :

  ```
  defSecurityName  inventaire
  defAuthPassphrase MotDePasseAuth
  defPrivPassphrase MotDePassePriv
  ```
- L'interface web n'a **pas d'authentification**. Si on l'ouvre au
  réseau, il faut la placer derrière un proxy (Nginx) avec HTTPS et
  authentification.
- Le formulaire de scan n'a pas de protection CSRF : sans importance tant
  que l'interface n'écoute qu'en local, à ajouter (Flask-WTF) sinon.

## 7.3 Limites connues

| Limite | Explication | Contournement / piste |
|---|---|---|
| **ARP limité au sous-réseau local** | ARP ne traverse pas les routeurs : pour un réseau distant, pas de MAC ni de détection des hôtes qui filtrent ICMP | Lire la table ARP du routeur en SNMP (`ipNetToMediaTable`, `1.3.6.1.2.1.4.22`) |
| **Hôtes totalement silencieux** | Un hôte distant qui filtre ICMP et n'a aucun port TCP ouvert est invisible | Inhérent à toute découverte active |
| **Clé = adresse IP** | Avec du DHCP, un appareil qui change d'IP apparaît comme « nouveau » et son ancienne IP comme « disparue » | Identifier par MAC quand elle est connue |
| **MAC aléatoires** | Les smartphones et portables récents changent de MAC par réseau Wi-Fi : constructeur inconnu, appareil difficile à suivre | Signalé comme « MAC locale / aléatoire » |
| **Hôtes sans LLDP** | Les postes n'émettent en général pas LLDP : on sait à quel sous-réseau ils appartiennent, pas à quel port de commutateur | Lire la table MAC des commutateurs (BRIDGE-MIB `dot1dTpFdbTable`) pour trouver le port de chaque MAC |
| **CDP non lu** | Certains équipements Cisco n'ont que CDP d'activé | Lire `CISCO-CDP-MIB` (`1.3.6.1.4.1.9.9.23`) |
| **Classification heuristique** | Le type est déduit, il peut être faux (un Linux de bureau avec SSH sera vu comme « serveur ») | La raison est affichée ; piste : correction manuelle du type dans l'interface |
| **IPv4 uniquement** | Un /64 IPv6 ne se balaie pas (2⁶⁴ adresses) | Découverte IPv6 par le cache des voisins NDP et le multicast `ff02::1` |
| **Linux uniquement** | Utilise `ping -W`, `ip neigh` et `/sys/class/net` | Fonctionne sous WSL ; un portage Windows demanderait d'adapter `decouverte.py` |

## 7.4 Améliorations possibles

Classées de la plus simple à la plus ambitieuse :

1. **Correction manuelle** du type et ajout d'un commentaire / d'un
   emplacement (bâtiment, baie) depuis la fiche d'un équipement.
2. **Lecture de CDP** en plus de LLDP pour les réseaux Cisco.
3. **Table ARP des routeurs en SNMP** pour inventorier les réseaux
   distants avec les adresses MAC.
4. **Table MAC des commutateurs** (BRIDGE-MIB / Q-BRIDGE-MIB) pour
   rattacher chaque poste au bon port : la topologie deviendrait complète
   jusqu'au poste de travail.
5. **Alertes** par e-mail ou webhook lors de l'apparition d'un équipement
   inconnu (détection d'appareils non autorisés).
6. **Export vers NetBox** (API REST) pour alimenter une source de vérité
   professionnelle.
7. **Supervision** légère : temps de réponse, disponibilité au fil du
   temps, graphiques.
8. **Authentification** dans l'interface et déploiement en conteneur
   Docker.
