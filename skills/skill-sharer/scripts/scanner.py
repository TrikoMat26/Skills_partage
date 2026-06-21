#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scanner d'inventaire des skills Antigravity (Google Gemini agent).

Ce module parcourt les répertoires de skills (global, plugin, workspace),
extrait les métadonnées depuis le frontmatter YAML de chaque ``SKILL.md``
et fournit des fonctions de recherche et de formatage.

Aucune dépendance externe n'est requise — le frontmatter YAML est analysé
manuellement (clés simples, chaînes multi-lignes ``>-`` / ``>``).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_ROOT: Path = Path.home() / ".gemini" / "config"

_SKILL_FILENAME: str = "SKILL.md"

_IGNORED_DIRS: set[str] = {"__pycache__"}

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SkillInfo:
    """Représente les métadonnées d'une skill Antigravity."""

    name: str
    """Nom de la skill (issu du frontmatter)."""

    description: str
    """Description de la skill (issue du frontmatter)."""

    source: str
    """Origine : ``global``, ``plugin:<nom_plugin>`` ou ``workspace``."""

    path: Path
    """Chemin absolu vers le répertoire de la skill."""

    last_modified: datetime
    """Date de dernière modification la plus récente parmi tous les fichiers."""

    files: list[str] = field(default_factory=list)
    """Liste des chemins relatifs de tous les fichiers (hors __pycache__)."""

    total_size: int = 0
    """Taille cumulée de tous les fichiers, en octets."""


