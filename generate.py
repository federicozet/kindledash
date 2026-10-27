"""Genera la pagina del pannello Kindle. Legge la configurazione dalle variabili d'ambiente
(in GitHub: Settings > Secrets and variables > Actions) cosi' nel repository non finiscono indirizzi di casa."""
import csv, io, json, os, html, urllib.request, urllib.parse
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
WMO = {0: "Sereno", 1: "Poco nuvoloso", 2: "Parzialmente nuvoloso", 3: "Coperto", 45: "Nebbia",
       48: "Nebbia", 51: "Pioggerella", 53: "Pioggerella", 55: "Pioggerella", 61: "Pioggia debole",
       63: "Pioggia", 65: "Pioggia forte", 71: "Neve", 73: "Neve", 75: "Neve forte",
       80: "Rovesci", 81: "Rovesci", 82: "Rovesci forti", 95: "Temporale", 96: "Temporale", 99: "Temporale"}

def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")

def esc(s):
    return html.escape(str(s or ""))

def meteo():
    lat, lon = os.environ.get("LAT"), os.environ.get("LON")
    if not (lat and lon):
        return None
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "Europe/Rome", "forecast_days": 1,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
    d = json.loads(get("https://api.open-meteo.com/v1/forecast?" + q))
    return {"temp": round(d["current"]["temperature_2m"]),
            "cond": WMO.get(d["current"]["weather_code"], "Variabile"),
            "vento": round(d["current"]["wind_speed_10m"]),
            "min": round(d["daily"]["temperature_2m_min"][0]),
            "max": round(d["daily"]["temperature_2m_max"][0]),
            "pioggia": d["daily"]["precipitation_probability_max"][0] or 0}

def percorsi():
    """ROUTES_JSON = [{"nome":"Studio","da":"indirizzo","a":"indirizzo"}]  +  chiave GOOGLE_API_KEY"""
    key, raw = os.environ.get("GOOGLE_API_KEY"), os.environ.get("ROUTES_JSON")
    if not (key and raw):
        return []
    out = []
    for r in json.loads(raw):
        body = json.dumps({"origin": {"address": r["da"]}, "destination": {"address": r["a"]},
                           "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE"}).encode()
        h = {"Content-Type": "application/json", "X-Goog-Api-Key": key,
             "X-Goog-FieldMask": "routes.duration,routes.staticDuration"}
        try:
            rt = json.loads(get("https://routes.googleapis.com/directions/v2:computeRoutes", body, h))["routes"][0]
            tot = int(rt["duration"].rstrip("s")) // 60
            base = int(rt["staticDuration"].rstrip("s")) // 60
            extra = tot - base
            out.append((r["nome"], f"{tot} min", f"+{extra} min di traffico" if extra >= 3 else "regolare"))
        except Exception as e:
            print("Percorso non disponibile:", r.get("nome"), e)
    return out

def csv_rows(var):
    url = os.environ.get(var)
    if not url:
        return []
    return list(csv.DictReader(io.StringIO(get(url))))

def agenda(oggi):
    url = os.environ.get("ICAL_URL")
    if not url:
        return []
    import icalendar, recurring_ical_events
    cal = icalendar.Calendar.from_ical(get(url))
    ini = datetime.combine(oggi, datetime.min.time(), TZ)
    ev = []
    for e in recurring_ical_events.of(cal).between(ini, ini + timedelta(days=2)):
        s = e.get("DTSTART").dt
        if isinstance(s, datetime):
            s = s.astimezone(TZ)
            ev.append((s, s.strftime("%H:%M"), str(e.get("SUMMARY", ""))))
        else:
            ev.append((datetime.combine(s, datetime.min.time(), TZ), "Tutto il giorno", str(e.get("SUMMARY", ""))))
    ev.sort(key=lambda x: x[0])
    return [(("Domani " if x[0].date() > oggi else "") + x[1], x[2]) for x in ev][:8]

def tab(righe):
    return "<table>" + "".join(righe) + "</table>" if righe else ""

def scuola(rows, giorno):
    d = giorno.isoformat()
    righe = []
    for r in rows:
        if (r.get("data") or "").strip() != d:
            continue
        testo = (r.get("materie") or r.get("mensa") or "").strip()
        if testo:
            nome = (r.get("bambino") or "").strip()
            nome = "Mensa" if (r.get("mensa") or "").strip() else nome.capitalize()
            righe.append(f"<tr><td>{esc(nome)}</td><td>{esc(testo)}</td></tr>")
    return tab(righe) or "<p>Nessun dato inserito.</p>"

