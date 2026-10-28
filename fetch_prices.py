import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


MADRID = ZoneInfo("Europe/Madrid")
ENDPOINT = (
    "https://apidatos.ree.es/es/datos/"
    "mercados/precios-mercados-tiempo-real"
)
OUTPUT = Path("data/prices.json")


def main():
    now = datetime.now(MADRID)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    params = {
        "start_date": f"{today.isoformat()}T00:00",
        "end_date": f"{tomorrow.isoformat()}T23:59",
        "time_trunc": "hour",
        "geo_trunc": "electric_system",
        "geo_limit": "peninsular",
        "geo_ids": "8741",
    }

    url = ENDPOINT + "?" + urlencode(params)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "precio-luz-hoy/1.0",
        },
    )

    with urlopen(request, timeout=45) as response:
        payload = json.load(response)

    matches = [
        item
        for item in payload.get("included", [])
        if str(item.get("id")) == "1001"
        and item.get("attributes", {}).get("title", "").upper() == "PVPC"
    ]

    if len(matches) != 1:
        raise ValueError("Expected exactly one PVPC series (1001).")

    attributes = matches[0]["attributes"]
    days = {
        today.isoformat(): [],
        tomorrow.isoformat(): [],
    }
    seen = set()

    for item in attributes.get("values", []):
        timestamp = datetime.fromisoformat(
            item["datetime"].replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            raise ValueError("A timestamp has no timezone.")

        local = timestamp.astimezone(MADRID)
        date_key = local.date().isoformat()

        if date_key not in days:
            continue

        if local.minute != 0 or local.second != 0:
            raise ValueError("Unexpected non-hourly timestamp.")

        unique_key = timestamp.astimezone(timezone.utc).isoformat()
        if unique_key in seen:
            raise ValueError("Duplicate hourly timestamp.")
        seen.add(unique_key)

        raw_value = item.get("value")
        if raw_value is None or isinstance(raw_value, bool):
            raise ValueError("Missing or invalid price.")

        eur_mwh = float(raw_value)
        if not math.isfinite(eur_mwh):
            raise ValueError("Price is not a finite number.")

        days[date_key].append({
            "datetime": local.isoformat(),
            "price_eur_mwh": eur_mwh,
            "price_eur_kwh": round(eur_mwh / 1000, 8),
        })

    results = {}

    for date_key, prices in days.items():
        prices.sort(
            key=lambda row: datetime.fromisoformat(
                row["datetime"]
            ).timestamp()
        )

        date = datetime.fromisoformat(date_key).date()
        start = datetime.combine(date, datetime.min.time(), MADRID)
        end = datetime.combine(
            date + timedelta(days=1),
            datetime.min.time(),
            MADRID,
        )
        expected_hours = int(
            (
                end.astimezone(timezone.utc)
                - start.astimezone(timezone.utc)
            ).total_seconds() / 3600
        )

        complete = len(prices) == expected_hours

        if complete:
            actual_times = [
                int(datetime.fromisoformat(row["datetime"]).timestamp())
                for row in prices
            ]
            expected_times = [
                int(start.timestamp()) + hour * 3600
                for hour in range(expected_hours)
            ]
            complete = actual_times == expected_times

        results[date_key] = {
            "status": "complete" if complete else "unavailable",
            "expected_hours": expected_hours,
            "received_hours": len(prices),
            "prices": prices if complete else [],
        }

    if results[today.isoformat()]["status"] != "complete":
        raise ValueError(
            "Today's data is incomplete. Existing JSON is not overwritten."
        )

    document = {
        "source": "Red Eléctrica de España / REData",
        "source_url": url,
        "series_id": "1001",
        "tariff": "PVPC",
        "region": "peninsular",
        "timezone": "Europe/Madrid",
        "unit": "EUR/kWh",
        "fetched_at": now.isoformat(),
        "source_updated_at": attributes.get("last-update"),
        "days": results,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, OUTPUT)

    print(f"Saved: {OUTPUT}")
    for date_key, result in results.items():
        print(
            date_key,
            result["status"],
            f'({result["received_hours"]}/{result["expected_hours"]} hours)',
        )


if __name__ == "__main__":
    main()
