# Architectural Decisions

Non-obvious choices in this codebase, with rationale.

---

## 1. SODA API queries, not local database

**Chosen:** Every question hits the City of Seattle's live SODA API. No data is
downloaded, cached, or committed to this repository.

**Rejected:** Downloading the full dataset as CSV, loading it into SQLite or
DuckDB, and querying locally.

**Why:**

1. **Data freshness.** The Building Permits dataset is updated daily. A local
   copy would be stale immediately and require a sync mechanism. The SODA API
   always returns current data.

2. **No data commitment.** The dataset is 192K+ records and growing. Committing
   it (or a derived database) to the repo would bloat the clone, create a
   versioning problem, and raise questions about whether the committed snapshot
   represents the city's current data.

3. **SoQL translates directly.** The Socrata Query Language (SoQL) is
   SQL-like: SELECT, WHERE, GROUP BY, ORDER BY, aggregate functions, date
   functions. Claude can generate SoQL from natural language with the same
   reliability as SQL, and the SODA API executes it server-side. There is no
   computational advantage to running the query locally for this data volume.

The tradeoff: every query requires network access, and the SODA API has rate
limits (~1000/hr unauthenticated, higher with an app token). For this tool's
usage pattern (a few queries per question, interactive pace), this is not a
constraint.

---

## 2. Natural language to SoQL via tool use, not text-to-SQL

**Chosen:** Claude receives the dataset schema in the system prompt and calls
a `query_seattle_permits` tool with SoQL parameters. The tool executes the
query via the SODA API and returns results for Claude to analyze.

**Rejected:**

- Text-to-SQL with a local SQLite database
- A RAG pipeline with embedded dataset documentation
- A fixed set of canned queries selected by intent classification

**Why:**

1. **SoQL is the native query language.** The SODA API speaks SoQL directly.
   Generating SQL and then translating to SoQL (or maintaining a SQL-compatible
   local copy) adds a translation layer with no benefit.

2. **Tool use gives grounded answers.** Claude generates the query, sees the
   actual results, and answers from those results. This is the retrieve-then-
   generate pattern: the model never answers from general knowledge about
   Seattle construction trends, only from data it just fetched.

3. **Multi-query reasoning.** Complex questions (comparisons, time series,
   drill-downs) often need 2-3 queries. The tool-use loop handles this
   naturally: Claude makes a broad query, sees the results, decides it needs
   a more specific follow-up, and makes another tool call. A canned-query
   approach cannot do this.

---

## 3. Building Permits as the single dataset

**Chosen:** The tool queries one dataset (Building Permits, ID `76t5-zqzr`)
rather than exposing multiple datasets from data.seattle.gov.

**Rejected:** A multi-dataset tool that queries 911 calls, code violations,
business licenses, etc.

**Why:**

1. **Schema specificity.** The system prompt includes the full column schema
   with descriptions so Claude can write accurate queries. Adding more datasets
   would either require a very long schema section (competing for context
   window space with the user's question and query results) or a dataset
   selection step that adds latency and failure modes.

2. **Depth over breadth.** The Building Permits dataset is rich: 40 columns
   covering cost, timing, location, zoning, contractor, housing units, and
   review cycles. A single dataset explored deeply (time series trends,
   geographic analysis, contractor comparison, review efficiency) demonstrates
   more analytical capability than shallow queries across five datasets.

3. **Extensibility is straightforward.** Adding a second dataset requires: (a)
   a new schema description, (b) a new tool definition or a dataset_id parameter
   on the existing tool, (c) a system prompt update. The architecture supports
   this without restructuring.

---

## 4. No data committed to the repository

**Chosen:** The repository contains zero rows of Seattle permit data. All data
comes from the live API at query time.

**Rejected:** Committing sample output, cached results, or a data snapshot.

**Why:**

1. **License compliance.** The dataset is Public Domain, so redistribution is
   legal. But committing a snapshot creates a version-of-record problem: the
   committed data becomes stale, and anyone reading the repo might treat it as
   authoritative when it is not.

2. **Reproducibility.** The `examples/sample-queries.md` file describes example
   questions and the SoQL they generate, but does not include results. Anyone
   running the tool gets current data from the live API. This is intentional:
   the tool's value is in producing fresh analysis, not in replaying a cached
   answer.

3. **Repo size.** 192K rows x 40 columns is ~150MB as JSON. Even a subset
   would add non-trivial weight to the repo for no functional benefit.
