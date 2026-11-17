"""Server lifecycle primitives for differential-oracle campaigns.

Extracted (roadmap step 6, batch 20) from
`function-compiler/scripts/run_runtime_probe.py` and
`function-compiler/scripts/run_entity_datapack_profile.py`. Everything here is
engine-agnostic: RCON transport, the pinned official server jar, the Mojang
packet-report extraction, RCON readiness, and standard server properties.

The headless protocol client is *not* here. By project decision the client
stays project-owned and pinned to its target protocol; the packet-report
parser is injected (``packet_ids_cls``) so a shared-harness change cannot
re-target a project's client.
"""

from __future__ import annotations

import hashlib
import os
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

#: SHA-256 of the pinned official Minecraft 26.3 server jar. A campaign that
#: cannot verify its server jar against this pin fails before measuring.
MINECRAFT_SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"

#: Historical alias kept for the consuming projects' import sites.
SERVER_JAR_SHA256 = MINECRAFT_SERVER_SHA256

#: Loom cache layout of the pinned server jar, relative to a Gradle home.
SERVER_JAR_RELATIVE = Path("caches") / "fabric-loom" / "26.3" / "minecraft-server.jar"


class RconClient:
    """Minimal binary RCON client: one request/response per command."""

    def __init__(self, host: str, port: int, password: str) -> None:
        self.socket = socket.create_connection((host, port), timeout=5)
        self.socket.settimeout(10)
        self.request_id = 0
        response_id, response_type, _ = self._request(3, password)
        if response_id == -1 or response_type != 2:
            raise RuntimeError("RCON authentication failed")

    def close(self) -> None:
        self.socket.close()

    def command(self, command: str) -> str:
        response_id, response_type, response = self._request(2, command)
        if response_id != self.request_id or response_type != 0:
            raise RuntimeError(
                f"Unexpected RCON command response id={response_id} type={response_type}"
            )
        return response

    def _request(self, packet_type: int, body: str) -> tuple[int, int, str]:
        self.request_id += 1
        packet_id = self.request_id
        encoded = body.encode("utf-8") + b"\0\0"
        payload = struct.pack("<ii", packet_id, packet_type) + encoded
        self.socket.sendall(struct.pack("<i", len(payload)) + payload)

        packet_length = struct.unpack("<i", self._read_exact(4))[0]
        packet = self._read_exact(packet_length)
        response_id, response_type = struct.unpack("<ii", packet[:8])
        response_body = packet[8:-2].decode("utf-8", errors="replace")
        return response_id, response_type, response_body

    def _read_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.socket.recv(length - len(chunks))
            if not chunk:
                raise ConnectionError("RCON closed before sending a full packet")
            chunks.extend(chunk)
        return bytes(chunks)


class DrainingRconClient(RconClient):
    """Ignore leftover split response packets before returning the next command result.

    Some servers split long command responses across multiple RCON packets; a
    plain client then reads the tail as the next command's reply. Draining the
    stale packets (``response_id < request_id``) keeps every command's response
    aligned.
    """

    def command(self, command: str) -> str:
        self.request_id += 1
        request_id = self.request_id
        encoded = command.encode("utf-8") + b"\0\0"
        payload = struct.pack("<ii", request_id, 2) + encoded
        self.socket.sendall(struct.pack("<i", len(payload)) + payload)
        while True:
            packet_length = struct.unpack("<i", self._read_exact(4))[0]
            packet = self._read_exact(packet_length)
            response_id, response_type = struct.unpack("<ii", packet[:8])
            response = packet[8:-2].decode("utf-8", errors="replace")
            if response_id < request_id:
                continue
            if response_id != request_id or response_type != 0:
                raise RuntimeError(
                    f"Unexpected RCON response id={response_id} type={response_type}; expected {request_id}"
                )
            return response


def default_cache_roots() -> list[Path]:
    """Gradle homes searched for the pinned server jar, in order."""
    roots: list[Path] = []
    configured = os.environ.get("GRADLE_USER_HOME")
    if configured:
        roots.append(Path(configured).expanduser().resolve())
    roots.append(Path.home() / ".gradle")
    return roots


def locate_official_server_jar(
    expected_sha256: str = MINECRAFT_SERVER_SHA256,
    cache_roots: list[Path] | None = None,
) -> Path:
    """Locate and fingerprint-verify the pinned official 26.3 server jar."""
    if cache_roots is None:
        cache_roots = default_cache_roots()
    for gradle_home in cache_roots:
        candidate = gradle_home / SERVER_JAR_RELATIVE
        if candidate.is_file():
            with candidate.open("rb") as server_file:
                digest = hashlib.file_digest(server_file, "sha256").hexdigest()
            if digest != expected_sha256:
                raise RuntimeError(
                    f"Cached server jar fingerprint mismatch at {candidate}: {digest}"
                )
            return candidate
    raise FileNotFoundError(
        "Official Minecraft 26.3 server jar is not cached. Run the pinned Gradle "
        "build once or set GRADLE_USER_HOME to the cache containing it."
    )


def generate_packet_ids(server_jar: Path, packet_ids_cls: Any) -> Any:
    """Extract the server jar's ``packets.json`` report and parse it.

    ``packet_ids_cls`` is the consuming project's protocol-client class (it
    must expose a ``load(path)`` classmethod). The report is generated from the
    exact jar under measurement, so packet IDs always match the pinned server.
    """
    with tempfile.TemporaryDirectory(prefix="mc-harness-packet-report-") as temp:
        temp_dir = Path(temp)
        report_root = temp_dir / "packet-report"
        report = subprocess.run(
            [
                "java",
                "-DbundlerMainClass=net.minecraft.data.Main",
                "-jar",
                str(server_jar),
                "--reports",
                "--output",
                str(report_root),
            ],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )
        packet_report = report_root / "reports" / "packets.json"
        if report.returncode != 0 or not packet_report.is_file():
            raise RuntimeError(
                "Minecraft packet report generation failed: " + report.stdout[-1600:]
            )
        return packet_ids_cls.load(packet_report)


def wait_for_rcon(
    process: subprocess.Popen[bytes],
    *,
    host: str,
    port: int,
    password: str,
    client_cls: type = RconClient,
    timeout_seconds: int = 240,
    poll_seconds: float = 1.0,
) -> Any:
    """Wait until the server's RCON answers, or the process dies, or time runs out."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft/server exited early with code {process.returncode}")
        try:
            return client_cls(host, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(poll_seconds)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def accept_eula(server_dir: Path) -> None:
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")


def write_server_properties(server_dir: Path, properties: dict[str, str]) -> None:
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / "server.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()),
        encoding="utf-8",
    )


def standard_server_properties(
    *,
    server_port: int,
    rcon_port: int,
    rcon_password: str,
    level_name: str = "world",
    host: str = "127.0.0.1",
    level_seed: str | None = None,
    view_distance: int = 4,
    simulation_distance: int = 4,
) -> dict[str, str]:
    """The shared deterministic-server property set every campaign arm uses."""
    properties = {
        "enable-rcon": "true",
        "rcon.password": rcon_password,
        "rcon.port": str(rcon_port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": host,
        "server-port": str(server_port),
        "level-name": level_name,
        "online-mode": "false",
        "white-list": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": str(view_distance),
        "simulation-distance": str(simulation_distance),
        "sync-chunk-writes": "false",
        "pause-when-empty-seconds": "-1",
    }
    if level_seed is not None:
        properties["level-seed"] = level_seed
    return properties
