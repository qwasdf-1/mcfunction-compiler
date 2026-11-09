#!/usr/bin/env python3
"""Attribute Spark server-thread samples to compiler-addressable command families.

The coverage-widening proposal's first census (``run_specialization_inventory.py``)
counts *static* eligible work. This analyzer answers the complementary runtime
question: what share of sampled server-thread time actually sits in the command
families the compiler can address?

Spark records class/method frames, not datapack function ids, so attribution is
at command-family granularity. For each sampled stack the analyzer finds the
nearest enclosing leaf command family (scoreboard, data, function call, return)
and attributes that frame's self weight there. Frames outside a leaf command are
attributed to generic families (function scheduler, execute control, command
queue, Brigadier, the compiler itself, or other). Entering
``ServerFunctionManager.execute`` resets the leaf owner so a function call's
body is attributed to its own commands instead of to the call site.

Fork detection is runtime, not lexical: a leaf command whose stack contains
``net.minecraft.commands.execution.tasks.ContinuationTask`` runs inside a forked
``execute`` context, which fused regions reject today. That split is the direct
runtime counterpart of the static census's forked-share column.

The addressable figure is deliberately an **upper bound**: Spark cannot tell a
fusable ``scoreboard players add`` from an unfusable ``scoreboard players get``,
nor a pure-leaf ``function`` call from an arbitrary one. It bounds what a
coverage widening could reach; it does not certify that every sampled command in
the family is eligible.

Usage:
    python3 scripts/attribute_specialization_share.py PROFILE [PROFILE ...]
    python3 scripts/attribute_specialization_share.py --label veinminer \
        build/benchmarks/.../veinminer.sparkprofile
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_spark_profile import (  # noqa: E402
    nested_fields,
    parse_fields,
    repeated_doubles,
    repeated_ints,
    scalar,
    string_field,
)


#: Leaf command families the compiler wraps or inlines today. Matching is by
#: class prefix because vanilla implements scoreboard/data subcommands as nested
#: classes and lambdas.
LEAF_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("scoreboard", re.compile(r"^net\.minecraft\.server\.commands\.ScoreboardCommand(\$|$)")),
    ("data", re.compile(r"^net\.minecraft\.server\.commands\.DataCommands?(\$|$)")),
    ("data", re.compile(r"^net\.minecraft\.server\.commands\.data\.")),
    ("function-call", re.compile(r"^net\.minecraft\.server\.commands\.FunctionCommand(\$|$)")),
    ("return", re.compile(r"^net\.minecraft\.server\.commands\.ReturnCommand(\$|$)")),
)

#: Non-leaf families, most specific first. ``function-manager`` is also the
#: traversal boundary between a call site and the called function's body.
GENERIC_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("compiler", re.compile(r"^dev\.functioncompiler\.")),
    ("function-manager", re.compile(r"^net\.minecraft\.server\.ServerFunctionManager(\$|$)")),
    ("macro", re.compile(r"^net\.minecraft\.commands\.functions\.MacroFunction(\$|$)")),
    (
        "function-iteration",
        re.compile(
            r"^net\.minecraft\.commands\.functions\."
            r"(PlainTextFunction|InstantiatedFunction|CommandFunction)(\$|$)"
        ),
    ),
    ("execute", re.compile(r"^net\.minecraft\.server\.commands\.ExecuteCommand(\$|$)")),
    ("command-queue", re.compile(r"^net\.minecraft\.commands\.execution\.")),
    ("brigadier", re.compile(r"^(com\.mojang\.brigadier\.|net\.minecraft\.commands\.CommandDispatcher)")),
    ("fabric-callback", re.compile(r"^net\.fabricmc\.")),
)

FORK_FRAME = re.compile(r"^net\.minecraft\.commands\.execution\.tasks\.ContinuationTask(\$|$)")

#: Server-thread idle frames. Spark samples wall-clock execution, so a server
#: waiting for the next tick shows up as a blocking syscall; those samples are
#: excluded from the active-tick denominators.
IDLE_FRAMES = {
    ("libc.so.6", "__syscall_cancel_arch_end"),
    ("java.lang.Thread", "sleep"),
    ("java.lang.Thread", "yield"),
}


def is_idle_frame(class_name: str, method_name: str) -> bool:
    if (class_name, method_name) in IDLE_FRAMES:
        return True
    return class_name in {
        "jdk.internal.misc.Unsafe",
        "java.util.concurrent.locks.LockSupport",
    } and method_name.startswith("park")


#: Macro argument construction. ``FunctionCommand$2.arguments`` builds the
#: macro parameter compound; the vanilla fallback reads the whole source tag
#: through ``DataCommands.getSingleTag``. That helper is not a ``data`` command,
#: so it must not be attributed to the data leaf family - it is the H4
#: selective-macro target instead.
MACRO_ARGUMENT_CLASS = re.compile(
    r"^net\.minecraft\.server\.commands\.FunctionCommand\$2(\$|$)"
)
FUNCTION_COMMAND_CLASS = re.compile(
    r"^net\.minecraft\.server\.commands\.FunctionCommand(\$|$)"
)
MACRO_ARGUMENT_METHODS = {"arguments", "getArgumentTag"}

#: Families counted in the addressable upper bound for today's leaf
#: specializers. ``execute`` is control flow, not a leaf command; it is
#: reported separately for the H1 question. Macro argument construction is
#: reported as its own H4 share.
ADDRESSABLE_FAMILIES = ("scoreboard", "data", "function-call", "return")


@dataclass
class StackNode:
    """One Spark stack node, flattened for attribution."""

    index: int
    class_name: str
    method_name: str
    weight: float
    children: list[int] = field(default_factory=list)

    @property
    def frame(self) -> str:
        return f"{self.class_name}.{self.method_name}"


def leaf_family(class_name: str) -> str | None:
    for family, pattern in LEAF_FAMILIES:
        if pattern.search(class_name):
            return family
    return None


def generic_family(class_name: str) -> str | None:
    for family, pattern in GENERIC_FAMILIES:
        if pattern.search(class_name):
            return family
    return None


def is_fork_frame(class_name: str) -> bool:
    return bool(FORK_FRAME.search(class_name))


def is_macro_argument_frame(class_name: str, method_name: str) -> bool:
    if MACRO_ARGUMENT_CLASS.search(class_name):
        return True
    return (
        bool(FUNCTION_COMMAND_CLASS.search(class_name))
        and method_name in MACRO_ARGUMENT_METHODS
    )


def load_thread(
    path: Path,
    thread_filter: str = "Server thread",
) -> dict[str, object]:
    """Read one thread's stack nodes, roots, and metadata from a profile."""
    data = path.read_bytes()
    root = parse_fields(data)
    metadata_fields = nested_fields(root, 1)
    if len(metadata_fields) != 1:
        raise ValueError("Spark profile must contain exactly one SamplerMetadata entry")
    metadata = metadata_fields[0]
    mode = scalar(metadata, 15, default=0)
    modes = {0: "execution", 1: "allocation", 2: "lock"}

    for thread_fields in nested_fields(root, 2):
        name = string_field(thread_fields, 1, "<unnamed>")
        if thread_filter and thread_filter.casefold() not in name.casefold():
            continue
        nodes: list[StackNode] = []
        for node_fields in nested_fields(thread_fields, 3):
            nodes.append(
                StackNode(
                    index=len(nodes),
                    class_name=string_field(node_fields, 3),
                    method_name=string_field(node_fields, 4),
                    weight=sum(repeated_doubles(node_fields, 8)),
                    children=repeated_ints(node_fields, 9),
                )
            )
        return {
            "thread": name,
            "sampler_mode": modes.get(mode, f"unknown-{mode}"),
            "interval": scalar(metadata, 3),
            "number_of_ticks": scalar(metadata, 12),
            "nodes": nodes,
            "roots": repeated_ints(thread_fields, 5),
            "thread_total_weight": sum(repeated_doubles(thread_fields, 4)),
        }
    raise ValueError(f"No Spark thread matched {thread_filter!r}")


