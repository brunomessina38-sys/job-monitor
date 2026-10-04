"""Monitora le pagine carriere di Meta, Microsoft e Google e invia una mail
quando compare una nuova posizione che corrisponde a config.py.

Uso:
  python monitor.py            # esecuzione normale (invia mail se ci sono novità)
  python monitor.py --dry-run  # stampa i risultati, non invia mail e non salva lo stato

Notifiche: di default apre una issue nel repository GitHub (GitHub la invia
per mail). In alternativa, impostando queste variabili, invia via Gmail:
  GMAIL_USER          indirizzo Gmail mittente
  GMAIL_APP_PASSWORD  "password per le app" di Google (16 caratteri)
  EMAIL_TO            destinatario (default: GMAIL_USER)
"""

import html
import json
import os
import re
import smtplib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import config

STATE_FILE = Path(__file__).with_name("seen_jobs.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
FAILURE_ALERT_THRESHOLD = 4  # esecuzioni fallite di fila prima di avvisarti


# ----------------------------------------------------------------- HTTP

def http(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    h.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if attempt == 4 or e.code not in (429, 500, 502, 503, 504):
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
            time.sleep(min(wait, 120))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))


# ----------------------------------------------------------------- filtri

def _compile_countries():
    names, codes = [], {}
    for country, aliases in config.COUNTRIES.items():
        for a in aliases:
            a = a.lower()
            if len(a) == 2:
                codes[a] = country
            else:
                names.append((re.compile(r"\b" + re.escape(a) + r"\b"), country))
    return names, codes


COUNTRY_NAMES, COUNTRY_CODES = _compile_countries()


def country_of(location_text="", code=None):
    if code and code.lower() in COUNTRY_CODES:
        return COUNTRY_CODES[code.lower()]
    text = location_text.lower()
    for rx, country in COUNTRY_NAMES:
        if rx.search(text):
            return country
    return None


def title_matches(title):
    t = title.lower()
    if any(x in t for x in config.TITLE_EXCLUDE):
        return False
    return any(k in t for k in config.TITLE_KEYWORDS)


def make_job(company, job_id, title, url, locations):
    """locations: lista di (testo, codice_paese_o_None)."""
    matched = [loc for loc, code in locations if country_of(loc, code)]
    if not matched or not title_matches(title):
        return None
    return {"key": f"{company}:{job_id}", "company": company, "title": title.strip(),
            "url": url, "locations": matched}


# ----------------------------------------------------------------- Microsoft

def fetch_microsoft():
    jobs = {}
    for country in config.COUNTRIES:
        start = 0
        while start < 1000:
            q = urllib.parse.urlencode({
                "domain": "microsoft.com", "query": "", "location": country,
                "start": start, "num": 10, "sort_by": "timestamp"})
            d = json.loads(http("https://apply.careers.microsoft.com/api/pcsx/search?" + q))["data"]
            positions = d.get("positions") or []
            for p in positions:
                locs = [(s, None) for s in p.get("locations") or []]
                locs += [(s, s.split(",")[-1].strip()) for s in p.get("standardizedLocations") or []]
                job = make_job("Microsoft", p["id"], p["name"],
                               "https://apply.careers.microsoft.com" + p["positionUrl"], locs)
                if job:
                    job["locations"] = p.get("locations") or job["locations"]
                    jobs[job["key"]] = job
            start += 10
            time.sleep(1)
            if len(positions) < 10 or start >= (d.get("count") or 0):
                break
    return jobs


# ----------------------------------------------------------------- Google

