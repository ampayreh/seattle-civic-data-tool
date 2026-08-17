"""
SODA (Socrata Open Data API) client for Seattle Open Data.

Translates SoQL queries into SODA API calls against data.seattle.gov
and returns structured results. No authentication required for public
datasets — the SODA API allows unauthenticated access with a
per-IP rate limit of ~1000 requests/hour.

An optional app token (SODA_APP_TOKEN env var) raises the rate limit
and is recommended for production use. Register at:
https://data.seattle.gov/profile/edit/developer_settings
"""

import os
from typing import Any
from urllib.parse import urlencode

import httpx


SEATTLE_DATA_HOST = "data.seattle.gov"
SODA_BASE_URL = f"https://{SEATTLE_DATA_HOST}/resource"

# Seattle Building Permits dataset
PERMITS_DATASET_ID = "76t5-zqzr"
PERMITS_PORTAL_URL = f"https://{SEATTLE_DATA_HOST}/Permitting/Building-Permits/{PERMITS_DATASET_ID}"

# Dataset schema for query validation and prompt context
PERMITS_COLUMNS = {
    "permitnum": {"type": "text", "description": "Permit number (unique identifier)"},
    "permitclass": {"type": "text", "description": "Permit class (e.g., Commercial, Multifamily, Single Family / Duplex)"},
    "permitclassmapped": {"type": "text", "description": "Mapped permit class"},
    "permittypemapped": {"type": "text", "description": "Mapped permit type"},
    "permittypedesc": {"type": "text", "description": "Permit type description (e.g., New, Addition/Alteration, Demolition)"},
    "description": {"type": "text", "description": "Free-text description of the permitted work"},
    "housingunits": {"type": "number", "description": "Total housing units after completion"},
    "housingunitsremoved": {"type": "number", "description": "Housing units removed"},
    "housingunitsadded": {"type": "number", "description": "Housing units added"},
    "estprojectcost": {"type": "number", "description": "Estimated project cost in USD"},
    "applieddate": {"type": "floating_timestamp", "description": "Date the permit application was submitted"},
    "issueddate": {"type": "floating_timestamp", "description": "Date the permit was issued"},
    "expiresdate": {"type": "floating_timestamp", "description": "Date the permit expires"},
    "completeddate": {"type": "floating_timestamp", "description": "Date the project was completed"},
    "statuscurrent": {"type": "text", "description": "Current permit status"},
    "relatedmup": {"type": "text", "description": "Related Master Use Permit number"},
    "originaladdress1": {"type": "text", "description": "Street address"},
    "originalcity": {"type": "text", "description": "City (typically Seattle)"},
    "originalstate": {"type": "text", "description": "State (typically WA)"},
    "originalzip": {"type": "text", "description": "ZIP code"},
    "contractorcompanyname": {"type": "text", "description": "Contractor company name"},
    "link": {"type": "url", "description": "Link to permit details on SDCI portal"},
    "latitude": {"type": "number", "description": "Latitude coordinate"},
    "longitude": {"type": "number", "description": "Longitude coordinate"},
    "totaldaysplanreview": {"type": "number", "description": "Total days in plan review"},
    "daysinitialplanreview": {"type": "number", "description": "Days for initial plan review"},
    "daysplanreviewcity": {"type": "number", "description": "Days plan review by city"},
    "daysoutcorrections": {"type": "number", "description": "Days out for corrections"},
    "numberreviewcycles": {"type": "number", "description": "Number of review cycles"},
    "initialreviewcompletedate": {"type": "floating_timestamp", "description": "Date initial review completed"},
    "planreviewcompletedate": {"type": "floating_timestamp", "description": "Date plan review completed"},
    "daysissuepermitcity": {"type": "number", "description": "Days for city to issue permit"},
    "readytoissuedate": {"type": "floating_timestamp", "description": "Date permit was ready to issue"},
    "zoning": {"type": "text", "description": "Zoning designation"},
    "dwellingunittype": {"type": "text", "description": "Dwelling unit type"},
    "standardplan": {"type": "text", "description": "Whether a standard plan was used"},
    "dependentbuilding": {"type": "text", "description": "Whether this is a dependent building"},
    "parentpermitnum": {"type": "text", "description": "Parent permit number (if dependent)"},
    "housingcategory": {"type": "text", "description": "Housing category classification"},
}


