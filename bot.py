import requests
import os
import time
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",  "8792539683:AAEfgGUx15iTkFmqcIANr4A5OGNuI06yBOQ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1034250836")
ODDS_API_KEY     = os.environ.get("ODDS_API_KEY", "")

# Filtros de calidad
MIN_VALUE    = 0.03   # value mínimo +3%
MIN_PROB     = 0.18   # probabilidad real mínima 18%
MAX_ODDS     = 5.50   # cuota máxima
MIN_KELLY    = 0.005  # kelly mínimo
KELLY_FRAC   = 0.25   # fracción kelly conservadora (quarter kelly)
EJEMPLO_ARS  = 10000  # monto ejemplo para mostrar ganancias

# Mercados a analizar
MARKETS = "h2h,totals,btts"

# Bookmakers — bplay primero
BOOKMAKERS = "bplay,betsson,codere,bet365,pinnacle,williamhill,unibet,bwin"

# Nombres legibles para cada mercado
MARKET_LABEL = {
    "h2h":    "Resultado final (1X2)",
    "totals": "Más/menos goles",
    "btts":   "Ambos equipos anotan",
}

# Deportes disponibles
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
    {"key": "soccer_usa_mls",                    "name": "MLS",              "emoji": "🇺🇸"},
    {"key": "basketball_nba",                    "name": "NBA",              "emoji": "🏀"},
    {"key": "basketball_euroleague",             "name": "Euroliga",         "emoji": "🏀"},
    {"key": "americanfootball_nfl",              "name": "NFL",              "emoji": "🏈"},
    {"key": "mma_mixed_martial_arts",            "name": "MMA / UFC",        "emoji": "🥊"},
    {"key": "tennis_atp_french_open",            "name": "ATP Tenis",        "emoji": "🎾"},
    {"key": "tennis_wta_french_open",            "name": "WTA Tenis",        "emoji": "🎾"},
]

BPLAY_ROUTES = {
    "soccer_argentina_primera_division": "/deportes/futbol/argentina/primera-division",
    "soccer_epl":                        "/deportes/futbol/inglaterra/premier-league",
    "soccer_spain_la_liga":              "/deportes/futbol/espana/la-liga",
    "soccer_uefa_champs_league":         "/deportes/futbol/europa/champions-league",
    "soccer_uefa_europa_league":         "/deportes/futbol/europa/europa-league",
    "soccer_brazil_campeonato":          "/deportes/futbol/brasil/serie-a",
    "soccer_italy_serie_a":              "/deportes/futbol/italia/serie-a",
    "soccer_germany_bundesliga":         "/deportes/futbol/alemania/bundesliga",
    "soccer_france_ligue_one":           "/deportes/futbol/francia/ligue-1",
    "soccer_usa_mls":                    "/deportes/futbol/usa/mls",
    "basketball_nba":                    "/deportes/basquet/usa/nba",
    "basketball_euroleague":             "/deportes/basquet/europa/euroliga",
    "americanfootball_nfl":              "/deportes/football-americano/usa/nfl",
    "mma_mixed_martial_arts":            "/deportes/mma",
    "tennis_atp_french_open":            "/deportes/tenis",
    "tennis_wta_french_open":            "/deportes/tenis",
}

def bplay_url(sport_key):
    return "https://www.bplay.bet.ar" + BPLAY_ROUTES.get(sport_key, "/deportes")

# ═══════════════════════════════════════════════════════════════
#  HELPERS — FECHA
# ═══════════════════════════════════════════════════════════════
DIAS_ES = {
    "Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
    "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"
}

def parse_date(commence):
    try:
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        dt_ar = dt - timedelta(hours=3)
        s = dt_ar.strftime("%A %d/%m a las %H:%M")
        for en, es in DIAS_ES.items():
            s = s.replace(en, es)
        return s
    except:
        return "—"

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
def tg_send(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": cid, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True
        }, timeout=15)
        return r.status_code == 200
    except:
        return False

def tg_send_long(text, chat_id=None):
    if len(text) <= 4000:
        tg_send(text, chat_id)
    else:
        for i in range(0, len(text), 4000):
            tg_send(text[i:i+4000], chat_id)
            time.sleep(0.5)

