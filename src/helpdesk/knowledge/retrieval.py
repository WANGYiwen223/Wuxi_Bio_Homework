"""Small deterministic lexical retriever for fictional runbooks and past cases."""

import json
import math
from collections import Counter
from pathlib import Path
import re


ALIASES = {"disconnects": "disconnect", "disconnected": "disconnect", "disconnections": "disconnect", "drops": "disconnect", "dropping": "disconnect", "locked": "lock", "lockout": "lock", "permissions": "access", "permission": "access", "login": "login", "signin": "login", "timeouts": "timeout"}
STOP_WORDS = {"a", "an", "the", "is", "are", "my", "i", "to", "in", "for", "of", "and", "every", "it", "with", "on", "can", "cannot"}


def tokens(text: str) -> list[str]:
    return [ALIASES.get(t, t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP_WORDS]


def ranked(query: str, documents: list[tuple[dict, str]], limit: int) -> list[dict]:
    query_terms = set(tokens(query))
    if not query_terms:
        return []
    counts = [Counter(tokens(text)) for _, text in documents]
    frequencies = {t: sum(t in count for count in counts) for t in query_terms}
    results = []
    for (record, _), count in zip(documents, counts):
        score = sum((1 + math.log(count[t])) * (1 + math.log((len(counts) + 1) / (frequencies[t] + 1))) for t in query_terms if count[t])
        if score:
            results.append({**record, "score": round(score, 4)})
    return sorted(results, key=lambda r: (-r["score"], r.get("article_id", r.get("history_id", ""))))[:limit]


class KnowledgeBase:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
        self._by_id = {r["article_id"]: r for r in self.index}

    def article(self, article_id: str) -> dict | None:
        record = self._by_id.get(article_id)
        if record is None:
            return None
        path = (self.directory / record["path"]).resolve()
        if not path.is_relative_to(self.directory):
            raise ValueError("Knowledge path escapes repository")
        content = path.read_text(encoding="utf-8")
        return {**record, "content": content}

    def search(self, query: str, service_id: str | None, limit: int) -> list[dict]:
        docs = []
        for metadata in self.index:
            if service_id and metadata["service_id"] != service_id:
                continue
            article = self.article(metadata["article_id"])
            text = f"{article['title']} {' '.join(article['tags'])} {article['applicability']} {article['content']}"
            docs.append(({**metadata, "excerpt": article["content"][:1600]}, text))
        return ranked(query, docs, limit)
