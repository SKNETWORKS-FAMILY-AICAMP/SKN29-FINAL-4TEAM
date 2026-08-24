"""Secret-free HTTPS smoke check for a deployed WaterBridge release."""

from __future__ import annotations

import argparse
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse


CORRELATION_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def request(url: str, *, follow_redirects: bool = True) -> tuple[int, object]:
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=ssl.create_default_context())
    ]
    if not follow_redirects:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(url, timeout=15) as response:
            response.read(1024)
            return response.status, response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://waterbridge.site")
    args = parser.parse_args()

    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        parser.error("--base-url must be an https origin")

    https_origin = f"https://{parsed.netloc}"
    http_origin = f"http://{parsed.netloc}"

    redirect_status, redirect_headers = request(http_origin, follow_redirects=False)
    if redirect_status not in {301, 302, 307, 308}:
        raise SystemExit(f"HTTP redirect failed: status={redirect_status}")
    location = str(redirect_headers.get("Location", ""))
    if not location.startswith(https_origin):
        raise SystemExit("HTTP redirect does not target the HTTPS origin")

    root_status, _ = request(f"{https_origin}/")
    if root_status != 200:
        raise SystemExit(f"HTTPS root failed: status={root_status}")

    health_status, health_headers = request(f"{https_origin}/health")
    if health_status != 200:
        raise SystemExit(f"HTTPS health failed: status={health_status}")
    correlation_id = str(health_headers.get("X-Correlation-ID", "")).strip()
    if CORRELATION_ID.fullmatch(correlation_id) is None:
        raise SystemExit("HTTPS health is missing a canonical X-Correlation-ID")

    print("PRODUCTION_SMOKE_PASS")
    print(f"origin={https_origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
