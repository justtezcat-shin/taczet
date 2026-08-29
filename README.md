# TACZET — un verrou de capacités pour un agent autonome

Assistant personnel bâti sur [Hermes Agent](https://github.com/NousResearch),
tournant nativement sous Windows. Il lit un agenda, des courriels, des dépôts
Git, prend des notes, pilote un navigateur, et exécute des tâches planifiées
sans supervision.

**Ce dépôt ne publie pas l'assistant. Il publie ce qui l'empêche de nuire.**

Donner à un modèle de langage un accès shell sur sa propre machine pose une
question simple et mal résolue : comment lui laisser faire son travail sans lui
laisser tout faire ? Ce qui suit est une réponse, construite en deux semaines,
éprouvée par 188 tests, et documentée par 25 pièges qui ont chacun coûté du
temps.

C'est un miroir **engendré** du système réel — voir *Provenance* en fin de
document.

---

## Le modèle

Trois règles, évaluées dans cet ordre. La première qui tranche l'emporte.

### 1. Le noyau, refusé à tout moment

Les fichiers qui gouvernent l'agent sont inaccessibles **en permanence** :
ses propres verrous, sa constitution, sa configuration, ses secrets, les
scripts que son planificateur exécute.

Même pendant une autorisation. Même sur demande explicite de l'utilisateur.

Sans cette règle, une fenêtre de quinze minutes suffisait à l'agent pour se
prolonger de mille ans, réécrire son propre verrou, ou vider sa constitution.
Un audit en a trouvé **huit contournements** de ce type ; ils sont tous fermés.

### 2. La fenêtre d'autorisation

Le reste — shell, écriture de fichiers, pilotage du bureau — n'est permis que
pendant une fenêtre ouverte **depuis le terminal**, jamais depuis la messagerie.

> Le canal qui autorise ne doit pas être le canal qui demande.

Une fenêtre dure jusqu'à 24 heures, mais **se referme après 60 minutes sans
usage**. C'est ce qui rend une longue durée acceptable : elle couvre une
journée de travail, pas une nuit. Seules les actions qui ont *besoin* de la
fenêtre la prolongent — consulter un agenda ne maintient pas la porte ouverte.

### 3. Les refus inconditionnels

Trois familles d'actions ne sont **jamais** permises, fenêtre ouverte comprise.

| | Pourquoi |
|---|---|
| **Supprimer des données** | `rm`, `del`, `Remove-Item`… La suppression définitive appartient à l'humain, au même rang que les dépenses et les mots de passe. |
| **Piloter le framework** | Créer une tâche planifiée survivrait à la fenêtre qui l'a créée. Une autorisation bornée dans le temps ne doit pas engendrer d'exécution permanente. |
| **S'écrire des instructions** | Une *skill* est du texte que le modèle lit et suit. En écrire une revient à amender sa propre constitution. |

### Ce qui reste libre

Lire. Un agenda, des courriels, des dépôts, des notes, des fichiers ordinaires.
Sans quoi l'assistant serait inutilisable au quotidien, et le verrou serait
désactivé au bout d'une semaine.

**Un verrou qu'on désactive ne protège rien.** C'est le critère de conception
qui a guidé toutes les exceptions.

---

## Les tests

```bash
python tests/verrou/run_all.py     # 154 cas — la logique
python tests/cablage.py            #  34 cas — le câblage
```

Deux dimensions, et la seconde est née d'une découverte désagréable.

**La logique** — sept suites qui attaquent le verrou : chemins cités,
enchaînements shell, redirections, imbrications, sessions forgées, expiration.
Les **faux refus** y comptent autant que les vrais : un verrou qui bloque
`grep -r "del"` est un verrou qu'on finit par désactiver.

**Le câblage** — parce qu'on a découvert qu'en cas de perte du fichier de
consentement des hooks, les 154 cas continuaient de passer *pendant que le
verrou était éteint en production*. La logique était bonne ; elle n'était plus
branchée. C'est la pire forme d'échec : celle qui se déguise en succès.

---

## Trois leçons, chacune payée

**Tester la chaîne littérale, jamais une reconstitution.** La lecture d'agenda
est restée cassée trois jours parce que les tests écrivaient la commande sans
guillemets, alors que le système la produisait avec. La logique était juste ;
son interface avec l'entrée réelle n'avait jamais été jouée.

**Le code fait foi, pas la documentation — pas même la sienne.** Un point
critique est resté marqué rouge deux semaines sur la foi d'une multiplication.
Trois minutes de mesure l'ont fermé : le framework avait deux garde-fous que
personne n'avait lus. Lire un réglage ne dit pas ce qu'il produit.

**Fournir la réponse littérale bat interdire la mauvaise méthode.** Écrire
« n'utilise pas cette variable » a échoué ; donner le chemin complet a réussi.
Une interdiction suppose que la consigne soit lue avant l'autre.

Les 25 pièges sont dans [`docs/`](docs/) — emplacements de configuration
silencieusement ignorés, fuseaux horaires, encodages, syntaxe de shell, et
plusieurs cas où l'agent a échoué d'une façon que personne n'avait prévue.

---

## Ce que ce dépôt ne prétend pas être

**L'inspection est textuelle.** Elle protège des accidents, des malentendus et
des dérives — pas d'un adversaire qui contrôlerait déjà le modèle. C'est écrit
dans le verrou lui-même, et ce n'est pas une négligence : c'en est le périmètre.

Ce n'est pas non plus un produit. Une machine, un utilisateur, deux semaines.
Les commentaires et la documentation sont en français.

---

## Provenance

Miroir engendré par `outils/publier.py` depuis le dépôt de travail, qui est
l'installation vivante elle-même. Le script fonctionne en **liste blanche** —
ce qui n'est pas nommé n'est pas publié — puis **rescanne sa propre sortie** et
refuse de produire quoi que ce soit si un motif interdit survit.

Sont retirés le chemin de la machine, les identifiants de salons, et **tout ce
qui désigne des tiers**. La mémoire de l'assistant et le profil de son
utilisateur ne sont pas publiés du tout.

Isaac Adamou — [@justtezcat-shin](https://github.com/justtezcat-shin)
