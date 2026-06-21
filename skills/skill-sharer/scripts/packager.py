"""Packager de skills Antigravity vers différents formats de partage.

Ce module permet d'exporter une skill Antigravity dans plusieurs formats
cibles pour la partager entre différents environnements d'IA :
  - markdown   : format universel (fichier .md autonome)
  - antigravity : copie native du répertoire
  - cursor     : format .mdc pour Cursor
  - windsurf   : format .md avec balises XML pour Windsurf
  - copilot    : format .instructions.md pour GitHub Copilot
  - chatgpt    : format .txt pour ChatGPT Custom GPT
"""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SUPPORTED_TARGETS: Final[tuple[str, ...]] = (
    "markdown",
    "antigravity",
    "cursor",
    "windsurf",
    "copilot",
    "chatgpt",
)

#: Correspondance extension → identifiant de langage pour les blocs de code.
_EXTENSION_MAP: Final[dict[str, str]] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".mdc": "markdown",
    ".txt": "text",
    ".csv": "csv",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".sql": "sql",
    ".r": "r",
    ".R": "r",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".env": "dotenv",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "protobuf",
    ".svg": "xml",
}

#: Répertoires à ignorer lors du parcours de fichiers.
_IGNORE_DIRS: Final[set[str]] = {"__pycache__", ".git", ".venv", "node_modules"}

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------


def detect_language(filename: str) -> str:
    """Détermine l'identifiant de langage à partir du nom de fichier.

    Gère les cas spéciaux comme ``Dockerfile`` ou les fichiers sans extension.

    Args:
        filename: Nom du fichier (peut inclure un chemin relatif).

    Returns:
        Identifiant de langage (ex. ``"python"``, ``"bash"``).
        Retourne ``"text"`` si l'extension n'est pas reconnue.
    """
    base = Path(filename).name.lower()

    # Cas spéciaux sans extension
    if base == "dockerfile":
        return "dockerfile"
    if base == "makefile":
        return "makefile"
    if base in (".gitignore", ".dockerignore", ".editorconfig"):
        return "text"

    suffix = Path(filename).suffix.lower()
    return _EXTENSION_MAP.get(suffix, "text")


def compute_checksum(skill_path: Path) -> str:
    """Calcule un SHA-256 de l'ensemble des fichiers de la skill.

    Les fichiers sont lus dans l'ordre lexicographique de leurs chemins
    relatifs. Le chemin relatif de chaque fichier est inclus dans le hash
    pour détecter les renommages.

    Args:
        skill_path: Chemin racine du répertoire de la skill.

    Returns:
        Empreinte SHA-256 hexadécimale.
    """
    hasher = hashlib.sha256()
    for file_path in _iter_skill_files(skill_path):
        rel = file_path.relative_to(skill_path).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


