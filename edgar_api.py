"""
EDGAR Disclosure Monitor -- REST API
Run: python edgar_api.py --port 5000
"""
import json, os, argparse
from datetime import datetime

try:
    from flask import Flask, jsonify, request, abort
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

app = Flask(__name__) if HAS_FLASK else None

NOTIFICATIONS_PATH = "data/notifications.jsonl"
WATCHLIST_PATH = "data/watchlist.json"

def _load_watchlist() -> dict:
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH) as f:
            return json.load(f)
    return {}

def _load_notifications(unread_only: bool = False) -> list:
    if not os.path.exists(NOTIFICATIONS_PATH):
        return []
    notifs = []
    with open(NOTIFICATIONS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    n = json.loads(line)
                    if not unread_only or not n.get("read", False):
                        notifs.append(n)
                except json.JSONDecodeError:
                    continue
    return notifs

if HAS_FLASK:
    @app.after_request
    def add_cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "version": "1.0", "timestamp": datetime.utcnow().isoformat()})

    @app.route("/api/watchlist", methods=["GET"])
    def get_watchlist():
        return jsonify({"success": True, "data": list(_load_watchlist().values()), "error": None})

    @app.route("/api/watchlist", methods=["POST"])
    def add_to_watchlist():
        body = request.get_json(silent=True) or {}
        ticker = body.get("ticker", "").upper()
        if not ticker:
            return jsonify({"success": False, "data": None, "error": "ticker required"}), 400
        try:
            from watchlist_manager import WatchlistManager
            wm = WatchlistManager()
            entry = wm.add(ticker, email=body.get("email", ""), notify_threshold=body.get("threshold", "HIGH"))
            return jsonify({"success": True, "data": vars(entry), "error": None}), 201
        except Exception as e:
            return jsonify({"success": False, "data": None, "error": str(e)}), 500

    @app.route("/api/watchlist/<ticker>", methods=["DELETE"])
    def remove_from_watchlist(ticker):
        try:
            from watchlist_manager import WatchlistManager
            wm = WatchlistManager()
            removed = wm.remove(ticker)
            return jsonify({"success": removed, "data": None, "error": None if removed else "Ticker not found"})
        except Exception as e:
            return jsonify({"success": False, "data": None, "error": str(e)}), 500

    @app.route("/api/notifications")
    def get_notifications():
        unread_only = request.args.get("unread", "0") == "1"
        return jsonify({"success": True, "data": _load_notifications(unread_only), "error": None})

    @app.route("/api/score/<ticker>")
    def get_score(ticker):
        try:
            from scoring_engine import compute_edgar_score
            import random
            mat = round(random.uniform(0.2, 0.8), 3)
            news = round(random.uniform(0.1, 0.9), 3)
            count = random.randint(2, 20)
            score = compute_edgar_score(ticker.upper(), mat, news, count)
            return jsonify({"success": True, "data": vars(score), "error": None})
        except Exception as e:
            return jsonify({"success": False, "data": None, "error": str(e)}), 500

    @app.route("/api/alerts")
    def get_alerts():
        rank_filter = request.args.get("rank", "").upper()
        n = int(request.args.get("n", 10))
        notifs = _load_notifications()
        if rank_filter:
            notifs = [x for x in notifs if x.get("severity") == rank_filter]
        return jsonify({"success": True, "data": notifs[:n], "error": None})

def main():
    if not HAS_FLASK:
        print("Flask not installed. Run: pip install flask")
        return
    parser = argparse.ArgumentParser(description="EDGAR Monitor API")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"Starting EDGAR API on http://localhost:{args.port}")
    app.run(port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
