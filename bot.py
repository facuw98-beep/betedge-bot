import requests
import json
import os
from datetime import datetime, timezone
import time

# ─── CONFIGURACIÓN ───────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8792539683:AAEfgGUx15iTkFmqcIANr4A5OGNuI06yBOQ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1034250836")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# Umbrales de filtro
MIN_VALUE = 0.04          # Mínimo 4% de value para incluir una apuesta
MIN_ARB_PROFIT = 0.8      # Mínimo 0.8% de ganancia garantizada en arbitraje
MAX_VALUE_BETS = 8        # Máximo de value bets a incluir en el mensaje
MAX_ARB = 3               # Máximo de arbitrajes a mostrar
QUARTER_KELLY = 0.25      # Fracción de Kelly a usar (conservador)

# Deportes a analizar (todos los disponibles en plan gratuito)
SPORTS = [
    {"key": "soccer_epl",                       "name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"},
    {"key": "soccer_spain_la_liga",             "name": "🇪🇸 La Liga"},
    {"key": "soccer_uefa_champs_league",        "name": "🏆 Champions League"},
    {"key": "soccer_uefa_europa_league",        "name": "🇪🇺 Europa League"},
    {"key": "soccer_argentina_primera_division","name": "🇦🇷 Liga Argentina"},
    {"key": "soccer_brazil_campeonato",         "name": "🇧🇷 Brasileirao"},
    {"key": "soccer_italy_serie_a",             "name": "🇮🇹 Serie A"},
    {"key": "soccer_germany_bundesliga",        "name": "🇩🇪 Bundesliga"},
    {"key": "soccer_france_ligue_one",          "name": "🇫🇷 Ligue 1"},
    {"key": "soccer_usa_mls",                   "name": "🇺🇸 MLS"},
    {"key": "basketball_nba",                   "name": "🏀 NBA"},
    {"key": "basketball_euroleague",            "name": "🏀 Euroliga"},
    {"key": "americanfootball_nfl",             "name": "🏈 NFL"},
    {"key": "tennis_atp_french_open",           "name": "🎾 ATP"},
    {"key": "tennis_wta_french_open",           "name": "🎾 WTA"},
    {"key": "mma_mixed_martial_arts",           "name": "🥊 MMA/UFC"},
]

# ─── TELEGRAM ────────────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code == 200

# ─── OBTENER CUOTAS ──────────────────────────────────────────
def fetch_odds(sport_key: str) -> list:
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=eu"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
        f"&bookmakers=bet365,betano,pinnacle,betfair,unibet,williamhill,bwin,1xbet"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            print(f"API Key inválida")
            return []
        elif r.status_code == 429:
            print(f"Límite de requests alcanzado")
            return []
    except Exception as e:
        print(f"Error fetching {sport_key}: {e}")
    return []