def fetch_google():
    jobs, ok = {}, 0
    for country in config.COUNTRIES:
        for page in range(1, 51):
            q = urllib.parse.urlencode({"location": country, "sort_by": "date", "page": page})
            page_html = http("https://www.google.com/about/careers/applications/jobs/results?" + q)
            m = re.search(r"key: 'ds:1', hash: '\d+', data:(.*?), sideChannel", page_html, re.S)
            if not m:
                break  # paese non riconosciuto da Google o nessun risultato
            ok += 1
            d = json.loads(m.group(1))
            results = d[0] or []
            for j in results:
                locs = [(l[0], l[5] if len(l) > 5 else None) for l in (j[9] or [])]
                job = make_job("Google", j[0], j[1],
                               f"https://www.google.com/about/careers/applications/jobs/results/{j[0]}", locs)
                if job:
                    jobs[job["key"]] = job
            page_size = d[3] if len(d) > 3 and d[3] else 20
            time.sleep(0.5)
            if not results or page * page_size >= (d[2] or 0):
                break
    if not ok:
        raise RuntimeError("Formato pagina Google cambiato (nessun dato leggibile)")
    return jobs


# ----------------------------------------------------------------- Meta

META_DOC_ID = "27129360303422352"  # CareersJobSearchResultsV2DataQuery
META_OP = "CareersJobSearchResultsV2DataQuery"


def _meta_discover_doc_id(page_html):
    """Se Meta cambia l'ID della query, lo ricerca nei file JS della pagina."""
    scripts = set(re.findall(r'src="(https://static\.xx\.fbcdn\.net/rsrc\.php/[^"]+\.js[^"]*)"', page_html))
    for s in scripts:
        try:
            js = http(html.unescape(s))
        except Exception:
            continue
        m = re.search(META_OP + r'_candidate_portalRelayOperation".*?a\.exports="(\d+)"', js)
        if m:
            return m.group(1)
    return None


def fetch_meta():
    page = http("https://www.metacareers.com/jobsearch/", headers={
        "Accept": "text/html", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", "Sec-Fetch-Dest": "document"})
    m = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', page)
    if not m:
        raise RuntimeError("Token LSD di Meta non trovato")
    lsd = m.group(1)

    def query(doc_id):
        variables = {"isLoggedIn": False, "viewasUserID": None,
                     "search_input": {"q": "", "results_per_page": None}}
        raw = http("https://www.metacareers.com/graphql", data={
            "lsd": lsd, "doc_id": doc_id, "variables": json.dumps(variables),
            "fb_api_req_friendly_name": META_OP,
        }, headers={"X-FB-LSD": lsd, "Origin": "https://www.metacareers.com",
                    "Referer": "https://www.metacareers.com/jobsearch/",
                    "Sec-Fetch-Site": "same-origin"})
        return json.loads(raw)["data"]["job_search_with_featured_jobs_v2"]["all_jobs"]

    try:
        all_jobs = query(META_DOC_ID)
    except Exception:
        doc_id = _meta_discover_doc_id(page)
        if not doc_id:
            raise
        all_jobs = query(doc_id)

    jobs = {}
    for j in all_jobs:
        locs = [(l, None) for l in j.get("locations") or []]
        job = make_job("Meta", j["id"], j["title"], f"https://www.metacareers.com/jobs/{j['id']}/", locs)
        if job:
            jobs[job["key"]] = job
    return jobs


# ----------------------------------------------------------------- email

def send_email(subject, body_html):
    user = os.environ["GMAIL_USER"]
    pwd = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("EMAIL_TO") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pwd)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())


def notify_github_issue(subject, jobs, intro):
    """Apre una issue nel repository: GitHub la invia per mail al proprietario."""
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    lines = [f"@{owner} " + intro.replace("<b>", "**").replace("</b>", "**"), ""]
    for company in ("Meta", "Microsoft", "Google"):
        group = sorted((j for j in jobs if j["company"] == company), key=lambda j: j["title"])
        if not group:
            continue
        lines.append(f"## {company} ({len(group)})")
        for j in group:
            locs = " · ".join(j["locations"][:3])
            lines.append(f"- [{j['title']}]({j['url']}) — {locs}")
        lines.append("")
    body = "\n".join(lines)
    if len(body) > 60000:
        body = body[:60000] + "\n\n…(elenco troncato)"
    repo = os.environ["GITHUB_REPOSITORY"]
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps({"title": subject, "body": body}).encode(),
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                 "Accept": "application/vnd.github+json", "User-Agent": "job-monitor"})
    urllib.request.urlopen(req, timeout=30).read()


