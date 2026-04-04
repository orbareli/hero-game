"""
db/client.py
------------
TCP client for OrSQL server.

Sends raw SQL strings to the server (localhost:5555),
receives JSON responses, and returns parsed Python objects.

Usage:
    db = DBClient()
    rows = db.query("SELECT * FROM characters")
    db.execute("INSERT INTO players (username, coins, gems) VALUES ('hero', 100, 10)")
"""

import socket
import json
import threading
from typing import Any

HOST = "localhost"
PORT = 5555
TIMEOUT = 10        # seconds before giving up on a response
BUFFER_SIZE = 65536 # 64KB — enough for large SELECT results


class DBError(Exception):
    """Raised when the DB server returns an error."""
    pass


class DBClient:
    """
    Thread-safe TCP client for OrSQL.

    One persistent connection per instance. Uses a lock so multiple
    FastAPI coroutines can share one client safely (since OrSQL is
    single-threaded, we serialize all requests through the lock).
    """

    def __init__(self, host: str = HOST, port: int = PORT):
        self.host = host
        self.port = port
        self._lock = threading.Lock()

    def _send(self, sql: str) -> dict:
        """
        Open a fresh TCP connection, send SQL, read full response, close.

        OrSQL server closes the connection after each response, so we
        reconnect for every query. This matches server.py behaviour.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)

        try:
            sock.connect((self.host, self.port))
            sock.sendall(sql.strip().encode("utf-8"))

            # Read until server closes connection
            chunks = []
            while True:
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
                except socket.timeout:
                    break

            raw = b"".join(chunks)
            if not raw:
                raise DBError("Empty response from DB server")

            return json.loads(raw.decode("utf-8"))

        finally:
            sock.close()

    def _run(self, sql: str) -> Any:
        """Send SQL, parse response, raise on error."""
        with self._lock:
            response = self._send(sql)

        if response.get("error"):
            raise DBError(f"DB error: {response['error']}  |  SQL: {sql}")

        return response.get("result")

    # ---------------------------------------------------------------- #
    #  Public API                                                        #
    # ---------------------------------------------------------------- #

    def query(self, sql: str) -> list[dict]:
        """
        Run a SELECT — always returns a list of dicts.
        Returns [] if no rows found.
        """
        result = self._run(sql)
        if result is None:
            return []
        if isinstance(result, list):
            return result
        # Some SELECTs return a single dict — normalise
        if isinstance(result, dict):
            return [result]
        return []

    def execute(self, sql: str) -> str:
        """
        Run INSERT / UPDATE / DELETE / CREATE TABLE / DROP TABLE.
        Returns the status string from OrSQL (e.g. "Inserted record with id=3.").
        """
        result = self._run(sql)
        return str(result) if result is not None else "OK"

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        try:
            rows = self.query("SHOW TABLES")
            names = [r.get("table_name", "") for r in rows]
            return table_name in names
        except DBError:
            return False

    def ping(self) -> bool:
        """Check if the DB server is reachable."""
        try:
            self.query("SHOW TABLES")
            return True
        except Exception:
            return False


# ------------------------------------------------------------------ #
#  Module-level singleton — import and use anywhere                   #
# ------------------------------------------------------------------ #

_client: DBClient | None = None


def get_db() -> DBClient:
    """
    Return the module-level DBClient singleton.
    FastAPI dependency — use as:
        from db.client import get_db
        db = get_db()
    """
    global _client
    if _client is None:
        _client = DBClient()
    return _client
