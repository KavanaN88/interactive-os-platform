"""Create an administrator account:   python -m app.auth.create_admin
The password is typed at a hidden prompt (never on the command line, never stored in a file)."""
import argparse
import getpass
import sys

from app.auth import service
from app.engines.errors import ValidationError


def main() -> int:
    ap = argparse.ArgumentParser(description="Create an OS LAB administrator")
    ap.add_argument("--email")
    ap.add_argument("--username")
    a = ap.parse_args()
    email = a.email or input("Admin email: ").strip()
    username = a.username or input("Admin username: ").strip()
    pw, again = getpass.getpass("Password (8+ characters, letters and digits): "), getpass.getpass("Repeat password: ")
    if pw != again:
        print("The passwords do not match.")
        return 1
    try:
        u = service.register(email, username, pw, role="administrator")
    except ValidationError as e:
        print(f"Could not create the administrator: {e}")
        return 1
    print(f"Administrator '{u['username']}' created. Sign in at the app and open the Admin tab.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
