"""Subprocess entry point for parsing a knowledge source.

The worker is started by :mod:`knowledge.jobs` with a memory limit and a
hard timeout so that a pathological document cannot take the whole service
down. The result is written to a JSON file and read back by the parent.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: parse_worker <input.json> <output.json>", file=sys.stderr)
        return 2
    input_path = Path(argv[1])
    output_path = Path(argv[2])

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    filename = str(payload.get("filename") or "document.txt")
    raw = b""
    if payload.get("path"):
        raw = Path(str(payload["path"])).read_bytes()
    elif payload.get("text_b64"):
        raw = base64.b64decode(str(payload["text_b64"]))

    # The import must happen inside the subprocess so that the memory limit
    # also covers the parsing libraries.
    from knowledge.parsing import KnowledgeParseError, parse_document

    try:
        result = parse_document(filename, raw)
    except KnowledgeParseError as exc:
        output_path.write_text(
            json.dumps(
                {"ok": False, "code": exc.code, "detail": exc.detail},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - reported to the parent
        output_path.write_text(
            json.dumps(
                {"ok": False, "code": "parse_failed", "detail": str(exc)[:500]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return 0

    output_path.write_text(
        json.dumps(
            {
                "ok": True,
                "needs_ocr": result.needs_ocr,
                "text": result.text,
                "segments": [
                    {
                        "text": segment.text,
                        "heading_path": segment.heading_path,
                        "page_start": segment.page_start,
                        "page_end": segment.page_end,
                        "char_start": segment.char_start,
                        "char_end": segment.char_end,
                    }
                    for segment in result.segments
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
