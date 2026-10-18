"""TF-IDF RAG over the 4 SOP documents.

Citations look like ``sop-02-crew-legality.md §Duty limits``. When nothing
relevant is found the retriever says so explicitly (never hallucinates).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

SOP_DIR = Path(__file__).resolve().parent.parent / "docs" / "sops"
NOT_FOUND = "No relevant SOP section found for this question."


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", text.lower())


def load_chunks() -> list[dict]:
    """Split each SOP into ## sections; skip title-only intros."""
    chunks = []
    for path in sorted(SOP_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = ""
        for part in re.split(r"(?m)^## ", text):
            part = part.strip()
            if not part:
                continue
            if "\n" not in part and not title:
                title = part  # "# SOP-.." title line, skip as chunk
                continue
            heading, _, body = part.partition("\n")
            if len(body.strip()) < 20:
                continue  # title-only intro, not real content
            chunks.append({"file": path.name, "section": heading.strip(),
                           "text": body.strip()})
    return chunks


class SopRag:
    def __init__(self, chunks: list[dict] | None = None):
        self.chunks = chunks if chunks is not None else load_chunks()
        self._df: Counter = Counter()
        self._tf: list[Counter] = []
        for ch in self.chunks:
            toks = set(_tokenize(ch["text"]))
            self._df.update(toks)
            self._tf.append(Counter(_tokenize(ch["text"])))
        self._n = len(self.chunks)

    def _score(self, query: str, i: int) -> float:
        score = 0.0
        for tok in _tokenize(query):
            tf = self._tf[i][tok]
            if tf and self._df[tok]:
                score += (1 + math.log(tf)) * math.log(self._n / self._df[tok])
        return score

    def retrieve(self, query: str, top_k: int = 2, min_score: float = 0.5) -> list[dict]:
        scored = [(self._score(query, i), i) for i in range(self._n)]
        scored.sort(reverse=True)
        out = []
        for score, i in scored[:top_k]:
            if score < min_score:
                continue
            ch = self.chunks[i]
            out.append({
                "citation": f"{ch['file']} §{ch['section']}",
                "text": ch["text"],
                "score": round(score, 2),
            })
        return out

    def answer(self, query: str) -> str:
        hits = self.retrieve(query)
        if not hits:
            return NOT_FOUND
        lines = [f"[{h['citation']}] {h['text']}" for h in hits]
        return "\n".join(lines)
