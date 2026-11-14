import json
import re
import collections

p = "data/raw/nlp/nlu/changechat/changechat_105k_train.json"

with open(p, encoding="utf-8") as f:
    d = json.load(f)

patterns = {
    "building_change": r"\b(changes?|changed|change|new|newly|constructed|construction|demolish(?:ed|ition)?|removed|added|disappeared|built)\b.*\b(building|buildings|house|houses|residential)\b|\b(building|buildings|house|houses|residential)\b.*\b(changes?|changed|change|new|newly|constructed|construction|demolish(?:ed|ition)?|removed|added|disappeared|built)\b",

    "building_count_change": r"\b(count|how many|number)\b.*\b(new|changed|added|removed)\b.*\b(building|buildings|house|houses)\b",

    "building_location_change": r"\b(location|where|locations|position|grid|top|bottom|left|right|center)\b.*\b(change|changed|building|buildings)\b"
}

counts = collections.Counter()
examples = {}

for item in d:
    for conv in item.get("conversations", []):
        if conv.get("from") != "human":
            continue

        q = conv.get("value", "").replace("<image>", " ").strip()

        for name, pattern in patterns.items():
            if re.search(pattern, q, re.I):
                counts[name] += 1
                examples.setdefault(name, q)

print("CANDIDATE COUNTS:")
for name, count in counts.items():
    print(f"{name}: {count}")

print("\nEXAMPLES:")
for name, example in examples.items():
    print(f"\n{name}: {example}")
