"""Aegis Mind - dependency-light HTTP + JSON backend (Phase 13).

A stdlib-only web backend (no external dependencies) that exposes one live
``Mind`` over a small JSON API and serves the dashboard in ``webui/index.html``.
A ``MindService`` facade owns the Mind, a bounded ring buffer of loop events,
and the serialization that keeps every payload JSON-safe (the OODA cycle is a
dataclass and is flattened here). A ``BaseHTTPRequestHandler`` maps routes onto
that facade; a ``ThreadingHTTPServer`` runs it.

SAFETY: unchanged and cumulative from the CLI. The API only drives *cognition*
-- perception, feedback, teaching, deliberation, consolidation, and the
sense-only watch loop. There is no hardware / motor endpoint, the brain can
only think, and the server binds localhost by default so nothing is exposed off
the machine.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple

from aegis_mind.core.mind import Mind
from aegis_mind.core.learning import FEATURE_NAMES
from aegis_mind.utils.config import load_config

# Run relative to this file so config.yaml / webui / memory_store resolve the
# same way whether launched from the repo root or elsewhere.
BASE = Path(__file__).resolve().parent
os.chdir(BASE)


# ---------------------------------------------------------------------------- #
# serialization helpers                                                        #
# ---------------------------------------------------------------------------- #
def _serialize_cycle(cycle: Any) -> Optional[Dict[str, Any]]:
    """Flatten an OODACycle dataclass to a JSON-safe dict.

    Drops the raw stimulus (large / not always serializable) and adds a
    human-readable ``render`` produced by the cycle itself.
    """
    if cycle is None:
        return None
    d = dataclasses.asdict(cycle)
    obs = d.get("observation")
    if isinstance(obs, dict):
        obs.pop("stimulus", None)
    d["render"] = cycle.render()
    return d


def _serialize_perceive(result: Dict[str, Any]) -> Dict[str, Any]:
    """The perceive_api result, with its OODACycle field made JSON-safe."""
    out = dict(result)
    out["ooda"] = _serialize_cycle(result.get("ooda"))
    return out


# ---------------------------------------------------------------------------- #
# the service facade                                                           #
# ---------------------------------------------------------------------------- #
class MindService:
    """A thin, JSON-oriented facade over a single ``Mind``."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.mind = Mind(config)
        self._events: Deque[Dict[str, Any]] = deque(maxlen=200)
        self._events_lock = threading.Lock()
        self._seq = 0
        # Capture background-loop announcements into the ring buffer so the
        # dashboard can poll them without holding a connection open.
        self.mind.loop.on_event = self._capture_event

    # -- events ------------------------------------------------------------- #
    def _capture_event(self, text: str) -> None:
        with self._events_lock:
            self._seq += 1
            self._events.append({"seq": self._seq, "text": str(text)})

    def events_since(self, since: int) -> Dict[str, Any]:
        with self._events_lock:
            fresh = [e for e in self._events if e["seq"] > since]
            return {"events": fresh, "next": self._seq}

    # -- the big read: everything the dashboard renders --------------------- #
    def state(self) -> Dict[str, Any]:
        m = self.mind

        lstats = m.learning.stats()
        ranked = sorted(zip(FEATURE_NAMES, m.learning.model.weights),
                        key=lambda kv: -abs(kv[1]))
        top_weights = [{"name": n, "weight": round(float(w), 4)} for n, w in ranked[:8]]
        salient = [{"word": w, "salience": round(float(s), 3)}
                   for w, s in m.learning.lexicon.top(8, "positive")]

        return {
            "state": {
                "name": m.state.name,
                "version": m.state.version,
                "cycles": m.state.cycle_count,
                "focus": m.state.focus,
                "threat_level": m.state.threat_level,
            },
            "learning": {
                "examples_seen": lstats["examples_seen"],
                "alpha": lstats["trust_in_learning_alpha"],
                "alpha_max": m.learning.alpha_max,
                "loss": lstats["model_loss_ema"],
                "feedback_updates": lstats["feedback_updates"],
                "lexicon_terms": lstats["lexicon_terms"],
                "habituated_patterns": lstats["habituated_patterns"],
                "top_weights": top_weights,
                "salient_words": salient,
            },
            "affect": m.affect.as_dict(),
            "chat": {
                "enabled": m.chat.enabled,
                "persona": m.chat.persona,
                "user_name": m.chat.profile.get("name"),
                "taught": len(m.chat.taught),
                "exchanges": m.chat.exchanges,
            },
            "domain": {
                "available": m.domain.available(),
                "counts": m.domain.counts(),
                "total_entities": m.domain.total_entities(),
            },
            "drives": m.drives.as_dict(),
            "goals": m.goals.as_dict(),
            "consolidation": m.consolidator.as_dict(),
            "knowledge": m.knowledge.as_dict(),
            "brain": m.brain.as_dict(),
            "watch": {
                "running": m.loop.is_running(),
                "ticks": m.loop.ticks,
                "perceived": m.loop.perceived,
                "notable": m.loop.notable,
                "musings": m.loop.musings,
                "interval": m.loop.interval,
            },
            "memory": {"recent": m.memory.recent(12)},
            "last_cycle": _serialize_cycle(m.last_cycle),
        }

    # -- actions ------------------------------------------------------------ #
    def perceive(self, text: str) -> Dict[str, Any]:
        return _serialize_perceive(self.mind.perceive_api(text))

    def feedback(self, memory_id: int, good: bool) -> Dict[str, Any]:
        return {"message": self.mind.feedback(memory_id, good)}

    def teach(self, pattern: str, reply: str) -> Dict[str, Any]:
        return {"message": self.mind.chat.teach(pattern, reply)}

    def prioritize(self, memory_id: int) -> Dict[str, Any]:
        return {"ok": bool(self.mind.memory.boost_importance(memory_id))}

    def forget(self, memory_id: int) -> Dict[str, Any]:
        return {"ok": bool(self.mind.memory.forget(memory_id))}

    def watch(self, action: str) -> Dict[str, Any]:
        action = (action or "status").lower()
        if action == "start":
            message = self.mind.loop.start()
        elif action == "stop":
            message = self.mind.loop.stop()
        else:
            message = self.mind.loop.status_text()
        return {"message": message, "running": self.mind.loop.is_running()}

    def goal(self, title: str) -> Dict[str, Any]:
        return {"message": self.mind.goals.add_goal(title)}

    def goal_drop(self, goal_id: int) -> Dict[str, Any]:
        return {"message": self.mind.goals.drop(goal_id)}

    def pursue(self) -> Dict[str, Any]:
        return {"message": self.mind.deliberate_once()}

    def sleep(self) -> Dict[str, Any]:
        return {"message": self.mind.consolidate_now()}

    def close(self) -> None:
        self.mind.close()


