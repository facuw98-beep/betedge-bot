import requests
import os
import time
from datetime import datetime, timedelta

# ─── CONFIGURACIÓN ───────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN",  "8792539683:AAEfgGUx15iTkFmqcIANr4A5OGNuI06yBOQ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1034250836")
ODDS_API_KEY    = os.environ.get("ODDS_API_KEY", "")

# Parámetros de análisis (ajustados)
TOP_BETS        = 3
MIN_VALUE       = 0.03      # mínimo 3% de value positivo
MIN_PROB        = 0.18      # mínimo 18% de probabilidad real
MAX_ODDS        = 5.50      # cuota máxima aceptable
MIN_KELLY       = 0.005     # kelly mínimo
QUARTER_KELLY   = 0.25      # fracción kelly conservadora
EJEMPLO_APUESTA = 10000     # ARS para ejemplos de ganancia

# Bookmakers priorizados
BOOKMAKERS = "bplay,betsson,codere,bet365,pinnacle,williamhill,unibet,bwin"

# Mercados a analizar
MARKETS = "h2h,totals,btts"

# Deportes
SPORTS = [
    {"key": "soccer_argentina_primera_division", "name": "Liga Argentina",   "emoji": "🇦🇷⚽"},
    {"key": "soccer_epl",                        "name": "Premier League",   "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿⚽"},
    {"key": "soccer_spain_la_liga",              "name": "La Liga",          "emoji": "🇪🇸⚽"},
    {"key": "soccer_uefa_champs_league",         "name": "Champions League", "emoji": "🏆⚽"},
    {"key": "soccer_uefa_europa_league",         "name": "Europa League",    "emoji": "🇪🇺⚽"},
    {"key": "soccer_brazil_campeonato",          "name": "Brasileirao",      "emoji": "🇧🇷⚽"},
    {"key": "soccer_italy_serie_a",              "name": "Serie A",          "emoji": "🇮🇹⚽"},
    {"key": "soccer_germany_bundesliga",         "name": "Bundesliga",       "emoji": "🇩🇪⚽"},
    {"key": "soccer_france_ligue_one",           "name": "Ligue 1",          "emoji": "🇫🇷⚽"},
    {"key": "soccer_usa_mls",                    "name": "MLS",              "emoji": "🇺🇸⚽"},
    {"key": "basketball_nba",                    "name": "NBA",              "emoji": "🏀"},
    {"key": "basketball_euroleague",             "name": "Euroliga",         "emoji": "🏀"},
    {"key": "americanfootball_nfl",              "name": "NFL",              "emoji": "🏈"},
    {"key": "mma_mixed_martial_arts",            "name": "MMA/UFC",          "emoji": "🥊"},
    {"key": "tennis_atp_french_open",            "name": "ATP Tenis",        "emoji": "🎾"},
    {"key": "tennis_wta_french_open",            "name": "WTA Tenis",        "emoji": "🎾"},
]

# ─── NOMBRES AMIGABLES PARA MERCADOS ─────────────────────────
MARKET_NAMES = {
    "h2h":    "Resultado (1X2)",
    "totals": "Over/Under goles",
    "btts":   "Ambos anotan (BTTS)",
    "spreads":"Handicap",
}

# ─── LINKS BPLAY ─────────────────────────────────────────────
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

def bplay_link(sport_key):
    route = BPLAY_ROUTES.get(sport_key, "/deportes")
    return f"https://www.bplay.bet.ar{route}"

# ─── TELEGRAM ────────────────────────────────────────────────
def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": cid, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False

def send_long(text, chat_id=None):
    """Divide mensajes largos en chunks."""
    if len(text) <= 4000:
        send_telegram(text, chat_id)
    else:
        for i in range(0, len(text), 4000):
            send_telegram(text[i:i+4000], chat_id)
            time.sleep(0.5)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ─── OBTENER CUOTAS ──────────────────────────────────────────
def fetch_odds(sport_key, markets=MARKETS):
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=eu,us,au"
        f"&markets={markets}"
        f"&oddsFormat=decimal"
        f"&bookmakers={BOOKMAKERS}"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching {sport_key}: {e}")
    return []

