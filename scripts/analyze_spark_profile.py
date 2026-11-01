#!/usr/bin/env python3
"""Summarize weighted methods and selected call paths in a Spark profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise ValueError("Malformed protobuf varint")


def parse_fields(data: bytes) -> list[tuple[int, int, int | bytes]]:
    fields: list[tuple[int, int, int | bytes]] = []
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        field_number, wire_type = key >> 3, key & 0x07
        if field_number == 0:
            raise ValueError("Invalid protobuf field number 0")
        if wire_type == 0:
            value, offset = read_varint(data, offset)
        elif wire_type == 1:
            value = data[offset : offset + 8]
            offset += 8
        elif wire_type == 2:
            length, offset = read_varint(data, offset)
            value = data[offset : offset + length]
            offset += length
        elif wire_type == 5:
            value = data[offset : offset + 4]
            offset += 4
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire_type}")
        if offset > len(data):
            raise ValueError("Truncated protobuf field")
        fields.append((field_number, wire_type, value))
    return fields


def scalar(fields: list[tuple[int, int, int | bytes]], number: int, default: int = 0) -> int:
    return next(
        (int(value) for field, wire, value in fields if field == number and wire == 0),
        default,
    )


def string_field(
    fields: list[tuple[int, int, int | bytes]],
    number: int,
    default: str = "",
) -> str:
    value = next(
        (value for field, wire, value in fields if field == number and wire == 2),
        None,
    )
    if value is None:
        return default
    assert isinstance(value, bytes)
    return value.decode("utf-8", errors="replace")


def nested_fields(
    fields: list[tuple[int, int, int | bytes]],
    number: int,
) -> list[list[tuple[int, int, int | bytes]]]:
    return [
        parse_fields(value)
        for field, wire, value in fields
        if field == number and wire == 2 and isinstance(value, bytes)
    ]


def repeated_doubles(
    fields: list[tuple[int, int, int | bytes]],
    number: int,
) -> list[float]:
    values: list[float] = []
    for field, wire, value in fields:
        if field != number:
            continue
        if wire == 1:
            assert isinstance(value, bytes)
            values.append(struct.unpack("<d", value)[0])
        elif wire == 2:
            assert isinstance(value, bytes)
            if len(value) % 8:
                raise ValueError(f"Packed double field {number} has invalid length")
            values.extend(struct.unpack("<" + "d" * (len(value) // 8), value))
    return values


def repeated_ints(
    fields: list[tuple[int, int, int | bytes]],
    number: int,
) -> list[int]:
    values: list[int] = []
    for field, wire, value in fields:
        if field != number:
            continue
        if wire == 0:
            values.append(int(value))
        elif wire == 2:
            assert isinstance(value, bytes)
            offset = 0
            while offset < len(value):
                item, offset = read_varint(value, offset)
                values.append(item)
    return values


def call_paths(
    thread_fields: list[tuple[int, int, int | bytes]],
    method_filter: str,
    path_count: int,
) -> list[dict[str, object]]:
    """Return the heaviest sampled stacks containing a class/method substring."""
    nodes = nested_fields(thread_fields, 3)
    records: list[tuple[str, str, float, list[int]]] = []
    for node in nodes:
        records.append(
            (
                string_field(node, 3),
                string_field(node, 4),
                sum(repeated_doubles(node, 8)),
                repeated_ints(node, 9),
            )
        )

    needle = method_filter.casefold()
    paths: dict[tuple[tuple[str, str], ...], float] = {}
    roots = repeated_ints(thread_fields, 5)
    stack: list[tuple[int, tuple[tuple[str, str], ...], frozenset[int]]] = [
        (root, (), frozenset()) for root in roots
    ]
    while stack:
        index, parent_path, ancestry = stack.pop()
        if index < 0 or index >= len(records) or index in ancestry:
            continue
        class_name, method_name, weight, children = records[index]
        frame = (class_name, method_name)
        path = parent_path + (frame,)
        if needle in f"{class_name}.{method_name}".casefold():
            paths[path] = paths.get(path, 0.0) + weight
        next_ancestry = ancestry | {index}
        stack.extend((child, path, next_ancestry) for child in children)

    ordered = sorted(paths.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "inclusive_weighted_value": weight,
            "frames_root_to_match": [
                {"class": class_name, "method": method_name}
                for class_name, method_name in path
            ],
        }
        for path, weight in ordered[:path_count]
    ]


def summarize(
    path: Path,
    thread_filter: str,
    top_count: int,
    method_filter: str = "",
    path_count: int = 10,
) -> dict[str, object]:
    data = path.read_bytes()
    root = parse_fields(data)
    metadata_fields = nested_fields(root, 1)
    if len(metadata_fields) != 1:
        raise ValueError("Spark profile must contain exactly one SamplerMetadata entry")
    metadata = metadata_fields[0]
    mode = scalar(metadata, 15, default=0)
    modes = {0: "execution", 1: "allocation", 2: "lock"}
    mode_name = modes.get(mode, f"unknown-{mode}")
    thread_records: list[dict[str, object]] = []
    for thread_fields in nested_fields(root, 2):
        name = string_field(thread_fields, 1, "<unnamed>")
        if thread_filter and thread_filter.casefold() not in name.casefold():
            continue
        nodes: dict[tuple[str, str], float] = {}
        for node_fields in nested_fields(thread_fields, 3):
            class_name = string_field(node_fields, 3)
            method_name = string_field(node_fields, 4)
            weighted_value = sum(repeated_doubles(node_fields, 8))
            key = (class_name, method_name)
            nodes[key] = nodes.get(key, 0.0) + weighted_value
        ordered = sorted(nodes.items(), key=lambda item: item[1], reverse=True)
        thread_record: dict[str, object] = {
            "name": name,
            "total_weighted_value": sum(repeated_doubles(thread_fields, 4)),
            "stack_node_count": len(nested_fields(thread_fields, 3)),
            "root_references": repeated_ints(thread_fields, 5),
            "top_methods": [
                {
                    "class": class_name,
                    "method": method_name,
                    "inclusive_weighted_value": value,
                }
                for (class_name, method_name), value in ordered[:top_count]
            ],
        }
        if method_filter:
            thread_record["top_call_paths"] = call_paths(
                thread_fields, method_filter, path_count
            )
        thread_records.append(thread_record)
    if not thread_records:
        raise ValueError(f"No Spark thread matched {thread_filter!r}")
    return {
        "profile": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "sampler_mode": mode_name,
        "interval": scalar(metadata, 3),
        "start_time_ms": scalar(metadata, 2),
        "end_time_ms": scalar(metadata, 11),
        "number_of_ticks": scalar(metadata, 12),
        "thread_count_in_profile": len(nested_fields(root, 2)),
        "time_windows": repeated_ints(root, 6),
        "matched_threads": thread_records,
        "weight_note": (
            "Method weights are inclusive Spark samples. Execution profiles use weighted "
            "sample time; allocation profiles use estimated allocated bytes. These are "
            "sampling estimates, not exact method timers."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--thread", default="Server thread", help="case-insensitive substring; empty selects all threads")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument(
        "--method",
        default="",
        help="also report the heaviest sampled call paths containing this class/method substring",
    )
    parser.add_argument("--paths", type=int, default=10, help="maximum matching call paths per thread")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args()
    if not args.profile.is_file():
        parser.error(f"profile does not exist: {args.profile}")
    if args.top < 1:
        parser.error("--top must be >= 1")
    if args.paths < 1:
        parser.error("--paths must be >= 1")
    result = summarize(args.profile, args.thread, args.top, args.method, args.paths)
    output = json.dumps(result, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(output)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Spark profile analysis failed: {error}", file=sys.stderr)
        raise