def tg_get_updates(offset=None):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 30, "offset": offset}, timeout=35
        )
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ═══════════════════════════════════════════════════════════════
#  API DE CUOTAS
# ═══════════════════════════════════════════════════════════════
def fetch_odds(sport_key, markets=MARKETS):
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}&regions=eu,us,au"
        f"&markets={markets}&oddsFormat=decimal&bookmakers={BOOKMAKERS}"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  Error {sport_key}: {e}")
    return []

def fetch_all():
    """Descarga partidos de todos los deportes."""
    all_games = []
    for sport in SPORTS:
        games = fetch_odds(sport["key"])
        for g in games:
            g["_sport"] = sport
        all_games.extend(games)
        if games:
            print(f"  {sport['emoji']} {sport['name']}: {len(games)} partidos")
        time.sleep(0.35)
    return all_games

# ═══════════════════════════════════════════════════════════════
#  MOTOR DE ANÁLISIS
# ═══════════════════════════════════════════════════════════════
def extract_markets(game):
    """
    Extrae de un partido:
      best[market][outcome]  = {price, bookmaker}   ← mejor cuota general
      bplay[market][outcome] = price                 ← cuota de bplay si existe
      all_prices[market][outcome] = [lista precios]  ← para calcular promedio
    """
    best       = {}
    bplay      = {}
    all_prices = {}

    for bm in game.get("bookmakers", []):
        is_bplay = "bplay" in bm["title"].lower()
        for mkt in bm.get("markets", []):
            mk = mkt["key"]
            if mk not in best:
                best[mk] = {}
                bplay[mk] = {}
                all_prices[mk] = {}

            for oc in mkt.get("outcomes", []):
                name = oc["name"]
                if mk == "totals" and "point" in oc:
                    name = f"{name} {oc['point']}"
                price = oc["price"]

                all_prices[mk].setdefault(name, []).append(price)

                if name not in best[mk] or price > best[mk][name]["price"]:
                    best[mk][name] = {"price": price, "bookmaker": bm["title"]}

                if is_bplay:
                    bplay[mk][name] = price

    return best, bplay, all_prices


def score_outcome(best_price, analysis_price, all_p):
    """Calcula fair_prob, value, kelly y score para un resultado."""
    # Esto se llama desde un contexto donde ya tenemos sum_inv
    # Devuelve un dict con los números clave
    pass  # se calcula inline abajo


def analyze_game_all_markets(game):
    """
    Analiza todos los mercados de un partido.
    Devuelve lista de candidatos con value positivo.
    """
    sport  = game["_sport"]
    home   = game.get("home_team", "?")
    away   = game.get("away_team", "?")
    date_s = parse_date(game.get("commence_time", ""))

    best, bplay, all_prices = extract_markets(game)
    candidates = []

    for mk, outcomes in best.items():
        if len(outcomes) < 2:
            continue

        sum_inv = sum(1 / outcomes[k]["price"] for k in outcomes)

        for outcome, info in outcomes.items():
            best_price     = info["price"]
            bookmaker      = info["bookmaker"]
            analysis_price = bplay.get(mk, {}).get(outcome, best_price)
            from_bplay     = outcome in bplay.get(mk, {})

            fair_prob  = (1 / best_price) / sum_inv
            value      = (fair_prob * analysis_price) - 1
            kelly_raw  = max(0, (fair_prob * analysis_price - 1) / (analysis_price - 1)) if analysis_price > 1 else 0
            kelly_q    = kelly_raw * KELLY_FRAC

            avg_p      = sum(all_prices[mk].get(outcome, [analysis_price])) / max(1, len(all_prices[mk].get(outcome, [analysis_price])))
            odds_edge  = (analysis_price - avg_p) / avg_p if avg_p > 0 else 0
            score      = value * 0.7 + odds_edge * 0.3

            if (value >= MIN_VALUE and fair_prob >= MIN_PROB
                    and analysis_price <= MAX_ODDS and kelly_q >= MIN_KELLY):

                candidates.append({
                    "sport":        sport,
                    "match":        f"{home} vs {away}",
                    "home": home,   "away": away,
                    "market_key":   mk,
                    "market_label": MARKET_LABEL.get(mk, mk),
                    "selection":    outcome,
                    "odds":         analysis_price,
                    "bookmaker":    "bplay" if from_bplay else bookmaker,
                    "from_bplay":   from_bplay,
                    "fair_prob":    fair_prob,
                    "value":        value,
                    "kelly_q":      kelly_q,
                    "date_str":     date_s,
                    "score":        score,
                    "ganancia":     EJEMPLO_ARS * analysis_price - EJEMPLO_ARS,
                    "retorno":      EJEMPLO_ARS * analysis_price,
                })

    return candidates


