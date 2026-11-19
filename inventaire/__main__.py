"""Point d'entrée en ligne de commande.

Exemples :

    python -m inventaire scan 192.168.1.0/24
    python -m inventaire scan 192.168.1.0/24 --repeter 15
    python -m inventaire web
    python -m inventaire demo
"""

import argparse
import sys
import time

from .base import Base
from .config import charger_config


def commande_scan(args, config) -> None:
    base = Base(config.base_de_donnees)
    from .scanner import scanner
    while True:
        for reseau in args.reseaux:
            try:
                scanner(reseau, config, base)
            except ValueError as erreur:
                sys.exit(f"Erreur : {erreur}")
        if not args.repeter:
            break
        print(f"Prochain scan dans {args.repeter} min (Ctrl+C pour arrêter)")
        time.sleep(args.repeter * 60)


def commande_web(args, config) -> None:
    from .web.app import creer_application
    application = creer_application(config)
    print(f"Interface web : http://{args.hote}:{args.port}/")
    application.run(host=args.hote, port=args.port)


def commande_demo(args, config) -> None:
    from .demo import remplir_demo
    remplir_demo(config.base_de_donnees)
    print(f"Données de démonstration écrites dans {config.base_de_donnees}")
    print("Lancez ensuite : python -m inventaire web")


def main(argv: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(
        prog="python -m inventaire",
        description="Inventaire réseau automatique (découverte, inventaire, topologie).")
    analyseur.add_argument("-c", "--config", default="config.ini",
                           help="fichier de configuration (défaut : config.ini)")
    sous = analyseur.add_subparsers(dest="commande", required=True)

    p_scan = sous.add_parser("scan", help="découvrir un ou plusieurs sous-réseaux")
    p_scan.add_argument("reseaux", nargs="+", metavar="RESEAU",
                        help="réseau en notation CIDR, ex. 192.168.1.0/24")
    p_scan.add_argument("--repeter", type=int, metavar="MIN", default=0,
                        help="relancer le scan toutes les MIN minutes")
    p_scan.add_argument("--communaute", help="communauté SNMP v2c (remplace la config)")
    p_scan.set_defaults(fonction=commande_scan)

    p_web = sous.add_parser("web", help="lancer l'interface web")
    p_web.add_argument("--hote", default="127.0.0.1",
                       help="adresse d'écoute (défaut : 127.0.0.1, accès local uniquement)")
    p_web.add_argument("--port", type=int, default=5000)
    p_web.set_defaults(fonction=commande_web)

    p_demo = sous.add_parser("demo", help="remplir la base avec un réseau fictif")
    p_demo.set_defaults(fonction=commande_demo)

    args = analyseur.parse_args(argv)
    config = charger_config(args.config)
    if getattr(args, "communaute", None):
        config.snmp.communaute = args.communaute
    try:
        args.fonction(args, config)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")


if __name__ == "__main__":
    main()