def read_skill_content(
    skill_path: Path,
) -> tuple[str, str, list[tuple[str, str]]]:
    """Lit le contenu complet d'une skill.

    Args:
        skill_path: Chemin racine du répertoire de la skill.

    Returns:
        Un tuple ``(frontmatter, body, auxiliary_files)`` où :
        - *frontmatter* est le bloc YAML du fichier ``SKILL.md`` (sans
          les délimiteurs ``---``), ou une chaîne vide s'il n'y en a pas.
        - *body* est le contenu Markdown de ``SKILL.md`` sans le
          frontmatter.
        - *auxiliary_files* est une liste de tuples
          ``(chemin_relatif, contenu)`` pour chaque fichier annexe.

    Raises:
        FileNotFoundError: Si ``SKILL.md`` est introuvable.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(
            f"Fichier SKILL.md introuvable dans {skill_path}"
        )

    raw = skill_md.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw)

    auxiliary_files: list[tuple[str, str]] = []
    for file_path in _iter_skill_files(skill_path):
        if file_path.name == "SKILL.md":
            continue
        rel = file_path.relative_to(skill_path).as_posix()
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fichier binaire : on l'ignore dans les formats texte
            continue
        auxiliary_files.append((rel, content))

    return frontmatter, body, auxiliary_files


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------


def package_skill(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    target: str,
    output_path: Path,
) -> Path:
    """Exporte une skill Antigravity dans le format cible demandé.

    Args:
        skill_path: Chemin vers le répertoire racine de la skill.
        skill_name: Nom de la skill.
        skill_description: Description courte de la skill.
        target: Format cible (``"markdown"``, ``"antigravity"``,
            ``"cursor"``, ``"windsurf"``, ``"copilot"``, ``"chatgpt"``).
        output_path: Chemin du fichier ou répertoire de sortie.

    Returns:
        Chemin effectif du fichier ou répertoire créé.

    Raises:
        ValueError: Si le format *target* n'est pas supporté.
        FileNotFoundError: Si *skill_path* n'existe pas.
    """
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Format cible inconnu : {target!r}. "
            f"Formats supportés : {', '.join(SUPPORTED_TARGETS)}"
        )
    if not skill_path.is_dir():
        raise FileNotFoundError(
            f"Le répertoire de la skill n'existe pas : {skill_path}"
        )

    dispatcher: dict[str, _PackagerFn] = {
        "markdown": _package_markdown,
        "antigravity": _package_antigravity,
        "cursor": _package_cursor,
        "windsurf": _package_windsurf,
        "copilot": _package_copilot,
        "chatgpt": _package_chatgpt,
    }
    return dispatcher[target](
        skill_path, skill_name, skill_description, output_path
    )


# Type alias pour les fonctions de packaging internes.
_PackagerFn = Callable[[Path, str, str, Path], Path]

# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _iter_skill_files(skill_path: Path) -> list[Path]:
    """Parcourt récursivement les fichiers de la skill, triés par chemin relatif.

    Exclut les répertoires listés dans ``_IGNORE_DIRS``.
    """
    files: list[Path] = []
    for item in sorted(skill_path.rglob("*")):
        if item.is_dir():
            continue
        # Vérifier qu'aucun parent n'est dans _IGNORE_DIRS
        if any(part in _IGNORE_DIRS for part in item.relative_to(skill_path).parts):
            continue
        files.append(item)
    return files


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Sépare le frontmatter YAML du corps Markdown.

    Returns:
        ``(frontmatter, body)`` — *frontmatter* est la chaîne YAML brute
        (sans les délimiteurs ``---``), ou ``""`` si absent.
    """
    pattern = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
    match = pattern.match(text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", text.strip()


def _build_files_list(
    auxiliary_files: list[tuple[str, str]],
) -> str:
    """Construit la liste YAML des fichiers pour le frontmatter étendu."""
    if not auxiliary_files:
        return "[]"
    lines: list[str] = []
    for rel_path, _ in auxiliary_files:
        lang = detect_language(rel_path)
        lines.append(f"  - path: \"{rel_path}\"")
        lines.append(f"    language: \"{lang}\"")
    return "\n".join(lines)


def _ensure_parent(path: Path) -> None:
    """Crée les répertoires parents si nécessaire."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    """Retourne l'horodatage courant en ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def _embed_auxiliary_files(
    auxiliary_files: list[tuple[str, str]],
) -> str:
    """Génère les blocs de code fencés pour les fichiers auxiliaires."""
    if not auxiliary_files:
        return ""
    parts: list[str] = []
    for rel_path, content in auxiliary_files:
        lang = detect_language(rel_path)
        parts.append(f"<!-- FILE: {rel_path} -->")
        parts.append(f"```{lang}")
        parts.append(content)
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Implémentations par format
# ---------------------------------------------------------------------------


