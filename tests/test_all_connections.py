"""
tests/test_all_connections.py
──────────────────────────────
Live API connectivity test — uses real credentials from .env.
Run directly:  python tests/test_all_connections.py
DO NOT run via pytest (conftest.py would replace real creds with mocks).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# ── Make sure project root is on sys.path ─────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env before importing settings
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from config.settings import get_settings

# ── Test results store ────────────────────────────────────────────────────────
results: dict[str, tuple[bool, str]] = {}  # name -> (passed, detail)


def record(name: str, passed: bool, detail: str = "") -> None:
    results[name] = (passed, detail)
    status = "PASS" if passed else "FAIL"
    mark = "OK" if passed else "!!"
    print(f"  [{mark}] {name}: {status}" + (f" — {detail}" if detail else ""))


# ── 1. Gemini API ─────────────────────────────────────────────────────────────
def test_gemini(s) -> None:
    print("\nTesting Gemini API...")
    try:
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning)
        import google.generativeai as genai
        genai.configure(api_key=s.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            'Reply with exactly this JSON and nothing else: {"status": "connected"}'
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = "\n".join(
                line for line in text.splitlines()
                if not line.startswith("```")
            ).strip()
        data = json.loads(text)
        if data.get("status") == "connected":
            record("Gemini API", True)
        else:
            record("Gemini API", False, f"Unexpected response: {text[:120]}")
    except Exception as exc:
        record("Gemini API", False, str(exc)[:120])


# ── 2. Apollo.io API ──────────────────────────────────────────────────────────
def test_apollo(s) -> None:
    print("\nTesting Apollo.io API...")
    try:
        import requests
        resp = requests.post(
            "https://api.apollo.io/api/v1/organizations/enrich",
            headers={
                "X-Api-Key": s.apollo_api_key,
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
            json={"domain": "nike.com"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        org = data.get("organization") or {}
        name = org.get("name") or org.get("primary_domain") or ""
        if name:
            record("Apollo API", True, f"org={name}")
        else:
            record("Apollo API", False, f"No org name returned: {str(data)[:120]}")
    except Exception as exc:
        record("Apollo API", False, str(exc)[:120])


# ── 3. Instantly.ai API ───────────────────────────────────────────────────────
def test_instantly(s) -> None:
    print("\nTesting Instantly.ai API...")
    try:
        import requests
        # Try v1 with query param first, then v2 Bearer header
        resp = requests.get(
            "https://api.instantly.ai/api/v1/authenticate",
            params={"api_key": s.instantly_api_key},
            timeout=15,
        )
        if resp.status_code == 401:
            # Try v2 Bearer token format (Instantly migrated to v2 in late 2024)
            resp = requests.get(
                "https://api.instantly.ai/api/v2/campaigns",
                headers={"Authorization": f"Bearer {s.instantly_api_key}"},
                params={"limit": 1},
                timeout=15,
            )
        data = resp.json()
        if resp.status_code == 200:
            record("Instantly API", True, f"authenticated ok")
        else:
            err = data.get("error") or data.get("message") or str(data)[:80]
            record("Instantly API", False, f"HTTP {resp.status_code}: {err}")
    except Exception as exc:
        record("Instantly API", False, str(exc)[:120])


# ── 4. Slack Webhook ──────────────────────────────────────────────────────────
def test_slack(s) -> None:
    print("\nTesting Slack Webhook...")
    try:
        import requests
        resp = requests.post(
            s.slack_webhook_url,
            json={"text": "AdRadar all-systems test - ignore this message"},
            timeout=15,
        )
        if resp.status_code == 200:
            record("Slack Webhook", True)
        else:
            record("Slack Webhook", False, f"HTTP {resp.status_code}: {resp.text[:80]}")
    except Exception as exc:
        record("Slack Webhook", False, str(exc)[:120])


# ── 5. Meta Ad Library API ────────────────────────────────────────────────────
def test_meta(s) -> None:
    print("\nTesting Meta Ad Library API...")
    try:
        import requests
        resp = requests.get(
            "https://graph.facebook.com/v21.0/ads_archive",
            params={
                "access_token": s.meta_access_token,
                "search_terms": "skincare",
                "ad_reached_countries": '["GB"]',
                "ad_type": "ALL",
                "fields": "page_name,ad_snapshot_url",
                "limit": 2,
            },
            timeout=20,
        )
        data = resp.json()
        # Check for API-level errors before raising HTTP error
        if "error" in data:
            err = data["error"]
            code = err.get("code", 0)
            msg = err.get("message", str(err))
            if code == 190 or "expired" in msg.lower():
                msg = "Access token expired — regenerate at developers.facebook.com/tools/explorer"
            record("Meta Ad Library", False, msg[:120])
            return
        resp.raise_for_status()
        ads = data.get("data", [])
        if ads and ads[0].get("page_name"):
            record("Meta Ad Library", True, f"got {len(ads)} ad(s), first page={ads[0]['page_name'][:40]}")
        elif ads:
            record("Meta Ad Library", False, f"Ads returned but missing page_name: {str(ads[0])[:120]}")
        else:
            record("Meta Ad Library", False, f"No ads returned. Response: {str(data)[:120]}")
    except Exception as exc:
        record("Meta Ad Library", False, str(exc)[:120])


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading settings from .env...")
    try:
        s = get_settings()
        print("Settings OK.\n")
    except Exception as exc:
        print(f"FATAL: Could not load settings — {exc}")
        sys.exit(1)

    test_gemini(s)
    test_apollo(s)
    test_instantly(s)
    test_slack(s)
    test_meta(s)

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for ok, _ in results.values() if ok)
    total = len(results)

    border = "=" * 34
    print(f"\n{border}")
    print(" ADRADAR API CONNECTION REPORT")
    print(border)
    labels = {
        "Gemini API":      "Gemini API:     ",
        "Apollo API":      "Apollo API:     ",
        "Instantly API":   "Instantly API:  ",
        "Slack Webhook":   "Slack Webhook:  ",
        "Meta Ad Library": "Meta Ad Library:",
    }
    for name, label in labels.items():
        ok, detail = results.get(name, (False, "not run"))
        mark = "PASS" if ok else "FAIL"
        extra = f"  ({detail})" if not ok and detail else ""
        print(f"  {label} {mark}{extra}")
    print(border)
    print(f"  RESULT: {passed}/{total} APIs connected and ready")
    print(border)

    sys.exit(0 if passed == total else 1)
