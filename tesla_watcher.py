"""
Tesla Inventory Watcher (Italien - Pronta Consegna)
Überwacht neue Fahrzeuge für Model Y und Model 3 und sendet E-Mail-Benachrichtigungen
an aperathoner@gmail.com, sobald ein neues Fahrzeug gelistet wird.
"""

import argparse
import json
import logging
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright

# Konfiguriere UTF-8 Ausgabe für Windows-Konsolen
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "seen_vehicles.json"
LOG_FILE = BASE_DIR / "watcher.log"
ENV_FILE = BASE_DIR / ".env"

# Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("TeslaWatcher")

URLS_TO_WATCH = [
    {
        "model_name": "Model Y",
        "model_code": "my",
        "url": "https://www.tesla.com/it_IT/inventory/new/my?arrangeby=plh&zip=39100&range=0",
    },
    {
        "model_name": "Model 3",
        "model_code": "m3",
        "url": "https://www.tesla.com/it_IT/inventory/new/m3?arrangeby=plh&zip=39100&range=0",
    },
]


def load_env() -> Dict[str, str]:
    """Lädt Umgebungsvariablen aus der .env Datei (falls vorhanden) und os.environ."""
    config = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            config[key.strip()] = val.strip().strip('"').strip("'")
    # System-Umgebungsvariablen (z.B. in GitHub Actions) haben Vorrang
    for k in [
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "RECIPIENT_EMAIL",
        "CHECK_INTERVAL_MINUTES",
        "INCLUDE_APPROXIMATE",
    ]:
        if k in os.environ and os.environ[k]:
            config[k] = os.environ[k]
    return config


