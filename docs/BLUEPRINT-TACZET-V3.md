# BLUEPRINT TACZET — v3

> **Destinataire.** Claude Cowork, agissant sur `%LOCALAPPDATA%\hermes\` de la machine d'Isaac.
> **Objet.** Partie I — auditer et corriger l'existant. Partie II — construire ce qui reste.
> **Base.** Hermes Agent 0.20.0 · ordinateur portable Windows 11, ressources modestes, sans GPU · Cerveau : `llama-3.3-70b-versatile` via Groq.
> **Remplace** le blueprint v2 du 15/08/2026, qu'il ne contredit pas : il l'audite et le prolonge.

---

> ## État au 2026-08-26
>
> **Quinze des dix-sept points de ce document sont clos.** Il n'en reste que
> deux, et ils attendent tous deux la même décision d'Isaac — publier ou non :
> **I.3.5** et **I.5.4**, l'hygiène des secrets avant mise en vitrine.
>
> Ce bandeau existe parce que le document mentait. Neuf points restaient
> marqués rouges ou orange alors qu'ils étaient résolus depuis des jours : ils
> avaient été **traités sans être inscrits**. C'est exactement le mal combattu
> toute la journée du 26/08 — une documentation qui décrit un système qui a
> bougé — et il avait atteint le document de pilotage lui-même.
>
> Chaque point clos porte désormais sa preuve en encadré, et le texte d'origine
> est conservé dessous : il dit pourquoi l'inquiétude était légitime.
>
> Deux d'entre eux se sont d'ailleurs révélés être des **fausses alertes**
> — I.2.4 et I.2.5 — fondées sur un calcul ou une supposition, closes par une
> mesure de quelques minutes. Lire un réglage ne dit pas ce qu'il produit.

## §0 — Protocole d'exécution (Cowork : lire en premier)

### Répartition des rôles

| | Acteur | Domaine |
|---|---|---|
| 🤖 | **Cowork** | Éditer les fichiers, écrire code/tests/docs, git, nettoyage des secrets |
| 🔷 | **TACZET** | Vérifier à l'exécution : redémarrages, lecture de logs, tests en conditions réelles |
| 🧑 | **Isaac** | Comptes externes, écrans OAuth, approbations, publications |

### Règles impératives

1. **Gateway arrêté pendant que Cowork écrit.** `hermes gateway stop` avant, `restart` après. Deux agents qui écrivent dans les mêmes fichiers = écrasements.
2. **Le code fait foi, pas la documentation.** La v1 de ce blueprint a échoué en prescrivant des outils inexistants. Avant d'écrire une clé de config, vérifie qu'elle existe dans le code d'Hermes 0.20.0. Si l'écart est constaté, signale-le au lieu de l'appliquer.
3. **Aucun secret dans un fichier versionné ou markdown.** Tokens et clés → `.env` uniquement.
4. **Ne jamais modifier le noyau inviolable** (`taczet-control`, `taczet-approval`, `hooks/`, `config.yaml`, `SOUL.md`, `.env`, `shell-hooks-allowlist`) sans montrer le diff à Isaac et obtenir un « oui » explicite.
5. **Une sauvegarde avant chaque écriture**, jusqu'à ce que git soit en place (§I.5.1).
6. **Rapporter les échecs.** Tout ce qui n'a pas pu être fait, avec la raison.

---

# PARTIE I — AUDIT DE L'EXISTANT

## §I.1 — Ce qui est solide : ne pas y toucher

Ces acquis sont au-dessus du niveau habituel d'un projet personnel. Ils sont à **préserver** et à **mettre en avant** en vitrine.

- [x] **WhatsApp colmaté sur deux couches** — `dm_policy` (adaptateur, bloque avant l'intake) + `unauthorized_dm_behavior` (runner, bloque la réponse). Fermer une seule couche laissait fuiter. Diagnostic exact.
- [x] **Audit adverse du verrou** — 8 contournements trouvés *par attaque de son propre système*, tous fermés, 20 tests. C'est la pièce maîtresse du projet.
- [x] **Noyau inviolable** — refus inconditionnel sur les fichiers de gouvernance, fenêtre plafonnée à 2 h même si le fichier de session est forgé.
- [x] **Choix du modèle mesuré** — 71 s sans appel d'outil → 0,42 s avec appel correct, même prompt, même schéma. Décision fondée, pas ressentie.
- [x] **`fail_closed: true`** sur les deux verrous — la panne du garde-fou retire les pouvoirs au lieu de les ouvrir. Bon sens de sécurité.
- [x] **Modèle fenêtre plutôt que jeton pour la machine** — raisonnement juste : « un verrou invivable finit désactivé ».
- [x] **Journal des pièges (§9 v2)** — rare et précieux. À publier tel quel.

## §I.2 — Ce qui est fragile : à corriger

### I.2.1 — Point de panne unique sur le modèle — CLOS ✅

> **Clos.** `fallback_model` enchaîne `laguna-s-2.1` puis `gemma-4-31b`, tous deux mesurés appelant correctement les outils. Motivé par un incident réel : le 22/08 le modèle en place a disparu du catalogue de son fournisseur et TACZET est devenu totalement muet.

Groq est le seul provider configuré. Un quota atteint (429) = TACZET totalement muet, vocal compris. Le blueprint v2 le reconnaît en §13 mais aucune parade n'existe.

### I.2.2 — Les tests ne couvraient que le verrou — CLOS le 2026-08-26 ✅

Le constat était juste, mais l'énoncé trompeur. Il ne manquait pas « des tests
de TACZET » : il manquait des tests du **câblage**.

Les sept suites de `tests/verrou/` (154 cas) éprouvent la **logique** du
verrou. Le 26/08 on a découvert que si `shell-hooks-allowlist.json`
disparaissait, **les 154 continueraient de passer pendant que le verrou serait
éteint en production**. La logique était bonne ; elle n'était plus branchée.
C'est la pire forme d'échec : celle qui se déguise en succès.

`tests/cablage.py` couvre l'autre moitié — **34 cas, aucun appel de modèle,
aucun effet de bord** :

| Ce qu'il vérifie | Ce qu'il attrape |
|---|---|
| commentaires de `config.yaml` > 300 | le gateway l'a réécrit (piège n 24) |
| `MEMORY.md` sous sa limite, marge > 500 | la saturation silencieuse |
| marqueurs dans les skills corrigées | une réinstallation les a écrasées |
| présence des identifiants | un jeton effacé ou expiré |
| portees du jeton Google | une ré-autorisation trop large |
| les 4 tâches planifiées | une tâche supprimée par mégarde |
| la tâche Windows du garde | la surveillance désarmée |
| scripts et lanceurs présents, syntaxe valide | un fichier perdu |

Les secrets sont testés par leur **présence**, jamais affichés.

**Il a trouvé un défaut dès le premier lancement** — et pas dans le système :
dans la carte qu'on s'en fait. Il cherchait `google_token.json` dans le
dossier de la skill ; il vit à la racine (`google_api.py:42`). Un banc de
câblage vérifie aussi ce qu'on **croit** savoir de l'installation.

**Ce qu'il ne couvre pas, et qu'il faut nommer :** il ne vérifie pas que
TACZET *répond*, ni qu'une tâche *se livre*. Ces deux-là coûtent des appels de
modèle et ne peuvent être éprouvés qu'en conditions réelles — c'est ce que
font les tâches planifiées elles-mêmes, tous les jours à 7 h.

### I.2.3 — Rollback artisanal — CLOS ✅

> **Clos.** Dépôt git, 53 commits, `.gitignore` en liste blanche, 25 fichiers suivis — configuration, constitution, verrous, tests, scripts, blueprints. Il a servi pour de vrai le 26/08 : `git checkout HEAD -- config.yaml` a rendu ses 333 commentaires après une réécriture automatique par le gateway.

23 fichiers `.bak` horodatés. Pas de diff lisible, pas d'historique, pas de message expliquant *pourquoi* un changement a eu lieu. Un dossier de config qui a subi 23 modifications sensibles mérite un vrai versionnement.

### I.2.4 — Compression du contexte — CLOS le 2026-08-26 ✅

**C'était une fausse alerte, fondée sur un calcul naïf.** L'entrée d'origine
craignait que la compression se déclenche à 32 000 tokens (50 % de 64 000),
« juste au-dessus du socle », donc en permanence. Mesure faite en appelant le
code plutôt qu'en lisant la configuration :

```
50 % de 64 000                       = 32 000
plancher MINIMUM_CONTEXT_LENGTH      = max(32 000, 64 000) = 64 000
ce plancher egale la fenetre entiere -> la compression ne pourrait JAMAIS
se declencher, le fournisseur refusant la requete avant 100 %.
Hermes detecte ce cas degenere -> _MIN_CTX_TRIGGER_RATIO = 85 %
declenchement reel                   = 54 400 tokens
```

| | Marge de conversation |
|---|---|
| Ce que cette entrée supposait | **642 tokens** |
| La réalité mesurée | **23 042 tokens** |

Deux garde-fous d'Hermes étaient ignorés, dont l'un existe **précisément**
pour éviter la pathologie décrite. Son commentaire dans le code la nomme :
« compaction re-fires every 1-2 turns and the session spends most of its
wall-clock summarizing ».

Le commentaire de `config.yaml` portait la même erreur ; il est corrigé.

**Reserve conservée :** après déclenchement à 54 400, il ne reste que 9 600
tokens de fenêtre. Si la compression ne récupère pas assez, elle pourrait se
rappeler souvent. C'est le scénario que le ratio de 85 % est censé couvrir,
mais **personne ne l'a observé**. À surveiller, pas à corriger d'avance.

**Leçon de méthode :** cette entrée était rouge depuis deux semaines sur la
foi d'une multiplication. Une mesure de trois minutes l'a close. Lire la
configuration ne dit pas ce que le code fait.

### I.2.5 — `hooks_auto_accept: true` — CLOS le 2026-08-26 ✅

**Ce n'était pas un compromis : c'est ce qui empêche le verrou d'être désarmé
en silence.** L'entrée d'origine le soupçonnait d'affaiblir la sécurité. La
lecture du code dit l'inverse.

Un hook déclaré dans `config.yaml` mais absent de
`shell-hooks-allowlist.json` est **purement ignoré** :

> `shell hook for %s (%s) not allowlisted — skipped`
> (`agent/shell_hooks.py`)

Le consentement se demande normalement au terminal, à la première utilisation.
**Or le gateway tourne sans terminal interactif** : personne n'est là pour
approuver. Sans `hooks_auto_accept: true`, un hook non encore consenti ne
s'arme donc jamais — et le verrou ne s'exécute pas, sans le moindre signe.

État actuel : les deux hooks **sont déjà consentis**, le réglage n'est donc
pas porteur aujourd'hui. Il le redeviendrait si l'allowlist était perdue —
réinstallation, corruption, changement de chemin.

**Risque résiduel réel**, et il faut le nommer : une commande de hook modifiée
serait approuvée sans que personne la voie. Il est contenu par `config.yaml`
dans le noyau (TACZET ne peut pas l'écrire) et par le protocole de Cowork
(diff montré, accord explicite avant toute modification du noyau).

**Trou de test fermé au passage.** Les 154 cas éprouvaient la LOGIQUE du
verrou ; aucun ne vérifiait qu'elle est **branchée**. Si l'allowlist
disparaissait, tous continueraient de passer pendant que le verrou serait
éteint en production. `test_matcher.py` vérifie désormais que les deux hooks
sont consentis et que le filet est armé.

C'est le même motif que I.2.2 : ce qui n'est pas testé, ce n'est pas la
logique, c'est son câblage.

### I.2.6 — Fichiers de mémoire hors limites — CLOS ✅

> **Clos, et à la cause.** `MEMORY.md` 6 147 / 9 000, `USER.md` 5 965 / 8 000. Surtout : la mémoire grossissait parce qu'elle **compensait des skills qui enseignaient un idiome impossible ici**. Les skills sont corrigées à la source, le mécanisme est supprimé. `cablage.py` surveille désormais la marge.

`USER.md` et `MEMORY.md` ont été rédigés en version longue. Hermes applique une limite de caractères sur la mémoire et réinjecte ces fichiers **à chaque session** (coût en tokens à chaque tour). Jamais vérifié depuis.

### I.2.7 — Transcription du mot « TACZET » — SANS OBJET ⏸

> **Sans objet tant que la voix dort.** Désactivée le 22/08, Isaac pilote au texte. `stt.enabled: true` la réactive telle quelle — et ce point avec elle.

Noté en §14 v2 : il faut éviter de prononcer le nom de son propre agent. Ironique et gênant à démontrer en vitrine. L'`initial_prompt` aide ; une alternative phonétique en secours serait plus robuste.

## §I.3 — Les trous connus

### I.3.1 — Outils non couverts par les verrous — CLOS ✅

> **Clos le 26/08**, après audit des huit outils concernés. Sept sont acceptables et la raison est écrite dans le commit. Le huitième, `skill_manage`, passe sous fenêtre : une skill est du texte que le modèle lit et suit, donc en écrire une revient à s'amender sa propre constitution. `test_matcher.py` porte l'invariant — tout outil accordé qui écrit doit être couvert.

`cronjob`, `skill_manage`, `delegate_task`, `memory`. Le v2 les qualifie de « aucun accès direct à la machine ». **C'est exact et insuffisant** : ce qui compte, ce sont les accès *indirects*. Trois questions ouvertes, non testées :

- **`delegate_task`** — un sous-agent qui appelle `terminal` déclenche-t-il le hook `pre_tool_call` du parent, ou s'exécute-t-il dans un contexte où le hook ne s'applique pas ? *Si la seconde réponse est la bonne, c'est un contournement complet du verrou machine.*
- **`cronjob`** — une tâche planifiée qui appelle `terminal` passe-t-elle par le verrou au moment de son exécution, et que se passe-t-il si la fenêtre est fermée à cet instant ?
- **`skill_manage`** — écrire une skill, est-ce un `write_file` (verrouillé) ou un chemin d'écriture propre (non verrouillé) ? Une skill est du code exécutable.

Ce n'est pas une accusation : c'est trois tests à faire. Mais tant qu'ils ne sont pas faits, l'affirmation « la machine est sous verrou » est **non prouvée**.

### I.3.2 — Écart entre la constitution et les verrous — CLOS ✅

> **Clos pour l'essentiel.** La suppression de données et le CLI `hermes` sont désormais refusés **à tout moment**, fenêtre ouverte comprise — ils traduisent deux promesses de `SOUL.md` que rien n'appliquait.
> 
> **L'écart de principe subsiste et il est assumé :** l'inspection est textuelle. Elle protège des accidents et des malentendus, pas d'un adversaire qui contrôlerait déjà le modèle. C'est écrit dans le verrou lui-même.

Le niveau 2 (« feu vert requis ») couvre : envoyer un message, modifier un événement, commiter, publier. **Aucun verrou ne couvre ces actions** — elles ne sont simplement pas encore branchées. Dès la Phase 2 (Google Calendar en écriture), l'écart devient réel : TACZET pourra modifier un agenda sans franchir le moindre contrôle dur.

**Conséquence directe pour le plan :** le verrou Google doit être écrit **avant** ou **en même temps** que la connexion Google, pas après.

### I.3.3 — Observabilité — LARGEMENT COUVERT 🟢

> **Largement couvert, autrement que prévu.** Le journal d'audit porte cinq verdicts distincts — `ALLOW_GOOGLE_READ`, `ALLOW_GITHUB_READ`, `BLOCK`, `BLOCK_NOYAU`, `BLOCK_SUPPRESSION`, `BLOCK_GOUVERNANCE` — et c'est lui qui a permis de diagnostiquer **trois pannes** le 25/08. S'y ajoutent le journal du garde et `cablage.py`.
> 
> Ce qui manque : aucun export structuré. `hermes monitoring` exige un point de collecte OTLP, hors de proportion pour un portable.

Trois journaux textuels. Aucun tracing par run (quel outil, quels arguments, quelle latence, quelle décision), aucune métrique, aucune détection de régression. C'est le principal écart avec l'état de l'art 2026 — et, en vitrine, le point qui sépare « projet perso » de « travail d'ingénieur ».

### I.3.4 — Résilience opérationnelle — CLOS ✅

> **Clos le 26/08.** Garde extérieur — nécessairement extérieur, le planificateur tournant *dans* le gateway qu'il devrait surveiller. Tâche Windows toutes les 15 minutes, prévient **avant** de réparer via `hermes send` qui joint Discord sans gateway. Testé en conditions réelles : détection et relance confirmées en 38 secondes.

Pas de health check, pas de redémarrage automatique du gateway, pas de surveillance de quota. Une IA « 24/7 » qui tombe pendant la nuit et le reste jusqu'au matin n'est pas 24/7.

### I.3.5 — Hygiène des secrets non préparée pour la publication 🔴

Trois éléments ne doivent **jamais** sortir : `.env`, `config.yaml` réel (tokens), et `platforms/whatsapp/session` (identifiants complets du compte WhatsApp). Aucun `.gitignore` n'existe encore, alors que la publication GitHub est un objectif déclaré.

## §I.4 — Les six tests qui lèvent l'incertitude

À exécuter **avant** toute nouvelle construction. Chacun a une réponse binaire.

| # | Test | Réponse attendue |
|---|---|---|
| 1 | `delegate_task` → sous-agent appelle `terminal` | Une ligne apparaît dans `taczet-control-audit.log` |
| 2 | `cronjob` → tâche planifiée appelant `terminal`, fenêtre **fermée** | `BLOCK` au journal |
| 3 | `skill_manage` → créer une skill | Passe par le verrou, ou tracé comme écriture |
| 4 | Écriture dans `hooks/` par TACZET | Refus inconditionnel (noyau) |
| 5 | Session longue → compression | Déclenchement observé avant saturation |
| 6 | Taille de `USER.md` + `MEMORY.md` | Sous la limite de la version |

**Si le test 1 ou 2 échoue, tout le reste attend :** le verrou machine serait contournable, ce qui invalide la principale garantie du système.

## §I.5 — Corrections à appliquer

### I.5.1 — Versionner le dossier de config — FAIT ✅

> **Fait.** Voir I.2.3.

- Initialiser un dépôt git **local** dans `%LOCALAPPDATA%\hermes\`
- `.gitignore` **d'abord** : `.env`, `platforms/whatsapp/session/`, `logs/`, `*.bak.*`, tout fichier de session ou de jeton
- Premier commit de l'état actuel
- Archiver les 23 `.bak` dans un sous-dossier ignoré, puis cesser d'en produire

> Bénéfice double : rollback réel avec diff et motif, **et** socle propre pour la vitrine GitHub.

### I.5.2 — Chaîne de secours sur le modèle — FAIT ✅

> **Fait.** Voir I.2.1.

- 🧑 Créer une clé chez un second provider gratuit à faible latence *(OpenRouter ou Cerebras — vérifier la disponibilité au moment de le faire)*
- 🤖 Déclarer la chaîne de fallback dans `config.yaml` après avoir confirmé la clé de config exacte dans le code
- 🔷 Tester en simulant l'indisponibilité du provider principal

### I.5.3 — Calibrer les fichiers de mémoire — FAIT ✅

> **Fait.** Voir I.2.6.

- Mesurer `USER.md` et `MEMORY.md` contre la limite réelle de la 0.20.0
- Si dépassement : produire une version resserrée pour Hermes, et conserver la version longue comme document de référence hors du dossier mémoire

### I.5.4 — Nettoyer avant publication 🤖 Cowork

- Produire `config.yaml.example` entièrement scrubbé
- Passer un scanner de secrets sur ce qui est destiné à être publié
- Vérifier qu'aucun ID Discord, numéro de téléphone ou chemin utilisateur ne subsiste

### I.5.5 — Corriger les écarts constitutionnels — FAIT ✅

> **Fait.** Voir I.3.2.

- Aligner `SOUL.md` : le niveau 2 doit indiquer explicitement quelles actions sont **réellement** sous verrou dur et lesquelles reposent encore sur une clause de confiance
- Ne pas promettre dans la constitution ce que le code n'applique pas

---

# PARTIE II — CE QUI RESTE À CONSTRUIRE

## §II.0 — Ordre et principe

Cinq phases. Chacune a un **critère binaire** : tant qu'il n'est pas atteint, on ne passe pas à la suivante. Un item par session.

```
A  Fermer l'audit        <- les 6 tests + corrections I.5
B  Google Calendar       <- 6 cas d'usage sur 7 en dependent
C  Autonomie             <- le seuil JARVIS
D  Fiabilite & evals     <- le differenciateur 2026
E  Vitrine               <- GitHub + LinkedIn
F  Menu                  <- au gout
```

**Pourquoi cet ordre.** L'essentiel du temps passé jusqu'ici l'a été sur le vocal, qui ne sert qu'un cas d'usage sur sept. La matière (agenda, mails) débloque les six autres. Et rien ne mérite d'être élargi tant que l'audit n'est pas fermé.

---

## PHASE A — Fermer l'audit

**Critère :** les 6 tests du §I.4 sont passés, les corrections du §I.5 appliquées, aucune question ouverte sur le verrou.

🔷 **TACZET** — exécute les 6 tests, rapporte chaque résultat avec la ligne de journal correspondante.
🤖 **Cowork** — applique I.5.1 à I.5.5. Écrit un correctif de verrou si le test 1 ou 2 révèle un contournement.
🧑 **Isaac** — approuve tout diff touchant au noyau. Crée la clé du provider de secours.

> Si un contournement est trouvé : c'est une **bonne nouvelle** pour la vitrine. Le récit « j'ai attaqué mon agent une seconde fois et j'ai encore trouvé » est plus fort que « tout était parfait ».

---

## PHASE B — Google Calendar, puis Gmail

**Critère :** « Qu'est-ce que j'ai demain ? » renvoie le vrai agenda.

### B.1 — Le verrou d'abord (§I.3.2)

🤖 **Cowork** — étendre le verrou machine, ou en écrire un troisième, couvrant les **écritures** Google : créer, modifier, supprimer un événement ; envoyer un mail. Lecture libre, écriture sous contrôle. À faire **avant** l'OAuth, pas après.

### B.2 — L'accès

🧑 **Isaac** (rien de ceci n'est délégable) :
- Projet Google Cloud, API Calendar activée, ID client OAuth **type Bureau**
- Sur l'écran de consentement : **ne cocher que Calendar**. Les scopes par défaut incluent tout le Drive ; le script accepte les autorisations partielles.
- Déposer `google_client_secret.json` à la racine Hermes
- Séquence : `setup.py --client-secret` → `--auth-url` → `--auth-code`

🔷 **TACZET** — valider par une lecture réelle de l'agenda.

### B.3 — Ensuite seulement

Gmail *(lecture d'abord, envoi sous verrou)*, puis GitHub, puis Obsidian *(fichiers markdown locaux — le plus simple, à faire quand le reste tient)*.

---

## PHASE C — L'autonomie

**Critère :** un matin, un message arrive dans `<SALON>` sans que rien n'ait été demandé.

C'est le passage d'un outil qu'on interroge à un assistant qui travaille. Le toolset `cronjob` est présent, **zéro tâche existe**.

- **C.1 — Brief matinal.** La procédure existe dans la skill Google. Agenda du jour + échéances + mails urgents. 🤖 Cowork écrit la tâche, 🔷 TACZET la planifie, 🧑 Isaac valide le premier envoi.
- **C.2 — Veille des échéances.** Remises et examens, depuis l'agenda.
- **C.3 — Révision Network+.** La seule skill à écrire entièrement. 🤖 Cowork.

> **Prérequis de sécurité :** ne créer aucune tâche planifiée avant que le test 2 du §I.4 soit passé. Une tâche autonome qui contourne le verrou est exactement le scénario à ne pas produire.

---

## PHASE D — Fiabilité et observabilité

**Critère :** une commande unique dit si TACZET va bien, et une mise à jour qui casse quelque chose est détectée automatiquement.

C'est l'angle mort principal (§I.3.3) et, en vitrine, le point qui fait la différence.

### D.1 — Suite d'évaluations 🤖 Cowork

- Un jeu de cas de référence : entrée → outil attendu → réponse attendue
- Couvrant : appel d'outil, refus par le verrou, transcription vocale, affichage Discord silencieux, lecture d'agenda
- Exécutable en une commande, rapport lisible
- **À lancer après chaque `hermes update`** — remplace la vérification manuelle du §11 v2

### D.2 — Tracing structuré 🤖 Cowork

Par run : outils appelés, arguments, latence par maillon *(VAD → Whisper → modèle → TTS)*, décision du verrou, issue. Un format exploitable, pas du texte libre.

### D.3 — Santé et résilience 🤖 Cowork

- Health check périodique *(le gateway répond-il ?)*
- Redémarrage automatique en cas de chute *(Planificateur de tâches Windows)*
- Surveillance du quota Groq, avec bascule sur le fallback (§I.5.2)

### D.4 — Métriques 🤖 Cowork

Latence médiane par maillon, taux de succès des appels d'outil, taux de blocage du verrou, volume de 429. Ce sont ces chiffres qui alimentent les posts LinkedIn.

---

## PHASE E — Vitrine : GitHub et LinkedIn

**Critère :** un recruteur comprend en 60 secondes ce que tu as construit et pourquoi c'est sérieux.

**L'angle.** Personne n'est impressionné par « j'ai branché un assistant vocal ». Ce qui est rare : **avoir attaqué son propre agent et fermé 8 contournements, avec des tests à l'appui.** La sécurité et l'observabilité sont l'histoire. Le vocal est l'illustration.

### E.1 — Le dépôt 🤖 Cowork

- ⚠️ **`.gitignore` avant le premier commit** (§I.5.1)
- `README` : problème → architecture → décisions → **limites assumées**
- Le **schéma de la chaîne** *(§2 du v2 — le reprendre tel quel, il est excellent)*
- Les **hooks de verrouillage**, anonymisés — le cœur technique
- Le **rapport d'audit** : les 8 contournements, comment trouvés, comment fermés
- Les **tests** — verrou + évals de la Phase D
- La section **Pièges rencontrés** *(§9 du v2 — rare, utile, très partageable)*
- `config.yaml.example` scrubbé, licence

🧑 **Isaac** — relit intégralement avant de rendre public. Cherche : jetons, ID Discord, numéro de téléphone, chemins personnels.

### E.2 — LinkedIn 🧑 Isaac *(🤖 Cowork rédige les brouillons)*

| Post | Sujet | Pourquoi il porte |
|---|---|---|
| 1 | Le projet + le schéma | Pose le décor |
| 2 | **L'audit sécurité** | *Le plus fort.* « J'ai essayé de contourner mon propre agent. J'ai réussi 8 fois. » |
| 3 | Les mesures | 71 s → 0,42 s, avec la méthode |
| 4 | Un piège technique | Les deux emplacements de config Discord |

- Démo vidéo de 30 s : ordre vocal → action réelle
- Profil : « Agent IA autonome — sécurité, observabilité, ops »
- Lier au dépôt

> **Note.** Publier après la Phase D, pas avant : les évals et les métriques sont précisément ce qui rend les posts crédibles.

---

## PHASE F — Menu

Sans ordre, au goût, une fois le reste acquis.

- **Mot de réveil** « Hey TACZET » — toolset `wake_word`, local, gratuit. Confort réel.
- **Spotify** — toolset natif, authentification à faire.
- **Mémoire par couches** — travail / résumés / artefacts / préférences durables. À considérer quand les fichiers plats montreront leurs limites, pas avant.
- **Raccourci bureau** pour ouvrir une fenêtre d'autorisation en double-clic.
- **Claude comme cerveau** — quand le crédit sera disponible. Groq reste alors en fallback rapide.

---

## §II.1 — Ce qui reste hors de portée, et pourquoi

À dire franchement, y compris en vitrine — l'honnêteté sur les limites est un signal de sérieux.

- **Le verrou ignore l'intention.** Fenêtre ouverte, il ne distingue pas un clic anodin d'un clic sur « Acheter ». Protection de constitution, donc promesse.
- **L'inspection shell est textuelle.** Un encodage base64 ou un passage par variable lui échappe.
- **La transcription restera imparfaite.** VAD et amorce réduisent sans éliminer.
- **8 Go de RAM** — pas de modèle local, jamais.
- **Aucun événement vocal exposé aux hooks** — pas de salutation automatique des arrivants sans patcher Hermes.
- **Un navigateur connecté engage l'identité d'Isaac.** Pas de mot de passe nécessaire : les sessions sont déjà ouvertes.
- **Vouloir par soi-même** — exclu par constitution. Un choix, pas une limite technique.

---

## §II.2 — Carte des fichiers

| Fichier | Touché en |
|---|---|
| `config.yaml` | I.5.2 *(fallback)*, D.3, B.1 |
| `.env` | I.5.2 — **secrets uniquement** |
| `SOUL.md` | I.5.5 *(alignement constitution)* — approbation requise |
| `memories/USER.md`, `MEMORY.md` | I.5.3 *(calibrage)* |
| `hooks/` | Phase A *(correctifs)*, B.1 *(verrou Google)* — noyau, approbation requise |
| *(nouveau)* `.gitignore`, `README.md`, `tests/`, `evals/` | I.5.1, D.1, E.1 |

---

## §II.3 — Méthode, pour toute capacité ajoutée

1. **Vérifier que l'outil existe** — dans le code, pas dans la doc.
2. **Trouver l'emplacement réel du réglage** — le code fait foi.
3. **Tester la brique isolément**, hors d'Hermes.
4. **Configurer, valider le YAML.**
5. **Redémarrer et vérifier le chargement** — écrit n'est pas actif.
6. **Consigner dans `MEMORY.md`** — le piège trouvé aujourd'hui sera reperdu.

---

*« Construis la puissance. Garde le contrôle. »*

*Blueprint TACZET v3 — Partie I audite l'existant, Partie II construit la suite. Toute clé de configuration citée doit être confirmée dans le code d'Hermes 0.20.0 avant application.*
