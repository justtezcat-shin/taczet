@echo off
REM Lanceur de la fenetre de controle. Fichier ASCII pur, comme le .ps1 :
REM Windows lit les scripts en ANSI par defaut et un caractere accentue
REM casserait l'analyse.
REM
REM Il existe parce que la commande complete depend du shell. En PowerShell,
REM %LOCALAPPDATA% n'est pas etendu et les guillemets imbriques ne sont pas
REM interpretes comme en cmd.exe : la meme ligne marche ici et echoue la.
REM Trois fois le 26/08. Un chemin unique supprime la question.
REM
REM   taczet-control.cmd open 15     autorise TACZET 15 minutes
REM   taczet-control.cmd open 1440   une journee entiere (maximum)
REM   taczet-control.cmd close       referme immediatement
REM   taczet-control.cmd status      etat, sans rien modifier
REM
REM La fenetre se referme AUSSI d'elle-meme apres 60 minutes sans usage.
powershell -ExecutionPolicy Bypass -File "C:\Users\<UTILISATEUR>\AppData\Local\hermes\hooks\taczet-control.ps1" %*
