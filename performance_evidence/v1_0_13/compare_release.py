"""Verify before/after whole-app traces without wall-clock pass/fail thresholds.

Run beside before_ordinary.json, after_ordinary.json and three owner pairs,
or pass their directory as the only argument. Writes comparison.json.
"""
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys


ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
CONFIGURATIONS = ("ordinary", "owner_1", "owner_2", "owner_3")
VISIBLE_FIELDS = ("ui_tree", "buttons", "errors", "saved_picks", "own_picks", "mode", "position")
TIMED_ACTIONS = (
    "build_my_five", "next_first_save", "next_existing_lineup", "back",
    "next_unchanged", "confirm_lineup", "edit_lineup", "starter_tap",
    "warm_season", "live_expired_cache",
)


def owner_query(query):
    return "commissioner_access.py:_owner_id" in query["stack"]


def data_queries(record):
    # UI function names intentionally changed. Preserve operation order,
    # selected fields and every data-layer stack frame for the comparison.
    return [
        (q["operation"], q["fields"], tuple(f for f in q["stack"] if f.startswith("store.py:")))
        for q in record["queries"] if not owner_query(q)
    ]


def emissions(record):
    return sum(run["bytes"] for run in record["protobuf_emissions_by_run"].values())


def main():
    paired = {}
    checks = []
    for configuration in CONFIGURATIONS:
        before = json.loads((ROOT / f"before_{configuration}.json").read_text())
        after = json.loads((ROOT / f"after_{configuration}.json").read_text())
        assert before["version"] == "1.0.12" and after["version"] == "1.0.13"
        assert before["blocked_network_attempts"] == after["blocked_network_attempts"] == 0
        assert before["delay_per_query_seconds"] == after["delay_per_query_seconds"]
        assert before["linked_owner"] == after["linked_owner"]
        assert before["streamlit"] == after["streamlit"] == "1.63.0"
        assert [r["scenario"] for r in before["results"]] == [r["scenario"] for r in after["results"]]
        assert len(before["results"]) == (44 if configuration == "ordinary" else 47)
        paired[configuration] = {}
        for old, new in zip(before["results"], after["results"]):
            name = old["scenario"]
            paired[configuration][name] = (old, new)
            for key in VISIBLE_FIELDS:
                assert old[key] == new[key], (configuration, name, key)
            assert new["full_runs"] == 1, (configuration, name, "full_runs")
            assert old["full_runs"] in (1, 2)
            assert data_queries(old) == data_queries(new), (configuration, name, "ordered data queries")
            old_owner = sum(owner_query(q) for q in old["queries"])
            new_owner = sum(owner_query(q) for q in new["queries"])
            if before["linked_owner"]:
                assert old_owner == old["full_runs"] and new_owner == new["full_runs"], (configuration, name, "owner check per run")
            else:
                assert old_owner == new_owner == 0
            assert old["query_count"] - new["query_count"] == old_owner - new_owner
            old_ops, new_ops = Counter(old["operations"]), Counter(new["operations"])
            old_ops["app_meta.select"] -= old_owner
            new_ops["app_meta.select"] -= new_owner
            assert +old_ops == +new_ops, (configuration, name, "operation counts")
        checks.append({
            "configuration": configuration,
            "scenarios": len(before["results"]),
            "visible_trees_and_saved_data": "identical",
            "operation_change": "identical" if configuration == "ordinary" else "only one owner lookup removed per eliminated run",
            "ordered_data_queries_and_store_frames": "identical",
            "all_after_full_runs": 1,
        })

    timings = []
    for name in TIMED_ACTIONS:
        old_records = [paired[f"owner_{i}"][name][0] for i in range(1, 4)]
        new_records = [paired[f"owner_{i}"][name][1] for i in range(1, 4)]
        timings.append({
            "scenario": name,
            "before_median_seconds": median(r["seconds"] for r in old_records),
            "after_median_seconds": median(r["seconds"] for r in new_records),
            "samples": {"before": [r["seconds"] for r in old_records], "after": [r["seconds"] for r in new_records]},
            "before_queries": old_records[0]["query_count"],
            "after_queries": new_records[0]["query_count"],
            "before_runs": old_records[0]["full_runs"],
            "after_runs": new_records[0]["full_runs"],
        })
    old, new = paired["owner_1"]["next_existing_lineup"]
    result = {
        "status": "PASS", "checks": checks,
        "compared_scenario_pairs": sum(c["scenarios"] for c in checks),
        "owner_query_delay_seconds": 0.04, "owner_timing": timings,
        "example_next_generated_protobuf_bytes": {"before": emissions(old), "after": emissions(new)},
        "limits": [
            "Synthetic transport waiting; no production or physical iPhone timing.",
            "Timings include instrumentation and AppTest overhead; not correctness thresholds.",
            "UI normalization removes runtime IDs and the deliberate Build version label only.",
            "Separate sessions receive the same existing randomized pool order; runtime shuffling is unchanged.",
            "Generated protobuf bytes precede coalescing/compression and are not measured wire traffic.",
        ],
    }
    (ROOT / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "compared_scenario_pairs": result["compared_scenario_pairs"]}))


if __name__ == "__main__":
    main()
