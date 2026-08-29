#!/usr/bin/env python3
"""Garde du gateway : le relance s'il est mort, et le dit.

**Pourquoi un garde EXTERIEUR.** Le planificateur de taches tourne DANS le
gateway. S'il meurt, aucune tache planifiee ne peut le constater — le point du
matin de 7 h n'arriverait simplement jamais, et rien ne le signalerait. Le
silence d'un assistant est indistinguable de « rien a dire ». Il faut donc un
observateur qui ne partage pas son sort : une tache Windows.

**Pourquoi il previent avant de reparer.** `hermes send` joint Discord par le
jeton du bot, sans gateway en marche. Isaac apprend donc l'incident meme si la
relance echoue — c'est le cas qui compte, celui ou personne ne saurait.

**La pause.** Sans elle, ce garde deferait chaque arret volontaire : Isaac
arrete le gateway pour que Cowork edite le noyau, et quinze minutes plus tard
il repart tout seul. Un fichier de pause suspend donc la surveillance — mais
il EXPIRE de lui-meme au bout de deux heures, pour qu'une pause oubliee ne
desarme pas la protection indefiniment. C'est la meme philosophie que la
fenetre de controle : une autorisation bornee dans le temps.

    pause   : python surveille-gateway.py pause
    reprise : python surveille-gateway.py reprise
    etat    : python surveille-gateway.py etat
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
CLI = HERMES / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
PAUSE = HERMES / "cache" / "surveillance-pause"
JOURNAL = HERMES / "logs" / "surveillance-gateway.log"

DISCORD = "discord:<ID-CONVERSATION-PRIVEE>"
PAUSE_MAX = 2 * 3600      # une pause oubliee ne desarme pas pour toujours
ATTENTE_RELANCE = 25      # secondes laissees au gateway pour remonter

# Sans ceci, CHAQUE sous-processus ouvre sa propre console : Isaac voyait un
# terminal clignoter toutes les quinze minutes. Lancer le script avec
# pythonw.exe ne suffit pas — c'est `hermes` qui ouvre la fenetre, pas nous.
# Les deux corrections sont necessaires, et la seconde est la moins evidente.
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def trace(texte: str) -> None:
    """Best-effort : le garde ne doit jamais echouer sur son propre journal."""
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as fh:
            fh.write("%s\t%s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), texte))
    except Exception:
        pass


def gateway_vivant() -> bool:
    """Vrai si le gateway tourne. Le code de sortie ne distingue pas les cas
    (0 dans les deux), on lit donc la sortie."""
    try:
        p = subprocess.run([str(CLI), "gateway", "status"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=60, creationflags=SANS_FENETRE)
        return "process running" in (p.stdout or "").lower()
    except Exception:
        return False  # injoignable = traite comme mort, on preferera relancer


def prevenir(texte: str) -> None:
    """`hermes send` joint Discord par le jeton du bot, gateway ou pas."""
    try:
        subprocess.run([str(CLI), "send", "--to", DISCORD, texte],
                       capture_output=True, text=True, timeout=90,
                       creationflags=SANS_FENETRE)
    except Exception:
        trace("ECHEC de la notification : " + texte)


def pause_active() -> bool:
    if not PAUSE.is_file():
        return False
    age = time.time() - PAUSE.stat().st_mtime
    if age > PAUSE_MAX:
        trace("pause expiree apres %d min — surveillance reprise" % (age // 60))
        try:
            PAUSE.unlink()
        except Exception:
            pass
        return False
    return True


def main() -> None:
    verbe = (sys.argv[1] if len(sys.argv) > 1 else "verifier").lower()

    if verbe == "pause":
        PAUSE.parent.mkdir(parents=True, exist_ok=True)
        PAUSE.write_text(datetime.now().isoformat(), encoding="utf-8")
        trace("pause demandee")
        print("Surveillance en PAUSE. Expire d'elle-meme dans 2 h.")
        return

    if verbe == "reprise":
        if PAUSE.is_file():
            PAUSE.unlink()
        trace("reprise demandee")
        print("Surveillance REPRISE.")
        return

    if verbe == "etat":
        print("gateway   :", "vivant" if gateway_vivant() else "ARRETE")
        if PAUSE.is_file():
            reste = PAUSE_MAX - (time.time() - PAUSE.stat().st_mtime)
            print("surveillance : EN PAUSE (%d min restantes)" % max(0, reste // 60))
        else:
            print("surveillance : active")
        return

    # --- Verification ordinaire ---
    if pause_active():
        return                      # silence : arret volontaire en cours
    if gateway_vivant():
        return                      # silence : rien a signaler

    trace("gateway ARRETE — relance")
    prevenir("TACZET : le gateway s'etait arrete. Je le relance.")
    try:
        subprocess.run([str(CLI), "gateway", "restart"], capture_output=True,
                       text=True, timeout=180, creationflags=SANS_FENETRE)
    except Exception as e:
        trace("la relance a leve : %s" % e)

    time.sleep(ATTENTE_RELANCE)
    if gateway_vivant():
        trace("relance REUSSIE")
        prevenir("TACZET : gateway relance, tout est reparti.")
    else:
        trace("relance ECHOUEE")
        prevenir("TACZET : le gateway s'est arrete et la relance a ECHOUE. "
                 "Les taches planifiees ne partiront pas — intervention requise.")


if __name__ == "__main__":
    main()
