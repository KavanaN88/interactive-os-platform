"""Runs tests/test_*.py without pytest (for offline sandboxes). Use `pytest` normally elsewhere."""
import importlib, pathlib, sys, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
passed = failed = 0
for f in sorted(pathlib.Path("tests").glob("test_*.py")):
    try:
        mod = importlib.import_module(f"tests.{f.stem}")
    except ImportError as e:
        print(f"SKIP {f.stem} (missing dependency: {e.name}) - run with real pytest after pip install"); continue
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)(); passed += 1; print(f"PASS {f.stem}::{name}")
        except Exception:
            failed += 1; print(f"FAIL {f.stem}::{name}"); traceback.print_exc()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
