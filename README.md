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

---

## 📖 Exemple Complet : Synchroniser un skill entre deux PC

Cet exemple montre comment partager le skill `home-assistant-management` de votre **PC Source** vers un **PC Cible** via GitHub.

### Sur le PC Source (Celui contenant le skill original)

**1. Exécuter la commande de partage**
Ouvrez un terminal dans ce dépôt et tapez :
```bash
python -X utf8 skills\skill-sharer\scripts\skill_sharer.py share home-assistant-management --method repo
```

**2. Que se passe-t-il sous le capot ?**
- **Scan & Packaging** : L'outil fouille dans votre configuration Antigravity locale (`~/.gemini/config/skills/`), récupère le `SKILL.md` et les scripts associés (`ha_tool.py`).
- **Hash SHA-256** : Il génère une empreinte unique basée sur le contenu exact du skill.
- **Git Push** : Il copie le tout dans le dossier `shared/home-assistant-management/` de votre dépôt local, puis lance automatiquement `git add`, `git commit` et `git push` vers GitHub.

### Sur le PC Cible (Celui qui doit recevoir le skill)

**1. Première installation (si ce n'est pas déjà fait)**
```bash
cd C:\Users\VotreNom\GitHub
git clone https://github.com/TrikoMat26/Skills_partage.git
cd Skills_partage
.\install.ps1
```

**2. Importer ou mettre à jour les skills**
Tapez simplement :
```bash
python -X utf8 skills\skill-sharer\scripts\skill_sharer.py update --all
```

**3. Que se passe-t-il sous le capot ?**
- **Git Pull** : L'outil télécharge les derniers changements depuis GitHub en arrière-plan.
- **Comparaison intelligente** : Il vérifie la configuration globale de ce PC. Grâce aux empreintes SHA-256, il ne copie que les skills modifiés ou manquants.
- **Installation** : Le contenu de `shared/home-assistant-management/` est copié dans `~/.gemini/config/skills/`. Le skill est immédiatement disponible pour Antigravity !

