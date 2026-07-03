"""send_test.py

Small one-off test script to exercise sender.send_newsletter() safely.

Usage:
  # Dry run (default, will not call SES)
  python send_test.py

  # Actually send the email (will call SES using boto3 / your env)
  python send_test.py --send --to ngocly039@gmail.com --name "Ngoc Ly"

Notes:
 - Put AWS creds (or rely on your AWS session) and SES_SENDER_EMAIL in `.env`.
 - In SES sandbox, recipients must be verified — you'll see the same MessageRejected error until the recipient is verified.
"""

import argparse
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TO = os.getenv("TEST_RECIPIENT", "ngocly039@gmail.com")


def build_sample_html(name: str, email: str) -> str:
    try:
        from newsletter_builder import build_html
        # Provide two small sample articles to match the app's format
        sample_articles = [
            {
                "title": "Sample: OpenAI releases GPT-5",
                "source": "Demo",
                "topic": "AI",
                "url": "https://example.com/gpt5",
                "summary": "This is a short sample summary for testing.",
                "reading_time": 2,
            },
            {
                "title": "Sample: Stripe raises funding",
                "source": "Demo",
                "topic": "Fintech",
                "url": "https://example.com/stripe",
                "summary": "Another short sample for testing the newsletter layout.",
                "reading_time": 1,
            },
        ]
        return build_html(name, email, ["AI", "Fintech"], sample_articles)
    except Exception:
        # Fallback simple HTML
        return f"<html><body><h1>TL;DR Newsletter - Sample</h1><p>Hi {name} ({email})</p><p>This is a test email.</p></body></html>"


def main():
    parser = argparse.ArgumentParser(description="Send a test TL;DR newsletter (dry-run by default)")
    parser.add_argument("--to", default=DEFAULT_TO, help="Recipient email address")
    parser.add_argument("--name", default="Test User", help="Recipient name used in the HTML")
    parser.add_argument("--subject", default=None, help="Email subject (defaults to generated subject)")
    parser.add_argument("--send", action="store_true", help="Actually call SES and send the email. Without this flag the script does a dry-run.")

    args = parser.parse_args()

    html = build_sample_html(args.name, args.to)
    subject = args.subject or "TL;DR Newsletter — Test Issue"

    print("Recipient:", args.to)
    print("Subject:", subject)
    print("Dry run mode:" , not args.send)

    if not args.send:
        print("--- HTML preview (truncated) ---")
        print(html[:1000])
        print("--- End preview ---")
        print("To actually send, re-run with --send")
        return

    # Attempt actual send via sender.send_newsletter
    try:
        from sender import send_newsletter
    except Exception as e:
        print("Failed to import sender.send_newsletter:", e)
        return

    print("Sending email via SES...")
    ok = send_newsletter(args.to, subject, html)
    if ok:
        print("Send reported success")
    else:
        print("Send reported failure — check logs above for SES errors")


if __name__ == "__main__":
    main()
