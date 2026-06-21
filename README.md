# Skill Sharer 🔄

Outil de partage et de synchronisation de skills entre différents environnements d'IA (Antigravity, Cursor, Windsurf, GitHub Copilot, Claude Desktop, ChatGPT).

## Fonctionnalités

| Commande | Description |
|---|---|
| `list` | Inventaire des skills installés localement |
| `package` | Export d'un skill vers un format cible |
| `share` | Partage via copie locale ou GitHub |
| `update` | Synchronisation depuis le registre GitHub |
| `check` | Vérification de compatibilité des environnements |

## Installation

### Automatique (symlink)

```powershell
# Depuis la racine du dépôt
.\install.ps1
```

> **Note** : Nécessite le mode développeur Windows activé ou un terminal administrateur pour créer le lien symbolique.

### Manuelle

```powershell
Copy-Item -Recurse ".\skills\skill-sharer" "$env:USERPROFILE\.gemini\config\skills\skill-sharer"
```

## Utilisation

### Lister les skills

```bash
python skill_sharer.py list
python skill_sharer.py list --format json
```

### Packager un skill

```bash
# Format Markdown universel (un seul fichier contenant tout)
python skill_sharer.py package home-assistant-management --target markdown

# Format Cursor (.mdc)
python skill_sharer.py package home-assistant-management --target cursor

# Format natif Antigravity (copie de la structure)
python skill_sharer.py package home-assistant-management --target antigravity --output ./export/

# Formats disponibles : antigravity, markdown, cursor, windsurf, copilot, chatgpt
```

### Partager un skill

```bash
# Partage via le dépôt GitHub (commit + push)
python skill_sharer.py share home-assistant-management --method repo

# Copie locale vers un autre répertoire
python skill_sharer.py share home-assistant-management --method local --destination "C:\autre\chemin"
```

### Mettre à jour les skills

```bash
# Mettre à jour tous les skills depuis GitHub
python skill_sharer.py update --all

# Mettre à jour un skill spécifique
python skill_sharer.py update --skill home-assistant-management
```

### Vérifier la compatibilité

```bash
# Vérifier tous les environnements
python skill_sharer.py check --all

# Vérifier un environnement spécifique
python skill_sharer.py check --env cursor

# Mettre à jour les timestamps après vérification
python skill_sharer.py check --all --update-fingerprints
```

## Formats Supportés

| Format | Extension | Environnement Cible |
|---|---|---|
| `antigravity` | Dossier structuré | Google Antigravity / Gemini CLI |
| `markdown` | `.md` | Universel (tout LLM) |
| `cursor` | `.mdc` | Cursor IDE |
| `windsurf` | `.md` | Windsurf (Codeium) |
| `copilot` | `.instructions.md` | GitHub Copilot |
| `chatgpt` | `.txt` | ChatGPT Custom GPT |

## Structure du Projet

```
Skills_partage/
├── skills/
│   └── skill-sharer/
│       ├── SKILL.md                # Instructions agent
│       ├── scripts/
│       │   ├── skill_sharer.py     # CLI principal
│       │   ├── scanner.py          # Scan des skills
│       │   ├── packager.py         # Export multi-format
│       │   ├── sync.py             # Synchronisation Git
│       │   └── checker.py          # Vérification compatibilité
│       └── resources/
│           └── env_fingerprints.json
├── shared/                         # Skills packagés (géré par Git)
├── install.ps1                     # Installation automatique
└── README.md                       # Ce fichier
```

## Licence

Usage personnel — Krikor Music
