import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.compute.rules_engine import RulesEngine

logger = logging.getLogger(__name__)

_latest_replay: dict[str, Any] | None = None


def run_replay(
    events: list[dict],
    strategy_config: dict | None = None,
    start_ts: str | None = None,
    end_ts: str | None = None,
) -> dict[str, Any]:
    global _latest_replay

    replay_start = time.time()
    strategy_config = strategy_config or {}

    filtered = _filter_events(events, start_ts, end_ts)

    steps = []
    decisions_generated = 0
    mismatches = 0
    non_replayable = 0

    for i, event in enumerate(filtered):
        event_type = event.get("event_type", "UNKNOWN")
        payload = event.get("payload", {})
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except Exception:
                payload = {}

        step = {
            "step": i + 1,
            "event_id": event.get("id", ""),
            "event_type": event_type,
            "original_ts": event.get("ts", ""),
            "replayable": True,
            "decision": None,
            "matches_original": None,
        }

        if event_type in ("ORDER_SENT", "ORDER_FILLED", "RULE_ACTION_PROPOSED"):
            data_context = payload.get("data_context", {})
            if not data_context:
                step["replayable"] = False
                step["reason"] = "Missing data_context for deterministic replay"
                non_replayable += 1
            else:
                market_state = {
                    "tariff_index": data_context.get("tariff_index", 0),
                    "shock_score": data_context.get("shock_score", 0),
                    "current_price": data_context.get("price", 0),
                    "vol_regime": data_context.get("vol_regime", "normal"),
                    "funding_regime": data_context.get("funding_regime", "neutral"),
                }
                market_state.update(strategy_config)

                try:
                    _rules = RulesEngine()
                    replay_actions = _rules.evaluate(market_state)
                    decisions_generated += 1
                    step["decision"] = {
                        "actions": replay_actions,
                        "action_count": len([a for a in replay_actions if a.get("triggered")]),
                    }

                    original_action = payload.get("action", payload.get("side", ""))
                    if original_action and replay_actions:
                        replay_action = replay_actions[0].get("action", "") if replay_actions[0].get("triggered") else "none"
                        step["matches_original"] = original_action == replay_action
                        if not step["matches_original"]:
                            mismatches += 1
                            step["mismatch_detail"] = {
                                "original": original_action,
                                "replayed": replay_action,
                            }
                except Exception as e:
                    step["replayable"] = False
                    step["reason"] = f"Replay evaluation failed: {str(e)}"
                    non_replayable += 1

        elif event_type in ("AGENT_SIGNAL", "AGENT_ACTION_PROPOSED"):
            step["decision"] = {"note": "Agent signal — recorded but not re-evaluated in replay"}
        else:
            step["decision"] = {"note": f"Event type {event_type} passed through"}

        steps.append(step)

    replay_duration = time.time() - replay_start

    result = {
        "status": "completed",
        "event_count": len(filtered),
        "total_events_available": len(events),
        "decisions_generated": decisions_generated,
        "mismatches": mismatches,
        "non_replayable": non_replayable,
        "replay_duration_seconds": round(replay_duration, 3),
        "steps": steps[:500],
        "truncated": len(steps) > 500,
        "strategy_config": strategy_config,
        "time_window": {
            "start": start_ts,
            "end": end_ts,
        },
        "outcome_summary": {
            "total_steps": len(steps),
            "replayable_steps": len(steps) - non_replayable,
            "mismatch_rate": round(mismatches / max(decisions_generated, 1), 4),
            "fidelity_score": round(1.0 - mismatches / max(decisions_generated, 1), 4),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    _latest_replay = result
    return result


def _filter_events(
    events: list[dict],
    start_ts: str | None,
    end_ts: str | None,
) -> list[dict]:
    if not start_ts and not end_ts:
        return events

    filtered = []
    for ev in events:
        ts = ev.get("ts", "")
        if start_ts and ts < start_ts:
            continue
        if end_ts and ts > end_ts:
            continue
        filtered.append(ev)
    return filtered


def get_latest_replay() -> dict[str, Any] | None:
    return _latest_replay
