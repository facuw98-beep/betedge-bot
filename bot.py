
import requests
import json
import os
from datetime import datetime, timezone
import time

# ─── CONFIGURACIÓN ───────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8792539683:AAEfgGUx15iTkFmqcIANr4A5OGNuI06yBOQ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1034250836")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# Configuración del análisis
TOP_BETS = 3                # Solo las 3 mejores apuestas del día
MIN_VALUE = 0.03            # Mínimo 3% de value POSITIVO
MIN_PROB = 0.25             # Probabilidad real mínima 25% (descarta perdedores claros)
MAX_ODDS = 4.50             # Cuota máxima aceptable (nada de apuestas al perdedor)
MIN_KELLY = 0.005           # Kelly mínimo (descarta apuestas sin ventaja real)
QUARTER_KELLY = 0.25        # Fracción de Kelly conservadora
EJEMPLO_APUESTA = 10000     # Monto de ejemplo para mostrar ganancia potencial (en ARS)

# Bookmakers a analizar — priorizamos bplay y fuentes argentinas
BOOKMAKERS_PRIORITY = ["bplay", "betsson", "codere", "bet365", "unibet", "pinnacle", "williamhill", "bwin"]

# Deportes a analizar
SPORTS = [
    {"key": "soccer_argentina_primera_division", "name": "🇦🇷 Liga Argentina",        "emoji": "⚽"},
    {"key": "soccer_epl",                        "name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",       "emoji": "⚽"},
    {"key": "soccer_spain_la_liga",              "name": "🇪🇸 La Liga",                "emoji": "⚽"},
    {"key": "soccer_uefa_champs_league",         "name": "🏆 Champions League",        "emoji": "⚽"},
    {"key": "soccer_uefa_europa_league",         "name": "🇪🇺 Europa League",          "emoji": "⚽"},
    {"key": "soccer_brazil_campeonato",          "name": "🇧🇷 Brasileirao",            "emoji": "⚽"},
    {"key": "soccer_italy_serie_a",              "name": "🇮🇹 Serie A",                "emoji": "⚽"},
    {"key": "soccer_germany_bundesliga",         "name": "🇩🇪 Bundesliga",             "emoji": "⚽"},
    {"key": "soccer_france_ligue_one",           "name": "🇫🇷 Ligue 1",               "emoji": "⚽"},
    {"key": "soccer_usa_mls",                    "name": "🇺🇸 MLS",                    "emoji": "⚽"},
    {"key": "basketball_nba",                    "name": "🏀 NBA",                     "emoji": "🏀"},
    {"key": "basketball_euroleague",             "name": "🏀 Euroliga",                "emoji": "🏀"},
    {"key": "americanfootball_nfl",              "name": "🏈 NFL",                     "emoji": "🏈"},
    {"key": "mma_mixed_martial_arts",            "name": "🥊 MMA/UFC",                 "emoji": "🥊"},
    {"key": "tennis_atp_french_open",            "name": "🎾 ATP",                     "emoji": "🎾"},
    {"key": "tennis_wta_french_open",            "name": "🎾 WTA",                     "emoji": "🎾"},
]

