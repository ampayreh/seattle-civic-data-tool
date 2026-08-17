#!/usr/bin/env python3
"""
Seattle Civic Data Tool — Natural Language Query Interface

Translates natural language questions about Seattle building permits
into SODA API queries, executes them against data.seattle.gov, and
produces Claude-analyzed summaries with source citations.

Usage:
    python query_tool.py "How many building permits were issued in 2024?"
    python query_tool.py "What are the most expensive construction projects in Capitol Hill?"
    python query_tool.py --interactive
    python query_tool.py "Show me demolition permits in 98103" --format json

Environment:
    ANTHROPIC_API_KEY  — required
    MODEL_ID           — model to use (default: claude-sonnet-4-20250514)
    SODA_APP_TOKEN     — optional, raises SODA API rate limit
"""

import argparse
import json
import os
import sys
import time
from typing import Any

import anthropic

from soda_client import (
    PERMITS_PORTAL_URL,
    SODA_QUERY_TOOL,
    SodaClient,
    get_schema_description,
)


MODEL_ID = os.environ.get("MODEL_ID", "claude-sonnet-4-20250514")
MAX_TOOL_ROUNDS = 5


SYSTEM_PROMPT = """You are a data analyst for Seattle civic data. You answer questions
about Seattle building permits by querying the City of Seattle's open data portal
(data.seattle.gov) through the SODA API.

{schema}

## Your workflow

1. Read the user's question carefully
2. Use the query_seattle_permits tool to fetch relevant data
   - You may make multiple queries to answer complex questions
   - Start with a focused query; refine if needed
   - Use aggregations (count, sum, avg) for summary questions
   - Use WHERE filters to narrow results
   - Use ORDER BY and LIMIT for "top N" or "most/least" questions
3. Analyze the results and provide a clear, data-backed answer
4. Always cite the data source and include the query URL

## Rules

- ALWAYS query the data — never answer from general knowledge about Seattle
- If a query returns 0 results, say so honestly; do not fabricate data
- Include specific numbers, dates, and permit IDs from the results
- For large result sets, summarize patterns rather than listing every row
- Format currency values with $ and commas
- When referencing specific permits, include the permit number
- End every answer with a "Source:" line linking to the dataset

## SoQL tips

- Column names are all lowercase
- Dates: use ISO format in WHERE, e.g. issueddate > '2024-01-01'
- Strings: LIKE is case-insensitive by default, use % wildcards
- Aggregation: date_trunc_y(issueddate) groups by year
- NULL handling: use IS NULL / IS NOT NULL
- For "recent" queries without a specific date, use the last 12 months
"""


def run_query(
    client: anthropic.Anthropic,
    soda: SodaClient,
    question: str,
) -> dict[str, Any]:
    """Send a question to Claude, let it query SODA, return the analysis."""

    schema_desc = get_schema_description()
    system = SYSTEM_PROMPT.format(schema=schema_desc)

    messages = [{"role": "user", "content": question}]
    tools = [SODA_QUERY_TOOL]

    tool_calls_total = 0
    input_tokens_total = 0
    output_tokens_total = 0
    queries_made = []
    t0 = time.monotonic()

    for round_idx in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        )

        input_tokens_total += response.usage.input_tokens
        output_tokens_total += response.usage.output_tokens

        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_calls_total += 1
                    params = block.input

                    print(
                        f"  Query #{tool_calls_total}: "
                        f"SELECT {params.get('select', '*')[:60]} "
                        f"WHERE {params.get('where', '(none)')[:60]}",
                        flush=True,
                    )

                    result = soda.query(
                        select=params.get("select"),
                        where=params.get("where"),
                        group=params.get("group"),
                        order=params.get("order"),
                        limit=params.get("limit", 100),
                    )

                    queries_made.append({
                        "select": params.get("select"),
                        "where": params.get("where"),
                        "group": params.get("group"),
                        "order": params.get("order"),
                        "limit": params.get("limit", 100),
                        "result_count": result["count"],
                        "query_url": result["query_url"],
                    })

                    # Format result for the model — truncate large payloads
                    result_text = json.dumps(result["rows"][:50], indent=2)
                    if result["count"] > 50:
                        result_text += f"\n\n... ({result['count']} total rows, showing first 50)"

                    if result.get("error"):
                        result_text = f"ERROR: {result['error']}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break
    else:
        print(f"Warning: reached max tool rounds ({MAX_TOOL_ROUNDS})", file=sys.stderr)

    latency_ms = (time.monotonic() - t0) * 1000

    # Extract final text
    answer = "\n".join(
        block.text for block in response.content if block.type == "text"
    )

    cost_usd = input_tokens_total * 3e-6 + output_tokens_total * 15e-6

    return {
        "question": question,
        "answer": answer,
        "queries": queries_made,
        "metrics": {
            "model": MODEL_ID,
            "input_tokens": input_tokens_total,
            "output_tokens": output_tokens_total,
            "tool_calls": tool_calls_total,
            "latency_ms": round(latency_ms),
            "cost_usd": round(cost_usd, 4),
        },
    }


def print_result(result: dict, fmt: str = "markdown"):
    """Print the query result in the requested format."""
    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{result['answer']}")
        m = result["metrics"]
        print(
            f"\n---\n"
            f"*{m['tool_calls']} queries, "
            f"{m['input_tokens']+m['output_tokens']} tokens, "
            f"{m['latency_ms']/1000:.1f}s, "
            f"${m['cost_usd']:.4f}*"
        )


def interactive_mode(client: anthropic.Anthropic, soda: SodaClient, fmt: str):
    """Run an interactive question loop."""
    print("Seattle Civic Data Tool — Interactive Mode")
    print(f"Dataset: Seattle Building Permits ({PERMITS_PORTAL_URL})")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            break

        print("Querying...", flush=True)
        result = run_query(client, soda, question)
        print_result(result, fmt)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Seattle Civic Data Tool — ask questions about "
        "Seattle building permits in natural language"
    )
    parser.add_argument(
        "question", nargs="?", default=None,
        help="Natural language question (omit for --interactive mode)"
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Run in interactive question loop mode"
    )
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)"
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    if not args.question and not args.interactive:
        print("Error: provide a question or use --interactive.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    client = anthropic.Anthropic()
    soda = SodaClient()

    if args.interactive:
        interactive_mode(client, soda, args.format)
    else:
        print(f"Model: {MODEL_ID}")
        print(f"Question: {args.question}")
        print("Querying...\n", flush=True)

        result = run_query(client, soda, args.question)
        print_result(result, args.format)


if __name__ == "__main__":
    main()