def _children_weight(nodes: list[StackNode], node: StackNode) -> float:
    total = 0.0
    for child in node.children:
        if 0 <= child < len(nodes):
            total += nodes[child].weight
    return total


def attribute_nodes(nodes: list[StackNode], roots: list[int]) -> dict[str, object]:
    """Partition node self weight across command families.

    Traversal carries the nearest enclosing leaf family, the runtime fork
    state, and a macro-argument flag. A node's self weight is
    ``node.weight - sum(child.weight)``, clamped at zero, which partitions the
    sampled stacks without double counting.
    """
    self_weights: dict[int, float] = {
        node.index: max(0.0, node.weight - _children_weight(nodes, node))
        for node in nodes
    }

    family_self: dict[str, float] = {}
    family_forked_self: dict[str, float] = {}
    family_inclusive: dict[str, float] = {}
    method_self: dict[tuple[str, str], float] = {}
    effective_family_by_node: dict[int, str] = {}
    parent_by_node: dict[int, int | None] = {root: None for root in roots}

    # (node index, enclosing leaf family, enclosing generic family, forked,
    #  inside macro argument construction, idle)
    stack: list[tuple[int, str | None, str | None, bool, bool, bool]] = [
        (root, None, None, False, False, False)
        for root in roots
        if 0 <= root < len(nodes)
    ]
    seen: set[int] = set()
    while stack:
        index, leaf_owner, generic_owner, forked, macro_argument, idle = stack.pop()
        if index in seen:
            continue
        seen.add(index)
        node = nodes[index]
        node_leaf = leaf_family(node.class_name)
        node_generic = generic_family(node.class_name)
        if is_idle_frame(node.class_name, node.method_name):
            idle = True
        if is_macro_argument_frame(node.class_name, node.method_name):
            macro_argument = True
            leaf_owner = None
        if node_leaf is not None and not macro_argument and not idle:
            leaf_owner = node_leaf
        if node_generic is not None:
            generic_owner = node_generic

        if idle:
            effective = "idle"
        elif node_generic == "function-manager":
            # A function body is its own command sequence. Reset both the
            # call-site leaf owner and the macro-argument context here.
            effective = "function-manager"
            leaf_owner = None
            macro_argument = False
        elif macro_argument:
            effective = "macro-argument"
        else:
            effective = leaf_owner or generic_owner or "other"
        effective_family_by_node[index] = effective

        weight = self_weights.get(index, 0.0)
        family_self[effective] = family_self.get(effective, 0.0) + weight
        if forked:
            family_forked_self[effective] = family_forked_self.get(effective, 0.0) + weight
        key = (node.class_name, node.method_name)
        method_self[key] = method_self.get(key, 0.0) + weight

        child_forked = forked or is_fork_frame(node.class_name)
        for child in node.children:
            if 0 <= child < len(nodes):
                parent_by_node.setdefault(child, index)
                stack.append(
                    (
                        child,
                        leaf_owner,
                        generic_owner,
                        child_forked,
                        macro_argument,
                        idle,
                    )
                )

    # Inclusive weight per family: the topmost node of each contiguous family
    # segment. This is the sampled time spent inside that family's subtree,
    # including nested non-family work; it nests across families.
    for index, family in effective_family_by_node.items():
        parent = parent_by_node.get(index)
        if parent is None or effective_family_by_node.get(parent) != family:
            family_inclusive[family] = (
                family_inclusive.get(family, 0.0) + nodes[index].weight
            )

    total = sum(self_weights.values())
    return {
        "total_self_weight": total,
        "family_self": family_self,
        "family_forked_self": family_forked_self,
        "family_inclusive": family_inclusive,
        "method_self": method_self,
    }