def run_full_analysis():
    """Corre el análisis completo de todos los deportes."""
    print(f"[{datetime.now()}] Descargando cuotas...")
    all_games = fetch_all()
    print(f"  Total: {len(all_games)} partidos")

    all_candidates = []
    for game in all_games:
        all_candidates.extend(analyze_game_all_markets(game))

    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    return all_candidates, len(all_games)

# ═══════════════════════════════════════════════════════════════
#  BÚSQUEDA DE PARTIDO POR NOMBRE
# ═══════════════════════════════════════════════════════════════
def search_and_analyze_match(query):
    """
    Busca un partido por nombre en todos los deportes.
    Devuelve el mensaje de análisis o None si no lo encuentra.
    """
    words = [w.lower() for w in query.split() if len(w) >= 3]
    if not words:
        return None

    best_match = None
    best_match_sport = None
    best_score = 0

    for sport in SPORTS:
        games = fetch_odds(sport["key"])
        time.sleep(0.3)
        for game in games:
            home = game.get("home_team", "").lower()
            away = game.get("away_team", "").lower()
            full = home + " " + away
            # contar cuántas palabras del query aparecen en el partido
            hits = sum(1 for w in words if w in full)
            if hits > best_score:
                best_score = hits
                game["_sport"] = sport
                best_match = game
                best_match_sport = sport

        if best_score >= len(words):
            break  # encontró todo, no seguir buscando

    if not best_match or best_score == 0:
        return None

    return build_match_analysis(best_match)


