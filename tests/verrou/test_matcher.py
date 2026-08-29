"""Le matcher : quels outils atteignent seulement le verrou.

Les autres suites éprouvent la LOGIQUE du verrou en l'appelant directement.
Aucune ne vérifiait ce qui la déclenche. Or un outil absent du `matcher` de
`config.yaml` n'atteint jamais le hook : sa logique peut être parfaite, elle
ne s'exécute pas. C'est un angle mort qu'un test du gate ne peut pas voir,
puisque le banc d'essai contourne le matcher par construction.

Découvert le 2026-08-26 en ajoutant `skill_manage` : le cas de test passait
avant même le changement, parce que le harness appelle le hook en lui
imposant le nom de l'outil.

L'invariant qui compte, dernier bloc : **tout outil capable d'écrire, accordé
à une plateforme, doit être couvert.** C'est ce qui attrapera le prochain
outil ajouté à un toolset sans que personne y pense.
"""

import re
import sys
from pathlib import Path

import yaml

HERMES = Path(__file__).resolve().parents[2]
CONFIG = HERMES / "config.yaml"

sys.path.insert(0, str(HERMES / "hermes-agent"))
import toolsets  # noqa: E402

cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
hooks = cfg["hooks"]["pre_tool_call"]

controle = next(h for h in hooks if "taczet-control-gate" in h["command"])
approbation = next(h for h in hooks if "taczet-approval-gate" in h["command"])
motif = re.compile(controle["matcher"])

echecs = 0
total = 0


def cas(libelle, condition):
    global echecs, total
    total += 1
    if not condition:
        echecs += 1
    print("  [%s] %s" % ("OK  " if condition else "FAIL", libelle))


def section(titre):
    print()
    print("--- " + titre + " " + "-" * max(0, 66 - len(titre)))


print("=" * 72)
print("Matcher : les outils qui atteignent effectivement le verrou")
print("=" * 72)

section("Les deux hooks sont armes en fail_closed")
cas("verrou machine : fail_closed", controle.get("fail_closed") is True)
cas("verrou Discord : fail_closed", approbation.get("fail_closed") is True)
cas("verrou Discord couvre discord_admin",
    re.fullmatch(approbation["matcher"], "discord_admin") is not None)

section("Les hooks sont ARMES, pas seulement declares")
# Un hook declare dans config.yaml mais absent de l'allowlist est
# PUREMENT IGNORE : « shell hook ... not allowlisted — skipped »
# (agent/shell_hooks.py). Le gateway tourne sans terminal interactif, donc
# personne n'est la pour approuver a chaud.
#
# Consequence : si cette allowlist etait perdue — reinstallation, corruption,
# changement de chemin — le verrou serait desarme EN SILENCE, et les 154
# autres cas continueraient de passer. Ils eprouvent la logique du verrou ;
# aucun ne verifiait qu'elle est branchee.
ALLOWLIST = HERMES / "shell-hooks-allowlist.json"
cas("l'allowlist existe", ALLOWLIST.is_file())
_approuves = ""
if ALLOWLIST.is_file():
    import json
    _approuves = json.dumps(json.loads(ALLOWLIST.read_text(encoding="utf-8")))
for _nom in ("taczet-control-gate", "taczet-approval-gate"):
    cas("%-22s consenti" % _nom, _nom in _approuves)

# `hooks_auto_accept` est le filet : il permet a un hook non encore consenti
# de s'armer sans terminal. Ce n'est PAS un affaiblissement — c'est ce qui
# evite le desarmement silencieux ci-dessus. Le risque residuel, approuver
# une commande de hook modifiee, est contenu par config.yaml dans le noyau.
cas("hooks_auto_accept arme le filet", cfg.get("hooks_auto_accept") is True)

section("Outils qui DOIVENT atteindre le verrou")
for outil in ("terminal", "process", "write_file", "patch", "execute_code",
              "computer_use", "read_file", "search_files", "skill_manage"):
    cas(outil, motif.fullmatch(outil) is not None)

section("Le matcher est un fullmatch, pas une recherche")
# Sans cette propriete, `terminal_readonly` ou `my_write_file` seraient
# couverts par accident — ou pire, un outil nomme `read` ne le serait pas
# alors qu'on croirait le contraire.
for outil in ("terminalx", "xterminal", "my_write_file", "read", "skill_view"):
    cas("%-16s non couvert (attendu)" % outil, motif.fullmatch(outil) is None)

section("INVARIANT : tout outil accordé qui ECRIT est couvert")
# Liste tenue a la main : Hermes n expose pas de drapeau « cet outil ecrit ».
# A completer si un outil ecrivant apparait dans un toolset.
ECRIVENT = {
    "terminal", "process", "write_file", "patch", "execute_code",
    "computer_use", "skill_manage",
}
for plateforme in ("discord", "whatsapp"):
    accordes = set(toolsets.resolve_multiple_toolsets(
        cfg["platform_toolsets"][plateforme]))
    manquants = sorted(t for t in accordes & ECRIVENT if not motif.fullmatch(t))
    cas("%-9s aucun outil ecrivant hors verrou (%s)"
        % (plateforme, ", ".join(manquants) or "aucun"), not manquants)

print()
if echecs:
    print("ECHEC : %d cas sur %d" % (echecs, total))
    sys.exit(1)
print("TOUS LES TESTS PASSENT (%d cas)" % total)
sys.exit(0)
