"""
Sample code with INTENTIONALLY missing or poor test coverage.
Used to test the Testing Agent's detection capabilities.

The agent should identify:
- Public functions without tests
- Edge cases not covered
- Missing error handling tests
- Untested branches
"""


# Issue 1: No input validation or tests for edge cases
# What happens with negative amounts? Zero? None? Very large numbers?
def calculate_discount(price: float, discount_percent: float) -> float:
    return price * (1 - discount_percent / 100)


# Issue 2: Complex branching with no tests
# There are 4+ code paths here but typically only the happy path gets tested.
def process_order(order: dict) -> str:
    if order.get("status") == "cancelled":
        refund(order)
        return "refunded"
    elif order.get("total", 0) > 1000:
        if order.get("member"):
            apply_bulk_discount(order)
            return "discounted"
        else:
            require_approval(order)
            return "pending_approval"
    else:
        charge(order)
        return "completed"


# Issue 3: Error handling that's never tested
# Tests usually only cover the success case, not what happens
# when the API call fails, times out, or returns unexpected data.
def fetch_user_profile(user_id: str) -> dict:
    try:
        response = api_client.get(f"/users/{user_id}")
        response.raise_for_status()
        return response.json()
    except ConnectionError:
        return {"error": "Service unavailable"}
    except TimeoutError:
        return {"error": "Request timed out"}
    except ValueError:
        return {"error": "Invalid response format"}


# Issue 4: Date/time logic without boundary tests
# Common bugs: timezone issues, leap years, month boundaries, DST
def is_subscription_active(start_date, end_date, current_date=None) -> bool:
    if current_date is None:
        from datetime import datetime
        current_date = datetime.now()
    return start_date <= current_date <= end_date


# Issue 5: Async function that's hard to test without mocking
async def send_notification(user_id: str, message: str) -> bool:
    user = await get_user(user_id)
    if not user.email:
        return False

    if user.preferences.get("email_notifications"):
        await email_service.send(user.email, message)
        return True
    elif user.preferences.get("sms_notifications"):
        await sms_service.send(user.phone, message)
        return True

    return False
