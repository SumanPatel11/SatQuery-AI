import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, ".")

from nlp.local_llm.m2_qwen import M2Qwen

BASE = Path("nlp/preprocessing/notebook/data/processed/nlp/rewrite/m2_satquery")
FILES = ["validation.jsonl", "test.jsonl"]

def normalize(items):
    return [" ".join(str(x).lower().split()).strip().rstrip(".") for x in items]

def evaluate_file(model, filename):
    path = BASE / filename

    with path.open("r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    total = len(records)
    valid = 0
    combine_correct = 0
    subqueries_correct = 0
    exact_match = 0
    failures = []
    categories = defaultdict(lambda: {"total": 0, "exact": 0})

    print(f"\n{'=' * 60}")
    print(f"EVALUATING: {filename} | Records: {total}")
    print(f"{'=' * 60}")

    for index, record in enumerate(records, start=1):
        category = record.get("followup_type", "unknown")
        categories[category]["total"] += 1

        try:
            response = model.predict(
                record["query"],
                record.get("context", [])
            )

            valid += 1

            combine_ok = response["combine"] == record["combine"]
            subqueries_ok = (
                normalize(response["subqueries"])
                == normalize(record["subqueries"])
            )

            combine_correct += int(combine_ok)
            subqueries_correct += int(subqueries_ok)

            exact_ok = combine_ok and subqueries_ok
            exact_match += int(exact_ok)
            categories[category]["exact"] += int(exact_ok)

            if not exact_ok and len(failures) < 10:
                failures.append({
                    "record": index,
                    "category": category,
                    "query": record["query"],
                    "expected": {
                        "subqueries": record["subqueries"],
                        "combine": record["combine"]
                    },
                    "predicted": response
                })

        except Exception as exc:
            if len(failures) < 10:
                failures.append({
                    "record": index,
                    "category": category,
                    "query": record["query"],
                    "error": f"{type(exc).__name__}: {exc}"
                })

        print(f"\rProcessed: {index}/{total}", end="", flush=True)

    print("\n\n--- RESULTS ---")
    print(f"Total records:       {total}")
    print(f"Valid outputs:       {valid}/{total} ({valid/total*100:.2f}%)")
    print(f"Combine accuracy:    {combine_correct}/{total} ({combine_correct/total*100:.2f}%)")
    print(f"Subquery accuracy:   {subqueries_correct}/{total} ({subqueries_correct/total*100:.2f}%)")
    print(f"Exact match:         {exact_match}/{total} ({exact_match/total*100:.2f}%)")

    print("\n--- FOLLOW-UP CATEGORY RESULTS ---")
    for category, stats in sorted(categories.items()):
        count = stats["total"]
        print(
            f"{category}: {stats['exact']}/{count} "
            f"({stats['exact']/count*100:.2f}%)"
        )

    print("\n--- FAILURE SAMPLES (maximum 10) ---")
    if failures:
        for failure in failures:
            print(json.dumps(failure, indent=2, ensure_ascii=False))
    else:
        print("No failures.")

    return {
        "file": filename,
        "total": total,
        "valid": valid,
        "combine_correct": combine_correct,
        "subqueries_correct": subqueries_correct,
        "exact_match": exact_match
    }


if __name__ == "__main__":
    model = M2Qwen()
    summaries = []

    for filename in FILES:
        summaries.append(evaluate_file(model, filename))

    print(f"\n{'=' * 60}")
    print("FINAL EVALUATION SUMMARY")
    print(f"{'=' * 60}")

    for item in summaries:
        print(
            f"{item['file']}: "
            f"Exact Match {item['exact_match']}/{item['total']}, "
            f"Valid {item['valid']}/{item['total']}"
        )
