"""
storage/airtable_client.py
───────────────────────────
Airtable read/write client using pyairtable.

Implements an upsert pattern: check for existing record by Website URL,
update if found, create if not. All field names match the canonical
Airtable schema defined in models/lead.py → Lead.to_airtable_fields().

Table schema expected in Airtable (create manually or via Airtable API):
  Brand Name        Single line text
  Website           URL
  Ad Platform       Single select
  Days Running      Number
  Num Ads           Number
  Monthly Traffic   Number
  Paid Traffic Pct  Number
  ROAS Risk Score   Number
  Lead Tier         Single select  (HOT / WARM / COLD)
  Score Breakdown   Long text
  Contact Name      Single line text
  Contact Title     Single line text
  Contact Email     Email
  Contact LinkedIn  URL
  Email 1 Subject   Single line text
  Email 1 Body      Long text
  Email 2 Subject   Single line text
  Email 2 Body      Long text
  Email 3 Subject   Single line text
  Email 3 Body      Long text
  Outreach Status   Single select  (Pending / Sent / Replied / Booked)
  Date Added        Date
  Notes             Long text
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pyairtable import Api
from pyairtable.formulas import match

from models.lead import Lead
from utils.logging_setup import get_logger
from utils.retry import with_retry

logger = get_logger(__name__)


class AirtableClient:
    """
    High-level Airtable client for the Leads table.

    Parameters
    ----------
    api_key:    Personal access token or legacy API key.
    base_id:    The Airtable base ID (starts with 'app').
    table_name: Name of the table inside the base (default 'Leads').
    """

    def __init__(
        self,
        api_key: str,
        base_id: str,
        table_name: str = "Leads",
    ) -> None:
        self._api = Api(api_key)
        self._table = self._api.table(base_id, table_name)

    # ── Internal helpers ──────────────────────────────────────────────────

    @with_retry(max_attempts=3, min_wait=1.0, max_wait=10.0)
    def _find_by_website(self, website_url: str) -> Optional[str]:
        """
        Search for an existing record by Website field.
        Returns Airtable record ID if found, else None.
        """
        try:
            formula = match({"Website": website_url})
            records = self._table.all(formula=formula, max_records=1)
            if records:
                return records[0]["id"]
        except Exception as exc:
            logger.warning("Airtable lookup failed for '%s': %s", website_url, exc)
        return None

    @with_retry(max_attempts=3, min_wait=1.0, max_wait=10.0)
    def _create_record(self, fields: Dict) -> str:
        """Create a new Airtable record. Returns the new record ID."""
        result = self._table.create(fields)
        return result["id"]

    @with_retry(max_attempts=3, min_wait=1.0, max_wait=10.0)
    def _update_record(self, record_id: str, fields: Dict) -> None:
        """Update an existing Airtable record."""
        self._table.update(record_id, fields)

    # ── Public API ────────────────────────────────────────────────────────

    def upsert_lead(self, lead: Lead) -> str:
        """
        Create or update an Airtable record for the given lead.

        Deduplicates on Website field. If a matching record exists,
        it is updated in-place; otherwise a new record is created.

        Parameters
        ----------
        lead: Fully populated Lead object.

        Returns
        -------
        Airtable record ID (str).

        Raises
        ------
        Exception on persistent API failure after retries.
        """
        fields = lead.to_airtable_fields()

        # Try to find existing record
        existing_id: Optional[str] = None
        if lead.website_url:
            existing_id = self._find_by_website(lead.website_url)
        elif lead.page_url:
            existing_id = self._find_by_website(lead.page_url)

        if existing_id:
            self._update_record(existing_id, fields)
            lead.airtable_record_id = existing_id
            logger.debug("Updated Airtable record %s for '%s'", existing_id, lead.brand_name)
            return existing_id
        else:
            new_id = self._create_record(fields)
            lead.airtable_record_id = new_id
            logger.debug("Created Airtable record %s for '%s'", new_id, lead.brand_name)
            return new_id

    def save_leads_batch(self, leads: List[Lead]) -> Dict[str, int]:
        """
        Upsert all leads to Airtable.

        Parameters
        ----------
        leads: List of Lead objects (typically HOT + WARM leads).

        Returns
        -------
        Dict with keys: created, updated, failed.
        """
        created = updated = failed = 0

        for lead in leads:
            # Pre-check: does the record already exist?
            existing_id: Optional[str] = None
            if lead.website_url:
                try:
                    existing_id = self._find_by_website(lead.website_url)
                except Exception:
                    pass

            try:
                record_id = self.upsert_lead(lead)
                if existing_id:
                    updated += 1
                else:
                    created += 1
            except Exception as exc:
                failed += 1
                logger.error("Failed to upsert '%s' to Airtable: %s", lead.brand_name, exc)

        logger.info(
            "Airtable batch complete: %d created | %d updated | %d failed",
            created, updated, failed,
        )
        return {"created": created, "updated": updated, "failed": failed}

    def get_hot_leads(self) -> List[Dict]:
        """
        Fetch all records where Lead Tier = 'HOT'.

        Returns
        -------
        List of raw Airtable record dicts.
        """
        try:
            formula = match({"Lead Tier": "HOT"})
            records = self._table.all(formula=formula)
            logger.info("Fetched %d HOT leads from Airtable", len(records))
            return records
        except Exception as exc:
            logger.error("Failed to fetch HOT leads from Airtable: %s", exc)
            return []

    def update_outreach_status(self, record_id: str, status: str) -> None:
        """Convenience method to update just the Outreach Status field."""
        try:
            self._update_record(record_id, {"Outreach Status": status})
        except Exception as exc:
            logger.error("Failed to update outreach status for %s: %s", record_id, exc)


def get_airtable_client(
    api_key: Optional[str] = None,
    base_id: Optional[str] = None,
    table_name: Optional[str] = None,
) -> AirtableClient:
    """
    Factory function — creates an AirtableClient from settings.

    Falls back to get_settings() for any omitted parameter.
    """
    from config.settings import get_settings
    cfg = get_settings()
    return AirtableClient(
        api_key=api_key or cfg.airtable_api_key,
        base_id=base_id or cfg.airtable_base_id,
        table_name=table_name or cfg.airtable_table_name,
    )