def get_schema_description() -> str:
    """Return a formatted description of the dataset schema for prompts."""
    lines = [
        "## Seattle Building Permits Dataset",
        "",
        f"Source: {PERMITS_PORTAL_URL}",
        "License: Public Domain",
        "Updated: Daily",
        f"Records: ~192,000+",
        "",
        "### Columns",
        "",
    ]
    for col, info in PERMITS_COLUMNS.items():
        lines.append(f"- `{col}` ({info['type']}): {info['description']}")
    return "\n".join(lines)


class SodaClient:
    """Client for the Socrata Open Data API (SODA)."""

    def __init__(self, dataset_id: str = PERMITS_DATASET_ID):
        self.dataset_id = dataset_id
        self.base_url = f"{SODA_BASE_URL}/{dataset_id}.json"
        self.app_token = os.environ.get("SODA_APP_TOKEN")

    def query(
        self,
        select: str = None,
        where: str = None,
        group: str = None,
        order: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Execute a SoQL query against the dataset.

        Args:
            select: SoQL SELECT clause (columns, aggregates).
            where: SoQL WHERE clause (filters).
            group: SoQL GROUP BY clause.
            order: SoQL ORDER BY clause.
            limit: Maximum rows to return (default 100, max 50000).
            offset: Row offset for pagination.

        Returns:
            Dict with "rows" (list of dicts), "count" (int), and "query_url" (str).
        """
        params = {"$limit": min(limit, 50000), "$offset": offset}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if group:
            params["$group"] = group
        if order:
            params["$order"] = order

        headers = {}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        query_url = f"{self.base_url}?{urlencode(params)}"

        try:
            response = httpx.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()

            return {
                "rows": rows,
                "count": len(rows),
                "query_url": query_url,
                "dataset_url": PERMITS_PORTAL_URL,
            }

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response else "No response body"
            return {
                "error": f"HTTP {e.response.status_code}: {error_body}",
                "query_url": query_url,
                "rows": [],
                "count": 0,
            }
        except httpx.RequestError as e:
            return {
                "error": f"Request failed: {str(e)}",
                "query_url": query_url,
                "rows": [],
                "count": 0,
            }


# Claude tool definition for the SODA query
SODA_QUERY_TOOL = {
    "name": "query_seattle_permits",
    "description": (
        "Query the Seattle Building Permits dataset via the SODA API. "
        "Uses SoQL (Socrata Query Language), which is similar to SQL. "
        "Returns up to 'limit' rows matching the query. "
        "All column names are lowercase. Date columns use ISO 8601 format. "
        "For aggregations, use SoQL functions: count(*), sum(), avg(), "
        "min(), max(), date_trunc_y(), date_trunc_ym(). "
        "String matching: use LIKE with % wildcards (case-insensitive by default). "
        "Example WHERE clauses: "
        "\"issueddate > '2024-01-01'\", "
        "\"permitclass = 'Commercial' AND estprojectcost > 1000000\", "
        "\"description LIKE '%solar%'\", "
        "\"originalzip = '98101'\". "
        "Example SELECT with aggregation: "
        "\"permitclass, count(*) as permit_count, avg(estprojectcost) as avg_cost\" "
        "with GROUP set to \"permitclass\"."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "select": {
                "type": "string",
                "description": (
                    "SoQL SELECT clause. Column names (lowercase), aggregates, "
                    "or aliases. Omit for all columns. Examples: "
                    "'permitnum, description, estprojectcost, issueddate', "
                    "'permitclass, count(*) as cnt'."
                ),
            },
            "where": {
                "type": "string",
                "description": (
                    "SoQL WHERE clause. Filter conditions. Examples: "
                    "\"issueddate > '2024-01-01'\", "
                    "\"permitclass = 'Commercial'\", "
                    "\"estprojectcost > 500000 AND description LIKE '%addition%'\"."
                ),
            },
            "group": {
                "type": "string",
                "description": (
                    "SoQL GROUP BY clause. Required when using aggregate "
                    "functions in SELECT. Example: 'permitclass'."
                ),
            },
            "order": {
                "type": "string",
                "description": (
                    "SoQL ORDER BY clause. Column or alias, ASC or DESC. "
                    "Example: 'estprojectcost DESC', 'cnt DESC'."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return (default 100, max 50000).",
                "default": 100,
            },
        },
        "required": [],
    },
}
