#!/usr/bin/env python3
"""Verrou de controle machine TACZET — BLUEPRINT v2.

Deux protections distinctes, dans cet ordre :

  1. NOYAU INVIOLABLE — les fichiers qui gouvernent TACZET et les secrets sont
     refuses A TOUT MOMENT, meme fenetre ouverte, meme sur demande d'Isaac.
     Sans cette regle, une fenetre de 15 minutes suffisait a TACZET pour se
     prolonger de mille ans, reecrire son propre verrou, ou vider sa
     constitution. Audit du 2026-08-13 : 8 contournements confirmes.

  2. FENETRE D'AUTORISATION — le reste des actions machine (shell, ecriture,
     pilotage du bureau) n'est permis que pendant une fenetre ouverte par
     Isaac depuis le TERMINAL.

La lecture ordinaire reste libre : seules les lectures visant le noyau sont
refusees. C'est ce qui rend le verrou vivable.

Contrat (agent/shell_hooks.py) : stdin JSON, stdout {"decision":"block",...},
exit 2 = blocage. Declare avec fail_closed: true.
"""

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
HOOK_DIR = HERMES_HOME / "hooks"
SESSION_PATH = HOOK_DIR / "taczet-control-session.json"
AUDIT_PATH = HOOK_DIR / "taczet-control-audit.log"
ACTIVITY_PATH = HOOK_DIR / "taczet-control-activity"

# --- Duree des fenetres -----------------------------------------------------
# Isaac travaille par journees entieres : rouvrir une fenetre toutes les
# quinze minutes lui coutait six ouvertures dans une soiree. Le plafond passe
# donc a 24 h, MAIS une fenetre longue ne doit pas rester ouverte la nuit.
#
# D ou la fermeture par inactivite : la fenetre se referme d elle-meme apres
# IDLE_TIMEOUT sans action ayant EU BESOIN d elle. Les lectures libres
# (agenda, mails, git) ne la prolongent pas — elles n en dependent pas.
#
# La reference est max(ouverture, derniere activite) : sans ce max, une
# fenetre neuve serait jugee inactive des la premiere seconde a cause d un
# horodatage laisse par la veille.
MAX_WINDOW_SECONDS = 86400.0    # 24 h
IDLE_TIMEOUT_SECONDS = 3600.0   # 60 min sans usage -> fermeture