def _package_markdown(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``markdown`` — fichier .md universel autonome."""
    frontmatter, body, auxiliary_files = read_skill_content(skill_path)
    checksum = compute_checksum(skill_path)
    files_yaml = _build_files_list(auxiliary_files)

    # Construction du frontmatter étendu
    extended_fm_lines = [
        "---",
        f"name: \"{skill_name}\"",
        f"description: \"{skill_description}\"",
        "version: \"1.0.0\"",
        "source_env: \"antigravity\"",
        f"exported_at: \"{_now_iso()}\"",
        f"checksum: \"{checksum}\"",
        f"files:",
    ]
    if auxiliary_files:
        extended_fm_lines.append(files_yaml)
    else:
        extended_fm_lines.append("  []")
    extended_fm_lines.append("---")

    # Assemblage du document
    sections: list[str] = [
        "\n".join(extended_fm_lines),
        "",
        body,
    ]

    if auxiliary_files:
        sections.append("")
        sections.append("## Fichiers Auxiliaires")
        sections.append("")
        sections.append(_embed_auxiliary_files(auxiliary_files))

    sections.append("")
    sections.append("## Instructions de Reconstruction")
    sections.append("")
    sections.append(
        "Pour recréer la structure de répertoires de cette skill :\n"
        "\n"
        "1. Créez un répertoire portant le nom de la skill.\n"
        "2. Copiez le contenu Markdown principal (hors frontmatter étendu "
        "et sections auxiliaires) dans un fichier `SKILL.md` à la racine "
        "de ce répertoire.\n"
        "3. Pour chaque fichier listé dans la section "
        "**Fichiers Auxiliaires**, créez le chemin relatif indiqué dans "
        "le commentaire `<!-- FILE: ... -->` et collez-y le contenu du "
        "bloc de code correspondant.\n"
        "4. Les sous-répertoires (`scripts/`, `examples/`, `resources/`, "
        "`references/`) seront recréés automatiquement si les chemins "
        "relatifs les contiennent.\n"
        "5. Vérifiez l'intégrité avec le checksum SHA-256 du frontmatter."
    )

    # Garantir l'extension .md
    if output_path.suffix != ".md":
        output_path = output_path.with_suffix(".md")

    _ensure_parent(output_path)
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def _package_antigravity(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``antigravity`` — copie native du répertoire."""
    if output_path.exists():
        shutil.rmtree(output_path)
    shutil.copytree(
        skill_path,
        output_path,
        ignore=shutil.ignore_patterns(*_IGNORE_DIRS),
    )
    return output_path


def _package_cursor(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``cursor`` — fichier .mdc pour Cursor."""
    _frontmatter, body, auxiliary_files = read_skill_content(skill_path)

    # Frontmatter Cursor
    fm_lines = [
        "---",
        f"description: \"{skill_description}\"",
        "globs: []",
        "alwaysApply: true",
        "---",
    ]

    sections: list[str] = [
        "\n".join(fm_lines),
        "",
        f"# {skill_name}",
        "",
        body,
    ]

    if auxiliary_files:
        sections.append("")
        sections.append("## Scripts et Ressources")
        sections.append("")
        sections.append(_embed_auxiliary_files(auxiliary_files))

    # Garantir l'extension .mdc
    if output_path.suffix != ".mdc":
        output_path = output_path.with_suffix(".mdc")

    _ensure_parent(output_path)
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def _package_windsurf(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``windsurf`` — fichier .md avec balises XML."""
    _frontmatter, body, auxiliary_files = read_skill_content(skill_path)

    sections: list[str] = [
        f"# {skill_name}",
        "",
        "<description>",
        skill_description,
        "</description>",
        "",
        "<instructions>",
        "",
        body,
        "",
        "</instructions>",
    ]

    if auxiliary_files:
        sections.append("")
        sections.append("<scripts>")
        sections.append("")
        sections.append(_embed_auxiliary_files(auxiliary_files))
        sections.append("</scripts>")

    # Garantir l'extension .md
    if output_path.suffix != ".md":
        output_path = output_path.with_suffix(".md")

    _ensure_parent(output_path)
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def _package_copilot(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``copilot`` — fichier .instructions.md pour GitHub Copilot."""
    _frontmatter, body, auxiliary_files = read_skill_content(skill_path)

    sections: list[str] = [
        f"# {skill_name}",
        "",
        "# Overview",
        "",
        skill_description,
        "",
        "# Instructions",
        "",
        body,
    ]

    if auxiliary_files:
        sections.append("")
        sections.append("# Code References")
        sections.append("")
        sections.append(_embed_auxiliary_files(auxiliary_files))

    # Garantir l'extension .instructions.md
    stem = output_path.stem
    # Si le nom se termine déjà par .instructions, on garde
    if not str(output_path).endswith(".instructions.md"):
        output_path = output_path.parent / f"{stem}.instructions.md"

    _ensure_parent(output_path)
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def _package_chatgpt(
    skill_path: Path,
    skill_name: str,
    skill_description: str,
    output_path: Path,
) -> Path:
    """Format ``chatgpt`` — fichier .txt pour ChatGPT Custom GPT."""
    _frontmatter, body, auxiliary_files = read_skill_content(skill_path)

    # Extraire les éventuelles consignes de formatage du body
    output_format = _extract_output_format(body)

    sections: list[str] = [
        f"## Role",
        "",
        f"You are an AI assistant specialized in: {skill_name}.",
        "",
        "## Objective",
        "",
        skill_description,
        "",
        "## Rules & Instructions",
        "",
        body,
    ]

    if auxiliary_files:
        sections.append("")
        sections.append("## Reference Code")
        sections.append("")
        for rel_path, content in auxiliary_files:
            lang = detect_language(rel_path)
            sections.append(f"### {rel_path}")
            sections.append("")
            sections.append(f"```{lang}")
            sections.append(content)
            sections.append("```")
            sections.append("")

    sections.append("")
    sections.append("## Output Format")
    sections.append("")
    if output_format:
        sections.append(output_format)
    else:
        sections.append(
            "Follow the formatting guidelines described in the instructions "
            "above. Use structured markdown when appropriate."
        )

    # Garantir l'extension .txt
    if output_path.suffix != ".txt":
        output_path = output_path.with_suffix(".txt")

    _ensure_parent(output_path)
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def _extract_output_format(body: str) -> str:
    """Tente d'extraire une section « Output Format » du corps Markdown.

    Recherche un titre de niveau 2 ou 3 contenant « output format »,
    « format de sortie » ou « formatting ». Retourne le contenu de
    cette section, ou une chaîne vide si aucune n'est trouvée.
    """
    pattern = re.compile(
        r"^#{2,3}\s+(?:output\s+format|format\s+de\s+sortie|formatting)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(body)
    if not match:
        return ""

    start = match.end()
    # Trouver la prochaine section de même niveau ou supérieur
    next_section = re.search(r"^#{1,3}\s+", body[start:], re.MULTILINE)
    if next_section:
        return body[start : start + next_section.start()].strip()
    return body[start:].strip()


# ---------------------------------------------------------------------------
# Point d'entrée CLI (optionnel)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Exporte une skill Antigravity dans un format cible.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python packager.py ./ma-skill \"Ma Skill\" \"Description\" "
            "markdown ./output/ma-skill.md\n"
            "  python packager.py ./ma-skill \"Ma Skill\" \"Description\" "
            "cursor ./output/ma-skill.mdc\n"
        ),
    )
    parser.add_argument(
        "skill_path",
        type=Path,
        help="Chemin vers le répertoire racine de la skill.",
    )
    parser.add_argument(
        "skill_name",
        help="Nom de la skill.",
    )
    parser.add_argument(
        "skill_description",
        help="Description courte de la skill.",
    )
    parser.add_argument(
        "target",
        choices=SUPPORTED_TARGETS,
        help="Format cible.",
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help="Chemin du fichier ou répertoire de sortie.",
    )

    args = parser.parse_args()

    try:
        result = package_skill(
            skill_path=args.skill_path.resolve(),
            skill_name=args.skill_name,
            skill_description=args.skill_description,
            target=args.target,
            output_path=args.output_path.resolve(),
        )
        print(f"✓ Export réussi : {result}")
    except (ValueError, FileNotFoundError) as exc:
        print(f"✗ Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
