import requests
import os
import time
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACION
# ═══════════════════════════════════════════════════════════════
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",  "8792539683:AAEfgGUx15iTkFmqcIANr4A5OGNuI06yBOQ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1034250836")
ODDS_API_KEY     = os.environ.get("ODDS_API_KEY", "")

MIN_VALUE   = 0.03   # value minimo 3%
MIN_PROB    = 0.18   # probabilidad real minima 18%
MAX_ODDS    = 5.50   # cuota maxima
KELLY_FRAC  = 0.25   # quarter kelly
EJEMPLO_ARS = 10000  # pesos para ejemplo de ganancia
TOP_N       = 3      # picks a enviar por dia

DIAS_ES = {
    "Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miercoles",
    "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sabado","Sunday":"Domingo"
}

# Deportes — usando regiones eu,us que tienen mas bookmakers disponibles
SPORTS = [
    {"key": "soccer_argentina_primera_division", "name": "Liga Argentina",   "emoji": "🇦🇷"},
    {"key": "soccer_epl",                        "name": "Premier League",   "emoji": "🏴"},
    {"key": "soccer_spain_la_liga",              "name": "La Liga",          "emoji": "🇪🇸"},
    {"key": "soccer_uefa_champs_league",         "name": "Champions League", "emoji": "🏆"},
    {"key": "soccer_uefa_europa_league",         "name": "Europa League",    "emoji": "🇪🇺"},
    {"key": "soccer_brazil_campeonato",          "name": "Brasileirao",      "emoji": "🇧🇷"},
    {"key": "soccer_italy_serie_a",              "name": "Serie A",          "emoji": "🇮🇹"},
    {"key": "soccer_germany_bundesliga",         "name": "Bundesliga",       "emoji": "🇩🇪"},
    {"key": "soccer_france_ligue_one",           "name": "Ligue 1",          "emoji": "🇫🇷"},
    {"key": "basketball_nba",                    "name": "NBA",              "emoji": "🏀"},
    {"key": "mma_mixed_martial_arts",            "name": "MMA / UFC",        "emoji": "🥊"},
]

BPLAY = {
    "soccer_argentina_primera_division": "https://www.bplay.bet.ar/deportes/futbol/argentina/primera-division",
    "soccer_epl":                        "https://www.bplay.bet.ar/deportes/futbol/inglaterra/premier-league",
    "soccer_spain_la_liga":              "https://www.bplay.bet.ar/deportes/futbol/espana/la-liga",
    "soccer_uefa_champs_league":         "https://www.bplay.bet.ar/deportes/futbol/europa/champions-league",
    "soccer_uefa_europa_league":         "https://www.bplay.bet.ar/deportes/futbol/europa/europa-league",
    "soccer_brazil_campeonato":          "https://www.bplay.bet.ar/deportes/futbol/brasil/serie-a",
    "soccer_italy_serie_a":              "https://www.bplay.bet.ar/deportes/futbol/italia/serie-a",
    "soccer_germany_bundesliga":         "https://www.bplay.bet.ar/deportes/futbol/alemania/bundesliga",
    "soccer_france_ligue_one":           "https://www.bplay.bet.ar/deportes/futbol/francia/ligue-1",
    "basketball_nba":                    "https://www.bplay.bet.ar/deportes/basquet/usa/nba",
    "mma_mixed_martial_arts":            "https://www.bplay.bet.ar/deportes/mma",
}

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
def tg(text, chat_id=None):
    cid = str(chat_id or TELEGRAM_CHAT_ID)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": cid, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def tg_long(text, chat_id=None):
    for i in range(0, len(text), 4000):
        tg(text[i:i+4000], chat_id)
        if len(text) > 4000:
            time.sleep(0.5)

def get_updates(offset=None):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 30, "offset": offset},
            timeout=35
        )
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ═══════════════════════════════════════════════════════════════
#  ODDS API — sin filtrar por bookmaker especifico
# ═══════════════════════════════════════════════════════════════
def fetch_sport(sport_key):
    """Trae cuotas de UN deporte usando todas las fuentes disponibles."""
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=eu,us"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
    )
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            data = r.json()
            print(f"  OK {sport_key}: {len(data)} partidos")
            return data
        else:
            print(f"  SKIP {sport_key}: status {r.status_code}")
    except Exception as e:
        print(f"  ERROR {sport_key}: {e}")
    return []

