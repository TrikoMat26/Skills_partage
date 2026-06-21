#!/usr/bin/env python3
"""Vérificateur de compatibilité des environnements cibles.

Ce module charge des empreintes d'environnements depuis un fichier JSON
(``env_fingerprints.json``) et exécute des contrôles de compatibilité
pour détecter d'éventuels changements de format depuis la dernière vérification.
"""

from __future__ import annotations

import glob
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Résultat d'une vérification d'environnement.

    Attributes:
        env_name: Nom de l'environnement vérifié.
        status: Statut global — ``'ok'``, ``'warning'`` ou ``'error'``.
        messages: Liste de messages détaillés décrivant chaque contrôle.
        format_version: Version du format attendu par l'environnement.
        last_checked: Horodatage ISO-8601 de la dernière vérification.
    """

    env_name: str
    status: str  # 'ok' | 'warning' | 'error'
    messages: list[str] = field(default_factory=list)
    format_version: str = ""
    last_checked: str = ""


# ---------------------------------------------------------------------------
# Chargement / sauvegarde des empreintes
# ---------------------------------------------------------------------------

def load_fingerprints(fingerprints_path: Path) -> dict:
    """Charge les empreintes d'environnements depuis un fichier JSON.

    Args:
        fingerprints_path: Chemin vers le fichier ``env_fingerprints.json``.

    Returns:
        Dictionnaire contenant la structure complète des empreintes.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        json.JSONDecodeError: Si le contenu n'est pas du JSON valide.
    """
    with fingerprints_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_fingerprints(fingerprints_path: Path, data: dict) -> None:
    """Sauvegarde les empreintes dans un fichier JSON avec horodatages mis à jour.

    Args:
        fingerprints_path: Chemin de destination du fichier JSON.
        data: Dictionnaire des empreintes à sérialiser.
    """
    fingerprints_path.parent.mkdir(parents=True, exist_ok=True)
    with fingerprints_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Vérification d'un environnement
# ---------------------------------------------------------------------------

def _resolve_path(raw: str, workspace_root: Path | None) -> Path:
    """Résout un chemin brut en chemin absolu.

    Gère l'expansion du ``~`` et les chemins relatifs par rapport à
    *workspace_root*.
    """
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded
    if workspace_root is not None:
        return workspace_root / expanded
    return expanded


def check_environment(
    env_name: str,
    env_config: dict,
    workspace_root: Path | None = None,
) -> CheckResult:
    """Vérifie la compatibilité d'un environnement cible.

    Contrôles effectués (selon les clés présentes dans ``checkpoints``) :

    * **config_dir_exists** — Vérifie l'existence du répertoire de
      configuration (expansion ``~``, résolution relative).
    * **legacy_file** — Détecte un fichier hérité et émet un avertissement
      recommandant la migration.
    * **required_file** — Vérifie qu'au moins un skill contenant le fichier
      requis existe dans le répertoire de configuration.
    * **sample_file_pattern** — Vérifie qu'au moins un fichier correspond au
      motif glob fourni.

    Args:
        env_name: Identifiant de l'environnement (ex. ``'cursor'``).
        env_config: Dictionnaire de configuration de l'environnement tel que
            lu depuis le JSON d'empreintes.
        workspace_root: Racine du workspace pour la résolution des chemins
            relatifs. Si ``None``, les chemins relatifs sont résolus depuis le
            répertoire courant.

    Returns:
        Un :class:`CheckResult` résumant les résultats de la vérification.
    """
    messages: list[str] = []
    status = "ok"
    checkpoints: dict = env_config.get("checkpoints", {})

    # --- config_dir_exists ---------------------------------------------------
    config_dir: Path | None = None
    if "config_dir_exists" in checkpoints:
        config_dir = _resolve_path(checkpoints["config_dir_exists"], workspace_root)
        if config_dir.is_dir():
            messages.append(
                f"Répertoire de configuration trouvé : {config_dir}"
            )
        else:
            status = "error"
            messages.append(
                f"Répertoire de configuration introuvable : {config_dir}"
            )

    # --- legacy_file ---------------------------------------------------------
    if "legacy_file" in checkpoints:
        legacy_path = _resolve_path(checkpoints["legacy_file"], workspace_root)
        if legacy_path.exists():
            if status != "error":
                status = "warning"
            messages.append(
                f"Fichier hérité détecté : {legacy_path} — "
                "migration recommandée vers le nouveau format"
            )
        else:
            messages.append(
                f"Aucun fichier hérité détecté ({legacy_path})"
            )

    # --- required_file -------------------------------------------------------
    if "required_file" in checkpoints and config_dir is not None:
        required = checkpoints["required_file"]
        if config_dir.is_dir():
            # Cherche dans les sous-répertoires directs du config_dir
            found = list(config_dir.glob(f"*/{required}"))
            if found:
                messages.append(
                    f"Fichier requis « {required} » trouvé dans "
                    f"{len(found)} skill(s)"
                )
            else:
                if status != "error":
                    status = "warning"
                messages.append(
                    f"Aucun skill ne contient le fichier requis « {required} » "
                    f"dans {config_dir}"
                )
        else:
            messages.append(
                f"Vérification de « {required} » ignorée — répertoire "
                "de configuration absent"
            )

    # --- sample_file_pattern -------------------------------------------------
    if "sample_file_pattern" in checkpoints and config_dir is not None:
        pattern = checkpoints["sample_file_pattern"]
        if config_dir.is_dir():
            matched = glob.glob(str(config_dir / pattern))
            if matched:
                messages.append(
                    f"Fichiers correspondant au motif « {pattern} » : "
                    f"{len(matched)} trouvé(s)"
                )
            else:
                if status != "error":
                    status = "warning"
                messages.append(
                    f"Aucun fichier correspondant au motif « {pattern} » "
                    f"dans {config_dir}"
                )
        else:
            messages.append(
                f"Vérification du motif « {pattern} » ignorée — "
                "répertoire de configuration absent"
            )

    return CheckResult(
        env_name=env_name,
        status=status,
        messages=messages,
        format_version=env_config.get("format_version", ""),
        last_checked=env_config.get("last_checked", ""),
    )


# ---------------------------------------------------------------------------
# Vérification globale
# ---------------------------------------------------------------------------

def check_all(
    fingerprints_path: Path,
    workspace_root: Path | None = None,
) -> list[CheckResult]:
    """Vérifie tous les environnements définis dans le fichier d'empreintes.

    Args:
        fingerprints_path: Chemin vers ``env_fingerprints.json``.
        workspace_root: Racine du workspace (voir :func:`check_environment`).

    Returns:
        Liste de :class:`CheckResult`, un par environnement.
    """
    data = load_fingerprints(fingerprints_path)
    environments: dict = data.get("environments", {})

    results: list[CheckResult] = []
    for env_name, env_config in environments.items():
        result = check_environment(env_name, env_config, workspace_root)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Formatage des résultats
# ---------------------------------------------------------------------------

_STATUS_EMOJI: dict[str, str] = {
    "ok": "✅",
    "warning": "⚠️",
    "error": "❌",
}


def format_check_results(results: list[CheckResult]) -> str:
    """Produit un affichage lisible des résultats de vérification.

    Chaque environnement est présenté avec un indicateur emoji
    (✅ OK, ⚠️ avertissement, ❌ erreur) suivi de ses messages détaillés.
    Une ligne de résumé conclut le rapport.

    Args:
        results: Liste de résultats issus de :func:`check_all` ou
            :func:`check_environment`.

    Returns:
        Chaîne de caractères formatée, prête à être affichée.
    """
    lines: list[str] = []

    for r in results:
        emoji = _STATUS_EMOJI.get(r.status, "❓")
        lines.append(
            f"{emoji} {r.env_name} (v{r.format_version}) "
            f"— dernière vérification : {r.last_checked}"
        )
        for msg in r.messages:
            lines.append(f"   • {msg}")
        lines.append("")  # ligne vide entre environnements

    # --- Résumé --------------------------------------------------------------
    ok_count = sum(1 for r in results if r.status == "ok")
    warn_count = sum(1 for r in results if r.status == "warning")
    err_count = sum(1 for r in results if r.status == "error")
    lines.append(
        f"📊 Résumé : {ok_count} OK, {warn_count} avertissements, "
        f"{err_count} erreurs"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mise à jour des horodatages
# ---------------------------------------------------------------------------

def update_fingerprints_timestamps(fingerprints_path: Path) -> None:
    """Met à jour tous les champs ``last_checked`` à l'instant courant.

    Le fichier JSON est relu, modifié en mémoire puis réécrit.

    Args:
        fingerprints_path: Chemin vers ``env_fingerprints.json``.
    """
    data = load_fingerprints(fingerprints_path)
    now_iso = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    for env_config in data.get("environments", {}).values():
        env_config["last_checked"] = now_iso

    save_fingerprints(fingerprints_path, data)


# ---------------------------------------------------------------------------
# Point d'entrée CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Point d'entrée en ligne de commande pour le vérificateur."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Vérifie la compatibilité des environnements cibles.",
    )
    parser.add_argument(
        "fingerprints",
        type=Path,
        help="Chemin vers le fichier env_fingerprints.json",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Racine du workspace pour les chemins relatifs",
    )
    parser.add_argument(
        "--update-timestamps",
        action="store_true",
        help="Met à jour les horodatages après la vérification",
    )
    args = parser.parse_args()

    results = check_all(args.fingerprints, workspace_root=args.workspace)
    print(format_check_results(results))

    if args.update_timestamps:
        update_fingerprints_timestamps(args.fingerprints)
        print("\n🕐 Horodatages mis à jour.")


if __name__ == "__main__":
    main()
