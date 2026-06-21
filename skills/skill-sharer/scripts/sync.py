"""Synchronisation Git pour le partage de skills.

Ce module fournit les fonctions nécessaires pour publier, mettre à jour
et synchroniser des skills entre un dépôt GitHub partagé et les
répertoires de configuration locaux.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

# Nom du fichier de métadonnées stocké à la racine de chaque skill partagé
_META_FILENAME = ".skill-sharer-meta.json"


# ---------------------------------------------------------------------------
# Utilitaire Git
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Exécute une commande git dans le répertoire *cwd*.

    Args:
        args: Arguments à passer à ``git`` (ex. ``["status", "--porcelain"]``).
        cwd: Répertoire de travail pour la commande.

    Returns:
        Le résultat de ``subprocess.run``.

    Raises:
        RuntimeError: Si la commande git échoue (code de retour non nul).
    """
    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Git n'est pas installé ou introuvable dans le PATH."
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"Échec de la commande git : {' '.join(cmd)}\n"
            f"Code de retour : {result.returncode}\n"
            f"Stderr : {stderr}"
        )
    return result


# ---------------------------------------------------------------------------
# Calcul de checksum
# ---------------------------------------------------------------------------

def _compute_checksum(path: Path) -> str:
    """Calcule un checksum SHA-256 pour un fichier ou un répertoire.

    Pour un répertoire, le hash est calculé sur l'ensemble des fichiers
    (triés par chemin relatif) en excluant le fichier de métadonnées.

    Args:
        path: Chemin du fichier ou répertoire à hasher.

    Returns:
        Chaîne hexadécimale du hash SHA-256.
    """
    hasher = hashlib.sha256()

    if path.is_file():
        hasher.update(path.read_bytes())
    else:
        # Parcours déterministe des fichiers du répertoire
        for file_path in sorted(path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == _META_FILENAME:
                continue
            # Inclure le chemin relatif pour différencier les arborescences
            rel = file_path.relative_to(path).as_posix()
            hasher.update(rel.encode("utf-8"))
            hasher.update(file_path.read_bytes())

    return hasher.hexdigest()


def _read_meta(skill_dir: Path) -> dict[str, str]:
    """Lit le fichier de métadonnées d'un skill partagé.

    Args:
        skill_dir: Répertoire du skill partagé.

    Returns:
        Dictionnaire des métadonnées (peut être vide si le fichier est absent).
    """
    meta_file = skill_dir / _META_FILENAME
    if meta_file.exists():
        return json.loads(meta_file.read_text(encoding="utf-8"))
    return {}


def _write_meta(skill_dir: Path, checksum: str) -> None:
    """Écrit le fichier de métadonnées avec le checksum actuel.

    Args:
        skill_dir: Répertoire du skill partagé.
        checksum: Hash SHA-256 du contenu courant.
    """
    meta_file = skill_dir / _META_FILENAME
    data = {"checksum": checksum}
    meta_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------

def share_to_repo(
    skill_name: str,
    packaged_path: Path,
    repo_root: Path,
) -> None:
    """Publie un skill packagé dans le dépôt partagé puis pousse les modifications.

    Le skill est copié dans ``<repo_root>/shared/<skill_name>/``, un fichier
    de métadonnées est généré, puis les changements sont commités et poussés.

    Args:
        skill_name: Nom du skill à publier.
        packaged_path: Chemin du skill packagé (fichier ou répertoire).
        repo_root: Racine du dépôt Git partagé.

    Raises:
        FileNotFoundError: Si *packaged_path* n'existe pas.
        RuntimeError: Si une commande git échoue.
    """
    if not packaged_path.exists():
        raise FileNotFoundError(
            f"Le chemin packagé est introuvable : {packaged_path}"
        )

    dest = repo_root / "shared" / skill_name
    # Nettoyer la destination avant la copie
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if packaged_path.is_dir():
        shutil.copytree(packaged_path, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(packaged_path, dest / packaged_path.name)

    # Écrire les métadonnées de checksum
    checksum = _compute_checksum(dest)
    _write_meta(dest, checksum)

    # Commiter et pousser
    relative_shared = f"shared/{skill_name}/"
    _run_git(["add", relative_shared], cwd=repo_root)
    _run_git(
        ["commit", "-m", f"[skill-sharer] Update {skill_name}"],
        cwd=repo_root,
    )
    _run_git(["push"], cwd=repo_root)


def share_to_local(packaged_path: Path, destination: Path) -> None:
    """Copie un skill packagé vers un chemin de destination local.

    Args:
        packaged_path: Chemin du skill packagé (fichier ou répertoire).
        destination: Chemin de destination.

    Raises:
        FileNotFoundError: Si *packaged_path* n'existe pas.
    """
    if not packaged_path.exists():
        raise FileNotFoundError(
            f"Le chemin packagé est introuvable : {packaged_path}"
        )

    if packaged_path.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(packaged_path, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packaged_path, destination)


def update_from_repo(
    skill_name: str | None,
    repo_root: Path,
    config_skills_dir: Path,
) -> list[str]:
    """Met à jour les skills locaux depuis le dépôt partagé.

    Effectue un ``git pull`` puis compare les checksums pour ne copier
    que les skills dont le contenu a changé.

    Args:
        skill_name: Nom d'un skill spécifique à mettre à jour, ou ``None``
            pour mettre à jour tous les skills présents dans ``shared/``.
        repo_root: Racine du dépôt Git partagé.
        config_skills_dir: Répertoire local où sont installés les skills.

    Returns:
        Liste des noms de skills effectivement mis à jour.

    Raises:
        RuntimeError: Si une commande git échoue.
        FileNotFoundError: Si le skill demandé n'existe pas dans le dépôt.
    """
    _run_git(["pull"], cwd=repo_root)

    shared_dir = repo_root / "shared"
    if not shared_dir.is_dir():
        return []

    # Déterminer les skills à traiter
    if skill_name is not None:
        skill_src = shared_dir / skill_name
        if not skill_src.is_dir():
            raise FileNotFoundError(
                f"Le skill « {skill_name} » est introuvable dans "
                f"{shared_dir}"
            )
        skills_to_check = [skill_name]
    else:
        skills_to_check = [
            entry.name
            for entry in sorted(shared_dir.iterdir())
            if entry.is_dir()
        ]

    updated: list[str] = []

    for name in skills_to_check:
        src = shared_dir / name
        dst = config_skills_dir / name

        # Lire le checksum du skill partagé
        shared_meta = _read_meta(src)
        shared_checksum = shared_meta.get("checksum", "")

        # Recalculer si le fichier de métadonnées est absent
        if not shared_checksum:
            shared_checksum = _compute_checksum(src)

        # Comparer avec la version locale
        if dst.is_dir():
            local_checksum = _compute_checksum(dst)
            if local_checksum == shared_checksum:
                continue  # Déjà à jour

        # Copier la nouvelle version
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

        # Supprimer le fichier de métadonnées de la copie locale
        # (il n'est utile que dans le dépôt partagé)
        local_meta = dst / _META_FILENAME
        if local_meta.exists():
            local_meta.unlink()

        updated.append(name)

    return updated


def get_repo_root() -> Path | None:
    """Détecte la racine du dépôt Git contenant le répertoire courant.

    Returns:
        Le chemin de la racine du dépôt, ou ``None`` si le répertoire
        courant ne fait pas partie d'un dépôt Git.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0:
        return None

    return Path(result.stdout.strip())


def ensure_git_clean(repo_root: Path) -> bool:
    """Vérifie que l'arbre de travail Git est propre (aucune modification en cours).

    Args:
        repo_root: Racine du dépôt Git à vérifier.

    Returns:
        ``True`` si l'arbre de travail est propre, ``False`` sinon.

    Raises:
        RuntimeError: Si la commande git échoue.
    """
    result = _run_git(["status", "--porcelain"], cwd=repo_root)
    return result.stdout.strip() == ""
