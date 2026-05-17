"""Stripe Service -- all Stripe API operations.

When STRIPE_SECRET_KEY is not set, returns mock data so the app
works in development without real keys.
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')

# Lazy init -- only import stripe when key is present
_stripe = None

def _get_stripe():
    global _stripe
    if _stripe is None and STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        _stripe = stripe
    return _stripe


def is_stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)


# ==================== PLANS CONFIG ====================
# These are the default plans. When Stripe is configured,
# prices can be overridden via STRIPE_PRICE_MONTHLY / STRIPE_PRICE_YEARLY env vars
# or fetched directly from Stripe products.

DEFAULT_PLANS = [
    {
        'id': 'free',
        'name': 'FREE',
        'price': 0,
        'currency': 'usd',
        'interval': None,
        'features': [
            'Basic signals (BUY/SELL/WAIT)',
            'Limited feed events',
            'Community sentiment',
        ],
    },
    {
        'id': 'pro_monthly',
        'name': 'PRO',
        'price': 1900,  # cents
        'currency': 'usd',
        'interval': 'month',
        'stripePriceId': os.getenv('STRIPE_PRICE_MONTHLY', ''),
        'features': [
            'Full signal breakdown (7+ factors)',
            'Deep Intel (Exchange / On-chain / Sentiment / Fractal)',
            'Edge opportunities',
            'Full track record',
            'Early signals (before public)',
            'Priority support',
        ],
        'popular': True,
    },
    {
        'id': 'pro_yearly',
        'name': 'PRO',
        'price': 9900,  # cents
        'currency': 'usd',
        'interval': 'year',
        'stripePriceId': os.getenv('STRIPE_PRICE_YEARLY', ''),
        'features': [
            'Everything in PRO Monthly',
            'Save 56%',
        ],
    },
]


def get_plans() -> list:
    """Return subscription plans.
    If Stripe is configured, enriches with real price data."""
    stripe = _get_stripe()
    if stripe and os.getenv('STRIPE_PRODUCT_ID'):
        try:
            prices = stripe.Price.list(
                product=os.getenv('STRIPE_PRODUCT_ID'),
                active=True,
                expand=['data.product'],
            )
            plans = [{
                'id': 'free', 'name': 'FREE', 'price': 0,
                'currency': 'usd', 'interval': None,
                'features': DEFAULT_PLANS[0]['features'],
            }]
            for p in prices.data:
                plans.append({
                    'id': f"pro_{p.recurring.interval if p.recurring else 'once'}",
                    'name': p.product.name if hasattr(p, 'product') and hasattr(p.product, 'name') else 'PRO',
                    'price': p.unit_amount,
                    'currency': p.currency,
                    'interval': p.recurring.interval if p.recurring else None,
                    'stripePriceId': p.id,
                    'features': DEFAULT_PLANS[1]['features'],
                    'popular': p.recurring and p.recurring.interval == 'month',
                })
            return plans
        except Exception as e:
            logger.warning(f'Failed to fetch Stripe prices: {e}')
    return DEFAULT_PLANS


# ==================== CUSTOMER ====================

def get_or_create_customer(user: dict) -> str | None:
    """Get or create Stripe customer for user. Returns customer ID."""
    stripe = _get_stripe()
    if not stripe:
        return None

    # Already has customer ID
    if user.get('stripeCustomerId'):
        return user['stripeCustomerId']

    try:
        # Search by email first
        existing = stripe.Customer.list(email=user['email'], limit=1)
        if existing.data:
            customer_id = existing.data[0].id
        else:
            customer = stripe.Customer.create(
                email=user['email'],
                name=user.get('name', ''),
                metadata={'userId': user['_id']},
            )
            customer_id = customer.id

        # Save to DB
        from routes.auth import users_collection
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'stripeCustomerId': customer_id, 'updatedAt': datetime.utcnow()}}
        )
        return customer_id
    except Exception as e:
        logger.error(f'Stripe customer creation failed: {e}')
        return None


# ==================== CHECKOUT ====================

def create_checkout_session(user: dict, price_id: str, success_url: str, cancel_url: str) -> dict | None:
    """Create a Stripe Checkout session."""
    stripe = _get_stripe()
    if not stripe:
        return None

    customer_id = get_or_create_customer(user)
    if not customer_id:
        return None

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'userId': user['_id']},
            allow_promotion_codes=True,
        )
        return {'sessionId': session.id, 'url': session.url}
    except Exception as e:
        logger.error(f'Stripe checkout creation failed: {e}')
        return None


# ==================== CUSTOMER PORTAL ====================

def create_portal_session(user: dict, return_url: str) -> dict | None:
    """Create a Stripe Customer Portal session for managing billing."""
    stripe = _get_stripe()
    if not stripe:
        return None

    customer_id = get_or_create_customer(user)
    if not customer_id:
        return None

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {'url': session.url}
    except Exception as e:
        logger.error(f'Stripe portal creation failed: {e}')
        return None


# ==================== WEBHOOK ====================

def construct_webhook_event(payload: bytes, sig_header: str):
    """Verify and construct Stripe webhook event."""
    stripe = _get_stripe()
    if not stripe:
        return None

    try:
        if STRIPE_WEBHOOK_SECRET:
            return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            import json
            return stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except Exception as e:
        logger.error(f'Webhook verification failed: {e}')
        return None


def handle_subscription_event(event: dict) -> bool:
    """Process subscription-related webhook events.
    Updates user plan in MongoDB."""
    from routes.auth import users_collection

    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})

    logger.info(f'Processing Stripe event: {event_type}')

    if event_type in (
        'customer.subscription.created',
        'customer.subscription.updated',
        'customer.subscription.resumed',
    ):
        customer_id = data.get('customer')
        status = data.get('status')  # active, past_due, canceled, etc.

        if not customer_id:
            return False

        user = users_collection.find_one({'stripeCustomerId': customer_id})
        if not user:
            logger.warning(f'No user found for Stripe customer {customer_id}')
            return False

        # Map Stripe status to our plan
        if status == 'active':
            new_plan = 'PRO'
            plan_status = 'ACTIVE'
        elif status == 'past_due':
            new_plan = 'PRO'
            plan_status = 'PAST_DUE'
        elif status == 'trialing':
            new_plan = 'PRO'
            plan_status = 'TRIALING'
        else:
            new_plan = 'FREE'
            plan_status = status.upper()

        # Extract renewal info
        current_period_end = data.get('current_period_end')
        renews_at = datetime.utcfromtimestamp(current_period_end).isoformat() if current_period_end else None

        # Get price info
        items = data.get('items', {}).get('data', [])
        price_amount = items[0].get('price', {}).get('unit_amount', 0) if items else 0
        price_interval = items[0].get('price', {}).get('recurring', {}).get('interval', 'month') if items else 'month'
        price_str = f"${price_amount / 100:.0f}/{price_interval}"

        update = {
            'plan': new_plan,
            'planStatus': plan_status,
            'subscription': {
                'plan': new_plan,
                'status': plan_status,
                'renewsAt': renews_at,
                'price': price_str,
                'stripeSubscriptionId': data.get('id'),
            },
            'access': {
                'miniSignals': True,
                'fullSignals': new_plan != 'FREE',
                'fullIntel': new_plan != 'FREE',
                'edge': new_plan != 'FREE',
                'tradingPreview': True,
                'tradingFull': new_plan == 'INSTITUTIONAL',
            },
            'updatedAt': datetime.utcnow(),
        }

        users_collection.update_one({'_id': user['_id']}, {'$set': update})
        logger.info(f'Updated user {user["_id"]} to plan={new_plan}, status={plan_status}')
        return True

    elif event_type in (
        'customer.subscription.deleted',
        'customer.subscription.paused',
    ):
        customer_id = data.get('customer')
        if not customer_id:
            return False

        user = users_collection.find_one({'stripeCustomerId': customer_id})
        if not user:
            return False

        update = {
            'plan': 'FREE',
            'planStatus': 'CANCELED' if event_type.endswith('deleted') else 'PAUSED',
            'subscription': {
                'plan': 'FREE',
                'status': 'CANCELED',
                'renewsAt': None,
                'price': '$0/month',
            },
            'access': {
                'miniSignals': True,
                'fullSignals': False,
                'fullIntel': False,
                'edge': False,
                'tradingPreview': False,
                'tradingFull': False,
            },
            'updatedAt': datetime.utcnow(),
        }

        users_collection.update_one({'_id': user['_id']}, {'$set': update})
        logger.info(f'Downgraded user {user["_id"]} to FREE (subscription {event_type})')
        return True

    elif event_type == 'checkout.session.completed':
        # Session completed -- subscription events handle the rest
        logger.info(f'Checkout completed for customer {data.get("customer")}')
        return True

    return False
