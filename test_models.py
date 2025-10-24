"""Test which Claude models are available with your API key."""

from anthropic import Anthropic
from flashygen.config import get_config

config = get_config()
client = Anthropic(api_key=config.anthropic_api_key)

# List of possible model names to try
models_to_test = [
    "claude-3-5-sonnet-20241022",  # Latest 3.5 Sonnet
    "claude-3-5-sonnet-20240620",  # Original 3.5 Sonnet
    "claude-3-opus-20240229",       # Claude 3 Opus
    "claude-3-sonnet-20240229",     # Claude 3 Sonnet
    "claude-3-haiku-20240307",      # Claude 3 Haiku
]

print("Testing model access...\n")

for model in models_to_test:
    try:
        # Try a minimal API call
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✓ {model} - WORKS")
    except Exception as e:
        error_str = str(e)
        if "404" in error_str or "not_found" in error_str:
            print(f"✗ {model} - Not available")
        elif "401" in error_str or "authentication" in error_str.lower():
            print(f"✗ {model} - Authentication error (check API key)")
        else:
            print(f"✗ {model} - Error: {error_str[:100]}")

print("\nDone! Use a model that WORKS in your config.py")