# ═══════════════════════════════════════════════════════════════
#  ANALISIS
# ═══════════════════════════════════════════════════════════════
def analyze(games, sport):
    """Analiza los partidos de un deporte y devuelve candidatos con value."""
    picks = []

    for game in games:
        bms = game.get("bookmakers", [])
        if len(bms) < 2:
            continue

        home = game.get("home_team", "?")
        away = game.get("away_team", "?")

        # Fecha en hora argentina
        try:
            dt = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
            dt_ar = dt - timedelta(hours=3)
            fecha = dt_ar.strftime("%A %d/%m a las %H:%M")
            for en, es in DIAS_ES.items():
                fecha = fecha.replace(en, es)
        except:
            fecha = "—"

        # Mejores cuotas y promedio por resultado
        best  = {}   # outcome -> {price, book}
        total = {}   # outcome -> [precios]

        for bm in bms:
            for mkt in bm.get("markets", []):
                if mkt["key"] != "h2h":
                    continue
                for oc in mkt["outcomes"]:
                    name  = oc["name"]
                    price = oc["price"]
                    total.setdefault(name, []).append(price)
                    if name not in best or price > best[name]["price"]:
                        best[name] = {"price": price, "book": bm["title"]}

        if len(best) < 2:
            continue

        # Suma inversa = margen del mercado
        sum_inv = sum(1/best[k]["price"] for k in best)

        for outcome, info in best.items():
            odds      = info["price"]
            fair_prob = (1/odds) / sum_inv
            value     = (fair_prob * odds) - 1
            kelly_raw = max(0, (fair_prob * odds - 1) / (odds - 1)) if odds > 1 else 0
            kelly_q   = kelly_raw * KELLY_FRAC

            # Promedio de cuotas del mercado para este resultado
            avg = sum(total[outcome]) / len(total[outcome])
            edge = (odds - avg) / avg

            if (value >= MIN_VALUE
                    and fair_prob >= MIN_PROB
                    and odds <= MAX_ODDS
                    and kelly_q >= 0.005):

                picks.append({
                    "sport":      sport,
                    "match":      f"{home} vs {away}",
                    "selection":  outcome,
                    "odds":       odds,
                    "book":       info["book"],
                    "fair_prob":  fair_prob,
                    "value":      value,
                    "kelly_q":    kelly_q,
                    "fecha":      fecha,
                    "score":      value * 0.6 + edge * 0.4,
                    "ganancia":   round(EJEMPLO_ARS * odds - EJEMPLO_ARS),
                    "retorno":    round(EJEMPLO_ARS * odds),
                })

    return picks

# ═══════════════════════════════════════════════════════════════
#  ANALISIS COMPLETO
# ═══════════════════════════════════════════════════════════════
def full_analysis():
    print(f"\n[{datetime.now()}] Iniciando analisis...")
    all_picks = []
    total_games = 0

    for sport in SPORTS:
        games = fetch_sport(sport["key"])
        total_games += len(games)
        picks = analyze(games, sport)
        all_picks.extend(picks)
        time.sleep(0.5)

    all_picks.sort(key=lambda x: x["score"], reverse=True)
    print(f"  Total: {total_games} partidos → {len(all_picks)} con value")
    return all_picks, total_games

# ═══════════════════════════════════════════════════════════════
#  BUSQUEDA DE PARTIDO
# ═══════════════════════════════════════════════════════════════
def buscar_partido(query):
    """Busca un partido y devuelve analisis detallado."""
    words = [w.lower() for w in query.split() if len(w) >= 3]
    if not words:
        return None

    best_game  = None
    best_sport = None
    best_hits  = 0

    for sport in SPORTS:
        games = fetch_sport(sport["key"])
        time.sleep(0.4)
        for game in games:
            texto = (game.get("home_team","") + " " + game.get("away_team","")).lower()
            hits = sum(1 for w in words if w in texto)
            if hits > best_hits:
                best_hits  = hits
                best_game  = game
                best_sport = sport
        if best_hits >= len(words):
            break

    if not best_game or best_hits == 0:
        return None

    return analisis_partido(best_game, best_sport)

