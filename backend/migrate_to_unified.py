#!/usr/bin/env python3
"""
MIGRATION SCRIPT - Єдина система користувачів
==============================================

Цей скрипт мігрує існуючих користувачів з різних систем
в єдину unified_users колекцію

Запуск: python migrate_to_unified.py
"""

import sys
sys.path.append('/app/backend')

from unified_auth import UnifiedUser, migrate_existing_users, users_collection, db
from pymongo import MongoClient
import os

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'intelligence_engine')

def main():
    print("="*60)
    print("MIGRATION TO UNIFIED AUTH SYSTEM")
    print("="*60)
    print()
    
    # 1. Міграція з mobile 'users'
    print("[Step 1] Migrating from mobile 'users' collection...")
    migrate_existing_users()
    
    # 2. Перевірка результатів
    print()
    print("[Step 2] Verification...")
    total_users = users_collection.count_documents({})
    web_users = users_collection.count_documents({'linkedApps.web': True})
    mobile_users = users_collection.count_documents({'linkedApps.mobile': True})
    miniapp_users = users_collection.count_documents({'linkedApps.miniapp': True})
    
    print(f"  Total users in unified_users: {total_users}")
    print(f"  - Web users: {web_users}")
    print(f"  - Mobile users: {mobile_users}")
    print(f"  - Telegram miniapp users: {miniapp_users}")
    
    # 3. Приклади користувачів
    print()
    print("[Step 3] Sample users:")
    for user in users_collection.find().limit(3):
        print(f"  - {user['email']}")
        print(f"    Plan: {user.get('plan', 'FREE')}")
        print(f"    Linked: Web={user['linkedApps'].get('web', False)}, "
              f"Mobile={user['linkedApps'].get('mobile', False)}, "
              f"Telegram={user['linkedApps'].get('miniapp', False)}")
        print()
    
    print("="*60)
    print("✅ MIGRATION COMPLETE!")
    print("="*60)
    print()
    print("Next steps:")
    print("1. Restart backend: supervisorctl restart backend")
    print("2. Test unified auth:")
    print("   curl -X POST https://.../api/unified/auth/dev-login \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"email\":\"test@example.com\",\"name\":\"Test\",\"platform\":\"mobile\"}'")
    print()

if __name__ == '__main__':
    main()
