"""
RIDE FARE RADAR — Simple working prototype
Team DEPTH MINDS
Run:  python app.py   →  open http://localhost:8000
      (use your PC's IP from your phone to test app prefill: http://192.168.x.x:8000)

Demo mode: provider quotes are SIMULATED (realistic pricing model).
Each result card deep-links to the REAL provider (app + web) with the
route prefilled so the user can verify actual prices in one tap.
"""
import hashlib
import random
import sqlite3
import time
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB = "radar.db"

# ─────────────────────────────────────────────
# 1. PROVIDERS  (demo adapters — swap for real APIs later)
#    fare = (base + per_km*dist + per_min*time) * surge + fee
# ─────────────────────────────────────────────
PROVIDERS = {
    "Uber":   {"base": 30, "per_km": 9.0, "per_min": 1.1, "fee": 7,  "typical_eta": 5},
    "Ola":    {"base": 25, "per_km": 8.5, "per_min": 1.0, "fee": 6,  "typical_eta": 7},
    "Rapido": {"base": 20, "per_km": 7.5, "per_min": 0.9, "fee": 4,  "typical_eta": 4},
}

RIDE_TYPES = ["bike", "auto", "mini", "sedan"]

# ─────────────────────────────────────────────
# 1b. REAL COORDINATES (for deep-link prefill on provider websites/apps)
# ─────────────────────────────────────────────
LOCATIONS = {
    "bangalore palace": (12.9986, 77.5921),
    "orion mall": (12.9917, 77.5537),
    "majestic": (12.9774, 77.5726),
    "kempegowda bus station": (12.9774, 77.5726),
    "indiranagar": (12.9784, 77.6408),
    "koramangala": (12.9352, 77.6245),
    "hsr layout": (12.9116, 77.6473),
    "whitefield": (12.9698, 77.7500),
    "electronic city": (12.8452, 77.6602),
    "marathahalli": (12.9569, 77.7011),
    "mg road": (12.9750, 77.6060),
    "cubbon park": (12.9763, 77.5929),
    "vidhana soudha": (12.9794, 77.5912),
    "kempegowda airport": (13.1986, 77.7066),
    "bangalore airport": (13.1986, 77.7066),
    "jayanagar": (12.9250, 77.5938),
    "jp nagar": (12.9063, 77.5857),
    "hebbal": (13.0358, 77.5970),
    "yeshwanthpur": (13.0234, 77.5522),
    "btm layout": (12.9166, 77.6101),
    "manyata tech park": (13.0450, 77.6206),
    "commercial street": (12.9776, 77.6069),
    "ulsoor lake": (12.9812, 77.6212),
    "banashankari": (12.9250, 77.5460),
    "malleshwaram": (13.0030, 77.5695),
    "rajajinagar": (12.9916, 77.5526),
}


def get_coords(place):
    """Return (lat, lng) for a known location, or None."""
    key = place.lower().strip()
    for name, coords in LOCATIONS.items():
        if name in key or key in name:
            return coords
    return None


# ─────────────────────────────────────────────
# 2. SIMULATION ENGINE
# ─────────────────────────────────────────────
def get_distance_km(pickup, destination):
    """Same route → same distance (deterministic hash). 2–15 km."""
    key = (pickup.lower() + "->" + destination.lower()).encode()
    return round(2 + int(hashlib.md5(key).hexdigest(), 16) % 130 / 10, 1)


def get_quote(provider, pickup, destination, ride_type):
    """Simulate one provider's response. ~10% chance of being unavailable."""
    p = PROVIDERS[provider]
    km = get_distance_km(pickup, destination)
    minutes = max(5, round(km * 2.5))          # ~24 km/h avg speed
    hour = datetime.now().hour
    peak = 1.2 if (8 <= hour < 11 or 17 <= hour < 21) else 1.0

    surge = round(min(2.0, peak * random.uniform(1.0, 1.15)), 1)
    fare = round((p["base"] + p["per_km"] * km + p["per_min"] * minutes) * surge + p["fee"])
    eta = max(2, p["typical_eta"] + random.randint(-1, 2))

    if random.random() < 0.10:
        return {"provider": provider, "status": "unavailable", "fare": 0,
                "eta": 0, "surge": surge, "distance_km": km}
    return {"provider": provider, "status": "available", "fare": fare,
            "eta": eta, "surge": surge, "distance_km": km}


# ─────────────────────────────────────────────
# 3. DEEP LINKS — open the REAL provider with route prefilled
#    app links = URL schemes (best prefill, open the mobile app)
#    web links = websites (best-effort prefill, need login on desktop)
# ─────────────────────────────────────────────
def build_links(pickup, destination):
    p = get_coords(pickup)
    d = get_coords(destination)
    pn, dn = quote_plus(pickup), quote_plus(destination)

    if p and d:
        plat, plng = p
        dlat, dlng = d
    else:
        # fall back to Bengaluru city centre if place unknown
        plat, plng, dlat, dlng = 12.9716, 77.5946, 12.9716, 77.5946

    links = {}

    # ── UBER ──
    links["Uber_app"] = (
        f"uber://?action=setPickup&pickup[latitude]={plat}&pickup[longitude]={plng}"
        f"&pickup[nickname]={pn}&dropoff[latitude]={dlat}&dropoff[longitude]={dlng}"
        f"&dropoff[nickname]={dn}"
    )
    links["Uber"] = (
        f"https://m.uber.com/ul/?action=setPickup&pickup[latitude]={plat}&pickup[longitude]={plng}"
        f"&pickup[nickname]={pn}&dropoff[latitude]={dlat}&dropoff[longitude]={dlng}"
        f"&dropoff[nickname]={dn}"
    )

    # ── OLA ──
    links["Ola"] = (
        f"https://book.olacabs.com/?lat={plat}&lng={plng}&pickup_name={pn}"
        f"&drop_lat={dlat}&drop_lng={dlng}&drop_name={dn}&utm_source=RideFareRadar"
    )
    links["Ola_app"] = (
        f"ola://book?pick_lat={plat}&pick_lng={plng}&drop_lat={dlat}"
        f"&drop_lng={dlng}&pickup_name={pn}&drop_name={dn}"
    )

    # ── RAPIDO (no public prefill link exists) →
    #    Google Maps route is the guaranteed-prefill option ──
    maps = (
        f"https://www.google.com/maps/dir/?api=1&origin={pn}&destination={dn}"
        f"&travelmode=driving"
    )
    links["Rapido"] = "https://www.rapido.bike/"
    links["Rapido_app"] = maps
    links["maps_check"] = maps

    return links