def analisis_partido(game, sport):
    home  = game.get("home_team", "?")
    away  = game.get("away_team", "?")

    try:
        dt = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
        dt_ar = dt - timedelta(hours=3)
        fecha = dt_ar.strftime("%A %d/%m a las %H:%M")
        for en, es in DIAS_ES.items():
            fecha = fecha.replace(en, es)
    except:
        fecha = "—"

    # Recopilar cuotas
    best = {}
    for bm in game.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "h2h":
                continue
            for oc in mkt["outcomes"]:
                name, price = oc["name"], oc["price"]
                if name not in best or price > best[name]["price"]:
                    best[name] = {"price": price, "book": bm["title"]}

    if len(best) < 2:
        return f"❌ No hay cuotas disponibles para {home} vs {away} todavia."

    sum_inv = sum(1/best[k]["price"] for k in best)
    margin  = (sum_inv - 1) * 100

    lines = []
    lines.append(f"🔍 <b>{home} vs {away}</b>")
    lines.append(f"{sport['emoji']} {sport['name']}  |  🕐 {fecha}")
    lines.append(f"Margen de la casa: {margin:.1f}%")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<b>RESULTADO FINAL:</b>")
    lines.append("")

    sorted_oc = sorted(best.items(), key=lambda x: 1/x[1]["price"], reverse=True)

    for outcome, info in sorted_oc:
        odds      = info["price"]
        fair_prob = (1/odds) / sum_inv
        value     = (fair_prob * odds) - 1
        kelly_raw = max(0, (fair_prob * odds - 1) / (odds - 1)) if odds > 1 else 0
        kelly_q   = kelly_raw * KELLY_FRAC * 100
        ganancia  = round(EJEMPLO_ARS * odds - EJEMPLO_ARS)
        ej_f      = f"${EJEMPLO_ARS:,.0f}".replace(",",".")
        gan_f     = f"${ganancia:,.0f}".replace(",",".")

        if value >= MIN_VALUE and fair_prob >= MIN_PROB:
            dot = "🟢"
            tag = " ← <b>VALUE</b>"
        elif value >= 0:
            dot = "🟡"
            tag = ""
        else:
            dot = "🔴"
            tag = ""

        lines.append(
            f"{dot} <b>{outcome}</b>{tag}\n"
            f"   Cuota: <b>{odds:.2f}</b>  |  Prob. real: <b>{fair_prob*100:.0f}%</b>  |  Value: <b>{value*100:+.1f}%</b>\n"
            f"   Apostas {ej_f} → ganas <b>{gan_f} ARS</b>"
        )
        if value >= MIN_VALUE and fair_prob >= MIN_PROB:
            lines.append(f"   Kelly: <b>{kelly_q:.1f}% del bankroll</b>")
        lines.append("")

    link = BPLAY.get(sport["key"], "https://www.bplay.bet.ar/deportes")
    lines.append(f"🔗 <a href='{link}'>Buscar en bplay →</a>")
    lines.append("⚠️ <i>Analisis matematico, no garantia.</i>")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
