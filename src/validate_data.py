"""
Tark data validator — run before every commit.
    python src/validate_data.py
Exit 0 = every product, the anchor plan, and all series satisfy the M0
contract. Exit 1 = violations listed below; fix before committing.
"""
import sys

from tark_data import validate_all


def main() -> int:
    report = validate_all()
    total = 0
    for scope in sorted(report):
        errs = report[scope]
        if errs:
            print(f"[FAIL] {scope}")
            for e in errs:
                print(f"       - {e}")
            total += len(errs)
        else:
            print(f"[ok]   {scope}")
    print(f"\n{total} violation(s)." if total else "\nAll clean — data contract holds.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
