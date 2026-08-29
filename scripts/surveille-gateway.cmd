@echo off
REM Lanceur du garde du gateway.
REM
REM Il existe pour une seule raison : supprimer l'imbrication de guillemets.
REM Passer directement "python.exe" + "script.py" a schtasks /TR obligeait a
REM echapper des guillemets a l'interieur de guillemets, ce que cmd.exe et
REM PowerShell traitent differemment — d'ou l'echec du 26/08. Ici, schtasks ne
REM voit qu'un seul chemin, sans espace ambigu, et la question disparait.
REM
REM Sert aussi de raccourci a la main :
REM   surveille-gateway.cmd pause     (avant une seance d'edition du noyau)
REM   surveille-gateway.cmd reprise
REM   surveille-gateway.cmd etat
"C:\Users\<UTILISATEUR>\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -X utf8 "C:\Users\<UTILISATEUR>\AppData\Local\hermes\scripts\surveille-gateway.py" %*
