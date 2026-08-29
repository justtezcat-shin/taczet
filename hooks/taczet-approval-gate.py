#!/usr/bin/env python3
"""Verrou d'approbation TACZET — BLUEPRINT Section 4.

Hook `pre_tool_call` (shell hook Hermes). Contrat verifie dans
agent/shell_hooks.py :
  - stdin  : JSON {hook_event_name, tool_name, tool_input, session_id, cwd, extra}
  - stdout : {"decision": "block", "reason": "..."} pour refuser
  - exit 2 : bloque l'appel meme sans JSON sur stdout
  - `pre_tool_call` est le SEUL evenement ou le blocage est honore
    (_BLOCKING_EVENTS, shell_hooks.py:173)

Principe : deny-by-default sur les actions irreversibles. TACZET ne peut pas
s'auto-autoriser : le feu vert prend la forme d'un jeton a usage unique
qu'Isaac depose depuis le TERMINAL, jamais depuis Discord. C'est la reponse
a la note d'honnetete du blueprint (les invites d'approbation s'affichent
mal sur Discord).

Ce script est volontairement court et sans dependance : declare avec
`fail_closed: true`, tout plantage ici bloque TOUS les appels d'outils.
"""

import json
import os
import sys
import time
from pathlib import Path

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
HOOK_DIR = HERMES_HOME / "hooks"
TOKEN_PATH = HOOK_DIR / "taczet-approval-token.json"
AUDIT_PATH = HOOK_DIR / "taczet-approval-audit.log"

# Table des actions sous verrou. Extensible : c'est ici qu'on ajoutera
# `terminal`, `write_file`, etc. si Isaac veut le verrou generalise
# (Roadmap point 1). Laisse volontairement au perimetre Discord de la §4.
GUARDED = {
    "discord_admin": {"delete_message", "add_role", "remove_role"},
}


def audit(verdict: str, tool: str, action: str, detail: str = "") -> None:
    """Trace best-effort. Ne doit JAMAIS faire echouer le hook."""
    try:
        HOOK_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}\t{verdict}\t{tool}\t{action}\t{detail}\n")
    except Exception:
        pass


def allow() -> None:
    sys.exit(0)


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(2)


def consume_token(tool: str, action: str) -> bool:
    """Vrai si un jeton valide autorise CE couple (tool, action).

    Le jeton est consomme (fichier supprime) des qu'il est reconnu, valide
    ou non : une autorisation = une action, conformement a SOUL.md.
    """
    if not TOKEN_PATH.is_file():
        return False
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        try:
            TOKEN_PATH.unlink()
        except Exception:
            pass
        return False

    try:
        TOKEN_PATH.unlink()
    except Exception:
        pass

    if data.get("tool") != tool or data.get("action") != action:
        audit("TOKEN_MISMATCH", tool, action,
              f"jeton pour {data.get('tool')}/{data.get('action')}")
        return False
    try:
        if float(data.get("expires", 0)) < time.time():
            audit("TOKEN_EXPIRED", tool, action)
            return False
    except Exception:
        return False
    return True


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        # Rien a inspecter : ne pas bloquer sur du bruit.
        allow()

    payload = json.loads(raw)  # fail_closed => un JSON casse bloque, voulu.

    tool = str(payload.get("tool_name") or "")
    guarded_actions = GUARDED.get(tool)
    if not guarded_actions:
        allow()

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    action = str(tool_input.get("action") or "")

    if action not in guarded_actions:
        allow()

    if consume_token(tool, action):
        audit("ALLOW", tool, action, "jeton consomme")
        allow()

    audit("BLOCK", tool, action, json.dumps(tool_input, ensure_ascii=False)[:300])
    block(
        f"Action irreversible '{action}' sur '{tool}' refusee par le verrou "
        "TACZET. Isaac doit deposer un jeton d'approbation depuis le TERMINAL "
        "(pas depuis Discord). Une autorisation = une action."
    )


if __name__ == "__main__":
    main()