def load_seen_vehicles() -> Dict[str, Dict[str, Any]]:
    """Lädt bereits gemeldete Fahrzeuge (VIN -> Fahrzeuginfo)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Konnte {STATE_FILE} nicht lesen: {e}")
    return {}


def save_seen_vehicles(seen: Dict[str, Dict[str, Any]]) -> None:
    """Speichert bereits gemeldete Fahrzeuge."""
    STATE_FILE.write_text(json.dumps(seen, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_vehicles_from_api(data: Dict[str, Any], model_name: str, model_code: str, source_url: str, include_approximate: bool = True) -> List[Dict[str, Any]]:
    """Extrahiert die Fahrzeugliste aus der Tesla Inventory v4 API-Antwort."""
    results = data.get("results", {})
    raw_list: List[Dict[str, Any]] = []

    if isinstance(results, list):
        raw_list.extend(results)
    elif isinstance(results, dict):
        exact = results.get("exact") or []
        raw_list.extend(exact)
        if include_approximate:
            approx = results.get("approximate") or []
            raw_list.extend(approx)

    vehicles: List[Dict[str, Any]] = []
    seen_in_batch = set()

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        vin = item.get("VIN") or item.get("vin") or item.get("Hash")
        if not vin or vin in seen_in_batch:
            continue
        seen_in_batch.add(vin)

        trim_name = item.get("TrimName") or item.get("Trim") or model_name
        price = item.get("InventoryPrice") or item.get("PurchasePrice") or item.get("Price")
        currency = item.get("CurrencyCode") or "EUR"
        year = item.get("Year") or datetime.now().year
        odometer = item.get("Odometer") or 0
        odometer_type = item.get("OdometerTypeShort") or "km"
        paint = ", ".join(item.get("PAINT", [])) if isinstance(item.get("PAINT"), list) else ""
        interior = ", ".join(item.get("INTERIOR", [])) if isinstance(item.get("INTERIOR"), list) else ""
        city = item.get("City") or item.get("LocationName") or "Italien"
        is_demo = item.get("IsDemo", False)

        detail_url = f"https://www.tesla.com/it_IT/{model_code}/order/{vin}?titleStatus=new&redirect=no#overview"

        vehicles.append({
            "vin": str(vin),
            "model_name": model_name,
            "trim_name": str(trim_name),
            "price": price,
            "currency": currency,
            "year": year,
            "odometer": f"{odometer} {odometer_type}",
            "paint": paint,
            "interior": interior,
            "location": city,
            "is_demo": is_demo,
            "detail_url": detail_url,
            "inventory_url": source_url,
            "found_at": datetime.now().isoformat(timespec="seconds"),
        })

    return vehicles


def check_tesla_inventory(include_approximate: bool = True) -> List[Dict[str, Any]]:
    """Ruft das Tesla-Inventar für Model Y und Model 3 mit Playwright ab."""
    found_vehicles: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        # Nutze echten Chrome/Edge-Kanal oder Chromium im Off-Screen-Modus (umgeht Akamai Bot-Blocker)
        launch_args = [
            "--window-position=-32000,-32000",
            "--window-size=1280,800",
            "--disable-blink-features=AutomationControlled",
        ]
        browser = None
        for channel in ["chrome", "msedge", None]:
            try:
                kwargs: Dict[str, Any] = {"headless": False, "args": launch_args}
                if channel:
                    kwargs["channel"] = channel
                browser = p.chromium.launch(**kwargs)
                break
            except Exception:
                continue

        if browser is None:
            raise RuntimeError("Konnte keinen Browser (Chrome/Edge/Chromium) starten.")

        context = browser.new_context(
            locale="it-IT",
            viewport={"width": 1280, "height": 800},
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for entry in URLS_TO_WATCH:
            model_name = entry["model_name"]
            model_code = entry["model_code"]
            url = entry["url"]

            page = context.new_page()
            captured_api: List[Dict[str, Any]] = []

            def handle_response(response, cap=captured_api):
                if "inventory-results" in response.url and response.status == 200:
                    try:
                        cap.append(response.json())
                    except Exception:
                        pass

            page.on("response", handle_response)
            try:
                logger.info(f"Prüfe {model_name}: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=35000)

                # Warte bis zu 12 Sekunden auf die Inventory-API-Antwort
                for _ in range(24):
                    if captured_api:
                        break
                    page.wait_for_timeout(500)

                if captured_api:
                    api_data = captured_api[0]
                    total_matches = api_data.get("total_matches_found", 0)
                    vehicles = extract_vehicles_from_api(
                        api_data,
                        model_name=model_name,
                        model_code=model_code,
                        source_url=url,
                        include_approximate=include_approximate,
                    )
                    logger.info(
                        f"{model_name}: API meldet total_matches_found={total_matches}, "
                        f"extrahierte Fahrzeuge={len(vehicles)}"
                    )
                    found_vehicles.extend(vehicles)
                else:
                    title = page.title()
                    logger.warning(f"{model_name}: Keine API-Antwort empfangen (Seitentitel: '{title}').")
            except Exception as e:
                logger.error(f"Fehler beim Abruf von {model_name}: {e}")
            finally:
                page.close()

        browser.close()

    return found_vehicles


def send_email_notification(vehicles: List[Dict[str, Any]], config: Dict[str, str], is_test: bool = False) -> bool:
    """Sendet eine formatierte HTML-E-Mail über SMTP."""
    smtp_server = config.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(config.get("SMTP_PORT", "587"))
    smtp_user = config.get("SMTP_USER", "")
    smtp_password = config.get("SMTP_PASSWORD", "")
    recipient = config.get("RECIPIENT_EMAIL", "aperathoner@gmail.com")

    if not smtp_user or not smtp_password or "DEIN_APP_PASSWORT" in smtp_password:
        logger.error(
            "E-Mail konnte nicht gesendet werden: Bitte SMTP_USER und SMTP_PASSWORD in der .env Datei eintragen!"
        )
        return False

    subject_prefix = "[TEST] " if is_test else "🚨 "
    models_str = ", ".join(sorted({v["model_name"] for v in vehicles}))
    subject = f"{subject_prefix}Tesla Pronta Consegna verfügbar! ({len(vehicles)}x {models_str})"

    rows_html = ""
    for v in vehicles:
        price_str = f"{v['price']:,} {v['currency']}".replace(",", ".") if isinstance(v["price"], (int, float)) else str(v["price"] or "Siehe Website")
        rows_html += f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; font-family: Arial, sans-serif;">
            <h3 style="margin-top: 0; color: #e82127;">{v['model_name']} – {v['trim_name']} ({v['year']})</h3>
            <p style="margin: 6px 0;"><strong>💰 Preis:</strong> {price_str}</p>
            <p style="margin: 6px 0;"><strong>🎨 Lackierung / Innenraum:</strong> {v['paint'] or '-'} / {v['interior'] or '-'}</p>
            <p style="margin: 6px 0;"><strong>📍 Standort:</strong> {v['location']} | <strong>Tacho:</strong> {v['odometer']}</p>
            <p style="margin: 6px 0;"><strong>🔢 VIN:</strong> <code>{v['vin']}</code></p>
            <p style="margin-top: 12px;">
                <a href="{v['detail_url']}" style="background-color: #e82127; color: #ffffff; padding: 10px 16px; text-decoration: none; border-radius: 5px; font-weight: bold;">Direkt zum Fahrzeug</a>
                &nbsp;
                <a href="{v['inventory_url']}" style="color: #333; text-decoration: underline;">Zur Pronta Consegna Übersicht</a>
            </p>
        </div>
        """

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.5;">
        <h2>Neue Tesla Fahrzeuge in Pronta Consegna gefunden!</h2>
        <p>Der Tesla Inventory Watcher hat folgende neue Fahrzeuge für deine Suche (PLZ 39100 / Italien) entdeckt:</p>
        {rows_html}
        <hr style="border: none; border-top: 1px solid #eee; margin-top: 24px;">
        <p style="font-size: 12px; color: #777;">Automatisch gesendet vom Tesla Inventory Watcher am {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')}.</p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [recipient], msg.as_string())
        logger.info(f"✅ E-Mail erfolgreich an {recipient} gesendet ({len(vehicles)} Fahrzeug(e)).")
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim E-Mail-Versand: {e}")
        return False


def run_check(config: Dict[str, str]) -> None:
    """Führt einen einzelnen Prüfdurchlauf durch."""
    include_approx = config.get("INCLUDE_APPROXIMATE", "true").lower() in ("true", "1", "yes")
    seen = load_seen_vehicles()

    vehicles = check_tesla_inventory(include_approximate=include_approx)
    new_vehicles = [v for v in vehicles if v["vin"] not in seen]

    if new_vehicles:
        logger.info(f"🎉 {len(new_vehicles)} neue(s) Fahrzeug(e) entdeckt!")
        sent = send_email_notification(new_vehicles, config, is_test=False)
        if sent:
            for v in new_vehicles:
                seen[v["vin"]] = v
            save_seen_vehicles(seen)
    else:
        logger.info("Keine neuen Fahrzeuge in Pronta Consegna gefunden.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tesla Inventory Watcher (Model Y & Model 3)")
    parser.add_argument("--once", action="store_true", help="Nur einmal prüfen und danach beenden (ideal für Cron / Cloud / Task Scheduler)")
    parser.add_argument("--test-email", action="store_true", help="Sendet eine Test-E-Mail an aperathoner@gmail.com zur Überprüfung der Konfiguration")
    args = parser.parse_args()

    config = load_env()

    if args.test_email:
        dummy_vehicle = [{
            "vin": "XP7YGCEK0RB000000",
            "model_name": "Model Y",
            "trim_name": "Model Y Rear-Wheel Drive (TEST)",
            "price": 42690,
            "currency": "EUR",
            "year": datetime.now().year,
            "odometer": "0 km",
            "paint": "Pearl White",
            "interior": "All Black",
            "location": "Bozen / Italien (Test)",
            "is_demo": False,
            "detail_url": "https://www.tesla.com/it_IT/inventory/new/my?arrangeby=plh&zip=39100&range=0",
            "inventory_url": "https://www.tesla.com/it_IT/inventory/new/my?arrangeby=plh&zip=39100&range=0",
            "found_at": datetime.now().isoformat(timespec="seconds"),
        }]
        send_email_notification(dummy_vehicle, config, is_test=True)
        return

    if args.once:
        run_check(config)
        return

    interval_minutes = int(config.get("CHECK_INTERVAL_MINUTES", "10"))
    logger.info(f"🚀 Tesla Inventory Watcher gestartet (Intervall: alle {interval_minutes} Minuten).")
    logger.info(f"Überwache Model Y & Model 3 für Benachrichtigung an {config.get('RECIPIENT_EMAIL', 'aperathoner@gmail.com')}")

    while True:
        try:
            run_check(config)
        except Exception as e:
            logger.error(f"Unerwarteter Fehler im Prüfdurchlauf: {e}")
        logger.info(f"Nächste Prüfung in {interval_minutes} Minuten...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()
