#!/usr/bin/env python3
"""
Migration script to encrypt existing plaintext passwords in the database.

This script should be run ONCE after deploying the encryption updates.
It will:
1. Fetch all users with plaintext passwords
2. Encrypt them using the new encryption system
3. Update the database

Prerequisites:
- ENCRYPTION_KEY must be set in environment variables
- Database must be accessible

Usage:
  python scripts/migrate_passwords.py           # Interactive mode
  python scripts/migrate_passwords.py --yes     # Non-interactive mode
  python scripts/migrate_passwords.py --dry-run # Show what would be done
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from app.database.database import SessionLocal
from app.database import models
from app.utils.security import encrypt_password, get_encryption_key

load_dotenv()


def migrate_passwords(dry_run=False):
    """Encrypt all existing plaintext passwords.

    Args:
        dry_run: If True, only show what would be done without making changes
    """

    # Verify encryption key is set
    try:
        get_encryption_key()
        print("✓ Encryption key found")
    except ValueError as e:
        print(f"✗ Error: {e}")
        return False

    db = SessionLocal()

    try:
        # Get all users
        users = db.query(models.UserProfile).all()
        print(f"Found {len(users)} users in database")

        migrated = 0
        skipped = 0
        errors = 0

        for user in users:
            if not user.garmin_password:
                skipped += 1
                continue

            # Check if password is already encrypted (Fernet encrypted strings start with 'gAAAAA')
            if user.garmin_password.startswith('gAAAAA'):
                print(f"  User {user.user_id}: Already encrypted, skipping")
                skipped += 1
                continue

            # Encrypt the plaintext password
            try:
                if dry_run:
                    print(f"  User {user.user_id}: Would encrypt password")
                else:
                    encrypted = encrypt_password(user.garmin_password)
                    user.garmin_password = encrypted
                    print(f"  User {user.user_id}: Password encrypted ✓")
                migrated += 1
            except Exception as e:
                print(f"  User {user.user_id}: Error encrypting - {e}")
                errors += 1

        # Commit all changes
        if not dry_run and migrated > 0:
            db.commit()
            print(f"\n✓ Migration complete!")
        elif dry_run:
            print(f"\n✓ Dry run complete! (no changes made)")
        else:
            print(f"\n✓ No changes needed")

        print(f"  Would migrate: {migrated} passwords" if dry_run else f"  Migrated: {migrated} passwords")
        print(f"  Skipped: {skipped} users")
        if errors > 0:
            print(f"  Errors: {errors}")
            return False

        return True

    except Exception as e:
        db.rollback()
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Migrate plaintext passwords to encrypted format',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt and run migration'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    print("=" * 50)
    print("Password Encryption Migration Script")
    print("=" * 50)
    print()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
        migrate_passwords(dry_run=True)
        sys.exit(0)

    print("This will encrypt all plaintext passwords in the database.")
    print("⚠️  Make sure you have a database backup before proceeding!")
    print()

    if not args.yes:
        try:
            response = input("Do you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nMigration cancelled.")
            sys.exit(0)

    success = migrate_passwords(dry_run=False)
    sys.exit(0 if success else 1)