# ─── ANALIZAR VALUE BETS ─────────────────────────────────────
def analyze_value_bets(games: list, sport_name: str) -> list:
    value_bets = []

    for game in games:
        if not game.get("bookmakers") or len(game["bookmakers"]) < 2:
            continue

        home = game.get("home_team", "?")
        away = game.get("away_team", "?")
        commence = game.get("commence_time", "")

        # Recopilar todas las cuotas por resultado
        all_odds = {}  # outcome -> [lista de precios]
        best_odds = {}  # outcome -> {price, bookmaker}

        for bm in game["bookmakers"]:
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for oc in market.get("outcomes", []):
                    name = oc["name"]
                    price = oc["price"]
                    if name not in all_odds:
                        all_odds[name] = []
                    all_odds[name].append(price)
                    if name not in best_odds or price > best_odds[name]["price"]:
                        best_odds[name] = {"price": price, "bookmaker": bm["title"]}

        if len(best_odds) < 2:
            continue

        # Calcular margen del mercado
        sum_inv = sum(1 / best_odds[k]["price"] for k in best_odds)

        for outcome, info in best_odds.items():
            odds = info["price"]
            bookmaker = info["bookmaker"]

            # Probabilidad justa ajustada por margen
            fair_prob = (1 / odds) / sum_inv

            # EV / Value
            value = (fair_prob * odds) - 1

            # Comparar con promedio del mercado
            avg_odds = sum(all_odds[outcome]) / len(all_odds[outcome])
            odds_edge = (odds - avg_odds) / avg_odds if avg_odds > 0 else 0

            # Kelly Quarter
            kelly_raw = max(0, (fair_prob * odds - 1) / (odds - 1)) if odds > 1 else 0
            kelly_q = kelly_raw * QUARTER_KELLY

            if value >= MIN_VALUE or odds_edge >= 0.03:
                # Fecha del partido
                try:
                    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d/%m %H:%M")
                except:
                    date_str = "—"

                value_bets.append({
                    "sport": sport_name,
                    "match": f"{home} vs {away}",
                    "selection": outcome,
                    "odds": odds,
                    "bookmaker": bookmaker,
                    "fair_prob": fair_prob,
                    "value": value,
                    "odds_edge": odds_edge,
                    "kelly_q": kelly_q,
                    "date": date_str,
                    "score": value + odds_edge,  # score compuesto para ordenar
                })

    return value_bets

# ─── ANALIZAR ARBITRAJE ──────────────────────────────────────
def analyze_arbitrage(games: list, sport_name: str) -> list:
    arb_opps = []

    for game in games:
        if not game.get("bookmakers") or len(game["bookmakers"]) < 2:
            continue

        home = game.get("home_team", "?")
        away = game.get("away_team", "?")
        commence = game.get("commence_time", "")

        # Mejores cuotas por resultado
        best_odds = {}
        for bm in game["bookmakers"]:
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for oc in market.get("outcomes", []):
                    name = oc["name"]
                    price = oc["price"]
                    if name not in best_odds or price > best_odds[name]["price"]:
                        best_odds[name] = {"price": price, "bookmaker": bm["title"]}

        if len(best_odds) < 2:
            continue

        arb_sum = sum(1 / best_odds[k]["price"] for k in best_odds)

        if arb_sum < 1:
            profit_pct = (1 - arb_sum) / arb_sum * 100
            if profit_pct >= MIN_ARB_PROFIT:
                try:
                    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d/%m %H:%M")
                except:
                    date_str = "—"

                legs = []
                for outcome, info in best_odds.items():
                    stake_pct = (1 / info["price"]) / arb_sum * 100
                    legs.append({
                        "outcome": outcome,
                        "odds": info["price"],
                        "bookmaker": info["bookmaker"],
                        "stake_pct": stake_pct,
                    })

                arb_opps.append({
                    "sport": sport_name,
                    "match": f"{home} vs {away}",
                    "profit": profit_pct,
                    "arb_sum": arb_sum,
                    "legs": legs,
                    "date": date_str,
                })

    return arb_opps

