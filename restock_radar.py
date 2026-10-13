
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
    api_url = "https://1.rome.api.flipkart.com/api/4/page/fetch"

    page_uri = (
        "/next-toppers-combo-3-books-"
        "cbse-sample-paper-class-10-science-mathematics-standard-"
        "social-science-2026-27/p/itmac61d4e4f7647"
        "?pid=9788168888883"
    )

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    headers = {
        "User-Agent": user_agent,
        "X-User-Agent": user_agent + " FKUA/website/42/website/Desktop",
        "Origin": "https://www.flipkart.com",
        "Referer": "https://www.flipkart.com/",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "pageUri": page_uri,
        "locationContext": {"pincode": "110001"},
    }

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=20,
        )
    except requests.RequestException as error:
        print("Network error:", type(error).__name__)
        return "UNKNOWN"

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("Flipkart availability request failed.")
        return "UNKNOWN"

    try:
        data = response.json()
    except ValueError:
        print("Flipkart did not return valid JSON.")
        print("Response preview:", response.text[:250])
        return "UNKNOWN"

    def find_status(item):
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() == "availabilitystatus":
                    if isinstance(value, str):
                        status_value = value.upper()
                        if status_value in {
                            "IN_STOCK",
                            "OUT_OF_STOCK",
                        }:
                            return status_value

            for value in item.values():
                result = find_status(value)
                if result:
                    return result

        elif isinstance(item, list):
            for value in item:
                result = find_status(value)
                if result:
                    return result

        return None

    status = find_status(data)
    print("National availability status:", status or "UNKNOWN")

    if status is None:
        print("Could not confirm national stock status.")
        print(
            "Response keys:",
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
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
