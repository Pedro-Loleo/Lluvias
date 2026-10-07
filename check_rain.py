import asyncio
import hashlib
import json
import os
from pathlib import Path

import requests
from playwright.async_api import async_playwright

URL = "https://www.arecoclima.com.ar/"
STATE_FILE = Path("state.json")


async def get_rain_text():
    """Abre la página con un navegador headless (porque los valores se
    pintan con JavaScript) y junta el texto de todos los elementos que
    tengan 'rain' en su id o clase."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)  # margen para que termine de cargar
        texts = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => el.children.length === 0)
                .filter(el => {
                    const id = (el.id || '').toLowerCase();
                    const cls = (el.className && el.className.toString)
                        ? el.className.toString().toLowerCase() : '';
                    return id.includes('rain') || cls.includes('rain');
                })
                .map(el => el.innerText.trim())
                .filter(Boolean)
            """
        )
        await browser.close()
        return texts


def load_previous():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"hash": None, "values": []}


def save_state(hash_, values):
    STATE_FILE.write_text(
        json.dumps({"hash": hash_, "values": values}, ensure_ascii=False, indent=2)
    )


def send_whatsapp(body):
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": phone, "text": body, "apikey": apikey},
        timeout=15,
    )


def main():
    values = asyncio.run(get_rain_text())
    blob = " | ".join(values)
    current_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    previous = load_previous()

    if previous["hash"] is None:
        # Primera corrida: guardamos el estado base sin avisar
        save_state(current_hash, values)
        print("Estado inicial guardado:", blob)
        return

    if current_hash != previous["hash"]:
        body = (
            "Cambio detectado en la lluvia de ArecoClima:\n\n"
            f"Antes: {' | '.join(previous['values'])}\n"
            f"Ahora: {blob}\n\n"
            f"{URL}"
        )
        send_whatsapp(body)
        save_state(current_hash, values)
        print("Cambio detectado y notificado.")
    else:
        print("Sin cambios.")


if __name__ == "__main__":
    main()