def build_match_analysis(game):
    """Construye el mensaje de análisis detallado de un partido."""
    sport  = game["_sport"]
    home   = game.get("home_team", "?")
    away   = game.get("away_team", "?")
    date_s = parse_date(game.get("commence_time", ""))

    best, bplay_d, all_prices = extract_markets(game)

    lines = []
    lines.append(f"🔍 <b>{home} vs {away}</b>")
    lines.append(f"{sport['emoji']} {sport['name']}  |  🕐 {date_s}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not best:
        lines.append("⚠️ No hay cuotas disponibles para este partido todavía.")
        return "\n".join(lines)

    for mk, outcomes in best.items():
        if len(outcomes) < 2:
            continue

        label = MARKET_LABEL.get(mk, mk)
        sum_inv = sum(1 / outcomes[k]["price"] for k in outcomes)
        margin = (sum_inv - 1) * 100

        lines.append(f"\n📋 <b>{label}</b>  <i>(margen casa: {margin:.1f}%)</i>")

        # Ordenar por probabilidad desc
        sorted_oc = sorted(outcomes.items(), key=lambda x: 1/x[1]["price"], reverse=True)

        for outcome, info in sorted_oc:
            price      = bplay_d.get(mk, {}).get(outcome, info["price"])
            fair_prob  = (1 / info["price"]) / sum_inv
            value      = (fair_prob * price) - 1
            kelly_raw  = max(0, (fair_prob * price - 1) / (price - 1)) if price > 1 else 0
            kelly_q    = kelly_raw * KELLY_FRAC * 100
            ganancia   = EJEMPLO_ARS * price - EJEMPLO_ARS
            ejemplo_f  = f"${EJEMPLO_ARS:,.0f}".replace(",",".")
            ganancia_f = f"${ganancia:,.0f}".replace(",",".")

            # Indicador visual
            if value >= MIN_VALUE and fair_prob >= MIN_PROB and kelly_q/100 >= MIN_KELLY:
                dot = "🟢"
                rec = " ← <b>HAY VALUE</b>"
            elif value >= 0:
                dot = "🟡"
                rec = ""
            else:
                dot = "🔴"
                rec = ""

            lines.append(
                f"  {dot} <b>{outcome}</b>{rec}\n"
                f"       Cuota: <b>{price:.2f}</b>  |  Prob. real: <b>{fair_prob*100:.0f}%</b>  |  Value: <b>{value*100:+.1f}%</b>\n"
                f"       Si apostás {ejemplo_f} → ganás <b>{ganancia_f} ARS</b>"
            )
            if value >= MIN_VALUE and fair_prob >= MIN_PROB:
                lines.append(f"       Kelly recomendado: <b>{kelly_q:.1f}% del bankroll</b>")

    lines.append(f"\n🔗 <a href='{bplay_url(sport['key'])}'>Ver en bplay →</a>")
    lines.append("\n⚠️ <i>Análisis matemático, no garantía. Jugá con responsabilidad.</i>")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
#  MENSAJE PICKS DIARIOS
# ═══════════════════════════════════════════════════════════════
def build_daily_message(top3, total_games):
    now = datetime.now().strftime("%d/%m/%Y")
    lines = []
    lines.append(f"⚡ <b>BETEDGE — PICKS DEL DÍA</b>")
    lines.append(f"📅 {now}  |  {total_games} partidos analizados en bplay")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not top3:
        lines.append("\n📭 <b>Hoy no hay apuestas con ventaja matemática clara.</b>")
        lines.append("Es mejor no apostar que apostar sin edge.")
        lines.append("\n💡 <i>Consultame cualquier partido escribiendo los nombres de los equipos.</i>")
        lines.append("\n🤖 <i>BetEdge Bot</i>")
        return "\n".join(lines)

    medals = ["🥇", "🥈", "🥉"]
    for i, b in enumerate(top3):
        sport     = b["sport"]
        ej_f      = f"${EJEMPLO_ARS:,.0f}".replace(",",".")
        gan_f     = f"${b['ganancia']:,.0f}".replace(",",".")
        ret_f     = f"${b['retorno']:,.0f}".replace(",",".")
        prob_f    = f"{b['fair_prob']*100:.0f}%"
        value_f   = f"{b['value']*100:+.1f}%"
        kelly_f   = f"{b['kelly_q']*100:.1f}%"

        if b["value"] >= 0.10:
            conf_emoji, conf = "🔥", "MUY ALTA"
        elif b["value"] >= 0.06:
            conf_emoji, conf = "✅", "ALTA"
        else:
            conf_emoji, conf = "📊", "MODERADA"

        lines.append(f"\n{medals[i]} <b>PICK #{i+1}</b>")
        lines.append("─────────────────────────")
        lines.append(f"{sport['emoji']} <b>{b['match']}</b>")
        lines.append(f"🏆 {sport['name']}  |  📋 {b['market_label']}")
        lines.append(f"🕐 {b['date_str']}")
        lines.append("")
        lines.append(f"📌 <b>APOSTAR A: {b['selection'].upper()}</b>")
        lines.append(f"💰 Cuota: <b>{b['odds']:.2f}</b>  |  Prob. real: <b>{prob_f}</b>")
        lines.append(f"{conf_emoji} Confianza: <b>{conf}</b>  |  Value: <b>{value_f}</b>")
        lines.append("")
        lines.append(f"💵 <b>GANANCIA ESTIMADA:</b>")
        lines.append(f"   Apostás {ej_f} ARS")
        lines.append(f"   → Ganás <b>{gan_f} ARS</b> de ganancia neta")
        lines.append(f"   → Recibís <b>{ret_f} ARS</b> en total")
        lines.append("")
        lines.append(f"💼 Kelly recomendado: <b>{kelly_f} de tu bankroll</b>")
        if b["from_bplay"]:
            lines.append(f"✅ <i>Cuota de bplay confirmada</i>")
        else:
            lines.append(f"⚠️ <i>Verificá la cuota exacta en bplay antes de apostar</i>")
        lines.append(f"🔗 <a href='{bplay_url(sport['key'])}'>Ir a apostar →</a>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Escribime el nombre de un partido para ver todas sus cuotas y probabilidades.</i>")
    lines.append("⚠️ <i>Análisis matemático, no garantía. Jugá con responsabilidad.</i>")
    lines.append("\n🤖 <i>BetEdge Bot</i>")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
#  MANEJO DE MENSAJES ENTRANTES
# ═══════════════════════════════════════════════════════════════
def handle_message(text, chat_id):
    t = text.strip().lower()

    if t in ["/start", "/help", "hola", "ayuda", "help"]:
        tg_send(
            "👋 <b>Hola! Soy BetEdge Bot</b>\n\n"
            "Todos los días a las 8AM te mando automáticamente los <b>3 mejores picks del día</b> en bplay.\n\n"
            "También podés consultarme cualquier partido ahora mismo. "
            "Escribime los nombres de los equipos y te analizo todas las cuotas disponibles:\n\n"
            "  ▸ <code>River Boca</code>\n"
            "  ▸ <code>Real Madrid Atletico</code>\n"
            "  ▸ <code>Lakers Warriors</code>\n"
            "  ▸ <code>Arsenal Chelsea</code>\n\n"
            "⚠️ <i>Solo puedo analizar partidos que estén próximos a jugarse y disponibles en la API.</i>\n\n"
            "🤖 <i>BetEdge Bot</i>",
            chat_id
        )
        return

    if t in ["/picks", "picks", "picks del dia", "análisis"]:
        tg_send("🔄 Corriendo análisis completo, esperá 1-2 minutos...", chat_id)
        candidates, total = run_full_analysis()
        msg = build_daily_message(candidates[:3], total)
        tg_send_long(msg, chat_id)
        return

    # Búsqueda de partido
    tg_send(f"🔍 Buscando <b>{text}</b>...", chat_id)
    msg = search_and_analyze_match(text)
    if msg:
        tg_send_long(msg, chat_id)
    else:
        tg_send(
            f"❌ No encontré <b>{text}</b> entre los partidos disponibles esta semana.\n\n"
            "Posibles razones:\n"
            "  • El partido es de una liga que no cubre la API\n"
            "  • Todavía no cargaron las cuotas\n"
            "  • Probá escribir solo apellidos: <code>Messi Ronaldo</code> no funciona, usá los equipos\n\n"
            "Ligas disponibles: Liga Argentina, Premier, La Liga, Champions, Serie A, Bundesliga, Ligue 1, NBA, NFL, MMA",
            chat_id
        )

# ═══════════════════════════════════════════════════════════════
#  LOOP PRINCIPAL
# ═══════════════════════════════════════════════════════════════
def run():
    if not ODDS_API_KEY:
        tg_send("⚠️ Falta la ODDS_API_KEY en las variables de Railway.")
        return

    print(f"[{datetime.now()}] BetEdge Bot arrancando...")

    # 1) Análisis diario
    candidates, total = run_full_analysis()
    msg = build_daily_message(candidates[:3], total)
    tg_send_long(msg)
    print(f"[{datetime.now()}] Picks enviados. Activando modo escucha...")

    # 2) Limpiar updates viejos para no procesar mensajes anteriores
    old_updates = tg_get_updates()
    offset = None
    if old_updates:
        offset = old_updates[-1]["update_id"] + 1
        print(f"  Descartados {len(old_updates)} mensajes viejos.")

    # 3) Escuchar mensajes nuevos
    while True:
        updates = tg_get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg_obj = upd.get("message", {})
            text    = msg_obj.get("text", "")
            chat_id = msg_obj.get("chat", {}).get("id")
            if text and chat_id:
                if str(chat_id) == str(TELEGRAM_CHAT_ID):
                    print(f"  → Mensaje: {text}")
                    handle_message(text, chat_id)
                else:
                    tg_send("⛔ No autorizado.", chat_id)
        time.sleep(1)


if __name__ == "__main__":
    run()