PAGINA = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><meta http-equiv="refresh" content="300">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pannello di casa</title>
<style>
body{margin:0;padding:8px 12px 70px;background:#fff;color:#000;font-family:Georgia,"Times New Roman",serif;font-size:20px;line-height:1.3}
h2{font-size:22px;margin:0 0 6px;padding-top:10px;border-top:3px solid #000}
.ora{font-family:Helvetica,Arial,sans-serif;font-size:96px;font-weight:bold;text-align:center;line-height:1;margin:6px 0 0}
.data{text-align:center;font-size:24px;padding-bottom:8px}
.meteo{overflow:hidden;padding:6px 0}
.temp{float:left;font-family:Helvetica,Arial,sans-serif;font-size:64px;font-weight:bold;margin-right:16px}
.cond{font-size:26px;font-weight:bold}
table{width:100%;border-collapse:collapse}
td{padding:6px 4px;border-bottom:1px solid #888;vertical-align:top}
td.r{text-align:right;white-space:nowrap;font-weight:bold}
.pic{font-size:16px;color:#444;font-weight:normal;display:block}
.nav{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:3px solid #000;text-align:center;padding:6px 0;font-family:Helvetica,Arial,sans-serif}
.nav a{display:inline-block;padding:8px 10px;margin:0 2px;border:2px solid #000;color:#000;text-decoration:none;font-size:16px}
.agg{font-size:14px;color:#444;text-align:center;margin-top:10px}
</style></head><body>
<div id="oggi">
<p class="ora" id="ora">{ora}</p>
<p class="data">{data}</p>
{blocco_meteo}{blocco_percorsi}
</div>
<div id="scuola"><h2>Oggi a scuola</h2>{scuola_oggi}<h2>Domani</h2>{scuola_domani}</div>
<div id="agenda"><h2>Agenda</h2>{agenda}</div>
<div id="dafare"><h2>Da fare</h2>{dafare}</div>
<p class="agg">Aggiornato {agg}</p>
<div class="nav"><a href="#oggi">Oggi</a><a href="#scuola">Scuola</a><a href="#agenda">Agenda</a><a href="#dafare">Da fare</a></div>
<script>
function t(){var d=new Date(),h=d.getHours(),m=d.getMinutes();document.getElementById('ora').innerHTML=(h<10?'0':'')+h+':'+(m<10?'0':'')+m;}
t();setInterval(t,30000);
</script></body></html>"""

def main():
    adesso = datetime.now(TZ)
    oggi = adesso.date()
    parti = {}
    def prova(nome, f, vuoto):
        try:
            return f()
        except Exception as e:
            print("Errore", nome, e)
            return vuoto
    m = prova("meteo", meteo, None)
    parti["blocco_meteo"] = (f'<div class="meteo"><span class="temp">{m["temp"]}°</span>'
        f'<span class="cond">{esc(m["cond"])}</span><br>Min {m["min"]}° · max {m["max"]}° · '
        f'vento {m["vento"]} km/h · pioggia {m["pioggia"]}%</div>') if m else ""
    p = prova("percorsi", percorsi, [])
    parti["blocco_percorsi"] = tab([f'<tr><td>{esc(n)}</td><td class="r">{esc(t)}<span class="pic">{esc(s)}</span></td></tr>'
                                    for n, t, s in p])
    sc = prova("scuola", lambda: csv_rows("SCUOLA_CSV_URL"), [])
    parti["scuola_oggi"] = scuola(sc, oggi)
    parti["scuola_domani"] = scuola(sc, oggi + timedelta(days=1))
    ag = prova("agenda", lambda: agenda(oggi), [])
    parti["agenda"] = tab([f'<tr><td class="r">{esc(o)}</td><td>{esc(t)}</td></tr>' for o, t in ag]) or "<p>Niente in programma.</p>"
    df = prova("dafare", lambda: csv_rows("DAFARE_CSV_URL"), [])
    voci = [r for r in df if (r.get("cosa") or "").strip() and (r.get("fatto") or "").strip().lower() not in ("si", "sì", "x", "true", "1")]
    parti["dafare"] = tab([f'<tr><td>☐ {esc(r["cosa"])}</td></tr>' for r in voci]) or "<p>Niente da fare.</p>"
    parti["ora"] = adesso.strftime("%H:%M")
    parti["data"] = f"{GIORNI[oggi.weekday()]} {oggi.day} {MESI[oggi.month - 1]}"
    parti["agg"] = adesso.strftime("%d/%m %H:%M")
    pagina = PAGINA
    for k, v in parti.items():
        pagina = pagina.replace("{" + k + "}", v)
    cartella = os.path.join("site", os.environ.get("PAGINA") or "pannello")
    os.makedirs(cartella, exist_ok=True)
    open(os.path.join(cartella, "index.html"), "w", encoding="utf-8").write(pagina)
    open(os.path.join("site", "index.html"), "w").write("")

if __name__ == "__main__":
    main()
