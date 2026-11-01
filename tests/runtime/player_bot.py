"""Small offline protocol client for repeatable Minecraft 26.3 server probes."""

from __future__ import annotations

import hashlib
import socket
import struct
import threading
import uuid
import zlib
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = 777
PLAYER_ACTION_IDS = {
    "start_destroy_block": 0,
    "abort_destroy_block": 2,
    "stop_destroy_block": 3,
}


def encode_varint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    out = bytearray()
    while True:
        part = value & 0x7F
        value >>= 7
        if value:
            out.append(part | 0x80)
        else:
            out.append(part)
            return bytes(out)


class Writer:
    def __init__(self) -> None:
        self.data = bytearray()

    def varint(self, value: int) -> "Writer":
        self.data.extend(encode_varint(value))
        return self

    def string(self, value: str) -> "Writer":
        encoded = value.encode("utf-8")
        self.varint(len(encoded))
        self.data.extend(encoded)
        return self

    def boolean(self, value: bool) -> "Writer":
        self.data.append(1 if value else 0)
        return self

    def integer(self, value: int) -> "Writer":
        self.data.extend(struct.pack(">i", value))
        return self

    def ushort(self, value: int) -> "Writer":
        self.data.extend(struct.pack(">H", value))
        return self

    def long(self, value: int) -> "Writer":
        self.data.extend(struct.pack(">q", value))
        return self

    def float(self, value: float) -> "Writer":
        self.data.extend(struct.pack(">f", value))
        return self

    def double(self, value: float) -> "Writer":
        self.data.extend(struct.pack(">d", value))
        return self

    def raw(self, value: bytes) -> "Writer":
        self.data.extend(value)
        return self


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, count: int) -> bytes:
        end = self.offset + count
        if end > len(self.data):
            raise EOFError("truncated Minecraft packet")
        result = self.data[self.offset:end]
        self.offset = end
        return result

    def varint(self) -> int:
        value = 0
        for shift in range(0, 35, 7):
            byte = self.take(1)[0]
            value |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return value - (1 << 32) if value & (1 << 31) else value
        raise ValueError("Minecraft VarInt exceeds five bytes")

    def string(self) -> str:
        return self.take(self.varint()).decode("utf-8")

    def boolean(self) -> bool:
        return self.take(1) != b"\0"

    def integer(self) -> int:
        return struct.unpack(">i", self.take(4))[0]

    def long(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def float(self) -> float:
        return struct.unpack(">f", self.take(4))[0]

    def double(self) -> float:
        return struct.unpack(">d", self.take(8))[0]


class PacketIds:
    """Packet names and IDs loaded from the exact server jar's data report."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.by_name: dict[tuple[str, str], int] = {}
        self.by_id: dict[tuple[str, int], str] = {}
        for state, directions in report.items():
            for direction, packets in directions.items():
                if direction == "serverbound":
                    for name, details in packets.items():
                        self.by_name[(state, name.removeprefix("minecraft:"))] = details["protocol_id"]
                elif direction == "clientbound":
                    for name, details in packets.items():
                        self.by_id[(state, details["protocol_id"])] = name.removeprefix("minecraft:")

    @classmethod
    def load(cls, report_path: Path) -> "PacketIds":
        import json

        return cls(json.loads(report_path.read_text(encoding="utf-8")))

    def serverbound(self, state: str, name: str) -> int:
        return self.by_name[(state, name)]

    def clientbound(self, state: str, packet_id: int) -> str:
        return self.by_id.get((state, packet_id), f"unknown_{packet_id}")


def _frame(packet_id: int, body: bytes, compression_threshold: int | None) -> bytes:
    payload = encode_varint(packet_id) + body
    if compression_threshold is not None:
        if len(payload) >= compression_threshold:
            payload = encode_varint(len(payload)) + zlib.compress(payload)
        else:
            payload = b"\0" + payload
    return encode_varint(len(payload)) + payload


def _offline_uuid(name: str) -> uuid.UUID:
    raw = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode(), usedforsecurity=False).digest())
    raw[6] = (raw[6] & 0x0F) | 0x30
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw))


class PlayerBot:
    """Connects and answers the server packets needed to remain a stationary player."""

    def __init__(self, name: str, host: str, port: int, packet_ids: PacketIds) -> None:
        if not 1 <= len(name) <= 16:
            raise ValueError("Minecraft player names must be 1 to 16 characters")
        self.name = name
        self.host = host
        self.port = port
        self.packet_ids = packet_ids
        self.socket: socket.socket | None = None
        self.compression_threshold: int | None = None
        self.phase = "handshake"
        self.joined = threading.Event()
        self.closed = threading.Event()
        self.error: BaseException | None = None
        self.thread: threading.Thread | None = None

    def connect(self, timeout: float = 45.0) -> "PlayerBot":
        self.socket = socket.create_connection((self.host, self.port), timeout=10)
        self.socket.settimeout(None)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        handshake = Writer().varint(PROTOCOL_VERSION).string(self.host).ushort(self.port).varint(2)
        self._send("handshake", "intention", handshake.data, compressed=False)
        hello = Writer().string(self.name).raw(_offline_uuid(self.name).bytes)
        self._send("login", "hello", hello.data, compressed=False)
        self.phase = "login"
        self.thread = threading.Thread(target=self._read_loop, name=f"mc-bot-{self.name}", daemon=True)
        self.thread.start()
        if not self.joined.wait(timeout):
            self.close()
            raise TimeoutError(f"{self.name} did not join the Minecraft server")
        if self.error is not None:
            raise RuntimeError(f"{self.name} protocol error: {self.error}") from self.error
        return self

    def assert_connected(self) -> None:
        if self.closed.is_set():
            raise ConnectionError(f"{self.name} disconnected")
        if self.error is not None:
            raise RuntimeError(f"{self.name} protocol error: {self.error}") from self.error

    def send_player_action(
        self,
        action: str,
        x: int,
        y: int,
        z: int,
        *,
        direction: int = 1,
        sequence: int = 0,
    ) -> None:
        """Send a 26.3 player block-action packet for deterministic mining probes."""
        try:
            action_id = PLAYER_ACTION_IDS[action]
        except KeyError as error:
            raise ValueError(f"Unsupported player action: {action!r}") from error
        if not -(1 << 25) <= x < (1 << 25) or not -(1 << 25) <= z < (1 << 25):
            raise ValueError("Block x/z coordinates must fit Minecraft's signed 26-bit fields")
        if not -(1 << 11) <= y < (1 << 11):
            raise ValueError("Block y coordinate must fit Minecraft's signed 12-bit field")
        if not 0 <= direction <= 5:
            raise ValueError("Block face direction must be in the range 0..5")
        if sequence < 0:
            raise ValueError("Block action sequence must not be negative")

        packed_position = (
            ((x & 0x3FFFFFF) << 38)
            | ((z & 0x3FFFFFF) << 12)
            | (y & 0xFFF)
        )
        body = (
            Writer()
            .varint(action_id)
            .long(packed_position)
            .raw(bytes((direction,)))
            .varint(sequence)
        )
        self._send("play", "player_action", body.data)

    def close(self) -> None:
        self.closed.set()
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        if self.thread is not None:
            self.thread.join(timeout=3)

    def _send(self, state: str, name: str, body: bytes, *, compressed: bool = True) -> None:
        assert self.socket is not None
        threshold = self.compression_threshold if compressed else None
        packet_id = self.packet_ids.serverbound(state, name)
        self.socket.sendall(_frame(packet_id, body, threshold))

    def _read_exact(self, size: int) -> bytes:
        assert self.socket is not None
        result = bytearray()
        while len(result) < size:
            chunk = self.socket.recv(size - len(result))
            if not chunk:
                raise ConnectionError("server closed the player connection")
            result.extend(chunk)
        return bytes(result)

    def _read_varint_socket(self) -> int:
        value = 0
        for shift in range(0, 35, 7):
            byte = self._read_exact(1)[0]
            value |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return value
        raise ValueError("Minecraft frame length exceeds five bytes")

    def _read_loop(self) -> None:
        try:
            while not self.closed.is_set():
                frame = self._read_exact(self._read_varint_socket())
                if self.compression_threshold is not None:
                    framed = Reader(frame)
                    uncompressed_length = framed.varint()
                    payload = framed.take(len(frame) - framed.offset)
                    if uncompressed_length:
                        frame = zlib.decompress(payload)
                    else:
                        frame = payload
                packet = Reader(frame)
                packet_id = packet.varint()
                name = self.packet_ids.clientbound(self.phase, packet_id)
                self._handle(name, packet)
        except BaseException as error:  # surfaced to the waiting caller
            if not self.closed.is_set():
                self.error = error
                self.closed.set()
                self.joined.set()
        finally:
            if self.socket is not None:
                try:
                    self.socket.close()
                except OSError:
                    pass

    def _handle(self, name: str, packet: Reader) -> None:
        if self.phase == "login":
            if name == "login_compression":
                self.compression_threshold = packet.varint()
            elif name == "login_finished":
                self._send("login", "login_acknowledged", b"")
                self.phase = "configuration"
            elif name == "cookie_request":
                self._send("login", "cookie_response", Writer().string(packet.string()).boolean(False).data)
            elif name == "custom_query":
                self._send("login", "custom_query_answer", Writer().varint(packet.varint()).boolean(False).data)
            elif name == "login_disconnect":
                raise ConnectionError("server rejected login")
            return

        if self.phase == "configuration":
            if name == "select_known_packs":
                packs = [(packet.string(), packet.string(), packet.string()) for _ in range(packet.varint())]
                response = Writer().varint(len(packs))
                for namespace, pack_id, version in packs:
                    response.string(namespace).string(pack_id).string(version)
                self._send("configuration", "select_known_packs", response.data)
            elif name == "finish_configuration":
                self._send("configuration", "finish_configuration", b"")
                self.phase = "play"
            elif name == "keep_alive":
                self._send("configuration", "keep_alive", Writer().long(packet.long()).data)
            elif name == "ping":
                self._send("configuration", "pong", Writer().integer(packet.integer()).data)
            elif name == "cookie_request":
                self._send("configuration", "cookie_response", Writer().string(packet.string()).boolean(False).data)
            elif name == "code_of_conduct":
                self._send("configuration", "accept_code_of_conduct", b"")
            elif name == "configuration_disconnect":
                raise ConnectionError("server rejected configuration")
            return

        if name == "login":
            self._send("play", "player_loaded", b"")
            self.joined.set()
        elif name == "player_position":
            teleport_id = packet.varint()
            x, y, z = packet.double(), packet.double(), packet.double()
            packet.double()  # delta movement x
            packet.double()  # delta movement y
            packet.double()  # delta movement z
            yaw, pitch = packet.float(), packet.float()
            packet.integer()  # relative-position bit set
            response = Writer().varint(teleport_id).double(x).double(y).double(z).float(yaw).float(pitch)
            self._send("play", "accept_teleportation", response.data)
        elif name == "respawn":
            self._send("play", "player_loaded", b"")
        elif name == "keep_alive":
            self._send("play", "keep_alive", Writer().long(packet.long()).data)
        elif name == "ping":
            self._send("play", "pong", Writer().integer(packet.integer()).data)
        elif name == "chunk_batch_finished":
            self._send("play", "chunk_batch_received", Writer().float(25.0).data)
        elif name == "start_configuration":
            self._send("play", "configuration_acknowledged", b"")
            self.phase = "configuration"
        elif name == "disconnect":
            raise ConnectionError("server disconnected the player")
