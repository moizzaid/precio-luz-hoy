import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo


def main():
    today = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()

    params = {
        "start_date": f"{today}T00:00",
        "end_date": f"{today}T23:59",
        "time_trunc": "hour",
        "geo_trunc": "electric_system",
        "geo_limit": "peninsular",
        "geo_ids": "8741",
    }

    endpoint = (
        "https://apidatos.ree.es/es/datos/"
        "mercados/precios-mercados-tiempo-real"
    )
    url = endpoint + "?" + urlencode(params)

    print("Date in Spain:", today)
    print("Testing URL:", url)

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "precio-luz-hoy-data-test/1.0",
        },
    )

    try:
        with urlopen(request, timeout=45) as response:
            print("HTTP status:", response.status)
            data = json.load(response)

    except HTTPError as error:
        print("HTTP error:", error.code)
        print(error.read().decode("utf-8", errors="replace")[:3000])
        raise

    except URLError as error:
        print("Connection error:", error.reason)
        raise

    print("\nWidget information:")
    print(json.dumps(
        data.get("data", {}).get("attributes", {}),
        ensure_ascii=False,
        indent=2,
    ))

    series = data.get("included", [])
    print("\nNumber of series:", len(series))

    if not series:
        print("No price series returned. Inspect the response:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:6000])
        return

    for item in series:
        attributes = item.get("attributes", {})
        values = attributes.get("values") or []

        print("\n" + "=" * 50)
        print("Series ID:", item.get("id"))
        print("Title:", attributes.get("title"))
        print("Type:", item.get("type"))

        metadata = {
            key: value
            for key, value in attributes.items()
            if key != "values"
        }
        print("Metadata:")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))

        print("Number of values:", len(values))
        print("First three values:")
        print(json.dumps(values[:3], ensure_ascii=False, indent=2))

    print("\nTest complete.")
    print("Verify the PVPC series and units before publishing prices.")


if __name__ == "__main__":
    main()