# ---------------------------------------------------------------------------- #
# HTTP handler                                                                 #
# ---------------------------------------------------------------------------- #
class MindHandler(BaseHTTPRequestHandler):
    service: MindService = None  # type: ignore[assignment]  # injected on the class

    server_version = "AegisMind/13"

    # -- low-level plumbing -------------------------------------------------- #
    def log_message(self, *_args: Any) -> None:  # keep the console quiet
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}

    def _serve_index(self) -> None:
        path = BASE / "webui" / "index.html"
        try:
            body = path.read_bytes()
        except OSError:
            self._send_error_json("index.html not found", status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _query(path: str) -> Tuple[str, Dict[str, str]]:
        if "?" not in path:
            return path, {}
        base, _, qs = path.partition("?")
        params: Dict[str, str] = {}
        for pair in qs.split("&"):
            if not pair:
                continue
            key, _, val = pair.partition("=")
            params[key] = val
        return base, params

    # -- verbs --------------------------------------------------------------- #
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path, params = self._query(self.path)
        try:
            if path == "/":
                self._serve_index()
            elif path == "/api/state":
                self._send_json(self.service.state())
            elif path == "/api/events":
                try:
                    since = int(params.get("since", "0"))
                except (TypeError, ValueError):
                    since = 0
                self._send_json(self.service.events_since(since))
            else:
                self._send_error_json("not found", status=404)
        except Exception as exc:  # never leak a stack trace / take the server down
            self._send_error_json(f"internal error: {exc}", status=500)

    def do_POST(self) -> None:  # noqa: N802
        path, _ = self._query(self.path)
        try:
            payload = self._read_json()
        except (ValueError, json.JSONDecodeError):
            self._send_error_json("invalid JSON body")
            return

        try:
            if path == "/api/perceive":
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send_error_json("missing 'text'")
                    return
                self._send_json(self.service.perceive(text))

            elif path == "/api/feedback":
                mid = payload.get("id")
                if not isinstance(mid, int) or isinstance(mid, bool):
                    self._send_error_json("'id' must be an integer")
                    return
                self._send_json(self.service.feedback(mid, bool(payload.get("good", False))))

            elif path == "/api/teach":
                pattern = str(payload.get("pattern", "")).strip()
                reply = str(payload.get("reply", "")).strip()
                if not pattern or not reply:
                    self._send_error_json("missing 'pattern' or 'reply'")
                    return
                self._send_json(self.service.teach(pattern, reply))

            elif path == "/api/prioritize":
                mid = payload.get("id")
                if not isinstance(mid, int) or isinstance(mid, bool):
                    self._send_error_json("'id' must be an integer")
                    return
                self._send_json(self.service.prioritize(mid))

            elif path == "/api/forget":
                mid = payload.get("id")
                if not isinstance(mid, int) or isinstance(mid, bool):
                    self._send_error_json("'id' must be an integer")
                    return
                self._send_json(self.service.forget(mid))

            elif path == "/api/watch":
                self._send_json(self.service.watch(str(payload.get("action", "status"))))

            elif path == "/api/goal":
                title = str(payload.get("title", "")).strip()
                if not title:
                    self._send_error_json("missing 'title'")
                    return
                self._send_json(self.service.goal(title))

            elif path == "/api/goal_drop":
                gid = payload.get("id")
                if not isinstance(gid, int) or isinstance(gid, bool):
                    self._send_error_json("'id' must be an integer")
                    return
                self._send_json(self.service.goal_drop(gid))

            elif path == "/api/pursue":
                self._send_json(self.service.pursue())

            elif path == "/api/sleep":
                self._send_json(self.service.sleep())

            else:
                self._send_error_json("not found", status=404)
        except Exception as exc:
            self._send_error_json(f"internal error: {exc}", status=500)


# ---------------------------------------------------------------------------- #
# entry point                                                                  #
# ---------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Aegis Mind web backend (Phase 13).")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost)")
    parser.add_argument("--port", type=int, default=8770, help="bind port (default: 8770)")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    service = MindService(config)
    MindHandler.service = service

    httpd = ThreadingHTTPServer((args.host, args.port), MindHandler)
    print("=" * 60)
    print("Aegis Mind web backend (Phase 13: The Resonance Workspace)")
    print(f"  serving  http://{args.host}:{args.port}/")
    print("  API only drives cognition -- no hardware endpoint, localhost bind.")
    print("  Press Ctrl+C to stop and save all state.")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down -- saving every store...")
    finally:
        httpd.shutdown()
        service.close()
        print("Aegis Mind stopped. State saved. Goodbye.")


if __name__ == "__main__":
    main()