def fetch_all_sports():
    """Busca en todos los deportes y devuelve todos los partidos."""
    all_games = []
    sports_found = 0
    for sport in SPORTS:
        games = fetch_odds(sport["key"])
        if games:
            sports_found += 1
            for g in games:
                g["_sport"] = sport
            all_games.extend(games)
            print(f"  {sport['name']}: {len(games)} partidos")
        time.sleep(0.4)
    return all_games, sports_found

# ─── ANALIZAR UN PARTIDO (todos los mercados) ────────────────
def analyze_game(game, sport):
    """Analiza todos los mercados de un partido y devuelve candidatos."""
    candidates = []
    home = game.get("home_team", "?")
    away = game.get("away_team", "?")
    commence = game.get("commence_time", "")

    # Fecha en hora argentina
    try:
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        dt_ar = dt - timedelta(hours=3)
        date_str = dt_ar.strftime("%A %d/%m a las %H:%M")
        dias = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
                "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}
        for en, es in dias.items():
            date_str = date_str.replace(en, es)
    except:
        date_str = "—"

    # Agrupar cuotas por mercado
    markets_data = {}  # market_key -> {outcome -> [precios]}
    bplay_data = {}    # market_key -> {outcome -> precio}
    best_data = {}     # market_key -> {outcome -> {price, bookmaker}}

    for bm in game.get("bookmakers", []):
        is_bplay = "bplay" in bm["title"].lower()
        for mkt in bm.get("markets", []):
            mk = mkt["key"]
            if mk not in markets_data:
                markets_data[mk] = {}
                best_data[mk] = {}
            if mk not in bplay_data:
                bplay_data[mk] = {}

            for oc in mkt.get("outcomes", []):
                name = oc["name"]
                # Para totals incluir el punto (Over 2.5, Under 2.5)
                if mk == "totals" and "point" in oc:
                    name = f"{name} {oc['point']}"
                price = oc["price"]

                if name not in markets_data[mk]:
                    markets_data[mk][name] = []
                markets_data[mk][name].append(price)

                if name not in best_data[mk] or price > best_data[mk][name]["price"]:
                    best_data[mk][name] = {"price": price, "bookmaker": bm["title"]}

                if is_bplay:
                    bplay_data[mk][name] = price

    # Analizar cada mercado
    for mk, outcomes in best_data.items():
        if len(outcomes) < 2:
            continue

        sum_inv = sum(1 / outcomes[k]["price"] for k in outcomes)
        has_bplay = len(bplay_data.get(mk, {})) > 0

        for outcome, info in outcomes.items():
            best_price = info["price"]
            analysis_price = bplay_data.get(mk, {}).get(outcome, best_price)
            display_book = "bplay" if outcome in bplay_data.get(mk, {}) else info["bookmaker"]

            fair_prob = (1 / best_price) / sum_inv
            value = (fair_prob * analysis_price) - 1
            kelly_raw = max(0, (fair_prob * analysis_price - 1) / (analysis_price - 1)) if analysis_price > 1 else 0
            kelly_q = kelly_raw * QUARTER_KELLY

            all_prices = markets_data.get(mk, {}).get(outcome, [analysis_price])
            avg_price = sum(all_prices) / len(all_prices)
            odds_edge = (analysis_price - avg_price) / avg_price if avg_price > 0 else 0

            score = (value * 0.7) + (odds_edge * 0.3)

            if (value >= MIN_VALUE and
                    fair_prob >= MIN_PROB and
                    analysis_price <= MAX_ODDS and
                    kelly_q >= MIN_KELLY):

                ganancia_neta = EJEMPLO_APUESTA * analysis_price - EJEMPLO_APUESTA
                ganancia_bruta = EJEMPLO_APUESTA * analysis_price

                if value >= 0.10:
                    confianza = "MUY ALTA"
                    stars = "★★★"
                    emoji_conf = "🔥"
                elif value >= 0.06:
                    confianza = "ALTA"
                    stars = "★★☆"
                    emoji_conf = "✅"
                else:
                    confianza = "MODERADA"
                    stars = "★☆☆"
                    emoji_conf = "📊"

                candidates.append({
                    "sport_name": sport["name"],
                    "sport_key":  sport["key"],
                    "sport_emoji": sport["emoji"],
                    "match":       f"{home} vs {away}",
                    "home": home, "away": away,
                    "market_key":  mk,
                    "market_name": MARKET_NAMES.get(mk, mk),
                    "selection":   outcome,
                    "odds":        analysis_price,
                    "bookmaker":   display_book,
                    "has_bplay":   has_bplay,
                    "fair_prob":   fair_prob,
                    "value":       value,
                    "kelly_q":     kelly_q,
                    "date_str":    date_str,
                    "score":       score,
                    "ganancia_neta":  ganancia_neta,
                    "ganancia_bruta": ganancia_bruta,
                    "confianza":   confianza,
                    "stars":       stars,
                    "emoji_conf":  emoji_conf,
                    "bplay_link":  bplay_link(sport["key"]),
                })

    return candidates

