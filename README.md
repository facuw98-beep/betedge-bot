# ⚡ BetEdge Bot — Guía de Instalación

Bot que analiza automáticamente cuotas deportivas todos los días y te manda un resumen por Telegram con value bets y arbitrajes detectados.

---

## Lo que necesitás antes de subir

1. **API Key de The Odds API** → registrate gratis en https://the-odds-api.com (500 requests/mes gratis)
2. **Token de Telegram** → ya lo tenés (el que te dio @BotFather)
3. **Tu Chat ID de Telegram** → ya lo tenés (el que te dio @userinfobot)
4. **Cuenta en Railway** → https://railway.app (gratis)

---

## Paso a paso para subir a Railway

### 1. Crear cuenta en Railway
- Entrá a https://railway.app
- Registrate con GitHub (es gratis)

### 2. Subir el bot
- En Railway hacé click en **"New Project"**
- Elegí **"Deploy from GitHub repo"** o **"Empty project"**
- Si elegís Empty project → hacé click en **"Add a service"** → **"GitHub Repo"**
- Subí estos archivos a un repositorio de GitHub (o usá la opción de subir directo)

### 3. Configurar las variables de entorno
En Railway, dentro de tu proyecto → pestaña **"Variables"**, agregá:

| Variable | Valor |
|---|---|
| `TELEGRAM_TOKEN` | Tu token de @BotFather |
| `TELEGRAM_CHAT_ID` | Tu ID de @userinfobot |
| `ODDS_API_KEY` | Tu key de the-odds-api.com |

### 4. Configurar el horario
El archivo `railway.toml` ya tiene configurado que el bot corra todos los días a las **8:00 AM UTC** (5:00 AM Argentina).

Si querés cambiarlo, editá la línea `cronSchedule` en `railway.toml`:
- `"0 8 * * *"` → 8:00 AM UTC (5:00 AM Argentina)
- `"0 11 * * *"` → 11:00 AM UTC (8:00 AM Argentina) ← recomendado
- `"0 20 * * *"` → 8:00 PM UTC (5:00 PM Argentina)

### 5. Deploy
- Railway detecta automáticamente que es Python y lo instala solo
- En la pestaña **"Deployments"** vas a ver que corre

---

## Ejecutar manualmente (para probar)

Si querés probarlo en tu PC primero:

```bash
pip install requests
python bot.py
```

Pero antes configurá las variables de entorno en tu sistema o editá directamente los valores en `bot.py`.

---

## Qué te manda el bot cada día

- 🎯 **Value Bets** — partidos donde las cuotas valen más de lo que deberían (mínimo 4% de value)
- ⚡ **Arbitrajes** — oportunidades de cubrir todos los resultados con ganancia garantizada
- 📊 **Kelly Criterion** — cuánto % de tu bankroll apostar en cada caso
- 🏆 Cubre: Premier League, La Liga, Champions, Liga Argentina, Brasileirao, Serie A, Bundesliga, Ligue 1, NBA, NFL, Tenis ATP/WTA, MMA/UFC

---

## Parámetros ajustables en bot.py

```python
MIN_VALUE = 0.04       # Mínimo 4% de value (subilo para ser más selectivo)
MIN_ARB_PROFIT = 0.8   # Mínimo 0.8% de ganancia en arbitraje
MAX_VALUE_BETS = 8     # Máximo de bets en el mensaje
QUARTER_KELLY = 0.25   # Fracción de Kelly (0.25 = conservador, recomendado)
```
