#!/usr/bin/env python3
"""
CAPTCHA Reader using Mistral Pixtral via REST API (No mistralai package needed)

Usage:
    python captcha_extractor.py <image_url_or_path>

Example:
    python captcha_extractor.py https://example.com/captcha.png
    python captcha_extractor.py ./captcha.png
"""

import os
import sys
import base64
import requests

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
MISTRAL_API_KEY = "IaJYXrPhWrYfKdXmIkkH6xCEnvPmJTQK"
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY environment variable not set.")

MODEL = "ministral-14b-2512"          # Mistral's vision model
API_URL = "https://api.mistral.ai/v1/chat/completions"

# ----------------------------------------------------------------------
# Helper: load image from URL or local file
# ----------------------------------------------------------------------
def load_image_data(source: str) -> bytes:
    """Return image bytes from a URL or local file path."""
    if source.startswith(("http://", "https://")):
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return response.content
    else:
        with open(source, "rb") as f:
            return f.read()

def guess_mime_type(data: bytes) -> str:
    """Simple MIME type detection from magic bytes."""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif data.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return "image/gif"
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return "image/webp"
    else:
        return "image/png"          # fallback

# ----------------------------------------------------------------------
# Main: read CAPTCHA via REST API
# ----------------------------------------------------------------------
def read_captcha(image_source: str) -> str:
    # 1. Load image bytes
    image_bytes = load_image_data(image_source)

    # 2. Encode as base64 data URL
    mime_type = guess_mime_type(image_bytes)
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{base64_image}"

    # 3. Build the request payload
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": data_url
                    },
                    {
                        "type": "text",
                        "text": "Read the CAPTCHA text in this image. Output only the alphanumeric characters, no extra text or explanation and if u can't read captcha then output NONE."
                    }
                ]
            }
        ],
        "max_tokens": 20,
        "temperature": 0.0
    }

    # 4. Set headers
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    # 5. Send request
    response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()          # raise error on HTTP failure

    # 6. Parse and return the result
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <image_url_or_path>")
        sys.exit(1)

    source = sys.argv[1]
    try:
        captcha_text = read_captcha(source)
        print(captcha_text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)