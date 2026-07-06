"""Generate a secure random string for use as a state parameter in OAuth flows."""

import secrets
import string


def generate_secure_random_string(length: int) -> str:
    """Generate a secure random string of the specified length."""
    # Define the possible characters (can also add punctuation if needed)
    characters = string.ascii_letters + string.digits

    # Generate the secure random string using secrets.choice
    secure_random_string = "".join(secrets.choice(characters) for _ in range(length))

    return secure_random_string
