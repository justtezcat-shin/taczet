"""Banc d'essai du verrou machine — infrastructure commune.

**Isolation.** Chaque cas s'exécute avec un `LOCALAPPDATA` temporaire. Le hook
y calcule donc sa session ET son journal d'audit, qui restent dans le dossier
jetable. Le journal réel d'Isaac n'est jamais touché.

Ce point n'est pas cosmétique. `hooks/taczet-control-audit.log` est ce qui a
permis de diagnostiquer trois pannes le 2026-08-25 : la lecture Google cassée
depuis son ajout, le `2>&1` qui faisait tomber le garde anti-chaînage, et
TACZET qui renonçait sans essayer. Un journal à moitié rempli de cas de test
aurait rendu ces diagnostics beaucoup plus difficiles — les premières suites
écrivaient dedans, d'où cette réécriture.

**La fenêtre est simulée, jamais ouverte pour de vrai.** Ouvrir une fenêtre de
contrôle est le geste d'autorisation d'Isaac. Un test qui l'ouvrirait sur sa
vraie session lui retirerait sa protection le temps de son exécution.

Usage :

    from harness import Suite, AUTORISE, REFUSE

    s = Suite("Ce que la suite prouve")
    s.section("Fenêtre fermée")
    s.cas("git log", AUTORISE, "git log --oneline -10")
    sys.exit(s.bilan())
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
PYTHON = str(HERMES / "hermes-agent" / "venv" / "Scripts" / "python.exe")

# Par defaut on eprouve le fichier REEL — c'est le seul qui dise ce que TACZET
# rencontrera. `VERROU_HOOK` permet de viser une copie candidate AVANT de
# toucher au noyau : on valide le correctif, puis on l'applique, puis on
# rejoue tout sur le vrai fichier.
HOOK = os.environ.get("VERROU_HOOK") or str(
    HERMES / "hooks" / "taczet-control-gate.py")

# Le contrat du hook (agent/shell_hooks.py) : 0 laisse passer, 2 bloque.
AUTORISE = 0
REFUSE = 2

_VERDICT = {AUTORISE: "AUTORISE", REFUSE: "refuse"}


class Suite:
    """Une série de cas, chacun joué contre le vrai fichier de hook."""

    def __init__(self, titre: str):
        self.titre = titre
        self.echecs = 0
        self.total = 0
        print("=" * 72)
        print(titre)
        print("=" * 72)

    def _env(self, fenetre_ouverte: bool, ouverte_min: float = 15,
             activite_il_y_a: float = None, ouverte_depuis: float = 0,
             session_brute: dict = None) -> dict:
        """Un LOCALAPPDATA neuf par cas — session et journal jetables.

        `ouverte_min` est la duree DECLAREE de la fenetre, `ouverte_depuis` le
        nombre de secondes ecoulees depuis son ouverture, `activite_il_y_a`
        celui depuis le dernier usage. Sans `activite_il_y_a`, aucun fichier
        d'activite n'est ecrit : c'est une fenetre jamais utilisee.

        Les trois sont independants parce que le verrou reconstitue l'heure
        d'ouverture depuis `expires` et `minutes`. Une premiere version ecrivait
        `expires = maintenant + duree`, ce qui datait TOUJOURS l'ouverture de
        l'instant present : l'activite se retrouvait anterieure a l'ouverture,
        un etat impossible, et la fermeture par inactivite ne pouvait jamais
        se declencher.
        """
        tmp = Path(tempfile.mkdtemp(prefix="verrou-test-"))
        hooks = tmp / "hermes" / "hooks"
        hooks.mkdir(parents=True)
        if fenetre_ouverte:
            maintenant = time.time()
            ouverture = maintenant - ouverte_depuis
            session = {"expires": ouverture + ouverte_min * 60,
                       "minutes": ouverte_min}
            if session_brute is not None:
                # Session ecrite telle quelle : sert a jouer les fichiers
                # forges, notamment ceux qui omettent `minutes`.
                session = session_brute
            (hooks / "taczet-control-session.json").write_text(
                json.dumps(session), encoding="utf-8")
            if activite_il_y_a is not None:
                (hooks / "taczet-control-activity").write_text(
                    str(maintenant - activite_il_y_a), encoding="utf-8")
        return dict(os.environ, LOCALAPPDATA=str(tmp))

    def section(self, titre: str) -> None:
        print()
        print("--- " + titre + " " + "-" * max(0, 66 - len(titre)))

    def cas(self, libelle, attendu, commande=None, *,
            outil="terminal", entree=None, fenetre=False,
            ouverte_min=15, activite_il_y_a=None, ouverte_depuis=0,
            session_brute=None) -> None:
        """Joue un cas. `entree` remplace `tool_input` pour les outils non-shell."""
        charge = entree if entree is not None else {"command": commande}
        proc = subprocess.run(
            [PYTHON, HOOK],
            input=json.dumps({"hook_event_name": "pre_tool_call",
                              "tool_name": outil, "tool_input": charge}),
            capture_output=True, text=True,
            env=self._env(fenetre, ouverte_min, activite_il_y_a,
                          ouverte_depuis, session_brute))
        self.total += 1
        obtenu = proc.returncode
        reussi = obtenu == attendu
        if not reussi:
            self.echecs += 1
        etat = "OK  " if reussi else "FAIL"
        vu = _VERDICT.get(obtenu, f"code {obtenu}")
        marque = " [fenetre ouverte]" if fenetre else ""
        print("  [%s] %-46s %s%s" % (etat, libelle[:46], vu, marque))

    def bilan(self) -> int:
        """Affiche le résultat et renvoie le code de sortie du processus."""
        print()
        if self.echecs:
            print("ECHEC : %d cas sur %d" % (self.echecs, self.total))
            return 1
        print("TOUS LES TESTS PASSENT (%d cas)" % self.total)
        return 0