def notify(subject, jobs, intro):
    if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        send_email(subject, jobs_html(jobs, intro))
    else:
        notify_github_issue(subject, jobs, intro)


def jobs_html(jobs, intro):
    colors = {"Meta": "#0866ff", "Microsoft": "#107c10", "Google": "#ea4335"}
    rows = []
    for company in ("Meta", "Microsoft", "Google"):
        group = sorted((j for j in jobs if j["company"] == company), key=lambda j: j["title"])
        if not group:
            continue
        rows.append(f'<h2 style="color:{colors[company]};margin:24px 0 8px">{company} ({len(group)})</h2>')
        for j in group:
            locs = html.escape(" · ".join(j["locations"][:4]))
            rows.append(
                f'<p style="margin:0 0 12px"><a href="{html.escape(j["url"])}" '
                f'style="font-size:15px;font-weight:600">{html.escape(j["title"])}</a>'
                f'<br><span style="color:#666;font-size:13px">{locs}</span></p>')
    return (f'<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:640px">'
            f'<p>{intro}</p>{"".join(rows)}'
            f'<p style="color:#999;font-size:12px;margin-top:32px">Job Monitor · filtri in config.py</p></div>')


# ----------------------------------------------------------------- main

def main():
    dry_run = "--dry-run" in sys.argv
    if "--test-notify" in sys.argv:
        notify("✅ Job Monitor: notifica di prova", [],
               "Se leggi questo messaggio per mail, le notifiche funzionano.")
        return
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    seen = state.get("seen", {})
    failures = state.get("failures", {})
    first_run = not seen

    sources = {"Meta": fetch_meta, "Microsoft": fetch_microsoft, "Google": fetch_google}
    current, errors = {}, {}
    for name, fn in sources.items():
        try:
            found = fn()
            current.update(found)
            failures[name] = 0
            print(f"{name}: {len(found)} posizioni corrispondenti")
        except Exception as e:
            failures[name] = failures.get(name, 0) + 1
            errors[name] = f"{type(e).__name__}: {e}"
            print(f"{name}: ERRORE {errors[name]}", file=sys.stderr)

    new = [j for k, j in current.items() if k not in seen]
    now = int(time.time())
    for k in current:
        seen.setdefault(k, now)

    if dry_run:
        for j in sorted(new, key=lambda j: (j["company"], j["title"])):
            print(f"  [{j['company']}] {j['title']} — {', '.join(j['locations'][:3])}\n    {j['url']}")
        print(f"\n{len(new)} nuove (dry run: nessuna mail, stato non salvato)")
        return

    if new and (not first_run or config.SEND_INITIAL_DIGEST):
        if first_run:
            subject = f"Job Monitor attivo: {len(new)} posizioni già aperte per te"
            intro = "Il monitoraggio è attivo. Queste sono le posizioni <b>già aperte</b> che corrispondono ai tuoi filtri; d'ora in poi riceverai solo le nuove."
        else:
            subject = f"🆕 {len(new)} nuov{'a posizione' if len(new) == 1 else 'e posizioni'}: " + \
                ", ".join(sorted({j['company'] for j in new}))
            intro = "Sono state pubblicate nuove posizioni che corrispondono ai tuoi filtri:"
        notify(subject, new, intro)
        print(f"Mail inviata: {subject}")

    broken = [n for n, c in failures.items() if c == FAILURE_ALERT_THRESHOLD]
    if broken:
        details = ", ".join(f"{n} ({errors.get(n, '')})" for n in broken)
        notify("⚠️ Job Monitor: un sito non risponde", [],
               f"Da {FAILURE_ALERT_THRESHOLD} controlli di fila non riesco a leggere: {details}. "
               "Probabilmente il sito ha cambiato struttura e lo script va aggiornato.")

    # tieni in memoria gli ID visti negli ultimi 180 giorni
    cutoff = now - 180 * 86400
    seen = {k: t for k, t in seen.items() if t >= cutoff or k in current}
    STATE_FILE.write_text(json.dumps({"seen": seen, "failures": failures}, indent=0, sort_keys=True))


if __name__ == "__main__":
    main()
