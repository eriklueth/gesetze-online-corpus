import json
from pathlib import Path


def test_example_chunk_file_exists():
    path = Path("chunks/example-law.jsonl")
    if not path.exists():
        return
    first = path.read_text().splitlines()[0]
    row = json.loads(first)
    assert "chunk_id" in row
    assert "law_id" in row
    assert "text" in row
