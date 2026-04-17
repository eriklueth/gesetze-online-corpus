#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import feedparser

RSS_URL = "https://www.gesetze-im-internet.de/aktuelles/aktuell.rss"
STATE_PATH = Path("data/state/rss_entries.json")


def load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text())
        return set(data.get("seen_ids", []))
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"seen_ids": sorted(seen)}, indent=2))


def main() -> int:
    feed = feedparser.parse(RSS_URL)
    if feed.bozo:
        print(f"warning: feed parse issue: {feed.bozo_exception}", file=sys.stderr)

    seen = load_seen()
    new_seen = set(seen)
    changed = []

    for entry in feed.entries:
        entry_id = entry.get("id") or entry.get("link") or entry.get("title")
        if not entry_id:
            continue
        new_seen.add(entry_id)
        if entry_id not in seen:
            changed.append(
                {
                    "id": entry_id,
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "published": entry.get("published"),
                    "summary": entry.get("summary", ""),
                }
            )

    save_seen(new_seen)
    print(json.dumps(changed, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
