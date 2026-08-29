# taczet-control.ps1 - ouvre / ferme la fenetre de controle machine de TACZET.
#
# A LANCER DEPUIS LE TERMINAL UNIQUEMENT, jamais depuis Discord.
# C'est le principe : le canal qui autorise ne doit pas etre le canal qui demande.
#
#   .\taczet-control.ps1 open 15    -> autorise TACZET pendant 15 minutes
#   .\taczet-control.ps1 open 1440  -> une journee entiere (maximum)
#   .\taczet-control.ps1 close      -> referme immediatement
#   .\taczet-control.ps1 status     -> etat de la fenetre
#
# La fenetre se referme AUSSI d elle-meme apres 60 minutes sans action de
# TACZET l ayant reellement utilisee : elle dure la journee de travail,
# pas la nuit.
#
# NB: fichier volontairement en ASCII pur. Windows PowerShell lit les .ps1
# en ANSI par defaut ; un caractere accentue ou un tiret cadratin casse le
# parsing du script entier.

param(
    [Parameter(Position = 0)][string]$Action = "status",
    [Parameter(Position = 1)][int]$Minutes = 15
)

$SessionPath = Join-Path $env:LOCALAPPDATA "hermes\hooks\taczet-control-session.json"
$AuditPath   = Join-Path $env:LOCALAPPDATA "hermes\hooks\taczet-control-audit.log"

function Get-Remaining {
    if (-not (Test-Path $SessionPath)) { return 0 }
    try {
        $data = Get-Content $SessionPath -Raw | ConvertFrom-Json
        # NE PAS utiliser (Get-Date -UFormat %s) : sur Windows PowerShell il
        # rend l heure LOCALE comme si elle etait UTC. A UTC-4, chaque fenetre
        # naissait expiree depuis 4 heures. Bug reel du 22/08.
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $left = [int]$data.expires - $now
        if ($left -le 0) { return 0 }

        # Fermeture par inactivite, ajoutee le 2026-08-26. SANS CE BLOC,
        # 'status' annoncait "OUVERTE, 21 h restantes" alors que le verrou
        # refusait deja tout : Isaac aurait cherche la panne ailleurs.
        # Constate en production le jour meme.
        #
        # La regle doit rester identique a celle du verrou
        # (taczet-control-gate.py, IDLE_TIMEOUT_SECONDS = 3600). La source de
        # verite est le Python ; ce bloc n'est qu'un miroir pour l'affichage.
        $idle = 3600
        $ouverture = [int]$data.expires - ([int]$data.minutes * 60)
        $activite = $ouverture
        $fichierActivite = Join-Path $env:LOCALAPPDATA "hermes\hooks\taczet-control-activity"
        if (Test-Path $fichierActivite) {
            try {
                $lu = [double](Get-Content $fichierActivite -Raw).Trim()
                if ($lu -gt $activite) { $activite = [int]$lu }
            } catch { }
        }
        if (($now - $activite) -gt $idle) { return 0 }
        return $left
    } catch { return 0 }
}

function Write-Audit([string]$Text) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $AuditPath -Value ($stamp + "`t" + $Text)
}

$verb = $Action.ToLower()

if ($verb -eq "open") {
    # Plafond porte a 1440 min (24 h) le 2026-08-26 : Isaac travaille par
    # journees entieres. La fermeture par inactivite, cote verrou, empeche
    # une fenetre longue de rester ouverte la nuit.
    if ($Minutes -lt 1 -or $Minutes -gt 1440) {
        Write-Host "Duree refusee : choisir entre 1 et 1440 minutes." -ForegroundColor Red
        exit 1
    }
    # Meme raison qu au-dessus : UtcNow explicite, jamais -UFormat %s.
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $payload = @{
        expires   = $now + ($Minutes * 60)
        opened_at = (Get-Date).ToString("s")
        minutes   = $Minutes
    } | ConvertTo-Json -Compress
    New-Item -ItemType Directory -Force (Split-Path $SessionPath) | Out-Null
    Set-Content -Path $SessionPath -Value $payload -Encoding UTF8
    Write-Audit ("WINDOW_OPEN`t" + $Minutes + " min")
    $end = (Get-Date).AddMinutes($Minutes).ToString("HH:mm:ss")
    Write-Host "Fenetre de controle OUVERTE pour $Minutes minutes." -ForegroundColor Green
    Write-Host "TACZET peut utiliser terminal, fichiers, code et controle du bureau."
    Write-Host "Fermeture automatique a $end, ou '.\taczet-control.ps1 close'."
    Write-Host "Elle se referme aussi apres 60 min sans usage." -ForegroundColor DarkGray
}
elseif ($verb -eq "close") {
    if (Test-Path $SessionPath) { Remove-Item $SessionPath -Force }
    Write-Audit "WINDOW_CLOSE`tmanuelle"
    Write-Host "Fenetre de controle FERMEE." -ForegroundColor Yellow
}
else {
    $left = Get-Remaining
    if ($left -gt 0) {
        $m = [int]($left / 60)
        $s = $left % 60
        Write-Host "Fenetre OUVERTE - $m min $s s restantes." -ForegroundColor Green
    } else {
        Write-Host "Fenetre FERMEE - TACZET ne peut ni executer, ni ecrire, ni piloter le bureau." -ForegroundColor Yellow
    }
}
