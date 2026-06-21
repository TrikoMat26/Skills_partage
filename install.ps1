# Script d'installation du skill-sharer pour Antigravity
# Crée un lien symbolique dans le répertoire de configuration globale

$ErrorActionPreference = "Stop"

$SkillSource = Join-Path $PSScriptRoot "skills\skill-sharer"
$SkillTarget = Join-Path $env:USERPROFILE ".gemini\config\skills\skill-sharer"

# Vérifier que le dossier source existe
if (-not (Test-Path $SkillSource)) {
    Write-Error "[ERREUR] Dossier source introuvable : $SkillSource"
    exit 1
}

# Vérifier si le lien/dossier existe déjà
if (Test-Path $SkillTarget) {
    $item = Get-Item $SkillTarget -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Write-Host "[INFO] Lien symbolique existant détecté. Suppression..." -ForegroundColor Yellow
        Remove-Item $SkillTarget -Force
    } else {
        Write-Error "[ERREUR] Un dossier (non-symlink) existe déjà à : $SkillTarget`nSupprimez-le manuellement avant de relancer l'installation."
        exit 1
    }
}

# Créer le répertoire parent si nécessaire
$ParentDir = Split-Path $SkillTarget -Parent
if (-not (Test-Path $ParentDir)) {
    New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
}

# Créer le lien symbolique (nécessite des droits administrateur ou le mode développeur activé)
try {
    New-Item -ItemType SymbolicLink -Path $SkillTarget -Target $SkillSource | Out-Null
    Write-Host "[OK] Skill 'skill-sharer' installé avec succès !" -ForegroundColor Green
    Write-Host "   Source  : $SkillSource" -ForegroundColor Gray
    Write-Host "   Cible   : $SkillTarget" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Le skill sera automatiquement détecté par Antigravity au prochain démarrage." -ForegroundColor Cyan
} catch {
    Write-Host "[ERREUR] Erreur lors de la création du lien symbolique." -ForegroundColor Red
    Write-Host "   Assurez-vous que le mode développeur est activé dans Windows," -ForegroundColor Yellow
    Write-Host "   ou exécutez ce script en tant qu'administrateur." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Alternative : copie manuelle" -ForegroundColor Yellow
    Write-Host "   Copy-Item -Recurse '$SkillSource' '$SkillTarget'" -ForegroundColor Gray
    exit 1
}
