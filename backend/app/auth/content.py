"""Learner-visible content = built-in lessons/questions (minus those an admin hid) + published admin-created ones."""
from __future__ import annotations

import json

from app.auth.store import get_store
from app.engines.learn import quiz as quiz_engine
from app.engines.learn.content import TOPICS


def _hidden(kind: str) -> set[str]:
    return {r["ref"] for r in get_store().all("SELECT ref FROM hidden_items WHERE kind=?", (kind,))}


def custom_topic(r: dict) -> dict:
    return {"id": f"c-{r['id']}", "module": r["module"], "level": r["level"], "title": r["title"], "summary": r["summary"], "points": json.loads(r["points"]),
            "example": r["example"], "exercise": r["exercise"], "answer": r["answer"], "source": "custom", "published": bool(r["published"])}


def topics(module: str | None = None) -> list[dict]:
    hid = _hidden("topic")
    out = [dict(t, source="built-in", published=True) for t in TOPICS if t["id"] not in hid and (module is None or t["module"] == module)]
    rows = get_store().all("SELECT * FROM custom_topics WHERE published=1" + (" AND module=?" if module else "") + " ORDER BY id", (module,) if module else ())
    return out + [custom_topic(r) for r in rows]


def topic(topic_id: str) -> dict | None:
    return next((t for t in topics() if t["id"] == topic_id), None)


class Provider:
    """Hooks admin-managed questions into the quiz engine."""

    def is_hidden(self, kind: str, ref: str) -> bool:
        return ref in _hidden(kind)

    def custom_mcq(self, module: str, levels: list[str]) -> list[dict]:
        rows = get_store().all("SELECT * FROM custom_questions WHERE published=1 AND module=? ORDER BY id", (module,))
        return [{"id": f"c|{r['id']}", "type": "mcq", "level": r["level"], "prompt": r["prompt"], "options": json.loads(r["options"])} for r in rows if r["level"] in levels]

    def get_custom(self, qid: str) -> dict | None:
        r = get_store().one("SELECT * FROM custom_questions WHERE id=?", (int(qid.split("|")[1]),))
        if not r:
            return None
        opts = json.loads(r["options"])
        return {"type": "mcq", "level": r["level"], "module": r["module"], "answer": str(r["correct_index"]), "shown": opts[r["correct_index"]],
                "explanation": r["explanation"], "options": opts}


def install() -> None:
    quiz_engine.PROVIDER = Provider()