def _last_activity() -> float:
    """Horodatage du dernier usage de la fenetre, 0 si inconnu."""
    try:
        return float(ACTIVITY_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        return 0.0


def _touch_activity() -> None:
    """Best-effort. En cas d echec la fenetre se fermera plus tot, jamais
    plus tard : le mode de defaillance va dans le sens de la fermeture."""
    try:
        HOOK_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVITY_PATH.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


# --- 1. Le noyau inviolable -------------------------------------------------
# Motifs cherches dans les chemins ET dans les commandes shell. En minuscules,
# separateurs normalises. Volontairement larges : mieux vaut refuser une action
# legitime qu'ouvrir une porte sur la gouvernance de TACZET.
PROTECTED = (
    "taczet-control",            # session, script et journal de CE verrou
    "taczet-approval",           # le verrou Discord et son jeton
    "hermes/hooks",              # tout le dossier des hooks
    "config.yaml",               # ou vivent les declarations de hooks
    "soul.md",                   # la constitution
    ".env",                      # cles API, tokens
    "shell-hooks-allowlist",     # le consentement qui arme les hooks
    "hermes/scripts",            # les scripts que le planificateur execute
)

# --- 1bis. Les commandes de suppression ------------------------------------
# Refusees A TOUT MOMENT, meme fenetre ouverte, exactement comme le noyau.
#
# Regle posee par Isaac des le premier jour : la suppression definitive de
# donnees fait partie du « interdit, Isaac le fait lui-meme », au meme rang
# que les depenses et les mots de passe. La fenetre, elle, ne distinguait
# rien : ouverte pour creer une note, elle autorisait aussi `rm -rf` sur
# n importe quel dossier pendant quinze minutes.
#
# Le 25/08, TACZET a tente `rm` sur une note du coffre. Il n a ete refuse que
# parce que la fenetre venait d expirer. Deux minutes plus tot, le fichier
# disparaissait.
#
# Les alias PowerShell de Remove-Item sont inclus : del, erase, rd, rmdir, ri.
DESTRUCTIVE_COMMANDS = {
    "rm", "rmdir", "rd", "del", "erase", "ri", "remove-item",
    "shred", "unlink", "truncate",
}

# Un jeton n est une COMMANDE que s il ouvre la ligne, suit un separateur, ou
# suit un drapeau qui introduit une sous-commande. Ailleurs, c est un argument.
# Sans cette distinction, `grep -r "del" src/` etait refuse a tort tandis que
# `powershell -Command "Remove-Item x"` passait : les guillemets effacent la
# difference entre commande et chaine. Constate au premier jeu de tests.
COMMAND_STARTERS = {";", "&&", "||", "|", "&"}
SHELL_INVOKERS = {"-command", "-c", "/c", "/k", "-encodedcommand"}


# Le CLI `hermes` gouverne TACZET lui-meme : il cree des taches planifiees,
# reecrit config.yaml (`hermes tools disable` a detruit 240 lignes de
# commentaires le 2026-08-12), arrete son propre gateway, manipule les
# secrets. Il appartient donc au noyau, comme les fichiers qu il modifie.
#
# L enjeu precis, trouve le 25/08 : sous fenetre, TACZET pouvait ecrire un
# script puis lancer `hermes cron create --no-agent --script ...`. Le mode
# no_agent saute entierement la boucle d outils (cron/scheduler.py:3258),
# donc le hook ne se declenche JAMAIS pour ces taches. Une fenetre de quinze
# minutes se convertissait ainsi en execution permanente et non supervisee —
# alors que toute la conception du verrou repose sur une autorite bornee dans
# le temps.
#
# Cela traduit aussi une regle deja ecrite : SOUL.md ligne 64, « Reactif,
# jamais a l initiative ». Planifier EST une initiative. Isaac cree les
# taches depuis son terminal.
GOVERNANCE_COMMANDS = {"hermes"}


def deletes_data(command: str, _depth: int = 0) -> str:
    """Renvoie le nom de la commande de suppression trouvee, ou ''."""
    return _first_command_among(command, DESTRUCTIVE_COMMANDS, _depth)


def controls_hermes(command: str) -> str:
    """Renvoie 'hermes' si la commande pilote Hermes lui-meme, sinon ''."""
    if "hermes_cli" in command.replace(chr(92), "/").lower():
        return "hermes"  # forme `python -m hermes_cli.main ...`
    return _first_command_among(command, GOVERNANCE_COMMANDS, 0)


def _first_command_among(command: str, noms: set, _depth: int = 0) -> str:
    """Cherche, EN POSITION DE COMMANDE, un mot appartenant a `noms`.

    Si shlex echoue (guillemets desequilibres), on retombe sur un split brut
    plutot que de ne rien voir : mieux vaut un refus injustifie, qui se
    contourne, qu un fichier supprime, qui ne revient pas.
    """
    normalized = command.replace(chr(92), "/")
    # Detacher les separateurs colles aux mots AVANT de decouper. shlex rend
    # "C:/tmp;" en UN jeton, si bien que le "rm" qui suit n etait pas vu comme
    # une position de commande : powershell -Command "cd C:/tmp; rm notes.md"
    # passait. Trouve le 25/08 en ajoutant un cas d imbrication profonde.
    for sep in (chr(38) * 2, chr(124) * 2, chr(59), chr(124), chr(38)):
        normalized = normalized.replace(sep, " " + sep + " ")
    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError:
        tokens = normalized.split()
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1].lower() if i else ""
        if i and prev not in COMMAND_STARTERS and prev not in SHELL_INVOKERS:
            continue  # simple argument, pas une commande
        inner = tok.split()
        # Deux lectures du meme jeton, car un jeton cite peut etre AUSSI BIEN
        # un chemin contenant des espaces ("C:/Program Files/.../rm.exe") qu une
        # sous-commande complete ("Remove-Item x"). Ne regarder que le premier
        # mot laissait passer le premier cas ; ne regarder que le jeton entier
        # laissait passer le second.
        for candidate in ([tok] + inner[:1]):
            name = candidate.rsplit("/", 1)[-1].lower()
            if name.endswith(".exe"):
                name = name[:-4]
            if name in noms:
                return name
        if len(inner) > 1 and _depth < 3:
            found = _first_command_among(tok, noms, _depth + 1)
            if found:
                return found
    return ""


# Actions computer_use sans effet de bord — alignees sur _SAFE_ACTIONS
# (tools/computer_use/tool.py:81). Regarder est libre, agir demande la fenetre.
SAFE_COMPUTER_ACTIONS = {
    "capture", "wait", "list_apps", "list_windows", "cua_browser_state",
}