# ─── LINK DIRECTO A BPLAY ────────────────────────────────────
def build_bplay_link(sport_key: str, home_team: str, away_team: str) -> str:
    """Genera el link más directo posible a bplay según el deporte."""
    base = "https://www.bplay.bet.ar"

    sport_routes = {
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

    route = sport_routes.get(sport_key, "/deportes")
    return f"{base}{route}"

# ─── TELEGRAM ────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Error enviando Telegram: {e}")
        return False

# ─── OBTENER CUOTAS ──────────────────────────────────────────
def fetch_odds(sport_key: str) -> list:
    bookmakers_str = ",".join(BOOKMAKERS_PRIORITY)
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=eu,us,au"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
        f"&bookmakers={bookmakers_str}"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            print("API Key inválida")
            return []
        elif r.status_code == 422:
            return []  # deporte no disponible en este momento
        elif r.status_code == 429:
            print("Límite de requests alcanzado")
            return []
    except Exception as e:
        print(f"Error fetching {sport_key}: {e}")
    return []

# ─── ANALIZAR PARTIDOS ───────────────────────────────────────
def analyze_games(games: list, sport: dict) -> list:
    candidates = []

    for game in games:
        if not game.get("bookmakers") or len(game["bookmakers"]) < 1:
            continue

        home = game.get("home_team", "?")
        away = game.get("away_team", "?")
        commence = game.get("commence_time", "")

        # Recopilar todas las cuotas disponibles por resultado
        all_odds_by_outcome = {}   # outcome -> [lista de precios]
        best_by_outcome = {}       # outcome -> {price, bookmaker}
        bplay_odds = {}            # outcome -> precio en bplay específicamente

        for bm in game["bookmakers"]:
            bm_name = bm["title"].lower()
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for oc in market.get("outcomes", []):
                    name = oc["name"]
                    price = oc["price"]

                    if name not in all_odds_by_outcome:
                        all_odds_by_outcome[name] = []
                    all_odds_by_outcome[name].append(price)

                    # Mejor cuota general
                    if name not in best_by_outcome or price > best_by_outcome[name]["price"]:
                        best_by_outcome[name] = {"price": price, "bookmaker": bm["title"]}

                    # Cuota específica de bplay
                    if "bplay" in bm_name:
                        bplay_odds[name] = price

        if len(best_by_outcome) < 2:
            continue

        # Si bplay no tiene cuotas para este partido, usamos la mejor disponible
        # pero lo marcamos como "verificar en bplay"
        has_bplay = len(bplay_odds) > 0

        # Calcular margen del mercado con las mejores cuotas disponibles
        sum_inv = sum(1 / best_by_outcome[k]["price"] for k in best_by_outcome)

        # Analizar cada resultado
        for outcome, info in best_by_outcome.items():
            best_price = info["price"]
            best_book = info["bookmaker"]

            # Usar cuota de bplay si está disponible, sino la mejor del mercado
            analysis_price = bplay_odds.get(outcome, best_price)
            display_book = "bplay" if outcome in bplay_odds else best_book

            # Probabilidad justa ajustada por margen
            fair_prob = (1 / best_price) / sum_inv

            # Value con la cuota de análisis
            value = (fair_prob * analysis_price) - 1

            # Comparar con promedio del mercado
            all_prices = all_odds_by_outcome.get(outcome, [analysis_price])
            avg_price = sum(all_prices) / len(all_prices)
            odds_edge = (analysis_price - avg_price) / avg_price if avg_price > 0 else 0

            # Kelly Quarter
            kelly_raw = max(0, (fair_prob * analysis_price - 1) / (analysis_price - 1)) if analysis_price > 1 else 0
            kelly_q = kelly_raw * QUARTER_KELLY

            # Score compuesto para ranking
            score = (value * 0.6) + (odds_edge * 0.4)

            if (value >= MIN_VALUE and
                    fair_prob >= MIN_PROB and
                    analysis_price <= MAX_ODDS and
                    kelly_q >= MIN_KELLY):
                # Fecha del partido
                try:
                    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                    # Convertir a Argentina (UTC-3)
                    from datetime import timedelta
                    dt_ar = dt - timedelta(hours=3)
                    date_str = dt_ar.strftime("%A %d/%m a las %H:%M")
                    # Traducir días
                    dias = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
                            "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}
                    for en, es in dias.items():
                        date_str = date_str.replace(en, es)
                except:
                    date_str = "—"

                # Cálculo de ganancia potencial con ejemplo
                ganancia_bruta = EJEMPLO_APUESTA * analysis_price
                ganancia_neta = ganancia_bruta - EJEMPLO_APUESTA

                # Nivel de confianza
                if value >= 0.10:
                    confianza = "🔥 MUY ALTA"
                    stars = "★★★"
                elif value >= 0.06:
                    confianza = "✅ ALTA"
                    stars = "★★☆"
                else:
                    confianza = "📊 MODERADA"
                    stars = "★☆☆"

                candidates.append({
                    "sport_name": sport["name"],
                    "sport_key": sport["key"],
                    "sport_emoji": sport["emoji"],
                    "match": f"{home} vs {away}",
                    "home": home,
                    "away": away,
                    "selection": outcome,
                    "odds": analysis_price,
                    "bookmaker": display_book,
                    "has_bplay": has_bplay,
                    "fair_prob": fair_prob,
                    "value": value,
                    "odds_edge": odds_edge,
                    "kelly_q": kelly_q,
                    "date_str": date_str,
                    "score": score,
                    "ganancia_neta": ganancia_neta,
                    "ganancia_bruta": ganancia_bruta,
                    "confianza": confianza,
                    "stars": stars,
                    "bplay_link": build_bplay_link(sport["key"], home, away),
                })

    return candidates

# ─── CONSTRUIR MENSAJE ───────────────────────────────────────
def build_message(top_bets: list, total_analyzed: int, sports_analyzed: int) -> str:
    now = datetime.now().strftime("%d/%m/%Y")
    lines = []

    lines.append(f"🟢 <b>BETEDGE — PICKS DEL DÍA</b>")
    lines.append(f"📅 {now} | Analizados: {total_analyzed} partidos en {sports_analyzed} deportes")
    lines.append(f"🎯 Las <b>3 mejores apuestas</b> del día en bplay")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not top_bets:
        lines.append("\n⚠️ Hoy no se encontraron apuestas con suficiente value.")
        lines.append("Mejor no apostar que apostar sin ventaja. Mañana habrá más opciones.")
        lines.append("\n🤖 <i>BetEdge Bot</i>")
        return "\n".join(lines)

    for i, b in enumerate(top_bets, 1):
        ejemplo_fmt = f"${EJEMPLO_APUESTA:,.0f}".replace(",", ".")
        ganancia_fmt = f"${b['ganancia_neta']:,.0f}".replace(",", ".")
        retorno_fmt = f"${b['ganancia_bruta']:,.0f}".replace(",", ".")
        prob_fmt = f"{b['fair_prob']*100:.0f}%"
        value_fmt = f"+{b['value']*100:.1f}%"
        kelly_fmt = f"{b['kelly_q']*100:.1f}%"

        lines.append(f"\n{'🥇' if i==1 else '🥈' if i==2 else '🥉'} <b>PICK #{i} — {b['stars']}</b>")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{b['sport_emoji']} <b>{b['match']}</b>")
        lines.append(f"🏆 {b['sport_name']}")
        lines.append(f"🕐 {b['date_str']}")
        lines.append("")
        lines.append(f"📌 <b>APOSTAR A: {b['selection'].upper()}</b>")
        lines.append(f"💰 Cuota: <b>{b['odds']:.2f}</b>")
        lines.append(f"📊 Confianza: <b>{b['confianza']}</b>")
        lines.append(f"🎯 Prob. real estimada: <b>{prob_fmt}</b>")
        lines.append(f"📈 Value detectado: <b>{value_fmt}</b>")
        lines.append("")
        lines.append(f"💵 <b>EJEMPLO DE GANANCIA:</b>")
        lines.append(f"   Si apostás {ejemplo_fmt} ARS")
        lines.append(f"   → Ganás <b>{ganancia_fmt} ARS</b> de ganancia")
        lines.append(f"   → Recibís <b>{retorno_fmt} ARS</b> en total")
        lines.append("")
        lines.append(f"💼 Kelly recomendado: <b>{kelly_fmt} de tu bankroll</b>")
        lines.append("")

        # Indicar si la cuota es de bplay directo o estimada
        if b["has_bplay"]:
            lines.append(f"✅ <i>Cuota verificada en bplay</i>")
        else:
            lines.append(f"⚠️ <i>Verificá la cuota exacta en bplay antes de apostar</i>")

        lines.append(f"🔗 <a href='{b['bplay_link']}'>Ir a apostar en bplay →</a>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ <i>Estas recomendaciones son análisis matemáticos, no garantías. Nunca apostés más de lo que podés perder. Jugá con responsabilidad.</i>")
    lines.append("")
    lines.append("🤖 <i>BetEdge Bot — análisis automático diario</i>")

    return "\n".join(lines)

# ─── MAIN ────────────────────────────────────────────────────
def run_analysis():
    print(f"[{datetime.now()}] Iniciando análisis enfocado en bplay...")

    if not ODDS_API_KEY:
        send_telegram(
            "⚠️ <b>BetEdge Bot</b>\n\n"
            "Falta configurar la ODDS_API_KEY en las variables de entorno de Railway."
        )
        return

    all_candidates = []
    total_games = 0
    sports_with_data = 0

    for sport in SPORTS:
        print(f"  Analizando {sport['name']}...")
        games = fetch_odds(sport["key"])
        if games:
            sports_with_data += 1
            total_games += len(games)
            candidates = analyze_games(games, sport)
            all_candidates.extend(candidates)
            print(f"    → {len(games)} partidos | {len(candidates)} candidatos")
        time.sleep(0.4)

    # Ordenar por score y tomar los 3 mejores
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    top_3 = all_candidates[:TOP_BETS]

    print(f"\nTotal: {len(all_candidates)} candidatos → seleccionados top {len(top_3)}")

    message = build_message(top_3, total_games, sports_with_data)

    # Telegram tiene límite de 4096 caracteres
    if len(message) > 4000:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            send_telegram(chunk)
            time.sleep(1)
    else:
        send_telegram(message)

    print(f"[{datetime.now()}] ✅ Picks enviados a Telegram")

if __name__ == "__main__":
    run_analysis()
