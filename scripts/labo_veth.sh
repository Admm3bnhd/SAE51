#!/bin/sh
# Labo de test local : un mini-réseau virtuel sur une seule machine Linux.
#
#   machine hôte (poste-admin, 10.99.0.1)
#        | veth
#   [ns sw-labo]  pont br0 (10.99.0.2)   ← « commutateur » SNMP + LLDP
#        | veth
#   [ns srv-labo] (10.99.0.3)            ← « serveur » SNMP + LLDP
#
# Chaque namespace réseau (ip netns) se comporte comme une machine à part.
# snmpd y répond en SNMP v2c (communauté « public ») et lldpd, branché
# sur snmpd via AgentX, expose ses voisins dans la LLDP-MIB.
#
# Prérequis (Debian/Ubuntu) : sudo apt install iproute2 snmp snmpd lldpd
# Utilisation               : sudo scripts/labo_veth.sh start | stop
# Puis                      : python -m inventaire scan 10.99.0.0/24
set -e

DIR=/run/inventaire-labo

demarrer_agents() {
    # $1 = namespace (vide pour l'hôte), $2 = nom, $3 = IP SNMP,
    # $4 = sysServices, $5 = description, $6 = interfaces LLDP
    ns=$1; nom=$2
    exe=""; [ -n "$ns" ] && exe="ip netns exec $ns"
    cat > "$DIR/$nom-snmpd.conf" <<EOF
agentAddress udp:$3:161
rocommunity public
master agentx
agentXSocket $DIR/$nom-agentx
sysName $nom
sysServices $4
sysDescr $5
EOF
    $exe snmpd -C -c "$DIR/$nom-snmpd.conf" -Lf "$DIR/$nom-snmpd.log" -p "$DIR/$nom-snmpd.pid"
    sleep 1
    $exe lldpd -x -X "$DIR/$nom-agentx" -u "$DIR/$nom-lldpd.sock" -I "$6"
    sleep 1
    lldpcli -u "$DIR/$nom-lldpd.sock" configure system hostname "$nom" >/dev/null
    lldpcli -u "$DIR/$nom-lldpd.sock" configure system description "$5" >/dev/null
    lldpcli -u "$DIR/$nom-lldpd.sock" resume >/dev/null
}

start() {
    mkdir -p "$DIR" /run/lldpd && chmod 755 "$DIR"
    ip netns add sw-labo
    ip netns add srv-labo

    # Liens : hôte <-> sw-labo, sw-labo <-> srv-labo
    ip link add veth-hote type veth peer name sw-p1 netns sw-labo
    ip link add srv-eth0 netns srv-labo type veth peer name sw-p2 netns sw-labo

    # Hôte
    ip addr add 10.99.0.1/24 dev veth-hote
    ip link set veth-hote up

    # « Commutateur » : un pont Linux qui relie ses deux ports
    ip -n sw-labo link add br0 type bridge
    for p in sw-p1 sw-p2; do
        ip -n sw-labo link set "$p" master br0
        ip -n sw-labo link set "$p" up
    done
    ip -n sw-labo addr add 10.99.0.2/24 dev br0
    ip -n sw-labo link set br0 up
    ip -n sw-labo link set lo up

    # « Serveur »
    ip -n srv-labo addr add 10.99.0.3/24 dev srv-eth0
    ip -n srv-labo link set srv-eth0 up
    ip -n srv-labo link set lo up

    demarrer_agents ""         poste-admin 10.99.0.1 72 "Poste d'administration Linux" "veth-hote"
    demarrer_agents sw-labo    sw-labo     10.99.0.2 2  "Commutateur de labo (pont Linux)" "sw-p*"
    demarrer_agents srv-labo   srv-labo    10.99.0.3 72 "Serveur Linux Debian de labo" "srv-eth0"

    # Tous les agents tournent : on force un nouvel envoi LLDP pour que
    # chacun annonce son nom définitif à des voisins déjà à l'écoute.
    sleep 1
    for nom in poste-admin sw-labo srv-labo; do
        lldpcli -u "$DIR/$nom-lldpd.sock" configure lldp tx-interval 10 >/dev/null
        lldpcli -u "$DIR/$nom-lldpd.sock" update >/dev/null
    done

    echo "Labo démarré. Patientez ~5 s (échange LLDP) puis :"
    echo "  python -m inventaire scan 10.99.0.0/24"
}

stop() {
    for pid in "$DIR"/*-snmpd.pid; do [ -f "$pid" ] && kill "$(cat "$pid")" 2>/dev/null || true; done
    pkill -f "lldpd -x -X $DIR" 2>/dev/null || true
    ip netns del sw-labo 2>/dev/null || true
    ip netns del srv-labo 2>/dev/null || true
    ip link del veth-hote 2>/dev/null || true
    rm -rf "$DIR"
    echo "Labo arrêté."
}

case "$1" in
    start) start ;;
    stop) stop ;;
    *) echo "Utilisation : $0 start|stop"; exit 1 ;;
esac
