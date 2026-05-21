"""email_file.py

Send a local file as an email attachment using Amazon SES.

Usage:
  # Dry run - prints summary, does NOT send
  python email_file.py --file send_test.py --to ngocly039@gmail.com

  # Actually send (will call SES using boto3 and your env/role)
  python email_file.py --file send_test.py --to ngocly039@gmail.com --send

Notes:
- Requires `SES_SENDER_EMAIL` and `AWS_REGION` in `.env` or environment.
- In SES sandbox, recipient must be verified. If you see MessageRejected, verify recipient in SES.
"""

import os
import argparse
from dotenv import load_dotenv
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

load_dotenv()

DEFAULT_SENDER = os.getenv("SES_SENDER_EMAIL", "newsletter@example.com")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def get_ses_client():
    import boto3
    kwargs = {"region_name": AWS_REGION}
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client("ses", **kwargs)


def build_message(sender: str, recipient: str, subject: str, body_text: str, file_path: str) -> bytes:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    # Body
    body = MIMEText(body_text, "plain")
    msg.attach(body)

    # Attachment
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename=\"{os.path.basename(file_path)}\"",
    )
    msg.attach(part)

    return msg.as_bytes()


def send_raw_email(recipient: str, raw_message: bytes) -> bool:
    client = get_ses_client()
    try:
        resp = client.send_raw_email(RawMessage={"Data": raw_message})
        print("[SES] Message sent. MessageId:", resp.get("MessageId"))
        return True
    except Exception as e:
        print("[SES] Send failed:", e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Email a file as attachment via SES (dry-run by default)")
    parser.add_argument("--file", required=True, help="Path to file to send")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--subject", default=None, help="Email subject")
    parser.add_argument("--send", action="store_true", help="Actually send via SES. Without this flag the script does a dry-run.")

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print("File not found:", args.file)
        return

    subject = args.subject or f"File from TL;DR repo: {os.path.basename(args.file)}"
    body = (
        f"Attached is the file {os.path.basename(args.file)} from your TL;DR repository.\n\n"
        "If you are in SES sandbox, ensure recipient is verified."
    )

    raw = build_message(DEFAULT_SENDER, args.to, subject, body, args.file)

    print("Dry run summary:")
    print("  From:", DEFAULT_SENDER)
    print("  To:", args.to)
    print("  Subject:", subject)
    print("  Attachment:", args.file)

    if not args.send:
        print("Dry-run mode: email NOT sent. Re-run with --send to actually send via SES.")
        return

    ok = send_raw_email(args.to, raw)
    if ok:
        print("Email send reported success")
    else:
        print("Email send failed — check logs above for SES errors")


if __name__ == "__main__":
    main()
