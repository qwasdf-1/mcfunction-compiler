#!/usr/bin/env python3
"""CI-only Fabric dedicated-server smoke check with no mc_harness dependency.

This is deliberately *not* a replacement for the project's differential
mc_harness suite. It verifies that the pinned Java/Fabric dependencies can
launch a real 26.3 server, accept RCON commands, load fixture functions,
and preserve a simple scoreboard result with the wrapper off and on.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "build" / "reports" / "ci-server-smoke"
RUNS = ROOT / "run"
MODES = ("off", "on")


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        block = sock.recv(size - len(data))
        if not block:
            raise ConnectionError("RCON closed the socket unexpectedly")
        data.extend(block)
    return bytes(data)


def send_packet(sock: socket.socket, packet_id: int, packet_type: int, payload: str) -> None:
    body = struct.pack("<ii", packet_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
    sock.sendall(struct.pack("<i", len(body)) + body)


def read_packet(sock: socket.socket) -> tuple[int, int, str]:
    (size,) = struct.unpack("<i", read_exact(sock, 4))
    if size < 10 or size > 1048576:
        raise ValueError(f"Invalid RCON packet length: {size}")
    body = read_exact(sock, size)
    packet_id, packet_type = struct.unpack("<ii", body[:8])
    return packet_id, packet_type, body[8:-2].decode("utf-8", errors="replace")


class Rcon:
    def __init__(self, port: int, password: str):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.sock.settimeout(6)
        try:
            send_packet(self.sock, 1, 3, password)
            # An auth request may have an empty response packet before its auth reply.
            for _ in range(3):
                packet_id, packet_type, _ = read_packet(self.sock)
                if packet_id == -1:
                    raise RuntimeError("RCON authentication rejected")
                if packet_id == 1 and packet_type == 2:
                    break
            else:
                raise RuntimeError("No matching RCON authentication packet")
        except BaseException:
            self.sock.close()
            raise

    def command(self, command: str) -> str:
        send_packet(self.sock, 2, 2, command)
        packet_id, _, response = read_packet(self.sock)
        if packet_id != 2:
            raise RuntimeError(f"Unexpected RCON packet id {packet_id} for {command}")
        return response

    def close(self) -> None:
        self.sock.close()


def wait_for_rcon(process: subprocess.Popen, port: int, password: str,
                  timeout_seconds: int = 180) -> Rcon:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server process exited before readiness: {process.returncode}")
        try:
            return Rcon(port, password)
        except (OSError, ConnectionError, TimeoutError, RuntimeError, ValueError) as exc:
            last_error = str(exc)
            time.sleep(1)
    raise TimeoutError(f"Server RCON not ready: {last_error}")


def check_mode(mode: str) -> dict[str, str]:
    run_dir = RUNS / f"ci-research-{mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    (run_dir / "server.properties").write_text(
        "\n".join((
            "online-mode=false",
            "enable-rcon=true",
            "broadcast-rcon-to-ops=false",
            "level-type=minecraft:flat",
            "view-distance=2",
            "simulation-distance=2",
            "max-tick-time=-1",
            f"server-port={port}",
            f"rcon.port={rcon_port}",
            f"rcon.password={password}",
        )) + "\n",
        encoding="utf-8",
    )
    log_file = REPORTS / f"fabric-wrapper-{mode}.log"
    env = dict(os.environ)
    env["FC_WRAPPER_PROBE"] = "true" if mode == "on" else "false"
    env["FC_SELECTIVE_MACRO_ARGUMENTS"] = "false"
    command = [
        str(ROOT / "gradlew"),
        "--no-daemon",
        f"-PfcRunDirectory={run_dir.relative_to(ROOT)}",
        "runServer",
    ]
    print(f"Starting Minecraft 26.3 Fabric server, wrapper={mode}", flush=True)
    with log_file.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        client: Rcon | None = None
        try:
            client = wait_for_rcon(process, rcon_port, password)
            status = client.command("functioncompiler status")
            expected = f"wrapped={'true' if mode == 'on' else 'false'}"
            if "FC_PROBE present=true" not in status or expected not in status:
                raise AssertionError(f"Incorrect wrapper status: {status!r}")
            if "tag_same_instance=true" not in status:
                raise AssertionError(f"Tag and direct function mismatch: {status!r}")

            objective = client.command("scoreboard objectives add fc_probe dummy")
            reset = client.command("scoreboard players set #fcprobe fc_probe 0")
            invoked = client.command("function function_compiler_probe:quota_three")
            score = client.command("scoreboard players get #fcprobe fc_probe")
            if not re.search(r"(?<![0-9])3(?![0-9])", score):
                raise AssertionError(f"Expected scoreboard value 3, got: {score!r}")
            print(
                f"PASS wrapper={mode} status={status[:120]!r} score={score!r}",
                flush=True,
            )
            return {"mode": mode, "status": status, "score": score,
                    "objective": objective, "reset": reset, "invoked": invoked}
        except BaseException:
            print(f"Server log retained at {log_file}", file=sys.stderr, flush=True)
            raise
        finally:
            if client is not None:
                try:
                    client.command("stop")
                except (OSError, RuntimeError):
                    pass
                client.close()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def main() -> int:
    results = [check_mode(mode) for mode in MODES]
    if results[0]["score"] != results[1]["score"]:
        raise AssertionError("Wrapper-on and wrapper-off differ in scoreboard response")
    print("PASS: dedicated Fabric server boots, function loads, and wrapper parity holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