# Outils de pure lecture : libres hors du noyau, sans fenetre.
READ_ONLY_TOOLS = {"read_file", "search_files"}

# Enchainements shell. Leur presence retire la voie libre Google : la
# commande retombe sous la fenetre, quel que soit le service appele.
SHELL_CHAINING = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n")

# --- Google Workspace (BLUEPRINT v3 §B.1) ----------------------------------
# La skill google-workspace s utilise via `python google_api.py <service>
# <action>`, donc par l outil `terminal` — deja sous verrou. Sans distinction,
# lire son agenda exigerait d ouvrir une fenetre, ce qui est absurde.
#
# Lecture libre, ECRITURE sous fenetre. Toute action non listee ici est
# traitee comme une ecriture : une sous-commande ajoutee par une mise a jour
# d Hermes sera donc verrouillee par defaut, jamais ouverte par oubli.
GOOGLE_READ_ACTIONS = {
    ("gmail", "search"), ("gmail", "get"), ("gmail", "labels"),
    ("calendar", "list"),
    ("drive", "search"), ("drive", "get"), ("drive", "download"),
    ("contacts", "list"),
    ("sheets", "get"),
    ("docs", "get"),
}


def google_read_only(command: str) -> bool:
    """Vrai si la commande est un appel Google EN LECTURE.

    Reconnait `... google_api.py <service> <action> ...`. L inspection est
    textuelle, donc contournable — meme limite que le reste du verrou (§5.4
    du blueprint). Elle protege des actions accidentelles, pas d un
    adversaire qui controlerait deja le modele.
    """
    low = command.replace("\\", "/").lower()
    if "google_api.py" not in low:
        return False
    # Un enchainement shell greffe n importe quelle commande derriere une
    # lecture Google legitime (`... calendar list ; rm -rf`). Dans ce cas,
    # pas de voie libre : on retombe sur la fenetre.
    # `2>&1` fusionne stderr dans stdout et n ecrit aucun fichier. TACZET
    # l ajoute par reflexe en fin de commande : sans cette neutralisation
    # son `>` declenche le garde ci-dessous et AUCUNE lecture ne passe.
    # Bug reel du 25/08, visible au journal. `> fichier` reste refuse :
    # celui-la peut ecraser un fichier existant.
    probe = low.replace("2>&1", " ")
    if any(sep in probe for sep in SHELL_CHAINING):
        return False
    tail = low.split("google_api.py", 1)[1]
    # Le chemin du script est presque toujours cite. Sans cette
    # neutralisation, le guillemet FERMANT devient le premier argument et
    # plus aucune lecture n est reconnue. Bug reel du 25/08 : la commande
    # exacte documentee en memoire etait refusee hors fenetre depuis le
    # branchement de Calendar, alors que les tests, ecrits sans guillemets,
    # passaient tous.
    tail = tail.replace(chr(34), " ").replace(chr(39), " ")
    # Ignorer les options pour atteindre <service> <action>.
    args = [p for p in tail.split() if not p.startswith("-")]
    if len(args) < 2:
        return False
    return (args[0], args[1]) in GOOGLE_READ_ACTIONS


# --- GitHub (BLUEPRINT v3 §B.3) --------------------------------------------
# Meme logique que Google : consulter est libre, agir demande la fenetre.
# `gh` et `git` passent par l outil `terminal`, donc deja sous verrou.
#
# Les verbes retenus sont TOUS intrinsequement non destructeurs, quels que
# soient leurs drapeaux : ni `git log` ni `gh pr view` ne peuvent rien casser.
# C est ce qui evite d avoir a maintenir une liste de drapeaux interdits, un
# exercice ou l on finit toujours par en oublier un.
#
# Volontairement ABSENT : `gh api`, qui ecrit des que `-X POST` ou `-f`
# apparait, et `git clone` / `git fetch`, qui ecrivent sur le disque. Ils
# restent accessibles sous fenetre.
GH_READ_ACTIONS = {
    ("repo", "list"), ("repo", "view"),
    ("issue", "list"), ("issue", "view"),
    ("pr", "list"), ("pr", "view"), ("pr", "diff"), ("pr", "checks"),
    ("release", "list"), ("release", "view"),
    ("run", "list"), ("run", "view"),
    ("search", "repos"), ("search", "issues"), ("search", "prs"),
    ("label", "list"),
    ("auth", "status"),
}

GIT_READ_SUBCOMMANDS = {"status", "log", "diff", "show", "blame"}


