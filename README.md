# Seattle Civic Data Tool

Ask questions about Seattle building permits in plain English. The tool translates your question into a SODA API query, fetches live data from data.seattle.gov, and produces a Claude-analyzed summary with source citations.

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│  User Question (natural language)                            │
│  "How many housing units were added in Seattle in 2024?"     │
└──────────────────────────┬───────────────────────────────────┘
                           │
                    query_tool.py
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  Claude (Sonnet via Anthropic API)                            │
│                                                              │
│  System prompt:                                              │
│    Dataset schema (40 columns, types, descriptions)          │
│    SoQL query rules + formatting instructions                │
│                                                              │
│  Tool: query_seattle_permits(select, where, group, order)    │
│    → translates to SoQL                                      │
│    → executes against SODA API                               │
│    → returns live data from data.seattle.gov                 │
│                                                              │
│  Claude may make 1-3 queries per question:                   │
│    1. Broad query to understand the data shape               │
│    2. Focused follow-up for specific numbers                 │
│    3. Comparison query for context                           │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  Analysis (Markdown)                                         │
│                                                              │
│  - Data-backed answer with specific numbers                  │
│  - Permit IDs, addresses, costs from actual records          │
│  - Source citation linking to data.seattle.gov               │
└──────────────────────────────────────────────────────────────┘
```

## Quickstart

```bash
git clone https://github.com/ampayreh/seattle-civic-data-tool.git
cd seattle-civic-data-tool
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...

# Ask a question
python query_tool.py "How many building permits were issued in 2024?"

# Interactive mode
python query_tool.py --interactive

# JSON output (includes query details and metrics)
python query_tool.py "Most expensive projects in 98101" --format json
```

## Example Questions

| Question | What it exercises |
|----------|------------------|
| "How many permits were issued in 2024?" | Counting, date filtering |
| "What are the 10 most expensive projects this year?" | Sorting, limiting, cost analysis |
| "Show me all solar panel installations since 2023" | Text search (LIKE), date range |
| "Average project cost by permit class?" | Aggregation, GROUP BY |
| "Housing units added per year since 2015?" | Time series, sum aggregation |
| "Which ZIP codes have the most construction?" | Geographic aggregation, ranking |
| "Average plan review time for commercial vs residential?" | Comparative aggregation |
| "Demolition permits in 98103?" | Multi-condition filtering |

See [examples/sample-queries.md](examples/sample-queries.md) for more, with the SoQL each generates.

## Project Structure

```
seattle-civic-data-tool/
├── query_tool.py          # Main CLI (Claude API + tool use)
├── soda_client.py         # SODA API client + dataset schema
├── requirements.txt       # Python dependencies (anthropic, httpx)
├── DECISIONS.md           # Documented architectural decisions
├── examples/
│   └── sample-queries.md  # Example questions with SoQL translations
└── README.md
```

## Dataset

**Seattle Building Permits** — all building permits issued or in progress within the City of Seattle.

| Property | Value |
|----------|-------|
| Source | [data.seattle.gov/Permitting/Building-Permits/76t5-zqzr](https://data.seattle.gov/Permitting/Building-Permits/76t5-zqzr) |
| Publisher | City of Seattle, Dept. of Construction & Inspections (SDCI) |
| License | Public Domain |
| Records | ~192,000+ |
| Updated | Daily |
| Columns | 40 (permits, costs, dates, locations, contractors, review times, housing units, zoning) |
| API | Socrata Open Data API (SODA), no authentication required |

No dataset rows are committed to this repository. All queries hit the live API at runtime.

## Data Flow

1. **No local data.** The tool stores nothing — every query goes to the city's live API
2. **SoQL, not SQL.** Queries use Socrata Query Language (SoQL) natively, with no translation layer
3. **Grounded answers.** Claude answers only from fetched data, never from general knowledge about Seattle
4. **Source citations.** Every answer includes the dataset URL; JSON output includes the exact query URL for reproducibility

## What This Does Not Do

- **Not a dashboard.** This is a CLI tool, not a web application. It answers one question at a time (or interactively in a loop).
- **Not a multi-dataset tool.** It queries the Building Permits dataset only. The architecture supports adding datasets (new schema + tool definition), but depth on one rich dataset demonstrates more than shallow queries across five.
- **Not real-time monitoring.** It queries on demand, not on a schedule. It does not alert on permit changes or track trends over time automatically.
- **Not a substitute for SDCI records.** The open data portal is a public convenience layer over the city's permitting system. For official permit status, building code compliance, or legal questions, contact [SDCI directly](https://www.seattle.gov/sdci).

## Optional: SODA App Token

The SODA API works without authentication (~1000 requests/hour). For higher rate limits, register a free app token at [data.seattle.gov developer settings](https://data.seattle.gov/profile/edit/developer_settings) and set:

```bash
export SODA_APP_TOKEN=your-token-here
```

## Author

**Graeme Tobias Ampeire** — MSIS Candidate, UW Foster School of Business (2026)
Seattle-based | Building AI tools on real civic data
