from twilio.rest import Client
import os
from dotenv import load_dotenv

# Load env vars from .env file (local only)
load_dotenv()

# Get credentials from env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def purchase_twilio_number(country: str = "US") -> str:
    """
    Purchase a new Twilio phone number in the given country.

    Args:
        country (str): Country code (e.g., "US", "IN", "GB").

    Returns:
        str: The purchased Twilio phone number in E.164 format.

    Raises:
        Exception: If no numbers are available in the given country.

    Usage:
        >>> from twilio_number_manager import purchase_twilio_number
        >>> phone_number = purchase_twilio_number("IN")
        >>> print(phone_number)   # "+918123456789"
    """

    # Search available numbers in the given country
    numbers = client.available_phone_numbers(country).local.list(limit=1)
    if not numbers:
        raise Exception(f"No numbers available in {country}")

    # Purchase the first available number
    purchased = client.incoming_phone_numbers.create(
        phone_number=numbers[0].phone_number,
        # voice_url="https://<domain.com>/voice-handler", # If we do not have domain name right now then comment this line out
        # sms_url="https://<domain.com>/sms-handler" # If we do not have domain name right now then comment this line out
    )

    return purchased.phone_number