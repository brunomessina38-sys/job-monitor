# Job Monitor — Meta · Microsoft · Google

Controlla ogni 20 minuti le pagine carriere di Meta, Microsoft e Google e ti manda una mail
quando compare una **nuova** posizione che corrisponde alle tue preferenze.

- Filtri (ruoli, esclusioni, paesi): `config.py`
- Script: `monitor.py`
- Pianificazione: `.github/workflows/monitor.yml`
- Memoria delle posizioni già viste: `seen_jobs.json` (creato in automatico)

## Notifiche
Per ogni gruppo di nuove posizioni lo script apre una **issue** in questo repository:
GitHub la invia per mail all'indirizzo del tuo account (nessuna password necessaria).
Al primo avvio ricevi l'elenco di tutte le posizioni già aperte; da lì in poi solo le nuove.
Se un sito non è leggibile per ~12 ore ricevi un avviso.

Facoltativo — mail via Gmail invece delle issue: aggiungi i secret `GMAIL_USER`,
`GMAIL_APP_PASSWORD` (https://myaccount.google.com/apppasswords) ed eventualmente `EMAIL_TO`
in Settings → Secrets and variables → Actions.

## Modificare le preferenze
Modifica `config.py` direttamente su GitHub (icona della matita) e salva.

## Prova in locale
```bash
python3 monitor.py --dry-run
```
