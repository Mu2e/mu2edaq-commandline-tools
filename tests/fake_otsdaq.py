"""Deterministic in-process HTTP harness for otsdaq client tests."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlsplit


@dataclass
class RecordedRequest:
    role: str
    path: str
    query: Dict[str, List[str]]
    form: Dict[str, List[str]]


@dataclass
class FakeResponse:
    body: str
    status: int = 200
    content_type: str = "text/xml"


class FakeOtsdaq:
    """Three local origins representing gateway, Slow Controls, and TFM."""

    def __init__(self) -> None:
        self.requests: List[RecordedRequest] = []
        self.routes: Dict[Tuple[str, str], List[FakeResponse]] = {}
        self._servers: Dict[str, ThreadingHTTPServer] = {}
        self._threads: List[threading.Thread] = []

    def __enter__(self) -> "FakeOtsdaq":
        for role in ("gateway", "slow-controls", "tfm"):
            harness = self

            class Handler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
                    parsed = urlsplit(self.path)
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length).decode("utf-8")
                    form = parse_qs(body, keep_blank_values=True)
                    harness.requests.append(
                        RecordedRequest(self.role_name, parsed.path, query, form)
                    )
                    request_type = (
                        query.get("RequestType")
                        or query.get("StateMachine")
                        or [""]
                    )[0]
                    responses = harness.routes.get((self.role_name, request_type))
                    response = (
                        responses.pop(0)
                        if responses
                        else FakeResponse(
                            "<ROOT><DATA Error=\"no fake route for %s\"/></ROOT>"
                            % request_type,
                            404,
                        )
                    )
                    self.send_response(response.status)
                    self.send_header("Content-Type", response.content_type)
                    self.end_headers()
                    self.wfile.write(response.body.encode("utf-8"))

                def log_message(self, format: str, *args: object) -> None:
                    return

            Handler.role_name = role
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            self._servers[role] = server
            thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.01},
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        return self

    def __exit__(self, *args: object) -> None:
        for server in self._servers.values():
            server.shutdown()
            server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)

    def origin(self, role: str) -> str:
        host, port = self._servers[role].server_address
        return "http://%s:%d" % (host, port)

    def add(
        self,
        role: str,
        request_type: str,
        body: str,
        *,
        status: int = 200,
        repeat: int = 1,
    ) -> None:
        self.routes.setdefault((role, request_type), []).extend(
            FakeResponse(body, status) for _ in range(repeat)
        )