#  MENSAJE DIARIO
# ═══════════════════════════════════════════════════════════════
def mensaje_diario(picks, total):
    now    = datetime.now().strftime("%d/%m/%Y")
    medals = ["🥇", "🥈", "🥉"]
    lines  = []

    lines.append("⚡ <b>BETEDGE — PICKS DEL DIA</b>")
    lines.append(f"📅 {now}  |  {total} partidos analizados")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not picks:
        lines.append("\n📭 <b>Hoy no hay apuestas con ventaja matematica clara.</b>")
        lines.append("Mejor no apostar que apostar sin edge.")
        lines.append("\n💡 Escribe los nombres de un partido para consultarme sus cuotas.")
        lines.append("\n🤖 <i>BetEdge Bot</i>")
        return "\n".join(lines)

    for i, p in enumerate(picks[:TOP_N]):
        sport   = p["sport"]
        ej_f    = f"${EJEMPLO_ARS:,.0f}".replace(",",".")
        gan_f   = f"${p['ganancia']:,.0f}".replace(",",".")
        ret_f   = f"${p['retorno']:,.0f}".replace(",",".")
        prob_f  = f"{p['fair_prob']*100:.0f}%"
        val_f   = f"{p['value']*100:+.1f}%"
        kell_f  = f"{p['kelly_q']*100:.1f}%"

        if p["value"] >= 0.10:
            conf = "🔥 MUY ALTA"
        elif p["value"] >= 0.06:
            conf = "✅ ALTA"
        else:
            conf = "📊 MODERADA"

        link = BPLAY.get(sport["key"], "https://www.bplay.bet.ar/deportes")

        lines.append(f"\n{medals[i]} <b>PICK #{i+1}</b>")
        lines.append("─────────────────────────")
        lines.append(f"{sport['emoji']} <b>{p['match']}</b>")
        lines.append(f"🏆 {sport['name']}  |  🕐 {p['fecha']}")
        lines.append("")
        lines.append(f"📌 <b>APOSTAR A: {p['selection'].upper()}</b>")
        lines.append(f"💰 Cuota: <b>{p['odds']:.2f}</b>  |  Prob. real: <b>{prob_f}</b>")
        lines.append(f"📈 Value: <b>{val_f}</b>  |  Confianza: {conf}")
        lines.append("")
        lines.append(f"💵 <b>EJEMPLO DE GANANCIA:</b>")
        lines.append(f"   Apostas {ej_f} ARS")
        lines.append(f"   → Ganas <b>{gan_f} ARS</b> netos")
        lines.append(f"   → Retorno total: <b>{ret_f} ARS</b>")
        lines.append("")
        lines.append(f"💼 Kelly: <b>{kell_f} de tu bankroll</b>")
        lines.append(f"📊 Referencia de cuota: {p['book']}")
        lines.append(f"🔗 <a href='{link}'>Buscar en bplay →</a>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Escribe los equipos de cualquier partido para ver sus probabilidades.</i>")
    lines.append("⚠️ <i>Analisis matematico, no garantia. Juga con responsabilidad.</i>")
    lines.append("\n🤖 <i>BetEdge Bot</i>")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
#  HANDLER DE MENSAJES
# ═══════════════════════════════════════════════════════════════
def handle(text, chat_id):
    t = text.strip()
    tl = t.lower()

    if tl in ["/start", "/help", "hola", "ayuda"]:
        tg(
            "👋 <b>BetEdge Bot</b>\n\n"
            "Todos los dias a las 8AM recibis automaticamente los mejores picks del dia.\n\n"
            "<b>Comandos:</b>\n"
            "▸ Escribi <code>/picks</code> para pedir el analisis ahora\n"
            "▸ Escribi los equipos de un partido para ver sus cuotas:\n"
            "  <code>Arsenal Chelsea</code>\n"
            "  <code>River Boca</code>\n"
            "  <code>Lakers Warriors</code>\n\n"
            "⚠️ <i>Solo partidos de los proximos dias disponibles en la API.</i>",
            chat_id
        )
        return

    if tl in ["/picks", "picks"]:
        tg("🔄 Analizando... espera 1-2 minutos.", chat_id)
        picks, total = full_analysis()
        tg_long(mensaje_diario(picks, total), chat_id)
        return

    # Busqueda de partido
    tg(f"🔍 Buscando <b>{t}</b>...", chat_id)
    resultado = buscar_partido(t)
    if resultado:
        tg_long(resultado, chat_id)
    else:
        tg(
            f"❌ No encontre <b>{t}</b> entre los partidos disponibles.\n\n"
            "Recordá: solo puedo analizar partidos de los proximos dias.\n"
            "Ligas disponibles: Liga Argentina, Premier, La Liga, Serie A, Bundesliga, Ligue 1, NBA, MMA",
            chat_id
        )

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not ODDS_API_KEY:
        tg("⚠️ Falta configurar ODDS_API_KEY en Railway → Variables.")
        exit(1)

    print(f"[{datetime.now()}] BetEdge Bot iniciando...")

    # Analisis diario al arrancar
    picks, total = full_analysis()
    tg_long(mensaje_diario(picks, total))
    print(f"[{datetime.now()}] Picks enviados. Escuchando mensajes...")

    # Descartar mensajes viejos
    old = get_updates()
    offset = (old[-1]["update_id"] + 1) if old else None
    if old:
        print(f"  Descartados {len(old)} mensajes viejos.")

    # Loop de escucha
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg    = upd.get("message", {})
            text   = msg.get("text", "")
            cid    = msg.get("chat", {}).get("id")
            if text and cid:
                if str(cid) == str(TELEGRAM_CHAT_ID):
                    print(f"  Mensaje: {text}")
                    handle(text, cid)
                else:
                    tg("⛔ No autorizado.", cid)
        time.sleep(1)
