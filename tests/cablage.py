#!/usr/bin/env python3
"""Banc de câblage : chaque pièce est-elle encore reliée aux autres ?

    python tests/cablage.py

Les sept suites de `tests/verrou/` éprouvent la **logique** du verrou. Aucune
ne vérifiait qu'elle est **branchée** — et le 2026-08-26 on a découvert que si
`shell-hooks-allowlist.json` disparaissait, les 154 cas continueraient de
passer pendant que le verrou serait éteint en production. La pire forme
d'échec : celle qui se déguise en succès.

Ce banc couvre l'autre moitié. Il ne teste aucune logique — il vérifie que les
fichiers existent, que les jetons sont là, que les tâches sont déclarées, que
les skills portent bien les corrections qu'on y a mises. Autrement dit, il
attrape ce qui se **détache en silence**.

**Aucun appel de modèle, aucun effet de bord.** Tout est en lecture. Les
secrets sont testés par leur PRÉSENCE, jamais affichés.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
PYTHON = HERMES / "hermes-agent" / "venv" / "Scripts" / "python.exe"
CLI = HERMES / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"

echecs, total = 0, 0


def cas(libelle, condition, detail=""):
    global echecs, total
    total += 1
    if not condition:
        echecs += 1
    print("  [%s] %-52s %s" % ("OK  " if condition else "FAIL", libelle[:52], detail))


def section(titre):
    print()
    print("--- " + titre + " " + "-" * max(0, 64 - len(titre)))


def lire(chemin: Path) -> str:
    try:
        return chemin.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


print("=" * 72)
print("Cablage : chaque piece est-elle reliee aux autres ?")
print("=" * 72)

# ---------------------------------------------------------------- config ---
cfg = {}
try:
    import yaml
    cfg = yaml.safe_load(lire(HERMES / "config.yaml")) or {}
except Exception:
    pass

section("Configuration et constitution")
cas("config.yaml lisible et valide", bool(cfg))
commentaires = sum(1 for l in lire(HERMES / "config.yaml").splitlines()
                   if l.strip().startswith("#"))
# Le gateway REECRIT config.yaml sans ses commentaires des qu il enregistre un
# salon d attache (piege n 24). Une chute brutale signale ce sinistre.
cas("commentaires preserves (> 300)", commentaires > 300, "%d lignes" % commentaires)
soul = lire(HERMES / "SOUL.md")
cas("SOUL.md present", len(soul) > 500, "%d caracteres" % len(soul))
for clause in ("initiative", "source d'instructions"):
    cas("SOUL.md porte la clause %r" % clause, clause in soul)

# ---------------------------------------------------------------- memoire ---
section("Memoire")
mem = lire(HERMES / "memories" / "MEMORY.md")
limite = ((cfg.get("memory") or {}).get("memory_char_limit")) or 0
cas("MEMORY.md present", len(mem) > 1000, "%d caracteres" % len(mem))
cas("sous la limite configuree", 0 < len(mem) < limite,
    "%d / %d, marge %d" % (len(mem), limite, limite - len(mem)))
cas("marge confortable (> 500)", limite - len(mem) > 500)
usr = lire(HERMES / "memories" / "USER.md")
limite_u = ((cfg.get("memory") or {}).get("user_char_limit")) or 0
cas("USER.md sous sa limite", 0 < len(usr) < limite_u,
    "%d / %d" % (len(usr), limite_u))

# ----------------------------------------------------------------- skills ---
section("Skills : les corrections y sont-elles encore ?")
# `sync_skills` PRESERVE les copies modifiees, mais une reinstallation
# complete les remplacerait. Ces marqueurs sont la preuve que nos corrections
# du 26/08 tiennent toujours.
verifs = [
    ("google-workspace", HERMES / "skills/productivity/google-workspace/SKILL.md",
     "Ne JAMAIS definir de variable shell"),
    ("obsidian", HERMES / "skills/note-taking/obsidian/SKILL.md",
     "TACZET-Vault"),
]
for nom, chemin, marqueur in verifs:
    contenu = lire(chemin)
    cas("skill %-18s presente" % nom, len(contenu) > 200)
    cas("skill %-18s corrigee" % nom, marqueur in contenu)
cas("skill github presente",
    len(lire(HERMES / "skills/github/github-auth/SKILL.md")) > 200)

# --------------------------------------------------------------- secrets ---
section("Identifiants (presence seulement, jamais la valeur)")
env = lire(HERMES / ".env")
for cle in ("DISCORD_BOT_TOKEN", "OPENROUTER_API_KEY", "GITHUB_TOKEN",
            "WHATSAPP_ALLOWED_USERS", "OBSIDIAN_VAULT_PATH"):
    m = re.search(r"^%s=(.+)$" % cle, env, re.M)
    cas("%-24s defini" % cle, bool(m and m.group(1).strip()))
# A la RACINE de hermes/, pas dans le dossier de la skill — c'est ce que dit
# `google_api.py:42` (TOKEN_PATH = HERMES_HOME / "google_token.json"). Ma
# premiere version supposait le contraire, et ce banc l'a attrapee : il verifie
# aussi la carte qu'on se fait du systeme, pas seulement le systeme.
jeton = HERMES / "google_token.json"
cas("jeton Google present", jeton.is_file())
if jeton.is_file():
    portees = json.loads(lire(jeton)).get("scopes", [])
    ecriture = [p for p in portees
                if not p.endswith(("readonly", ".events.readonly")) and "gmail.send" in p]
    cas("aucune portee d'envoi Gmail accordee", not ecriture, "%d portees" % len(portees))

# --------------------------------------------------------------- scripts ---
section("Scripts planifiables")
for nom in ("rappel-2h.py", "surveille-gateway.py"):
    chemin = HERMES / "scripts" / nom
    cas("%-24s present" % nom, chemin.is_file())
    if chemin.is_file():
        try:
            import ast
            ast.parse(lire(chemin))
            cas("%-24s syntaxe valide" % nom, True)
        except SyntaxError as e:
            cas("%-24s syntaxe valide" % nom, False, str(e)[:40])
cas("lanceur .cmd du garde present",
    (HERMES / "scripts" / "surveille-gateway.cmd").is_file())
cas("lanceur .cmd de la fenetre present",
    (HERMES / "hooks" / "taczet-control.cmd").is_file())

# ----------------------------------------------------------------- taches ---
section("Taches planifiees")
try:
    sortie = subprocess.run([str(CLI), "cron", "list"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            timeout=90).stdout or ""
except Exception:
    sortie = ""
for tache in ("point-du-matin", "rappel-24h-discord",
              "rappel-24h-whatsapp", "rappel-2h"):
    cas("tache %-22s declaree" % tache, tache in sortie)

section("Garde du gateway")
try:
    q = subprocess.run(["schtasks", "/Query", "/TN", "TACZET_Surveillance"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    cas("tache Windows enregistree", q.returncode == 0)
except Exception as e:
    cas("tache Windows enregistree", False, str(e)[:40])

# ------------------------------------------------------------------- docs ---
section("Documentation")
for nom in ("BLUEPRINT-TACZET-V2.md", "BLUEPRINT-TACZET-V3.md"):
    cas("%-24s versionne" % nom, (HERMES / "docs" / nom).is_file())

print()
if echecs:
    print("ECHEC : %d cas sur %d — une piece s'est detachee." % (echecs, total))
    sys.exit(1)
print("TOUT EST RELIE (%d cas)" % total)
sys.exit(0)
