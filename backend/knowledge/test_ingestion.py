"""Tests for the chunking rules.

Section 16.5 requires that every effective character of a source ends up in
an indexed chunk, and that the overlap between neighbouring chunks actually
exists.
"""
from __future__ import annotations

from django.test import TestCase

from knowledge.ingestion import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS, chunk_segments
from knowledge.parsing import Segment


def covered_characters(chunks: list[dict], source: str) -> int:
    """How many source characters appear in at least one chunk."""
    if not source:
        return 0
    positions = [0]
    for char in source:
        positions.append(positions[-1] + 1)
    covered = set()
    for chunk in chunks:
        start = chunk.get("char_start") or 0
        end = chunk.get("char_end") or 0
        for index in range(start, min(end, len(source))):
            covered.add(index)
    return len(covered)


class ChunkingTestCase(TestCase):
    def test_short_paragraph_is_one_chunk(self):
        segments = [Segment(text="短文本。")]
        chunks = chunk_segments(segments)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "短文本。")

    def test_long_paragraph_keeps_its_tail(self):
        body = "甲" * 300 + "乙" * 700
        chunks = chunk_segments([Segment(text=body)])
        self.assertGreaterEqual(len(chunks), 2)
        # Every character must be indexed, including the tail.
        self.assertEqual(covered_characters(chunks, body), len(body))
        self.assertIn("乙" * 50, "".join(chunk["text"] for chunk in chunks))

    def test_long_paragraph_1100_chars(self):
        body = "丙" * 1100
        chunks = chunk_segments([Segment(text=body)])
        self.assertEqual(covered_characters(chunks, body), len(body))

    def test_long_paragraph_1200_chars(self):
        body = "丁" * 1200
        chunks = chunk_segments([Segment(text=body)])
        self.assertEqual(covered_characters(chunks, body), len(body))

    def test_multiple_paragraphs_cover_everything(self):
        first = "戊" * 300
        second = "己" * 700
        source = first + second
        segments = [
            Segment(text=first, char_start=0, char_end=300),
            Segment(text=second, char_start=300, char_end=1000),
        ]
        chunks = chunk_segments(segments)
        self.assertEqual(covered_characters(chunks, source), len(source))
        # Every chunk body must come from the source, never invented.
        for chunk in chunks:
            body = chunk["text"].replace("\n", "")
            self.assertIn(body, source)

    def test_tail_shorter_than_minimum_is_not_dropped(self):
        # 600 + 100 characters: the 100 character tail must still be indexed.
        body = "庚" * 600 + "辛" * 100
        chunks = chunk_segments([Segment(text=body)])
        self.assertEqual(covered_characters(chunks, body), len(body))
        self.assertIn("辛" * 100, "".join(chunk["text"] for chunk in chunks))

    def test_neighbouring_chunks_share_an_overlap(self):
        body = "壬" * 2000
        chunks = chunk_segments([Segment(text=body)])
        self.assertGreaterEqual(len(chunks), 3)
        for previous, current in zip(chunks, chunks[1:]):
            tail = previous["text"][-CHUNK_OVERLAP_CHARS:]
            self.assertIn(tail, current["text"])

    def test_heading_metadata_is_preserved(self):
        segments = [
            Segment(text="标题", heading_path="一级 > 二级", page_start=3, page_end=3),
            Segment(text="正文内容。", heading_path="一级 > 二级", page_start=3, page_end=4),
        ]
        chunks = chunk_segments(segments)
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertEqual(chunk["heading_path"], "一级 > 二级")
            self.assertEqual(chunk["page_start"], 3)

    def test_chunks_respect_the_target_size(self):
        body = "癸" * 3000
        chunks = chunk_segments([Segment(text=body)])
        for chunk in chunks:
            self.assertLessEqual(len(chunk["text"]), CHUNK_TARGET_CHARS)