# ---------------------------------------------------------------------------
# Analyse du frontmatter YAML (sans PyYAML)
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Extrait les paires clé-valeur du frontmatter YAML d'un fichier SKILL.md.

    Gère les chaînes en ligne ainsi que les blocs multi-lignes introduits par
    ``>-`` ou ``>``.  Les clés sont renvoyées en minuscules.

    Args:
        text: Contenu complet du fichier SKILL.md.

    Returns:
        Dictionnaire des métadonnées extraites du frontmatter.
    """
    # Isoler le bloc entre les deux délimiteurs ---
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    block = match.group(1)
    lines = block.splitlines()

    result: dict[str, str] = {}
    current_key: str | None = None
    current_value_parts: list[str] = []
    is_folded: bool = False  # mode >- ou >

    def _flush() -> None:
        """Enregistre la clé/valeur en cours dans *result*."""
        nonlocal current_key, current_value_parts, is_folded
        if current_key is not None:
            if is_folded:
                # En mode « folded » on joint les lignes par un espace
                value = " ".join(current_value_parts)
            else:
                value = "\n".join(current_value_parts)
            result[current_key] = value.strip()
        current_key = None
        current_value_parts = []
        is_folded = False

    for line in lines:
        # Ligne vide — on l'ignore dans le contexte frontmatter simple
        if not line.strip():
            continue

        # Nouvelle clé ? (pas d'indentation, contient « : »)
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)", line)
        if key_match:
            _flush()
            current_key = key_match.group(1).lower()
            raw_value = key_match.group(2).strip()

            if raw_value in (">-", ">"):
                # Bloc multi-ligne à suivre
                is_folded = True
            elif raw_value:
                # Valeur en ligne — retirer d'éventuels guillemets
                current_value_parts.append(
                    raw_value.strip("\"'")
                )
            continue

        # Ligne de continuation (indentée) — appartient à la clé courante
        if current_key is not None and (line.startswith("  ") or line.startswith("\t")):
            current_value_parts.append(line.strip())

    _flush()
    return result


# ---------------------------------------------------------------------------
# Collecte des fichiers d'une skill
# ---------------------------------------------------------------------------


def _collect_files(skill_dir: Path) -> tuple[list[str], int, datetime]:
    """Parcourt récursivement *skill_dir* et renvoie les fichiers trouvés.

    Les répertoires listés dans ``_IGNORED_DIRS`` sont exclus.

    Args:
        skill_dir: Répertoire racine de la skill.

    Returns:
        Tuple contenant :
        - la liste des chemins relatifs (``str``) de chaque fichier,
        - la taille totale cumulée en octets,
        - le ``datetime`` de dernière modification le plus récent.
    """
    relative_paths: list[str] = []
    total_size: int = 0
    latest_mtime: float = 0.0

    for dirpath, dirnames, filenames in os.walk(skill_dir):
        # Élaguer les répertoires à ignorer (modification in-place)
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]

        for fname in filenames:
            full = Path(dirpath) / fname
            try:
                stat = full.stat()
            except OSError:
                continue

            rel = full.relative_to(skill_dir).as_posix()
            relative_paths.append(rel)
            total_size += stat.st_size
            if stat.st_mtime > latest_mtime:
                latest_mtime = stat.st_mtime

    # Garantir un datetime valide même si le répertoire est vide
    if latest_mtime == 0.0:
        latest_mtime = skill_dir.stat().st_mtime

    last_modified = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
    relative_paths.sort()
    return relative_paths, total_size, last_modified


def _build_skill_info(
    skill_dir: Path,
    source: str,
) -> SkillInfo | None:
    """Construit un ``SkillInfo`` à partir d'un répertoire de skill.

    Renvoie ``None`` si le fichier ``SKILL.md`` est absent ou illisible.

    Args:
        skill_dir: Répertoire racine de la skill.
        source: Chaîne décrivant l'origine (``global``, ``plugin:…``, ``workspace``).

    Returns:
        Instance de ``SkillInfo`` ou ``None``.
    """
    skill_file = skill_dir / _SKILL_FILENAME
    if not skill_file.is_file():
        return None

    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return None

    meta = _extract_frontmatter(text)
    name = meta.get("name", skill_dir.name)
    description = meta.get("description", "")

    files, total_size, last_modified = _collect_files(skill_dir)

    return SkillInfo(
        name=name,
        description=description,
        source=source,
        path=skill_dir.resolve(),
        last_modified=last_modified,
        files=files,
        total_size=total_size,
    )


# ---------------------------------------------------------------------------
# Itérateurs sur les différentes sources
# ---------------------------------------------------------------------------


def _iter_global_skills(config_root: Path) -> Iterator[SkillInfo]:
    """Parcourt les skills globales sous ``<config_root>/skills/*``.

    Args:
        config_root: Racine de la configuration Gemini.

    Yields:
        ``SkillInfo`` pour chaque skill trouvée.
    """
    skills_dir = config_root / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir():
            info = _build_skill_info(child, source="global")
            if info is not None:
                yield info


def _iter_plugin_skills(config_root: Path) -> Iterator[SkillInfo]:
    """Parcourt les skills de plugins sous ``<config_root>/plugins/*/skills/*``.

    Args:
        config_root: Racine de la configuration Gemini.

    Yields:
        ``SkillInfo`` pour chaque skill trouvée.
    """
    plugins_dir = config_root / "plugins"
    if not plugins_dir.is_dir():
        return
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        plugin_name = plugin_dir.name
        plugin_skills = plugin_dir / "skills"
        if not plugin_skills.is_dir():
            continue
        for child in sorted(plugin_skills.iterdir()):
            if child.is_dir():
                info = _build_skill_info(child, source=f"plugin:{plugin_name}")
                if info is not None:
                    yield info


def _iter_workspace_skills(workspace_root: Path) -> Iterator[SkillInfo]:
    """Parcourt les skills du workspace sous ``<workspace_root>/.agents/skills/*``.

    Args:
        workspace_root: Racine du workspace courant.

    Yields:
        ``SkillInfo`` pour chaque skill trouvée.
    """
    skills_dir = workspace_root / ".agents" / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir():
            info = _build_skill_info(child, source="workspace")
            if info is not None:
                yield info


# ---------------------------------------------------------------------------
# API publique — scan et recherche
# ---------------------------------------------------------------------------


def scan_skills(
    config_root: Path = _DEFAULT_CONFIG_ROOT,
    workspace_root: Path | None = None,
) -> list[SkillInfo]:
    """Scanne l'ensemble des skills disponibles et renvoie leur inventaire.

    Args:
        config_root: Racine de la configuration Gemini
            (par défaut ``~/.gemini/config``).
        workspace_root: Chemin optionnel vers un workspace pour inclure
            les skills locales (``.agents/skills``).

    Returns:
        Liste triée (par nom) de ``SkillInfo``.
    """
    skills: list[SkillInfo] = []

    skills.extend(_iter_global_skills(config_root))
    skills.extend(_iter_plugin_skills(config_root))

    if workspace_root is not None:
        skills.extend(_iter_workspace_skills(workspace_root))

    skills.sort(key=lambda s: s.name.lower())
    return skills


def get_skill_by_name(name: str, skills: list[SkillInfo]) -> SkillInfo | None:
    """Recherche une skill par son nom (insensible à la casse).

    Args:
        name: Nom de la skill recherchée.
        skills: Liste de ``SkillInfo`` dans laquelle chercher.

    Returns:
        ``SkillInfo`` correspondante ou ``None``.
    """
    name_lower = name.lower()
    for skill in skills:
        if skill.name.lower() == name_lower:
            return skill
    return None


# ---------------------------------------------------------------------------
# API publique — formatage
# ---------------------------------------------------------------------------


def _truncate(text: str, width: int) -> str:
    """Tronque *text* à *width* caractères en ajoutant ``…`` si nécessaire."""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _human_size(size_bytes: int) -> str:
    """Convertit une taille en octets en chaîne lisible (Ko, Mo…)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ("Ko", "Mo", "Go"):
        size_bytes_f = size_bytes / 1024
        if size_bytes_f < 1024 or unit == "Go":
            return f"{size_bytes_f:.1f} {unit}"
        size_bytes = int(size_bytes_f)
    return f"{size_bytes} B"  # pragma: no cover


def format_skills_table(skills: list[SkillInfo]) -> str:
    """Génère un tableau ASCII formaté pour l'affichage en terminal.

    Les colonnes affichées sont : Nom, Source, Fichiers, Taille, Description.

    Args:
        skills: Liste des skills à afficher.

    Returns:
        Chaîne multi-lignes représentant le tableau.
    """
    if not skills:
        return "(aucune skill trouvée)"

    # Largeurs des colonnes
    col_name = 28
    col_source = 22
    col_files = 7
    col_size = 9
    col_desc = 50

    header = (
        f"{'Nom':<{col_name}} "
        f"{'Source':<{col_source}} "
        f"{'Fich.':<{col_files}} "
        f"{'Taille':<{col_size}} "
        f"{'Description':<{col_desc}}"
    )
    separator = (
        f"{'-' * col_name} "
        f"{'-' * col_source} "
        f"{'-' * col_files} "
        f"{'-' * col_size} "
        f"{'-' * col_desc}"
    )

    lines: list[str] = [header, separator]
    for s in skills:
        desc_first_line = s.description.split("\n")[0] if s.description else ""
        line = (
            f"{_truncate(s.name, col_name):<{col_name}} "
            f"{_truncate(s.source, col_source):<{col_source}} "
            f"{len(s.files):<{col_files}} "
            f"{_human_size(s.total_size):<{col_size}} "
            f"{_truncate(desc_first_line, col_desc)}"
        )
        lines.append(line)

    lines.append(separator)
    lines.append(f"Total : {len(skills)} skill(s)")
    return "\n".join(lines)


def format_skills_json(skills: list[SkillInfo]) -> str:
    """Sérialise la liste de skills au format JSON (indenté, UTF-8).

    Les objets ``Path`` et ``datetime`` sont convertis en chaînes.

    Args:
        skills: Liste des skills à sérialiser.

    Returns:
        Chaîne JSON.
    """

    def _default(obj: object) -> str:
        """Sérialiseur personnalisé pour ``json.dumps``."""
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type non sérialisable : {type(obj)}")  # pragma: no cover

    return json.dumps(
        [asdict(s) for s in skills],
        default=_default,
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Point d'entrée CLI (usage rapide)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scanner d'inventaire des skills Antigravity.",
    )
    parser.add_argument(
        "--config-root",
        type=Path,
        default=_DEFAULT_CONFIG_ROOT,
        help="Racine de la configuration Gemini (défaut : ~/.gemini/config).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Chemin du workspace pour inclure les skills locales.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Afficher le résultat au format JSON.",
    )
    args = parser.parse_args()

    found = scan_skills(
        config_root=args.config_root,
        workspace_root=args.workspace,
    )

    if args.as_json:
        print(format_skills_json(found))
    else:
        print(format_skills_table(found))
