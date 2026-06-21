---
name: skill-sharer
description: >-
  Partage et synchronisation de skills entre différents environnements d'IA
  (Antigravity, Cursor, Windsurf, GitHub Copilot, Claude Desktop, ChatGPT).
  Utilisez quand l'utilisateur veut lister ses skills, exporter un skill
  vers un autre outil ou PC, mettre à jour un skill partagé, ou vérifier
  la compatibilité des formats des environnements cibles.
---

# Skill Sharer

## Overview

Ce skill permet de **lister, packager, partager, synchroniser et vérifier** la compatibilité des skills entre différents environnements d'IA. Il s'appuie sur un script Python CLI qui scanne les configurations locales, génère des fichiers dans le format attendu par chaque environnement cible, et utilise Git/GitHub comme registre central de synchronisation.

## Dependencies

- Python 3.10+ (standard library uniquement, aucune dépendance externe)
- Git (pour les fonctions de partage et de synchronisation)

## Utility Scripts

Le script principal est accessible via le skill installé dans votre configuration Antigravity.

> **Note** : Les chemins ci-dessous utilisent `%USERPROFILE%` (Windows) ou `~` (macOS/Linux) pour rester portables d'un PC à l'autre.

Les scripts doivent être exécutés depuis n'importe quel répertoire. Le script détecte automatiquement les chemins de configuration.

---

## Commandes Disponibles

### 1. Lister les skills installés

Affiche un inventaire de tous les skills détectés dans l'environnement actuel.

```bash
# Affichage en tableau
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" list

# Affichage en JSON
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" list --format json
```

### 2. Packager un skill pour un autre environnement

Exporte un skill dans le format natif d'un environnement cible.

```bash
# Format Markdown universel (fichier unique contenant tout le skill)
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" package <nom_du_skill> --target markdown

# Format Cursor (.mdc)
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" package <nom_du_skill> --target cursor

# Format Antigravity (copie native de la structure)
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" package <nom_du_skill> --target antigravity --output ./export/

# Formats disponibles : antigravity, markdown, cursor, windsurf, copilot, chatgpt
```

### 3. Partager un skill via GitHub ou en local

```bash
# Partage via le dépôt GitHub (commit + push automatique)
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" share <nom_du_skill> --method repo

# Copie locale vers un répertoire spécifique
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" share <nom_du_skill> --method local --destination "C:\chemin\vers\destination"
```

### 4. Mettre à jour les skills depuis GitHub

```bash
# Mettre à jour tous les skills partagés
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" update --all

# Mettre à jour un skill spécifique
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" update --skill <nom_du_skill>
```

### 5. Vérifier la compatibilité des environnements

Détecte si les formats des environnements cibles ont changé depuis la dernière utilisation.

```bash
# Vérifier tous les environnements
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" check --all

# Vérifier un environnement spécifique
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" check --env cursor

# Mettre à jour les timestamps après vérification manuelle
python "%USERPROFILE%\.gemini\config\skills\skill-sharer\scripts\skill_sharer.py" check --all --update-fingerprints
```

---

## Formats Cibles

| Format | Extension | Environnement | Description |
|---|---|---|---|
| `antigravity` | Dossier | Antigravity / Gemini CLI | Copie fidèle de la structure SKILL.md + sous-dossiers |
| `markdown` | `.md` | Universel | Fichier unique contenant tout le skill avec scripts embarqués |
| `cursor` | `.mdc` | Cursor IDE | Frontmatter description/globs/alwaysApply |
| `windsurf` | `.md` | Windsurf (Codeium) | Markdown avec balises XML |
| `copilot` | `.instructions.md` | GitHub Copilot | Sections Overview/Instructions/Code References |
| `chatgpt` | `.txt` | ChatGPT Custom GPT | Texte structuré Role/Objective/Rules/Examples |

---

## Workflow Typique

1. **Lister** : `list` pour voir les skills disponibles
2. **Choisir** : identifier le skill à partager et le format cible
3. **Packager** : `package` pour générer le fichier dans le bon format
4. **Partager** : `share` pour pousser vers GitHub ou copier localement
5. **Vérifier** : `check` pour s'assurer que les formats sont toujours à jour

## Common Mistakes

1. **Exécution UTF-8** : Sur Windows, si des caractères spéciaux posent problème, exécuter avec `python -X utf8 skill_sharer.py ...`
2. **Droits Git** : Pour le partage via `repo`, assurez-vous que le dépôt local est configuré avec les bons accès (SSH ou token).
3. **Symlink Windows** : Le script `install.ps1` nécessite le mode développeur activé ou un terminal administrateur.
