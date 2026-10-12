
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
    except requests.RequestException as error:
        print("Network error:", type(error).__name__)
        return "UNKNOWN"

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("The website did not return a usable page.")
        return "UNKNOWN"

    html = response.text
    print("Page length:", len(html))
    print("Product ID found:", PRODUCT_ID in html)
    print("Listing ID found:", LISTING_ID in html)

    if PRODUCT_ID not in html or LISTING_ID not in html:
        print("The expected product listing could not be verified.")
        return "UNKNOWN"

    position = html.find(LISTING_ID)
    section = html[position:position + 5000]

    match = re.search(
        r'"availabilityStatus"\s*:\s*"([^"]+)"',
        section,
    )

    if not match:
        print("Stock-status field not found beside the listing.")
        return "UNKNOWN"

    status = match.group(1).upper()
    print("Raw listing status:", status)

    if status not in {"IN_STOCK", "OUT_OF_STOCK"}:
        print("Unrecognized stock status.")
        return "UNKNOWN"

    return status


def send_email():
    message = EmailMessage()
    message["Subject"] = "Restock Radar: Check your sample papers"
    message["From"] = (
        os.environ.get("ALERT_EMAIL_FROM")
        or os.environ["SMTP_USERNAME"]
    )
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
        previous = json.loads(
            STATE.read_text(encoding="utf-8")
        ).get("status")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        previous = None

    current = check_stock()
    print("Final listing status:", current)

    if current == "UNKNOWN":
        print("No alert sent because stock could not be confirmed.")
        return

    if current == "OUT_OF_STOCK":
        STATE.write_text(
            json.dumps({"status": current}),
            encoding="utf-8",
        )
        print("Listing reports out of stock.")
        return

    if previous == "IN_STOCK":
        print("Already reported in stock; no duplicate alert.")
        return

    required = [
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "ALERT_EMAIL_TO",
    ]

    if not all(os.environ.get(key) for key in required):
        print("Email setup incomplete; no email sent.")
        print("Previous state retained so a later run can retry.")
        return

    try:
        send_email()
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print("Email failed:", type(error).__name__)
        print("Previous state retained so a later run can retry.")
        return

    STATE.write_text(
        json.dumps({"status": "IN_STOCK"}),
        encoding="utf-8",
    )
    print("Restock email sent. Verify delivery before purchasing.")


if __name__ == "__main__":
    main()
