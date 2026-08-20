"""
Q4 Demo Runner
==============
Runs all four simulation scenarios and prints a full results report.
This is the "recorded live demo" deliverable — shows real-time processing
with nudges generated while the conversation is playing (not after).

Usage:
    python -m q4_live_insights.run_demo
    python -m q4_live_insights.run_demo --scenario compliance_gap
"""

from __future__ import annotations

import asyncio
import argparse
import json
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from q4_live_insights.pipeline import LiveInsightsPipeline
from q4_live_insights.models import Nudge, NudgePriority
from q4_live_insights.simulation_scenarios import SCENARIOS

console = Console()

PRIORITY_COLORS = {
    NudgePriority.HIGH:   "bold red",
    NudgePriority.MEDIUM: "bold yellow",
    NudgePriority.LOW:    "dim white",
}


async def run_scenario(name: str, turns: list, realtime: bool = True) -> dict:
    console.rule(f"[bold cyan]SCENARIO: {name.upper().replace('_', ' ')}")

    nudges_received = []

    async def on_nudge(nudge: Nudge) -> None:
        color = PRIORITY_COLORS.get(nudge.priority, "white")
        console.print(
            f"\n  [{color}]⚡ NUDGE [{nudge.priority.value.upper()}][/{color}] "
            f"{nudge.headline}\n"
            f"     {nudge.body}\n"
            f"     [dim]Trigger: \"{nudge.source_text[:80]}\"[/dim]\n"
            f"     [dim]Confidence: {round(nudge.confidence*100)}% | "
            f"E2E: {round(nudge.end_to_end_latency_ms or 0)}ms[/dim]"
        )
        nudges_received.append(nudge)

    pipeline = LiveInsightsPipeline(session_id=f"demo_{name}", on_nudge=on_nudge)

    console.print(f"\n[dim]Playing {len(turns)} turns at {'real-time' if realtime else 'instant'} speed...[/dim]\n")

    for turn in turns:
        if realtime:
            await asyncio.sleep(turn.get("delay_s", 1.5))
        speaker_label = "AGENT   " if turn["speaker"] == "agent" else "CUSTOMER"
        color = "cyan" if turn["speaker"] == "agent" else "green"
        console.print(f"  [{color}][{speaker_label}][/{color}] {turn['text']}")

        from q4_live_insights.models import Speaker
        speaker = Speaker.AGENT if turn["speaker"] == "agent" else Speaker.CUSTOMER
        import random
        await pipeline.process_chunk(
            text=turn["text"],
            speaker=speaker,
            asr_latency_ms=random.uniform(200, 420),
            is_final=True,
        )

    summary = pipeline.get_session_summary()
    latency = pipeline.get_latency_report()

    console.print(f"\n[bold]Results: {len(nudges_received)} nudges generated[/bold]")

    # Latency table
    if latency.get("e2e_latency"):
        e2e = latency["e2e_latency"]
        table = Table(title="Latency Report", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("P50 E2E", f"{e2e.get('p50_ms', '—')} ms")
        table.add_row("P95 E2E", f"{e2e.get('p95_ms', '—')} ms")
        comp = latency.get("component_latency_avg_ms", {})
        table.add_row("Avg ASR", f"{comp.get('asr', '—')} ms")
        table.add_row("Avg Signal Detection", f"{comp.get('signal_detection', '—')} ms")
        table.add_row("Avg LLM", f"{comp.get('llm', '—')} ms")
        table.add_row("Avg Delivery", f"{comp.get('delivery', '—')} ms")
        console.print(table)

    return {
        "scenario": name,
        "nudges": len(nudges_received),
        "signals": summary["total_signals"],
        "latency": latency,
    }


async def main(scenario_filter: str = None, realtime: bool = False):
    console.print(Panel.fit(
        "[bold cyan]Darwix Live Insights — Q4 Demo[/bold cyan]\n"
        "Real-time signal detection and nudge generation from call audio\n"
        "[dim]Audio → ASR → Signal Detection → Nudge → Dashboard[/dim]",
        border_style="cyan",
    ))

    scenarios_to_run = (
        {scenario_filter: SCENARIOS[scenario_filter]}
        if scenario_filter and scenario_filter in SCENARIOS
        else SCENARIOS
    )

    all_results = []
    for name, turns in scenarios_to_run.items():
        result = await run_scenario(name, turns, realtime=realtime)
        all_results.append(result)
        await asyncio.sleep(0.5)

    # Final summary
    console.rule("[bold]FINAL SUMMARY")
    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Scenario")
    summary_table.add_column("Signals")
    summary_table.add_column("Nudges")
    summary_table.add_column("P50 E2E (ms)")
    summary_table.add_column("P95 E2E (ms)")

    for r in all_results:
        e2e = r["latency"].get("e2e_latency", {})
        summary_table.add_row(
            r["scenario"].replace("_", " ").title(),
            str(r["signals"]),
            str(r["nudges"]),
            str(e2e.get("p50_ms", "—")),
            str(e2e.get("p95_ms", "—")),
        )

    console.print(summary_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=str, default=None,
                        choices=list(SCENARIOS.keys()),
                        help="Run a specific scenario only")
    parser.add_argument("--realtime", action="store_true",
                        help="Replay at real-time speed (slower but realistic)")
    args = parser.parse_args()

    asyncio.run(main(scenario_filter=args.scenario, realtime=args.realtime))
