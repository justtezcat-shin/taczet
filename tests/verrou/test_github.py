"""GitHub : consulter est libre, agir demande la fenêtre.

Les verbes autorisés sont tous intrinsèquement non destructeurs, quels que
soient leurs drapeaux — c'est ce qui évite d'avoir à maintenir une liste de
drapeaux interdits, exercice où l'on finit toujours par en oublier un.
`git branch -D` n'est pas refusé par un filtre sur `-D` : il est refusé parce
que `branch` n'est pas dans la liste.

Le cas du chemin complet est celui qui a fait échouer la première version :
l'espace de « Program Files » cassait un `split()` naïf, d'où le passage à
`shlex`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import Suite, AUTORISE, REFUSE  # noqa: E402

GH_COMPLET = '"C:/Program Files/GitHub CLI/gh.exe"'

s = Suite("GitHub : consultation libre, ecriture sous fenetre")

s.section("Consultation gh, fenetre fermee")
for cmd in ("gh repo list --limit 10",
            "gh repo view justtezcat-shin/exemple-depot",
            "gh issue list --state open",
            "gh pr view 12 --json title,body",
            "gh pr diff 12",
            "gh run list --limit 5 2>&1",
            "gh auth status"):
    s.cas(cmd[:44], AUTORISE, cmd)
s.cas("chemin complet avec espaces", AUTORISE, GH_COMPLET + " repo list --limit 3")

s.section("Consultation git, fenetre fermee")
for cmd in ("git status", "git log --oneline -20", "git diff HEAD~1",
            "git show abc123", "git blame src/main.py"):
    s.cas(cmd, AUTORISE, cmd)

s.section("Ecriture refusee hors fenetre")
for cmd in ("gh pr create --title X --body Y",
            "gh issue create --title X",
            "gh repo delete justtezcat-shin/depot-de-test",
            "gh repo clone justtezcat-shin/depot-de-test",
            "gh repo rename nouveau-nom",
            "git push origin master",
            'git commit -m "x"',
            "git reset --hard origin/master",
            "git clean -fd",
            "git branch -D main",
            "git clone https://github.com/x/y",
            "git fetch origin"):
    s.cas(cmd[:44], REFUSE, cmd)

s.section("gh api reste sous fenetre, meme en lecture")
s.cas("gh api -X POST", REFUSE, "gh api -X POST /repos/x/y/issues")
s.cas("gh api /user (GET)", REFUSE, "gh api /user")

s.section("Pas de tunnel : seul le PREMIER mot compte")
s.cas("python outil.py git status", REFUSE, "python outil.py git status")
s.cas("rm -rf gh repo list", REFUSE, "rm -rf gh repo list")
s.cas("git log && git push", REFUSE, "git log && git push")
s.cas("git status > out.txt", REFUSE, "git status > out.txt")

s.section("Fenetre ouverte")
s.cas("git push", AUTORISE, "git push origin master", fenetre=True)
s.cas("gh pr create", AUTORISE, "gh pr create --title X --body Y", fenetre=True)
s.cas("git log config.yaml (noyau)", REFUSE, "git log config.yaml", fenetre=True)

sys.exit(s.bilan())
