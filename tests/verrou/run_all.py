"""Rejoue toutes les suites du verrou. À lancer après CHAQUE modification.

    python tests/verrou/run_all.py

Code de sortie 0 si tout passe, 1 sinon.

Ces suites testent le fichier réel `hooks/taczet-control-gate.py`, jamais une
copie : c'est la seule façon de savoir ce que TACZET rencontrera. Elles
s'exécutent en revanche dans un `LOCALAPPDATA` isolé, pour ne toucher ni au
journal d'audit ni à la fenêtre de contrôle d'Isaac.
"""

import subprocess
import sys
from pathlib import Path

# La console Windows est en cp1252 : sans ces deux precautions, une suite qui
# affiche un accent fait planter le lanceur (piege n 21, rencontre ici dans
# notre propre outillage le 26/08). `-X utf8` cote enfant pour qu il ecrive
# de l UTF-8 valide, reconfiguration cote parent pour qu il sache l afficher.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ICI = Path(__file__).parent
SUITES = [
    "test_noyau_et_fenetre.py",
    "test_google.py",
    "test_github.py",
    "test_suppression.py",
    "test_gouvernance.py",
    "test_duree_fenetre.py",
    "test_matcher.py",
]

resultats = []
for nom in SUITES:
    proc = subprocess.run([sys.executable, "-X", "utf8", str(ICI / nom)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    print(proc.stdout, end="")
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr, end="")
    resultats.append((nom, proc.returncode))
    print()

print("=" * 72)
echecs = [nom for nom, code in resultats if code != 0]
for nom, code in resultats:
    print("  %-30s %s" % (nom, "OK" if code == 0 else "ECHEC"))
print("=" * 72)

if echecs:
    print("\nLe verrou a REGRESSE sur : " + ", ".join(echecs))
    print("Ne pas redemarrer le gateway avant correction.")
    sys.exit(1)

print("\nLe verrou est intact.")
sys.exit(0)
