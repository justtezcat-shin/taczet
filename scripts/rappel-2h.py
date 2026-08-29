#!/usr/bin/env python3
"""Rappel des rendez-vous qui commencent dans moins de deux heures.

Concu pour `hermes cron create ... --no-agent --script rappel-2h.py`.
Le contrat de ce mode : **une sortie vide vaut silence** — aucune livraison,
execution comptee comme reussie (cron/scheduler.py:3270). C'est ce qui permet
de sonder tous les quarts d'heure sans envoyer vingt-quatre messages par jour.

AUCUN appel de modele. Le script lit l'agenda, compare des heures, et ecrit
une ligne ou rien. La livraison des taches planifiees ne traverse pas le
filtre de silence d'Hermes : une reponse « rien a signaler » produite par le
modele serait, elle, bel et bien envoyee.

**Anti-doublon.** Sonder tous les quarts d'heure signifie qu'un rendez-vous
reste « dans moins de deux heures » pendant huit executions consecutives.
Les identifiants deja annonces sont donc memorises dans un petit fichier
d'etat, purge des entrees passees. Sans lui, huit rappels par rendez-vous.

Le fichier d'etat vit dans `cache/`, PAS dans `scripts/` : ce dernier
appartient au noyau, et rien qui s'ecrit au fil de l'eau n'a sa place dans
un dossier cense ne jamais bouger.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# La console Windows est en cp1252 : sans ceci, un rendez-vous dont le titre
# porte un accent ou un emoji ferait echouer le script au lieu de prevenir.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
PYTHON = HERMES / "hermes-agent" / "venv" / "Scripts" / "python.exe"
GOOGLE = (HERMES / "skills" / "productivity" / "google-workspace"
          / "scripts" / "google_api.py")
ETAT = HERMES / "cache" / "rappel-2h.json"

FENETRE = timedelta(hours=2)


def agenda(depuis: datetime, jusqu_a: datetime) -> list:
    """Evenements de la periode. Liste vide si quoi que ce soit echoue."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(
            [str(PYTHON), "-X", "utf8", str(GOOGLE), "calendar", "list",
             "--start", depuis.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "--end", jusqu_a.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "--max", "25"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120, input="", env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        donnees = json.loads(proc.stdout)
    except Exception:
        # Panne reseau, jeton expire, sortie illisible : on se tait. Un script
        # de rappel qui crie sa propre panne tous les quarts d'heure est pire
        # que le silence — et le journal du cron garde la trace de l'echec.
        return []
    return donnees if isinstance(donnees, list) else donnees.get("items", [])


def debut(evenement: dict):
    """Heure de debut, ou None si l'evenement dure toute la journee."""
    brut = evenement.get("start")
    if isinstance(brut, dict):
        brut = brut.get("dateTime") or brut.get("date")
    if not brut or len(str(brut)) <= 10:
        return None  # '2026-08-28' = journee entiere, pas de rappel a 2 h
    try:
        return datetime.fromisoformat(str(brut).replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> None:
    maintenant = datetime.now(timezone.utc)

    try:
        deja = json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        deja = {}

    annonces = []
    for ev in agenda(maintenant, maintenant + FENETRE):
        heure = debut(ev)
        if heure is None:
            continue
        restant = heure - maintenant
        if not (timedelta(0) < restant <= FENETRE):
            continue
        cle = str(ev.get("id") or ev.get("iCalUID") or f"{heure}-{ev.get('summary')}")
        if cle in deja:
            continue
        deja[cle] = heure.isoformat()
        minutes = int(restant.total_seconds() // 60)
        titre = str(ev.get("summary") or "sans titre").strip()
        lieu = str(ev.get("location") or "").strip()
        ligne = "%s a %s (dans %d min)" % (
            titre, heure.astimezone().strftime("%H:%M"), minutes)
        annonces.append(ligne + (" - " + lieu if lieu else ""))

    # Purger les evenements passes : le fichier d'etat ne doit pas grossir
    # indefiniment, et un identifiant reutilise plus tard doit pouvoir resonner.
    limite = (maintenant - timedelta(days=2)).isoformat()
    deja = {k: v for k, v in deja.items() if v > limite}
    try:
        ETAT.parent.mkdir(parents=True, exist_ok=True)
        ETAT.write_text(json.dumps(deja), encoding="utf-8")
    except Exception:
        # Si l'etat ne peut pas s'ecrire, le rappel se repetera au prochain
        # tour. Genant, jamais dangereux : on prefere doubler que perdre.
        pass

    if annonces:
        print("Dans moins de 2 h :")
        for ligne in annonces:
            print("  - " + ligne)


if __name__ == "__main__":
    main()