def summarize_profile(path: Path, thread_filter: str = "Server thread", top: int = 25) -> dict[str, object]:
    """Compute attribution shares and top self-time methods for one profile."""
    loaded = load_thread(path, thread_filter)
    nodes: list[StackNode] = loaded["nodes"]  # type: ignore[assignment]
    roots: list[int] = loaded["roots"]  # type: ignore[assignment]
    attribution = attribute_nodes(nodes, roots)
    total = float(attribution["total_self_weight"])
    if total <= 0:
        raise ValueError("Profile has no sampled self weight")

    family_self: dict[str, float] = attribution["family_self"]  # type: ignore[assignment]
    family_forked: dict[str, float] = attribution["family_forked_self"]  # type: ignore[assignment]
    family_inclusive: dict[str, float] = attribution["family_inclusive"]  # type: ignore[assignment]
    method_self: dict[tuple[str, str], float] = attribution["method_self"]  # type: ignore[assignment]

    families: dict[str, dict[str, float]] = {}
    for family in sorted(set(family_self) | set(family_inclusive)):
        self_weight = family_self.get(family, 0.0)
        forked_weight = family_forked.get(family, 0.0)
        families[family] = {
            "self_weight": self_weight,
            "self_share": self_weight / total,
            "unforked_self_weight": self_weight - forked_weight,
            "unforked_share": (self_weight - forked_weight) / total,
            "forked_self_weight": forked_weight,
            "forked_share": forked_weight / total,
            "inclusive_weight": family_inclusive.get(family, 0.0),
            "inclusive_share": family_inclusive.get(family, 0.0) / total,
        }

    addressable_self = sum(families.get(family, {}).get("self_weight", 0.0) for family in ADDRESSABLE_FAMILIES)
    addressable_unforked = sum(
        families.get(family, {}).get("unforked_self_weight", 0.0) for family in ADDRESSABLE_FAMILIES
    )
    function_manager = families.get("function-manager", {})
    function_inclusive = function_manager.get("inclusive_weight", 0.0)
    idle_weight = families.get("idle", {}).get("self_weight", 0.0)
    active_total = total - idle_weight

    def active_share(value: float) -> float | None:
        return value / active_total if active_total > 0 else None

    top_methods = sorted(method_self.items(), key=lambda item: item[1], reverse=True)[:top]
    return {
        "profile": str(path),
        "label": path.parent.name or path.stem,
        "thread": loaded["thread"],
        "sampler_mode": loaded["sampler_mode"],
        "interval": loaded["interval"],
        "number_of_ticks": loaded["number_of_ticks"],
        "stack_node_count": len(nodes),
        "thread_total_weight": loaded["thread_total_weight"],
        "total_self_weight": total,
        "self_weight_coverage": (
            total / float(loaded["thread_total_weight"]) if loaded["thread_total_weight"] else None
        ),
        "families": families,
        "addressable_upper_bound_share": addressable_self / total,
        "addressable_unforked_share": addressable_unforked / total,
        "macro_argument_share": families.get("macro-argument", {}).get("self_share", 0.0),
        "function_manager_inclusive_share": function_inclusive / total if total else 0.0,
        "idle_share": idle_weight / total,
        "active_total_self_weight": active_total,
        "addressable_active_share": active_share(addressable_self),
        "macro_argument_active_share": active_share(
            families.get("macro-argument", {}).get("self_weight", 0.0)
        ),
        "function_manager_active_share": active_share(function_inclusive),
        "addressable_share_of_function_time": (
            addressable_self / function_inclusive if function_inclusive else None
        ),
        "top_self_methods": [
            {
                "class": class_name,
                "method": method_name,
                "self_weight": weight,
                "self_share": weight / total,
            }
            for (class_name, method_name), weight in top_methods
        ],
    }


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_markdown(results: list[dict[str, object]]) -> str:
    lines = [
        "# Spark time-share attribution",
        "",
        "Server-thread self weight attributed to command families by the nearest",
        "enclosing leaf frame. `Addressable (unforked)` is the upper bound for",
        "today's leaf specializers; forked samples run behind an `execute` fork",
        "that fused regions reject. `Function time` is the inclusive share of",
        "`ServerFunctionManager.execute`.",
        "",
        "| Profile | Sampler | Interval | Total weight | Idle | Function time | Active function | Macro arg (H4) | Active macro arg | Addressable (all) | Active addressable | Addressable / function time |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            "| {label} | {sampler_mode} | {interval} | {total:.1f} | {idle} | {function} | "
            "{active_function} | {macro} | {active_macro} | {all_addressable} | "
            "{active_addressable} | {ratio} |".format(
                label=result["label"],
                sampler_mode=result["sampler_mode"],
                interval=result["interval"],
                total=float(result["total_self_weight"]),
                idle=_percent(float(result["idle_share"])),
                function=_percent(float(result["function_manager_inclusive_share"])),
                active_function=_percent(
                    None
                    if result["function_manager_active_share"] is None
                    else float(result["function_manager_active_share"])
                ),
                macro=_percent(float(result["macro_argument_share"])),
                active_macro=_percent(
                    None
                    if result["macro_argument_active_share"] is None
                    else float(result["macro_argument_active_share"])
                ),
                all_addressable=_percent(float(result["addressable_upper_bound_share"])),
                active_addressable=_percent(
                    None
                    if result["addressable_active_share"] is None
                    else float(result["addressable_active_share"])
                ),
                ratio=_percent(
                    None
                    if result["addressable_share_of_function_time"] is None
                    else float(result["addressable_share_of_function_time"])
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Family breakdown",
            "",
            "| Profile | Family | Self | Unforked | Forked | Inclusive |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for result in results:
        families: dict[str, dict[str, float]] = result["families"]  # type: ignore[assignment]
        for family, values in sorted(
            families.items(), key=lambda item: item[1]["self_weight"], reverse=True
        ):
            lines.append(
                "| {label} | {family} | {self_share} | {unforked} | {forked} | {inclusive} |".format(
                    label=result["label"],
                    family=family,
                    self_share=_percent(values["self_share"]),
                    unforked=_percent(values["unforked_share"]),
                    forked=_percent(values["forked_share"]),
                    inclusive=_percent(values["inclusive_share"]),
                )
            )

    lines.extend(["", "## Top self-time methods", ""])
    for result in results:
        lines.append(f"### {result['label']}")
        lines.append("")
        lines.append("| Class | Method | Self share |")
        lines.append("| --- | --- | ---: |")
        for method in result["top_self_methods"]:  # type: ignore[union-attr]
            lines.append(
                "| {class_name} | {method_name} | {share} |".format(
                    class_name=method["class"],
                    method_name=method["method"],
                    share=_percent(float(method["self_share"])),
                )
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--thread", default="Server thread")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--labels", nargs="*", default=None, help="One label per profile")
    parser.add_argument("--output", type=Path, help="Write the JSON result here")
    parser.add_argument("--markdown", type=Path, help="Write the Markdown report here")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be >= 1")
    if args.labels is not None and len(args.labels) != len(args.profiles):
        parser.error("--labels must have one entry per profile")

    results: list[dict[str, object]] = []
    for index, profile in enumerate(args.profiles):
        if not profile.is_file():
            parser.error(f"profile does not exist: {profile}")
        result = summarize_profile(profile, args.thread, args.top)
        if args.labels is not None:
            result["label"] = args.labels[index]
        results.append(result)
        print(
            f"{result['label']}: {result['stack_node_count']} nodes, "
            f"{float(result['function_manager_inclusive_share']):.1%} function time, "
            f"{float(result['addressable_upper_bound_share']):.1%} addressable "
            f"({float(result['addressable_unforked_share']):.1%} unforked)"
        )

    payload = json.dumps({"profiles": results}, indent=2) + "\n"
    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(results), encoding="utf-8")
        print(f"Wrote {args.markdown}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Spark attribution failed: {error}", file=sys.stderr)
        raise