# ─────────────────────────────────────────────
# 4. DATABASE
# ─────────────────────────────────────────────
def db_init():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, pickup TEXT, destination TEXT, ride_type TEXT,
        provider TEXT, fare REAL, eta INTEGER, surge REAL, distance_km REAL)""")
    con.commit()
    con.close()


def save_comparison(quotes, pickup, destination, ride_type):
    con = sqlite3.connect(DB)
    ts = datetime.now().isoformat()
    for q in quotes:
        con.execute(
            "INSERT INTO history (ts,pickup,destination,ride_type,provider,fare,eta,surge,distance_km) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, pickup, destination, ride_type, q["provider"], q["fare"],
             q["eta"], q["surge"], q["distance_km"]))
    con.commit()
    con.close()


# ─────────────────────────────────────────────
# 5. API ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/compare", methods=["POST"])
def compare():
    data = request.get_json() or {}
    pickup = (data.get("pickup") or "").strip()
    destination = (data.get("destination") or "").strip()
    ride_type = data.get("ride_type", "auto")

    if not pickup or not destination:
        return jsonify({"error": "Pickup and destination are required."}), 400
    if pickup.lower() == destination.lower():
        return jsonify({"error": "Pickup and destination cannot be the same."}), 400
    if ride_type not in RIDE_TYPES:
        return jsonify({"error": "Invalid ride type."}), 400

    # collect quotes (small delay to feel 'live')
    time.sleep(random.uniform(0.4, 0.9))
    quotes = [get_quote(name, pickup, destination, ride_type) for name in PROVIDERS]
    ok = [q for q in quotes if q["status"] == "available"]

    if not ok:
        return jsonify({"error": "All providers are unavailable. Try again."}), 503

    # value score: 60% price + 30% eta + 10% surge (higher is better)
    max_f, min_f = max(q["fare"] for q in ok), min(q["fare"] for q in ok)
    max_e, min_e = max(q["eta"] for q in ok), min(q["eta"] for q in ok)
    max_s, min_s = max(q["surge"] for q in ok), min(q["surge"] for q in ok)

    def norm(val, lo, hi):
        return 1.0 if hi == lo else 1 - (val - lo) / (hi - lo)

    for q in ok:
        q["score"] = round(
            0.6 * norm(q["fare"], min_f, max_f)
            + 0.3 * norm(q["eta"], min_e, max_e)
            + 0.1 * norm(q["surge"], min_s, max_s), 3)

    cheapest = min(ok, key=lambda q: q["fare"])
    fastest = min(ok, key=lambda q: q["eta"])
    best = max(ok, key=lambda q: q["score"])

    fares = [q["fare"] for q in ok]
    variation = {"max": max(fares), "min": min(fares),
                 "diff": max(fares) - min(fares),
                 "pct": round((max(fares) - min(fares)) / min(fares) * 100, 1)}

    # insights (simple rules)
    lo_surge_q = min(ok, key=lambda q: q["surge"])
    insights = [
        f"💡 {cheapest['provider']} is currently ₹{variation['diff']} cheaper than the costliest option.",
        f"💡 {lo_surge_q['provider']} has the lowest surge ({lo_surge_q['surge']}x).",
        f"⚡ {fastest['provider']} is the fastest ({fastest['eta']} min).",
        f"📊 Prices are about {variation['pct']}% apart across providers.",
        f"🏆 {best['provider']} has the best price-to-ETA combination "
        f"(value score {round(best['score'] * 100)}/100).",
    ]

    save_comparison(quotes, pickup, destination, ride_type)

    return jsonify({
        "timestamp": datetime.now().strftime("%I:%M:%S %p"),
        "quotes": quotes, "cheapest": cheapest["provider"],
        "fastest": fastest["provider"], "best": best["provider"],
        "variation": variation, "insights": insights,
        "links": build_links(pickup, destination),
    })


@app.route("/api/history")
def history():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM history ORDER BY ts DESC, id DESC LIMIT 90").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/history/<int:rid>", methods=["DELETE"])
def delete_history(rid):
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM history WHERE id=?", (rid,))
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM history")
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/trends")
def trends():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT ts, provider, fare FROM history ORDER BY ts ASC LIMIT 90").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


db_init()
if __name__ == "__main__":
    print("🚦 Ride Fare Radar → http://localhost:8000")
    print("   From your phone (same Wi-Fi): use your PC's IP, e.g. http://192.168.1.5:8000")
    # host="0.0.0.0" makes it reachable from your phone → app deep-link prefill works
    app.run(debug=True, host="0.0.0.0", port=8000)