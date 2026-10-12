
import os
import re
import json
import smtplib
from pathlib import Path
from email.message import EmailMessage

import requests

URL = (
    "https://www.flipkart.com/next-toppers-combo-3-books-"
    "cbse-sample-paper-class-10-science-mathematics-standard-"
    "social-science-2026-27/p/itmac61d4e4f7647"
    "?pid=9788168888883"
)
PRODUCT_ID = "9788168888883"
LISTING_ID = "LSTBOK9788168888883HDARHM"
STATE = Path(".state/status.json")


def check_stock():
    try:
        response = requests.get(
            URL,
            headers={"User-Agent": "RestockRadar/1.0"},
            timeout=20,
        )
        if response.status_code != 200:
            return "UNKNOWN"

        html = response.text
        if PRODUCT_ID not in html or LISTING_ID not in html:
            return "UNKNOWN"

        position = html.find(LISTING_ID)
        section = html[position:position + 5000]

        match = re.search(
            r'"availabilityStatus"\s*:\s*"([^"]+)"',
            section,
        )
        if not match:
            return "UNKNOWN"

        status = match.group(1).upper()
        return status if status in {
            "IN_STOCK", "OUT_OF_STOCK"
        } else "UNKNOWN"

    except requests.RequestException:
        return "UNKNOWN"


def send_email():
    message = EmailMessage()
    message["Subject"] = "Restock Radar: Check your sample papers"
    message["From"] = os.environ.get("ALERT_EMAIL_FROM") or os.environ["SMTP_USERNAME"]
    message["To"] = os.environ["ALERT_EMAIL_TO"]
    message.set_content(
        "Flipkart's listing may be back in stock!\n\n"
        "Open the product page and verify delivery to your PIN code:\n"
        + URL
    )

    with smtplib.SMTP(
        os.environ["SMTP_HOST"],
        int(os.environ.get("SMTP_PORT", "587")),
        timeout=20,
    ) as server:
        server.starttls()
        server.login(
            os.environ["SMTP_USERNAME"],
            os.environ["SMTP_PASSWORD"],
        )
        server.send_message(message)


def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)

    try:
        previous = json.loads(STATE.read_text()).get("status")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        previous = None

    current = check_stock()
    print("Flipkart listing status:", current)

    if current == "UNKNOWN":
        print("Could not confirm stock; no alert sent.")
        return

    if current == "OUT_OF_STOCK":
        STATE.write_text(json.dumps({"status": current}))
        print("Listing reports out of stock.")
        return

    if previous == "IN_STOCK":
        print("Already reported in stock; no duplicate alert.")
        return

    required = [
        "SMTP_HOST", "SMTP_USERNAME",
        "SMTP_PASSWORD", "ALERT_EMAIL_TO",
    ]
    if not all(os.environ.get(key) for key in required):
        print("Stock may be available, but email setup is incomplete.")
        print("No email sent; previous state retained.")
        return

    try:
        send_email()
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print("Email failed:", type(error).__name__)
        print("Previous state retained so a later run can retry.")
        return

    STATE.write_text(json.dumps({"status": "IN_STOCK"}))
    print("Restock email sent. Verify your PIN code before purchasing.")


if __name__ == "__main__":
    main()