# ─── ANÁLISIS COMPLETO DE TODOS LOS DEPORTES ─────────────────
def full_analysis():
    all_games, sports_found = fetch_all_sports()
    all_candidates = []
    for game in all_games:
        sport = game["_sport"]
        candidates = analyze_game(game, sport)
        all_candidates.extend(candidates)

    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    return all_candidates[:TOP_BETS], len(all_games), sports_found

# ─── BUSCAR PARTIDO POR NOMBRE ────────────────────────────────
def search_match(query):
    """Busca un partido por nombre en todos los deportes y lo analiza."""
    query_lower = query.lower()
    found_game = None
    found_sport = None

    for sport in SPORTS:
        games = fetch_odds(sport["key"])
        time.sleep(0.3)
        for game in games:
            home = game.get("home_team", "").lower()
            away = game.get("away_team", "").lower()
            # Buscar si alguna palabra del query coincide con los equipos
            words = [w for w in query_lower.split() if len(w) > 3]
            matches = sum(1 for w in words if w in home or w in away)
            if matches >= 1:
                found_game = game
                found_sport = sport
                break
        if found_game:
            break

    return found_game, found_sport

# ─── ANALIZAR PARTIDO ESPECÍFICO (modo consulta) ──────────────
def analyze_single_match(game, sport):
    """Genera un análisis completo de un partido específico."""
    home = game.get("home_team", "?")
    away = game.get("away_team", "?")
    commence = game.get("commence_time", "")

    try:
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        dt_ar = dt - timedelta(hours=3)
        date_str = dt_ar.strftime("%A %d/%m a las %H:%M")
        dias = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
                "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}
        for en, es in dias.items():
            date_str = date_str.replace(en, es)
    except:
        date_str = "—"

    lines = []
    lines.append(f"🔍 <b>ANÁLISIS: {home} vs {away}</b>")
    lines.append(f"{sport['emoji']} {sport['name']} | {date_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Recopilar todos los mercados disponibles
    markets_summary = {}  # mk -> {outcome -> {best_price, fair_prob, value, bookmaker}}

    for bm in game.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            mk = mkt["key"]
            if mk not in markets_summary:
                markets_summary[mk] = {}
            for oc in mkt.get("outcomes", []):
                name = oc["name"]
                if mk == "totals" and "point" in oc:
                    name = f"{name} {oc['point']}"
                price = oc["price"]
                if name not in markets_summary[mk] or price > markets_summary[mk][name]["price"]:
                    markets_summary[mk][name] = {"price": price, "bookmaker": bm["title"]}

    if not markets_summary:
        lines.append("⚠️ No se encontraron cuotas disponibles para este partido.")
        return "\n".join(lines)

    # Mostrar cada mercado
    for mk, outcomes in markets_summary.items():
        if len(outcomes) < 2:
            continue

        market_label = MARKET_NAMES.get(mk, mk)
        lines.append(f"\n📋 <b>{market_label}</b>")

        sum_inv = sum(1 / outcomes[k]["price"] for k in outcomes)
        margin = (sum_inv - 1) * 100

        for outcome, info in outcomes.items():
            price = info["price"]
            fair_prob = (1 / price) / sum_inv
            value = (fair_prob * price) - 1
            kelly_raw = max(0, (fair_prob * price - 1) / (price - 1)) if price > 1 else 0
            kelly_q = kelly_raw * QUARTER_KELLY

            # Indicador de value
            if value >= MIN_VALUE and fair_prob >= MIN_PROB and kelly_q >= MIN_KELLY:
                indicator = "🟢"  # hay value
            elif value >= 0:
                indicator = "🟡"  # neutro
            else:
                indicator = "🔴"  # sin value

            ganancia = EJEMPLO_APUESTA * price - EJEMPLO_APUESTA
            ganancia_fmt = f"${ganancia:,.0f}".replace(",",".")
            ejemplo_fmt = f"${EJEMPLO_APUESTA:,.0f}".replace(",",".")

            lines.append(
                f"  {indicator} <b>{outcome}</b>: cuota {price:.2f} "
                f"| prob. {fair_prob*100:.0f}% "
                f"| value {'+' if value>=0 else ''}{value*100:.1f}%"
            )
            lines.append(
                f"      Si apostás {ejemplo_fmt} → ganás <b>{ganancia_fmt} ARS</b>"
            )

        lines.append(f"  <i>Margen de la casa: {margin:.1f}%</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🟢 Con value claro  🟡 Neutral  🔴 Sin ventaja")
    lines.append(f"🔗 <a href='{bplay_link(sport['key'])}'>Ver en bplay →</a>")
    lines.append("\n⚠️ <i>Análisis matemático, no garantía. Jugá con responsabilidad.</i>")

    return "\n".join(lines)

# ─── MENSAJE PICKS DIARIOS ────────────────────────────────────
def build_daily_message(top_bets, total_games, sports_found):
    now = datetime.now().strftime("%d/%m/%Y")
    lines = []
    lines.append(f"🟢 <b>BETEDGE — PICKS DEL DÍA</b>")
    lines.append(f"📅 {now} | {total_games} partidos en {sports_found} deportes analizados")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not top_bets:
        lines.append("\n⚠️ <b>Hoy no hay apuestas con ventaja matemática clara.</b>")
        lines.append("Es mejor no apostar que apostar sin edge. Mañana habrá más opciones.")
        lines.append("\n💡 <i>Tip: Mandame el nombre de un partido y te analizo todas las cuotas disponibles.</i>")
        lines.append("\n🤖 <i>BetEdge Bot</i>")
        return "\n".join(lines)

    medals = ["🥇", "🥈", "🥉"]
    for i, b in enumerate(top_bets):
        ejemplo_fmt  = f"${EJEMPLO_APUESTA:,.0f}".replace(",",".")
        ganancia_fmt = f"${b['ganancia_neta']:,.0f}".replace(",",".")
        retorno_fmt  = f"${b['ganancia_bruta']:,.0f}".replace(",",".")
        prob_fmt     = f"{b['fair_prob']*100:.0f}%"
        value_fmt    = f"+{b['value']*100:.1f}%"
        kelly_fmt    = f"{b['kelly_q']*100:.1f}%"

        lines.append(f"\n{medals[i]} <b>PICK #{i+1} — {b['stars']}</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{b['sport_emoji']} <b>{b['match']}</b>")
        lines.append(f"🏆 {b['sport_name']}  |  📋 {b['market_name']}")
        lines.append(f"🕐 {b['date_str']}")
        lines.append("")
        lines.append(f"📌 <b>APOSTAR A: {b['selection'].upper()}</b>")
        lines.append(f"💰 Cuota: <b>{b['odds']:.2f}</b>")
        lines.append(f"{b['emoji_conf']} Confianza: <b>{b['confianza']}</b>  |  Prob. real: <b>{prob_fmt}</b>")
        lines.append(f"📈 Value detectado: <b>{value_fmt}</b>")
        lines.append("")
        lines.append(f"💵 <b>EJEMPLO DE GANANCIA:</b>")
        lines.append(f"   Apostás {ejemplo_fmt} ARS → ganás <b>{ganancia_fmt} ARS</b>")
        lines.append(f"   Recibís <b>{retorno_fmt} ARS</b> en total")
        lines.append("")
        lines.append(f"💼 Kelly recomendado: <b>{kelly_fmt} de tu bankroll</b>")
        if b["has_bplay"]:
            lines.append(f"✅ <i>Cuota verificada en bplay</i>")
        else:
            lines.append(f"⚠️ <i>Verificá la cuota exacta en bplay</i>")
        lines.append(f"🔗 <a href='{b['bplay_link']}'>Ir a apostar en bplay →</a>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Mandame el nombre de cualquier partido y te analizo todas sus cuotas al instante.</i>")
    lines.append("⚠️ <i>Análisis matemático, no garantía. Jugá con responsabilidad.</i>")
    lines.append("\n🤖 <i>BetEdge Bot</i>")
    return "\n".join(lines)

# ─── MODO CONSULTA EN TIEMPO REAL ────────────────────────────
def handle_message(text, chat_id):
    text = text.strip()
    lower = text.lower()

    # Comandos especiales
    if lower in ["/start", "/help", "hola", "ayuda"]:
        msg = (
            "👋 <b>Hola! Soy BetEdge Bot</b>\n\n"
            "Puedo hacer dos cosas:\n\n"
            "1️⃣ <b>Análisis diario automático</b> — todos los días a las 8AM te mando los mejores picks del día\n\n"
            "2️⃣ <b>Consulta de partido</b> — escribime el nombre de cualquier partido y te analizo todas las cuotas disponibles al instante\n\n"
            "<b>Ejemplos de consultas:</b>\n"
            "• <code>River Boca</code>\n"
            "• <code>Real Madrid Barcelona</code>\n"
            "• <code>Lakers Celtics</code>\n\n"
            "🤖 <i>BetEdge Bot</i>"
        )
        send_telegram(msg, chat_id)
        return

    if lower in ["/picks", "picks", "picks del dia", "picks del día"]:
        send_telegram("🔄 <b>Buscando los mejores picks de hoy...</b> Puede tardar 1-2 minutos.", chat_id)
        top_bets, total_games, sports_found = full_analysis()
        msg = build_daily_message(top_bets, total_games, sports_found)
        send_long(msg, chat_id)
        return

    # Búsqueda de partido
    send_telegram(f"🔍 <b>Buscando:</b> {text}\nEspera un momento...", chat_id)
    game, sport = search_match(text)

    if not game:
        send_telegram(
            f"❌ No encontré el partido <b>{text}</b>.\n\n"
            "Probá escribir solo los nombres de los equipos, por ejemplo:\n"
            "<code>River Boca</code> o <code>Real Madrid Atletico</code>",
            chat_id
        )
        return

    msg = analyze_single_match(game, sport)
    send_long(msg, chat_id)

# ─── MODO ESCUCHA (polling) ───────────────────────────────────
def listen_mode():
    """Modo conversacional: escucha mensajes y responde en tiempo real."""
    print(f"[{datetime.now()}] Modo escucha activado...")
    offset = None

    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")

            if text and chat_id:
                # Solo responder al chat autorizado
                if str(chat_id) == str(TELEGRAM_CHAT_ID):
                    print(f"  Mensaje recibido: {text}")
                    handle_message(text, chat_id)
                else:
                    send_telegram("⛔ No autorizado.", chat_id)

        time.sleep(1)

# ─── ANÁLISIS DIARIO ──────────────────────────────────────────
def daily_run():
    """Corre el análisis diario y manda los picks."""
    print(f"[{datetime.now()}] Iniciando análisis diario...")
    if not ODDS_API_KEY:
        send_telegram("⚠️ Falta la ODDS_API_KEY en las variables de Railway.")
        return
    top_bets, total_games, sports_found = full_analysis()
    msg = build_daily_message(top_bets, total_games, sports_found)
    send_long(msg)
    print(f"[{datetime.now()}] Picks enviados.")

# ─── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    mode = os.environ.get("BOT_MODE", "daily")

    if mode == "listen":
        # Modo conversacional continuo
        listen_mode()
    else:
        # Modo análisis diario (cron)
        daily_run()
