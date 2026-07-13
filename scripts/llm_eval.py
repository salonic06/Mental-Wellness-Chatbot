"""CLI entry for LLM eval harness."""

from __future__ import annotations

import json
import sys

from llm_eval_harness import run_offline_harness


def main() -> int:
    import llm_client
    from llm_wellness import empathetic_vent_reply

    def live(msg: str):
        if not llm_client.is_enabled():
            return None
        return empathetic_vent_reply(msg, "mild_negative", "eval-user")

    report = run_offline_harness(live if llm_client.is_enabled() else None)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
