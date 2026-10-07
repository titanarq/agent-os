"""How one model turn ended, and what a whole invocation of them cost."""

from __future__ import annotations

from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import BackendRun
from agent_os.product.puntal.stream.observer import StreamObserver
from agent_os.product.puntal.stream.turn_run import TurnRun
from agent_os.streams.claude_jsonl import result_total_tokens

USAGE_COUNTERS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def classify_turn(run: BackendRun, observer: StreamObserver) -> tuple[str, str]:
    """`(outcome, detail)` of one turn. The order is the order of what a person waiting must be told:
    a hung run, then a run that broke the contract, then one that ran out of ceiling, then one the
    CLI itself reported as failed."""
    if run.timed_out:
        return "timeout", "the backend produced no result before the safety timeout"
    if run.cut is not None:
        return run.cut
    result = observer.result
    if result is None:
        tail = "; ".join(observer.non_event_lines[-3:])
        return (
            "error",
            f"no result event (exit status {run.exit_code}){': ' + tail if tail else ''}",
        )
    if result.get("subtype") == "error_max_budget_usd":
        return "ceiling_cut", "the CLI stopped the run at --max-budget-usd"
    if result.get("is_error") or run.exit_code not in (0, None):
        detail = result.get("result") if isinstance(result.get("result"), str) else ""
        return (
            "error",
            f"{result.get('subtype') or 'error'} (exit status {run.exit_code}) {detail}"[:400],
        )
    return "ok", ""


def turn_usage(observer: StreamObserver) -> dict:
    """Tokens of one turn: the terminal `result`'s own aggregate when the turn reached one, else what
    the messages seen so far add up to (a cut turn has no `result`)."""
    result = observer.result
    if result is not None and isinstance(result.get("usage"), dict):
        fields = {name: result["usage"].get(name) or 0 for name in USAGE_COUNTERS}
        total = result_total_tokens(result)
    else:
        fields = {
            name: sum(m.usage.get(name) or 0 for m in observer.messages.values())
            for name in USAGE_COUNTERS
        }
        total = sum(fields.values())
    return {**fields, "total_tokens": total}


def turn_cost(observer: StreamObserver) -> float | None:
    return observer.result.get("total_cost_usd") if observer.result else None


def invocation_usage(turns: list[TurnRun]) -> dict:
    """Tokens of the whole invocation: the sums over its turns, the context floor of the FIRST turn
    (what the call carried before it did anything) and the peak of any turn."""
    per_turn = [turn_usage(turn.observer) for turn in turns]
    first = turns[0].observer
    return {
        **{
            name: sum(usage[name] for usage in per_turn)
            for name in (*USAGE_COUNTERS, "total_tokens")
        },
        "first_turn": first.first_turn_usage(),
        "context_tokens_first_turn": first.first_turn_context_tokens(),
        "context_tokens_peak": max(turn.observer.peak_context_tokens() for turn in turns),
        "turns": sum((turn.observer.result or {}).get("num_turns") or 0 for turn in turns) or None,
    }


def invocation_cost(turns: list[TurnRun]) -> float | None:
    costs = [cost for turn in turns if (cost := turn_cost(turn.observer)) is not None]
    return round(sum(costs), 6) if costs else None


def ceilings_exceeded(
    ceilings: Ceilings, turns: list[TurnRun], usage: dict, cost_usd: float | None
) -> list[str]:
    exceeded = []
    if usage["context_tokens_peak"] > ceilings.max_context:
        exceeded.append("max_context")
    if usage["total_tokens"] > ceilings.max_total_tokens:
        exceeded.append("max_total_tokens")
    if cost_usd is not None and cost_usd > ceilings.max_cost_usd:
        exceeded.append("max_cost_usd")
    if any(len(turn.observer.tool_calls) > ceilings.max_tool_calls for turn in turns):
        exceeded.append("max_tool_calls")
    return exceeded
