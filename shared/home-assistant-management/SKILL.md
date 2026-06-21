---
name: home-assistant-management
description: >-
  Facilite les modifications, le développement et la maintenance de Home Assistant (gestion des entités, configurations et dashboards) via l'API REST/WebSocket et le script utilitaire ha_tool.py.
---

# Home Assistant Management

## Overview
Ce skill est conçu pour simplifier et sécuriser l'administration, le développement et la maintenance de votre serveur Home Assistant. Il s'appuie sur le script Python CLI `ha_tool.py` qui communique avec l'API REST et l'API WebSocket de Home Assistant pour récupérer ou téléverser à chaud les configurations.

## Dependencies
- Le package python `websocket-client` (déjà installé localement sur la machine hôte).
- Un fichier `.env` contenant les identifiants d'accès dans le workspace de travail.

## Quick Start
Assurez-vous que le fichier `.env` à la racine de votre projet contient vos accès :
```ini
HOMEASSISTANT_URL_LOCAL=http://192.168.1.79:8123
HOMEASSISTANT_URL_EXTERNAL=https://triko26.duckdns.org
HOMEASSISTANT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Utility Scripts
Le script de gestion est situé à l'emplacement suivant :
`C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py`

### 1. Interroger l'état complet d'une entité
Affiche le JSON complet représentant l'état et tous les attributs d'une entité.
```bash
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" get-state sensor.ab2000_06618_max_temp
```

### 2. Lister les entités
Liste toutes les entités. Utile pour la recherche de capteurs ou de boutons.
```bash
# Lister toutes les entités du domaine sensor
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" list-entities --domain sensor
```

### 3. Télécharger la configuration d'un dashboard
Télécharge proprement la structure JSON d'un dashboard via l'API WebSocket (plus propre et sécurisé qu'un transfert SSH brut).
```bash
# Télécharger le dashboard principal (Aperçu)
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" download-dashboard lovelace --output lovelace.json

# Télécharger le dashboard mobile
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" download-dashboard lovelace.dashboard_mobile --output dashboard_mobile.json
```

### 4. Téléverser la configuration d'un dashboard (Mise à jour à chaud)
Téléverse la structure JSON locale d'un dashboard vers Home Assistant via la WebSocket. Cette action met immédiatement à jour la RAM du serveur, écrit la configuration sur le disque dur et force le rafraîchissement en temps réel à l'écran de tous les utilisateurs (pas de redémarrage requis).
```bash
# Mettre à jour le dashboard principal (Aperçu)
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" upload-dashboard lovelace --input lovelace.json
```

### 5. Vérifier la configuration YAML
Lance une analyse de conformité syntaxique de la configuration de Home Assistant (équivalent à la vérification de configuration dans les outils de développement HA).
```bash
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" check-config
```

### 6. Lister les dashboards enregistrés
Affiche la liste de tous les dashboards disponibles sur le serveur (avec leur ID, URL Path, titre, etc.).
```bash
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" list-dashboards
```

### 7. Redémarrer Home Assistant Core
```bash
python "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" restart-core
```

### 8. Appeler un service Home Assistant
Permet d'appeler n'importe quel service disponible sur Home Assistant en passant des paramètres JSON.
```bash
# Exemple : Créer une notification persistante
python -X utf8 "C:\Users\kriko\.gemini\config\skills\home-assistant-management\scripts\ha_tool.py" call-service persistent_notification.create --% --data {\"title\":\"Test\",\"message\":\"Hello\"}
```

## Common Mistakes
1. **Écriture directe dans `.storage/lovelace.lovelace`** : N'écrasez jamais directement ce fichier via SSH/Samba pendant que Home Assistant tourne. Le serveur écrasera vos modifications avec la version qu'il garde en RAM. Utilisez toujours `ha_tool.py upload-dashboard` pour appliquer à chaud.
2. **Chemins d'accès et exécution** : Si l'agent travaille dans un sous-dossier, le script `ha_tool.py` remontera automatiquement l'arborescence pour localiser le fichier `.env` contenant le token.
3. **Erreur d'encodage sur Windows (CP1252/Unicode)** : Lors de la récupération d'entités contenant des accents ou caractères spéciaux, la console Windows peut planter avec `UnicodeEncodeError`. Résoudre en exécutant python avec l'option UTF-8 forcée : `python -X utf8 ha_tool.py list-entities`.