# ─── CONSTRUIR MENSAJE TELEGRAM ──────────────────────────────
def build_message(all_value_bets: list, all_arb: list) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = []
    lines.append(f"⚡ <b>BETEDGE — ANÁLISIS DIARIO</b>")
    lines.append(f"📅 {now} (Argentina)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")

    # ── VALUE BETS ──
    if all_value_bets:
        top_bets = sorted(all_value_bets, key=lambda x: x["score"], reverse=True)[:MAX_VALUE_BETS]
        lines.append(f"\n🎯 <b>VALUE BETS DETECTADOS ({len(all_value_bets)} total, top {len(top_bets)})</b>")
        lines.append("")

        for i, b in enumerate(top_bets, 1):
            value_pct = b["value"] * 100
            kelly_pct = b["kelly_q"] * 100
            prob_pct = b["fair_prob"] * 100
            star = "🔥" if value_pct >= 10 else "✅" if value_pct >= 6 else "📊"

            lines.append(f"{star} <b>#{i} — {b['match']}</b>")
            lines.append(f"   🏆 {b['sport']} | 📅 {b['date']}")
            lines.append(f"   📌 Apostar a: <b>{b['selection']}</b>")
            lines.append(f"   💰 Cuota: <b>{b['odds']:.2f}</b> en {b['bookmaker']}")
            lines.append(f"   📈 Value: <b>+{value_pct:.1f}%</b> | Prob. real: {prob_pct:.0f}%")
            lines.append(f"   💼 Kelly (¼): <b>{kelly_pct:.1f}% del bankroll</b>")
            lines.append("")
    else:
        lines.append("\n🎯 <b>VALUE BETS</b>")
        lines.append("Sin oportunidades claras hoy.")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")

    # ── ARBITRAJE ──
    if all_arb:
        top_arb = sorted(all_arb, key=lambda x: x["profit"], reverse=True)[:MAX_ARB]
        lines.append(f"\n⚡ <b>ARBITRAJES ({len(all_arb)} detectados)</b>")
        lines.append("")

        for a in top_arb:
            lines.append(f"💎 <b>{a['match']}</b>")
            lines.append(f"   🏆 {a['sport']} | 📅 {a['date']}")
            lines.append(f"   💰 Ganancia garantizada: <b>+{a['profit']:.2f}%</b>")
            for leg in a["legs"]:
                lines.append(f"   ▸ {leg['outcome']}: {leg['odds']:.2f} @ {leg['bookmaker']} ({leg['stake_pct']:.0f}% del capital)")
            lines.append("")
    else:
        lines.append(f"\n⚡ <b>ARBITRAJE</b>")
        lines.append("Sin arbitrajes rentables en este momento.")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")

    # ── RESUMEN ──
    lines.append(f"\n📊 <b>RESUMEN</b>")
    lines.append(f"• Value bets encontrados: <b>{len(all_value_bets)}</b>")
    lines.append(f"• Arbitrajes encontrados: <b>{len(all_arb)}</b>")
    lines.append(f"• Deportes analizados: <b>{len(SPORTS)}</b>")
    lines.append("")
    lines.append("⚠️ <i>Recordá: apostá siempre con Kelly (¼) y nunca más del 5% del bankroll por apuesta. Las apuestas conllevan riesgo.</i>")
    lines.append("")
    lines.append("🤖 <i>BetEdge Bot — análisis automático diario</i>")

    return "\n".join(lines)

# ─── MAIN ────────────────────────────────────────────────────
def run_analysis():
    print(f"[{datetime.now()}] Iniciando análisis...")

    if not ODDS_API_KEY:
        send_telegram("⚠️ <b>BetEdge Bot</b>\n\nFalta configurar la ODDS_API_KEY en las variables de entorno de Railway.")
        return

    all_value_bets = []
    all_arb = []

    for sport in SPORTS:
        print(f"  Analizando {sport['name']}...")
        games = fetch_odds(sport["key"])
        if games:
            vb = analyze_value_bets(games, sport["name"])
            arb = analyze_arbitrage(games, sport["name"])
            all_value_bets.extend(vb)
            all_arb.extend(arb)
            print(f"    → {len(games)} partidos | {len(vb)} value bets | {len(arb)} arbs")
        time.sleep(0.3)  # pequeña pausa entre requests

    print(f"Total: {len(all_value_bets)} value bets, {len(all_arb)} arbitrajes")

    message = build_message(all_value_bets, all_arb)

    # Telegram tiene límite de 4096 caracteres, dividir si es necesario
    if len(message) > 4000:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            send_telegram(chunk)
            time.sleep(1)
    else:
        send_telegram(message)

    print(f"[{datetime.now()}] ✅ Mensaje enviado a Telegram")

if __name__ == "__main__":
    run_analysis()