def github_read_only(command: str) -> bool:
    """Vrai si la commande est une consultation GitHub ou git EN LECTURE.

    Le decoupage passe par shlex et NON par un split() naif : sur Windows
    l executable est souvent cite parce que son chemin contient un espace
    ("C:/Program Files/GitHub CLI/gh.exe"). Un split() rendait « c:/program »
    comme premier mot et refusait toute consultation. Constate au premier jeu
    de tests du 25/08 — meme famille que le piege n 20.

    Analyse volontairement distincte de google_read_only() : Google cherche
    ses arguments APRES le chemin du script, ici l executable est le premier
    mot. Mutualiser demanderait de reecrire une fonction de securite qui
    fonctionne, pour economiser quelques lignes.
    """
    normalized = command.replace(chr(92), "/")
    probe = normalized.replace("2>&1", " ")
    if any(sep in probe.lower() for sep in SHELL_CHAINING):
        return False
    try:
        tokens = shlex.split(probe, posix=True)
    except ValueError:
        return False  # guillemets desequilibres : on ne devine pas, on refuse
    args = [p.lower() for p in tokens if not p.startswith("-")]
    if not args:
        return False
    # SEUL le premier mot est examine. Balayer toute la ligne laisserait
    # passer `python quelquechose.py git status`, qui n est pas un appel git.
    exe = args[0].rsplit("/", 1)[-1]
    rest = args[1:]
    if exe in ("git", "git.exe"):
        return bool(rest) and rest[0] in GIT_READ_SUBCOMMANDS
    if exe in ("gh", "gh.exe"):
        return len(rest) >= 2 and (rest[0], rest[1]) in GH_READ_ACTIONS
    return False


def audit(verdict: str, tool: str, detail: str = "") -> None:
    """Trace best-effort. Ne doit JAMAIS faire echouer le hook."""
    try:
        HOOK_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}\t{verdict}\t{tool}\t{detail}\n")
    except Exception:
        pass


def allow() -> None:
    sys.exit(0)


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(2)


def touches_core(payload_text: str) -> str:
    """Renvoie le motif protege touche, ou '' si aucun.

    On normalise les separateurs et la casse. Les variables d'environnement
    (%LOCALAPPDATA%, $env:LOCALAPPDATA) sont couvertes puisqu'on cherche le
    NOM des fichiers, pas leur chemin absolu.
    """
    haystack = payload_text.replace("\\", "/").lower()
    haystack = re.sub(r"\s+", " ", haystack)
    for needle in PROTECTED:
        if needle in haystack:
            return needle
    return ""


