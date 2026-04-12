"""scripts/seed_db.py
Bootstraps the database with the initial admin user (clarkehines).
Safe to run multiple times — exits cleanly if the user already exists.
All other users are added via the invite flow, never through this script.

Run from the project root:
    python scripts/seed_db.py
"""

import getpass
import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt

from db.auth.factory import get_auth_repository
from db.auth.models import User
from db.schema import create_tables

ADMIN_USERNAME = "clarkehines"
DEFAULT_ASSISTANT_NAME = "JARVIS"


def main() -> None:
    print("=== JARVIS seed_db ===\n")

    # Ensure all tables exist before attempting any writes
    create_tables()

    repo = get_auth_repository()

    # Idempotent — do nothing if the admin already exists
    if repo.get_user(ADMIN_USERNAME) is not None:
        print(f"User '{ADMIN_USERNAME}' already exists. Nothing to do.")
        return

    assistant_name = input(f"Assistant name [{DEFAULT_ASSISTANT_NAME}]: ").strip()
    if not assistant_name:
        assistant_name = DEFAULT_ASSISTANT_NAME

    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user = User(
        username=ADMIN_USERNAME,
        password_hash=password_hash,
        tier="admin",
        assistant_name=assistant_name,
        token_version=0,
    )

    repo.create_user(user)
    print(f"\nAdmin user '{ADMIN_USERNAME}' created with assistant name '{assistant_name}'.")
    print("You can now start the server and log in.")


if __name__ == "__main__":
    main()
