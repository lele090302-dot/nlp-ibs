import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "newsletter@example.com")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def get_ses_client():
    kwargs = {"region_name": AWS_REGION}
    # Only pass explicit credentials if both are set in .env
    # Otherwise boto3 falls back to system AWS session / SSO
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client("ses", **kwargs)


def send_newsletter(recipient_email: str, subject: str, html_content: str) -> bool:
    """
    Send an HTML email via Amazon SES.
    Returns True on success, False on failure.

    Note: In SES sandbox mode, both sender and recipient must be verified emails.
    Request production access in the AWS console to send to any address.
    """
    client = get_ses_client()

    try:
        response = client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_content, "Charset": "UTF-8"},
                    "Text": {
                        # Plain text fallback for email clients that don't render HTML
                        "Data": "Your TL;DR Newsletter - please view in an HTML-capable email client.",
                        "Charset": "UTF-8",
                    },
                },
            },
        )
        print(f"[SES] Email sent to {recipient_email} — MessageId: {response['MessageId']}")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        print(f"[SES] Failed to send to {recipient_email}: {error_code} — {error_msg}")
        print(f"[SES] Full error: {e}")
        return False
    except Exception as e:
        print(f"[SES] Unexpected error sending to {recipient_email}: {e}")
        return False


def send_to_all_users(users: list[dict], html_by_email: dict[str, str]):
    """
    Send personalized newsletters to all active users.
    html_by_email: { email: rendered_html }
    """
    results = {"sent": 0, "failed": 0}

    for user in users:
        email = user["email"]
        html = html_by_email.get(email)
        if not html:
            continue

        subject = f"Your TL;DR Newsletter - {', '.join(user['topics'].split(','))}"
        success = send_newsletter(email, subject, html)

        if success:
            results["sent"] += 1
        else:
            results["failed"] += 1

    print(f"[SES] Done. Sent: {results['sent']}, Failed: {results['failed']}")
    return results
