"""Fenêtres longues : 24 h au plus, refermées après une heure sans usage.

Isaac travaille par journées entières. Rouvrir une fenêtre toutes les quinze
minutes lui coûtait six ouvertures dans une soirée. Le plafond passe donc à
24 h — mais une fenêtre de 24 h qui reste ouverte pendant qu'il dort rendrait
le verrou décoratif : `computer_use` peut cliquer dans un navigateur où ses
comptes sont ouverts, `terminal` fait le reste.

La fermeture par inactivité est ce qui rend les deux compatibles. La fenêtre
se referme après 60 minutes sans action **ayant eu besoin d'elle**. Les
lectures libres — agenda, mails, git — ne la prolongent pas : elles n'en
dépendent pas, et les compter reviendrait à maintenir la porte ouverte parce
que TACZET consulte un calendrier.

Le piège évité ici : la référence d'inactivité est `max(ouverture, dernière
activité)`. Sans ce `max`, une fenêtre neuve serait jugée inactive dès la
première seconde, à cause d'un horodatage laissé la veille.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import Suite, AUTORISE, REFUSE  # noqa: E402

s = Suite("Duree des fenetres et fermeture par inactivite")

s.section("Une fenetre fraiche fonctionne, sans aucun historique d'activite")
s.cas("15 min, jamais utilisee", AUTORISE, "dir", fenetre=True)
s.cas("24 h, jamais utilisee", AUTORISE, "dir", fenetre=True, ouverte_min=1440)

s.section("Une fenetre longue survit tant qu'elle sert")
s.cas("ouverte 8 h, active il y a 1 min", AUTORISE, "dir",
      fenetre=True, ouverte_min=1440, ouverte_depuis=8 * 3600,
      activite_il_y_a=60)
s.cas("ouverte 8 h, active il y a 59 min", AUTORISE, "dir",
      fenetre=True, ouverte_min=1440, ouverte_depuis=8 * 3600,
      activite_il_y_a=59 * 60)

s.section("Elle se referme des que l'usage cesse")
s.cas("inactive depuis 61 min", REFUSE, "dir",
      fenetre=True, ouverte_min=1440, ouverte_depuis=2 * 3600,
      activite_il_y_a=61 * 60)
s.cas("inactive depuis 8 h (la nuit)", REFUSE, "dir",
      fenetre=True, ouverte_min=1440, ouverte_depuis=10 * 3600,
      activite_il_y_a=8 * 3600)
s.cas("write_file, inactive depuis 3 h", REFUSE, outil="write_file",
      fenetre=True, ouverte_min=1440, ouverte_depuis=5 * 3600,
      activite_il_y_a=3 * 3600,
      entree={"path": "C:/Users/<UTILISATEUR>/Documents/x.md", "content": "x"})
s.cas("computer_use clic, inactive depuis 3 h", REFUSE, outil="computer_use",
      fenetre=True, ouverte_min=1440, ouverte_depuis=5 * 3600,
      activite_il_y_a=3 * 3600,
      entree={"action": "left_click", "coordinate": [10, 10]})
# Jamais utilisee, mais ouverte depuis 2 h : c'est l'OUVERTURE qui sert de
# reference, et elle est trop ancienne.
s.cas("jamais utilisee, ouverte depuis 2 h", REFUSE, "dir",
      fenetre=True, ouverte_min=1440, ouverte_depuis=2 * 3600)

s.section("Une fenetre inactive ne bloque pas ce qui est libre")
s.cas("read_file", AUTORISE, outil="read_file",
      fenetre=True, ouverte_min=1440, ouverte_depuis=10 * 3600,
      activite_il_y_a=8 * 3600, entree={"path": "notes.md"})
s.cas("lecture agenda", AUTORISE,
      'python -X utf8 "C:/Users/<UTILISATEUR>/AppData/Local/hermes/skills/productivity/'
      'google-workspace/scripts/google_api.py" calendar list --max 10',
      fenetre=True, ouverte_min=1440, ouverte_depuis=10 * 3600,
      activite_il_y_a=8 * 3600)
s.cas("git status", AUTORISE, "git status",
      fenetre=True, ouverte_min=1440, ouverte_depuis=10 * 3600,
      activite_il_y_a=8 * 3600)

s.section("Les refus inconditionnels le restent, fenetre longue et active")
s.cas("suppression", REFUSE, "rm C:/Users/<UTILISATEUR>/Documents/x.md",
      fenetre=True, ouverte_min=1440, activite_il_y_a=60)
s.cas("CLI hermes", REFUSE, "hermes cron list",
      fenetre=True, ouverte_min=1440, activite_il_y_a=60)
s.cas("noyau", REFUSE, "cat .env",
      fenetre=True, ouverte_min=1440, activite_il_y_a=60)

s.section("Une session forgee ne depasse pas le plafond")
# 30 jours declares : la fenetre reste utilisable, mais window_remaining()
# ne renvoie jamais plus de 24 h.
s.cas("30 jours declares, active", AUTORISE, "dir",
      fenetre=True, ouverte_min=43200, activite_il_y_a=60)
s.cas("30 jours declares, inactive 2 h", REFUSE, "dir",
      fenetre=True, ouverte_min=43200, ouverte_depuis=4 * 3600,
      activite_il_y_a=2 * 3600)

s.section("Session forgee SANS champ minutes")
# L heure d ouverture ne peut plus etre reconstituee. Sans garde, elle
# tomberait dans le futur et la fenetre n expirerait JAMAIS par inactivite.
# La premiere observation fait donc foi, et l horloge part de la.
FORGEE = {"expires": time.time() + 30 * 86400}
s.cas("premiere observation : toleree", AUTORISE, "dir",
      fenetre=True, session_brute=FORGEE)
s.cas("observee il y a 2 h : refusee", REFUSE, "dir",
      fenetre=True, session_brute=FORGEE, activite_il_y_a=2 * 3600)

sys.exit(s.bilan())
