"""Run this file: python main.py. Opens the local game in your browser."""

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from urllib.parse import urlsplit, unquote
import webbrowser

from game import Game

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def create_server(game, root=ROOT, port=0):
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()
    root = Path(root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {"error": "Invalid host."})
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                with lock:
                    return self.respond(200, {"state": game.public(), "token": token})
            if path == "/":
                path = "/index.html"
            allowed = path in ("/index.html", "/game.js", "/commissions.js", "/ui-icons.js", "/opening.js", "/skills.js", "/equipment.js", "/battle-effects.js", "/finance.js", "/audio-manager.js", "/character-creation.js", "/game.css", "/item-icons.html", "/item-icons.css") or (path.startswith("/assets/") and path.endswith(".png")) or (path.startswith("/assets/audio/") and path.endswith((".mp4", ".wav", ".mp3", ".m4a")))
            target = (root / path.lstrip("/")).resolve()
            if not allowed or not target.is_relative_to(root) or not target.is_file():
                return self.respond(404, {"error": "Not found."})
            return self.respond(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.valid_host() or self.headers.get("X-Game-Token") != token or self.headers.get("Origin", origin) != origin:
                return self.respond(403, {"error": "Invalid session."})
            if self.path != "/api/action" or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond(400, {"error": "Expected a JSON game action."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Invalid request.")
                with lock:
                    if payload.get("action") == "commission_preview":
                        return self.respond(200, game.commission_preview(payload.get("customer_id"), payload.get("region_id"), payload.get("gear"), payload.get("use_relic", False), payload.get("deep", False), payload.get("weapon"), payload.get("armour")))
                    if payload.get("action") == "preview":
                        return self.respond(200, game.negotiation_preview(payload.get("price")))
                    result = game.action(payload.get("action"), payload)
                return self.respond(200, {"state": result})
            except (ValueError, TypeError) as exc:
                return self.respond(400, {"error": str(exc)})
            except OSError:
                return self.respond(500, {"error": "Could not save the game. Check the save folder permissions."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    default_save = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DungeonMerchant/save.json") if getattr(sys, "frozen", False) else ROOT / "saves/save.json"
    game = Game(ROOT / "assets", args.save or default_save)
    server = create_server(game, port=args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Dungeon Merchant: {url}\nSave: {game.save_path}\nPress Ctrl+C to stop the local server.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
