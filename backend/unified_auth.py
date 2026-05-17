"""
UNIFIED CROSS-PLATFORM AUTHENTICATION & SYNC
==============================================

Єдина система авторизації та синхронізації для:
- Web (Emergent OAuth)
- Mobile (Google OAuth + JWT)
- Telegram mini-app

Принцип: EMAIL = PRIMARY KEY
Один email = один користувач на всіх платформах
"""

from typing import Optional, Literal
from datetime import datetime, timezone
from pymongo import MongoClient
import os

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'intelligence_engine')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
users_collection = db['unified_users']

# Ensure indexes
users_collection.create_index('email', unique=True)
users_collection.create_index('googleId')
users_collection.create_index('telegramChatId')
users_collection.create_index('emergentUserId')

PlatformType = Literal['web', 'mobile', 'miniapp']
AuthProvider = Literal['google', 'emergent', 'telegram']


class UnifiedUser:
    """
    Єдина модель користувача для всіх платформ
    """
    
    @staticmethod
    def find_or_create(
        email: str,
        name: str,
        platform: PlatformType,
        auth_provider: AuthProvider,
        provider_id: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ) -> dict:
        """
        Знайти або створити користувача
        
        Args:
            email: Email користувача (PRIMARY KEY)
            name: Ім'я користувача
            platform: Платформа входу (web/mobile/miniapp)
            auth_provider: Провайдер авторизації (google/emergent/telegram)
            provider_id: ID від провайдера (googleId, emergentUserId, telegramId)
            telegram_chat_id: Telegram chat ID для синхронізації
        
        Returns:
            dict: Документ користувача
        """
        now = datetime.now(timezone.utc)
        
        # Шукаємо існуючого користувача
        user = users_collection.find_one({'email': email})
        
        if user:
            # Користувач вже існує - оновлюємо його дані
            update = {
                'updatedAt': now,
                f'linkedApps.{platform}': True,
                f'authProviders.{auth_provider}': True,
            }
            
            # Оновлюємо provider ID якщо є
            if provider_id:
                if auth_provider == 'google':
                    update['googleId'] = provider_id
                elif auth_provider == 'emergent':
                    update['emergentUserId'] = provider_id
                elif auth_provider == 'telegram':
                    update['telegramId'] = provider_id
            
            # Оновлюємо telegram chat ID
            if telegram_chat_id:
                update['telegramChatId'] = telegram_chat_id
            
            users_collection.update_one({'_id': user['_id']}, {'$set': update})
            user = users_collection.find_one({'_id': user['_id']})
            
            print(f"[Unified Auth] Existing user logged in: {email} via {platform}/{auth_provider}")
            
        else:
            # Новий користувач - створюємо
            user_id = f"u_{email.split('@')[0]}_{str(now.timestamp()).replace('.', '')[:10]}"
            
            user = {
                '_id': user_id,
                'email': email,
                'name': name,
                'avatarUrl': None,
                
                # Subscription (єдина для всіх платформ)
                'plan': 'FREE',
                'planStatus': 'ACTIVE',
                'planRenewsAt': None,

                # Auth providers
                'authProviders': {
                    'google': auth_provider == 'google',
                    'emergent': auth_provider == 'emergent',
                    'telegram': auth_provider == 'telegram',
                },
                
                # Linked platforms
                'linkedApps': {
                    'web': platform == 'web',
                    'mobile': platform == 'mobile',
                    'miniapp': platform == 'miniapp',
                },
                
                # Provider IDs
                'googleId': provider_id if auth_provider == 'google' else None,
                'emergentUserId': provider_id if auth_provider == 'emergent' else None,
                'telegramId': provider_id if auth_provider == 'telegram' else None,
                'telegramChatId': telegram_chat_id,
                
                # Security
                'hasPassword': False,
                'twoFactorEnabled': False,
                'twoFactorSecret': None,
                
                # Referral system (єдина для всіх платформ)
                'referralCode': f"FOMO-{user_id.split('_')[1].upper()[:4]}",
                'referredBy': None,
                'referrals': {
                    'invites': 0,
                    'paidReferrals': 0,
                    'earned': 0,
                },
                
                # Preferences (синхронізуються між платформами)
                'preferences': {
                    'defaultAsset': 'BTC',
                    'theme': 'dark',
                    'language': 'ru',
                    'notifications': True,
                    'dataSources': {
                        'exchange': True,
                        'onchain': True,
                        'sentiment': True,
                        'fractals': True,
                        'technicals': True,
                        'prediction': True,
                    },
                },
                
                # Stats (агреговані по всіх платформах)
                'stats': {
                    'signalsViewed': 0,
                    'edgeBetsPlaced': 0,
                    'totalSessions': 0,
                },
                
                # Timestamps
                'createdAt': now,
                'updatedAt': now,
                'memberSince': now.strftime('%b %Y'),
            }
            
            users_collection.insert_one(user)
            print(f"[Unified Auth] New user created: {email} via {platform}/{auth_provider}")
        
        return user
    
    @staticmethod
    def sync_subscription_across_platforms(email: str, new_plan: str, new_status: str):
        """
        Синхронізувати підписку на всіх платформах
        
        Коли користувач оплачує на будь-якій платформі - 
        підписка оновлюється для ВСІХ платформ одразу
        """
        now = datetime.now(timezone.utc)
        
        result = users_collection.update_one(
            {'email': email},
            {
                '$set': {
                    'plan': new_plan,
                    'planStatus': new_status,
                    'updatedAt': now,
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"[Subscription Sync] Updated {email}: {new_plan} ({new_status})")
            print(f"  ✓ Web will see: {new_plan}")
            print(f"  ✓ Mobile will see: {new_plan}")
            print(f"  ✓ Telegram will see: {new_plan}")
        
        return result.modified_count > 0
    
    @staticmethod
    def get_by_email(email: str) -> Optional[dict]:
        """Отримати користувача по email"""
        return users_collection.find_one({'email': email})
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional[dict]:
        """Отримати користувача по ID"""
        return users_collection.find_one({'_id': user_id})
    
    @staticmethod
    def update_preference(email: str, key: str, value):
        """Оновити налаштування (синхронізується між платформами)"""
        users_collection.update_one(
            {'email': email},
            {
                '$set': {
                    f'preferences.{key}': value,
                    'updatedAt': datetime.now(timezone.utc),
                }
            }
        )
    
    @staticmethod
    def link_telegram(email: str, telegram_chat_id: str, telegram_username: str = None):
        """Зв'язати Telegram з користувачем"""
        users_collection.update_one(
            {'email': email},
            {
                '$set': {
                    'telegramChatId': telegram_chat_id,
                    'telegramUsername': telegram_username,
                    'linkedApps.miniapp': True,
                    'authProviders.telegram': True,
                    'updatedAt': datetime.now(timezone.utc),
                }
            }
        )
        print(f"[Telegram Link] {email} linked to chat {telegram_chat_id}")
    
    @staticmethod
    def increment_stat(email: str, stat_name: str, amount: int = 1):
        """Інкрементувати статистику"""
        users_collection.update_one(
            {'email': email},
            {
                '$inc': {f'stats.{stat_name}': amount},
                '$set': {'updatedAt': datetime.now(timezone.utc)},
            }
        )


# Migration helper
def migrate_existing_users():
    """
    Міграція існуючих користувачів з різних систем
    в єдину unified_users колекцію
    """
    print("[Migration] Starting migration to unified_users...")
    
    # 1. Мігруємо з mobile 'users' колекції
    mobile_users = db['users'].find()
    migrated_mobile = 0
    
    for user in mobile_users:
        email = user.get('email')
        if not email:
            continue
        
        # Перевіряємо чи вже є в unified
        if users_collection.find_one({'email': email}):
            print(f"  [Skip] {email} already in unified_users")
            continue
        
        # Створюємо в unified
        unified_user = {
            '_id': user.get('_id'),
            'email': email,
            'name': user.get('name', email.split('@')[0]),
            'plan': user.get('plan', 'FREE'),
            'planStatus': user.get('planStatus', 'ACTIVE'),
            'googleId': user.get('googleId'),
            'telegramChatId': user.get('telegramChatId'),
            'referralCode': user.get('referralCode'),
            'authProviders': user.get('authProviders', {}),
            'linkedApps': user.get('linkedApps', {}),
            'preferences': user.get('preferences', {}),
            'createdAt': user.get('createdAt'),
            'updatedAt': datetime.now(timezone.utc),
        }
        
        users_collection.insert_one(unified_user)
        migrated_mobile += 1
        print(f"  [Mobile] Migrated: {email}")
    
    print(f"[Migration] Complete! Migrated {migrated_mobile} mobile users")
    
    # TODO: Додати міграцію з user_sessions (веб) якщо потрібно


if __name__ == '__main__':
    # Тест
    print("Testing Unified Auth System...")
    
    # Тест 1: Створення користувача через мобільний
    user1 = UnifiedUser.find_or_create(
        email='test@example.com',
        name='Test User',
        platform='mobile',
        auth_provider='google',
        provider_id='google_123456'
    )
    print(f"Created user: {user1['_id']}")
    
    # Тест 2: Той же користувач входить через веб
    user2 = UnifiedUser.find_or_create(
        email='test@example.com',
        name='Test User',
        platform='web',
        auth_provider='emergent',
        provider_id='emergent_789'
    )
    print(f"Same user on web: {user2['_id']}")
    print(f"Linked apps: {user2['linkedApps']}")
    
    # Тест 3: Синхронізація підписки
    UnifiedUser.sync_subscription_across_platforms('test@example.com', 'PRO', 'ACTIVE')
    
    user3 = UnifiedUser.get_by_email('test@example.com')
    print(f"Plan after sync: {user3['plan']}")