def window_remaining() -> float:
    """Secondes restantes sur la fenetre, 0 si fermee/expiree/illisible."""
    if not SESSION_PATH.is_file():
        return 0.0
    try:
        # utf-8-sig, PAS utf-8 : Windows PowerShell ecrit ce fichier avec un
        # BOM (Set-Content -Encoding UTF8). En utf-8 strict, json.loads leve
        # "Unexpected UTF-8 BOM", l exception est avalee, et TOUTE fenetre
        # ouverte depuis le terminal est traitee comme fermee. Bug reel du
        # 22/08 : les fenetres d Isaac n ont jamais fonctionne, seules celles
        # ecrites par les tests Python (sans BOM) passaient.
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8-sig"))
        expires = float(data.get("expires", 0))
        minutes = float(data.get("minutes", 0))
        remaining = expires - time.time()
    except Exception:
        return 0.0
    if remaining <= 0:
        return 0.0
    # Fermeture par inactivite. `opened_at` est reconstitue depuis expires et
    # minutes, tous deux ecrits par le script d ouverture a partir de la meme
    # horloge UTC.
    opened_at = expires - minutes * 60.0
    if minutes <= 0 or opened_at > time.time():
        # Session sans duree declaree, ou dont l ouverture tomberait dans le
        # futur : on ne s y fie pas. Sans cette garde, une session forgee sans
        # champ `minutes` n expirait JAMAIS par inactivite — exactement le cas
        # contre lequel l ancien plafond de 2 h protegeait.
        opened_at = 0.0
    reference = max(opened_at, _last_activity())
    if reference <= 0:
        # Premiere observation : elle fait foi. La fenetre se fermera donc
        # 60 min plus tard si rien ne s en sert.
        _touch_activity()
        reference = time.time()
    if time.time() - reference > IDLE_TIMEOUT_SECONDS:
        return 0.0
    # Garde-fou : une fenetre ne peut jamais depasser 24 h, quoi qu il y ait
    # dans le fichier. Neutralise une session forgee a echeance lointaine.
    return min(remaining, MAX_WINDOW_SECONDS)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        allow()

    payload = json.loads(raw)  # fail_closed => un JSON casse bloque, voulu.
    tool = str(payload.get("tool_name") or "")

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    # --- Regle 1 : le noyau, refuse a tout moment ---------------------------
    hit = touches_core(json.dumps(tool_input, ensure_ascii=False))
    if hit:
        audit("BLOCK_NOYAU", tool, f"motif={hit}")
        block(
            f"Refus absolu : '{tool}' vise '{hit}', qui fait partie du noyau "
            "de gouvernance de TACZET (verrous, constitution, configuration, "
            "secrets). Ces fichiers ne sont modifiables NI par TACZET, NI "
            "pendant une fenetre de controle. Isaac les edite lui-meme."
        )

    # --- Regle 1bis : la suppression, refusee a tout moment ------------------
    if tool == "terminal":
        killer = deletes_data(str(tool_input.get("command") or ""))
        if killer:
            audit("BLOCK_SUPPRESSION", tool, f"commande={killer}")
            block(
                f"Refus absolu : '{killer}' supprime des donnees de maniere "
                "definitive. C'est une action qu'Isaac se reserve, au meme "
                "titre que les depenses et les mots de passe. Aucune fenetre "
                "de controle ne l'autorise. Lui dire quel fichier supprimer "
                "et le laisser faire."
            )

    # --- Regle 1ter : piloter Hermes lui-meme, refuse a tout moment ----------
    if tool == "terminal" and controls_hermes(str(tool_input.get("command") or "")):
        audit("BLOCK_GOUVERNANCE", tool, str(tool_input.get("command") or "")[:200])
        block(
            "Refus absolu : la commande `hermes` gouverne TACZET lui-meme — "
            "taches planifiees, configuration, gateway, secrets. Aucune "
            "fenetre de controle ne l'autorise, car une tache planifiee "
            "survivrait a la fenetre qui l'a creee. Isaac s'en charge depuis "
            "son terminal."
        )

    # --- Regle 2 : lecture ordinaire, toujours permise ----------------------
    if tool in READ_ONLY_TOOLS:
        allow()

    # Lecture Google (agenda, mails, fichiers) : libre, comme read_file.
    # L ecriture Google reste soumise a la fenetre, regle 3.
    if tool == "terminal":
        command = str(tool_input.get("command") or "")
        if google_read_only(command):
            # Tracer AUSSI les lectures autorisees. Sans cette ligne le
            # journal ne montrait que les refus, et l exception de
            # confort a pu rester cassee des jours sans qu on le voie.
            audit("ALLOW_GOOGLE_READ", tool, command[:300])
            allow()
        if github_read_only(command):
            audit("ALLOW_GITHUB_READ", tool, command[:300])
            allow()

    if tool == "computer_use":
        if str(tool_input.get("action") or "") in SAFE_COMPUTER_ACTIONS:
            allow()

    # --- Regle 3 : le reste depend de la fenetre ----------------------------
    remaining = window_remaining()
    if remaining > 0:
        # Seules les actions qui ONT BESOIN de la fenetre la prolongent.
        _touch_activity()
        audit("ALLOW", tool, f"fenetre ouverte, {int(remaining)}s restantes")
        allow()

    detail = json.dumps(tool_input, ensure_ascii=False)[:300]
    audit("BLOCK", tool, detail)
    block(
        f"Outil '{tool}' refuse : aucune fenetre de controle ouverte. "
        "Isaac doit l'ouvrir depuis le TERMINAL (pas depuis Discord) : "
        # Pointe le lanceur .cmd, pas la commande PowerShell complete.
        #
        # Historique de cette seule ligne, qui dit quelque chose : elle a
        # d abord employe %LOCALAPPDATA%, syntaxe cmd.exe que PowerShell
        # n etend pas — Isaac recevait « L argument ... n existe pas » a
        # chaque refus, sur l instruction la plus utilisee du systeme (25/08).
        # Remplacee par la forme PowerShell complete, elle imposait alors
        # d ecrire des guillemets imbriques que les deux shells traitent
        # differemment (26/08, trois echecs).
        #
        # Le lanceur supprime la question : UN chemin, aucun guillemet
        # imbrique, aucune dependance au shell. La meme ligne fonctionne
        # depuis cmd comme depuis PowerShell.
        '"C:\\Users\\Hp\\AppData\\Local\\hermes\\hooks\\taczet-control.cmd" open 15'
    )


if __name__ == "__main__":
    main()
