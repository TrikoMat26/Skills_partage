#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI principal du Skill Sharer.

Point d'entrée pour lister, packager, partager, synchroniser
et vérifier la compatibilité des skills.
"""

import argparse
import io
import sys
import tempfile
from pathlib import Path

# Garantir que les modules voisins sont trouvables même via symlink
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from scanner import scan_skills, get_skill_by_name, format_skills_table, format_skills_json
from packager import package_skill
from sync import share_to_repo, share_to_local, update_from_repo, get_repo_root
from checker import load_fingerprints, check_all, check_environment, format_check_results, update_fingerprints_timestamps

def main():
    # Forcer UTF-8 sur stdout/stderr pour éviter les UnicodeEncodeError Windows
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="Skill Sharer: Partage et synchronisation de skills")
    parser.add_argument("--config-root", type=str, help="Chemin racine de la configuration Gemini (défaut: ~/.gemini/config)")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Commande: list
    parser_list = subparsers.add_parser("list", help="Inventaire des skills installés")
    parser_list.add_argument("--format", choices=["table", "json"], default="table", help="Format d'affichage (table ou json)")

    # Commande: package
    parser_package = subparsers.add_parser("package", help="Exporter un skill vers un format cible")
    parser_package.add_argument("skill", type=str, help="Nom du skill à packager")
    parser_package.add_argument("--target", required=True, choices=["antigravity", "markdown", "cursor", "windsurf", "copilot", "chatgpt"], help="Format cible")
    parser_package.add_argument("--output", type=str, help="Répertoire de sortie (défaut: ./export)")

    # Commande: share
    parser_share = subparsers.add_parser("share", help="Partager un skill")
    parser_share.add_argument("skill", type=str, help="Nom du skill à partager")
    parser_share.add_argument("--method", required=True, choices=["local", "repo", "gist"], help="Méthode de partage")
    parser_share.add_argument("--destination", type=str, help="Chemin de destination (pour --method local)")

    # Commande: update
    parser_update = subparsers.add_parser("update", help="Synchroniser depuis le registre")
    parser_update.add_argument("--all", action="store_true", help="Mettre à jour tous les skills")
    parser_update.add_argument("--skill", type=str, help="Mettre à jour un skill spécifique")

    # Commande: check
    parser_check = subparsers.add_parser("check", help="Vérifier la compatibilité des environnements")
    parser_check.add_argument("--all", action="store_true", help="Vérifier tous les environnements")
    parser_check.add_argument("--env", type=str, help="Vérifier un environnement spécifique")
    parser_check.add_argument("--update-fingerprints", action="store_true", help="Mettre à jour les timestamps de dernière vérification")

    args = parser.parse_args()

    # Définition des chemins par défaut
    config_root = Path(args.config_root).expanduser() if args.config_root else Path.home() / ".gemini" / "config"
    current_dir = Path.cwd()
    repo_root = get_repo_root()
    skills_sharer_dir = Path(__file__).resolve().parent.parent
    fingerprints_path = skills_sharer_dir / "resources" / "env_fingerprints.json"

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        skills = scan_skills(config_root, current_dir)
        if args.format == "json":
            print(format_skills_json(skills))
        else:
            print(format_skills_table(skills))
            
    elif args.command == "package":
        skills = scan_skills(config_root, current_dir)
        skill_info = get_skill_by_name(args.skill, skills)
        if not skill_info:
            print(f"❌ Erreur : Skill '{args.skill}' introuvable.")
            sys.exit(1)
        
        output_dir = Path(args.output).expanduser() if args.output else current_dir / "export"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            print(f"📦 Packaging du skill '{skill_info.name}' au format '{args.target}'...")
            output_path = package_skill(Path(skill_info.path), skill_info.name, skill_info.description, args.target, output_dir)
            print(f"✅ Skill packagé avec succès : {output_path}")
        except Exception as e:
            print(f"❌ Erreur lors du packaging : {e}")
            sys.exit(1)

    elif args.command == "share":
        skills = scan_skills(config_root, current_dir)
        skill_info = get_skill_by_name(args.skill, skills)
        if not skill_info:
            print(f"❌ Erreur : Skill '{args.skill}' introuvable.")
            sys.exit(1)

        print(f"🚀 Partage du skill '{skill_info.name}' via '{args.method}'...")
        
        # Packaging universel en markdown (ou antigravity selon le besoin)
        target_format = "markdown" if args.method == "gist" else "antigravity"

        with tempfile.TemporaryDirectory(prefix="skill-sharer-") as tmp:
            temp_export = Path(tmp)
            packaged_path = package_skill(Path(skill_info.path), skill_info.name, skill_info.description, target_format, temp_export)
            
            if args.method == "local":
                if not args.destination:
                    print("❌ L'option --destination est requise pour la méthode 'local'.")
                    sys.exit(1)
                dest = Path(args.destination).expanduser()
                share_to_local(packaged_path, dest)
                print(f"✅ Skill copié vers : {dest}")
                
            elif args.method == "repo":
                if not repo_root:
                    print("❌ Vous n'êtes pas dans un dépôt Git. Impossible d'utiliser la méthode 'repo'.")
                    sys.exit(1)
                share_to_repo(skill_info.name, packaged_path, repo_root)
                print(f"✅ Skill '{skill_info.name}' partagé sur le dépôt GitHub.")
                
            elif args.method == "gist":
                print("ℹ️ Le partage Gist nécessite le CLI 'gh'. (Non implémenté dans cet exemple, vous pouvez copier/coller le fichier suivant :)")
                print(f"Fichier : {packaged_path}")

    elif args.command == "update":
        if not args.all and not args.skill:
            print("❌ Spécifiez --all ou --skill <nom>.")
            sys.exit(1)
            
        if not repo_root:
             print("❌ Vous n'êtes pas dans un dépôt Git. Impossible de mettre à jour.")
             sys.exit(1)
             
        print("🔄 Mise à jour depuis le registre partagé...")
        try:
            skills_dir = config_root / "skills"
            updated = update_from_repo(args.skill, repo_root, skills_dir)
            if updated:
                print(f"✅ Skills mis à jour : {', '.join(updated)}")
            else:
                print("ℹ️ Tous les skills sont déjà à jour.")
        except Exception as e:
             print(f"❌ Erreur lors de la mise à jour : {e}")
             sys.exit(1)

    elif args.command == "check":
        if not args.all and not args.env:
             print("❌ Spécifiez --all ou --env <environnement>.")
             sys.exit(1)
             
        if not fingerprints_path.exists():
             print(f"❌ Fichier de signatures introuvable : {fingerprints_path}")
             sys.exit(1)
             
        print("🔍 Vérification des environnements cibles...\n")
        try:
            fingerprints_data = load_fingerprints(fingerprints_path)
            results = []
            if args.all:
                results = check_all(fingerprints_path, current_dir)
            else:
                env_config = fingerprints_data.get("environments", {}).get(args.env)
                if not env_config:
                    print(f"❌ Environnement '{args.env}' inconnu.")
                    sys.exit(1)
                res = check_environment(args.env, env_config, current_dir)
                results.append(res)
                
            print(format_check_results(results))
            
            if args.update_fingerprints:
                update_fingerprints_timestamps(fingerprints_path)
                print("\n✅ Horodatages mis à jour.")
                
        except Exception as e:
            print(f"❌ Erreur lors de la vérification : {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
