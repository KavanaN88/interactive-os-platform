"""Idempotent seed: roles, the 10 modules, and their algorithms.
Run from the backend folder:  python -m app.db.seed
Existing rows are left untouched, so re-running is safe and never overwrites admin edits."""
from sqlalchemy import select

from app.db.models import Algorithm, Module, Role
from app.db.seed_data import MODULES, ROLES, algorithm_rows
from app.db.session import new_session


def run() -> dict:
    created = {"roles": 0, "modules": 0, "algorithms": 0}
    with new_session() as db:
        for name in ROLES:
            if not db.scalar(select(Role).where(Role.name == name)):
                db.add(Role(name=name)); created["roles"] += 1
        by_slug = {}
        for pos, (slug, name, desc, _a) in enumerate(MODULES, start=1):
            m = db.scalar(select(Module).where(Module.slug == slug))
            if not m:
                m = Module(slug=slug, name=name, description=desc, position=pos)
                db.add(m); created["modules"] += 1
            by_slug[slug] = m
        db.flush()
        for mslug, aslug, name, desc, rules, implemented in algorithm_rows():
            mod = by_slug[mslug]
            if not db.scalar(select(Algorithm).where(Algorithm.module_id == mod.id, Algorithm.slug == aslug)):
                db.add(Algorithm(module_id=mod.id, slug=aslug, name=name, description=desc, rules=rules, implemented=implemented))
                created["algorithms"] += 1
        db.commit()
    return created


if __name__ == "__main__":
    print("Seed complete:", run())
