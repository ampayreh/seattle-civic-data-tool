# Sample Queries

Example questions you can ask the Seattle Civic Data Tool, with descriptions of what they exercise in the SODA API.

## Basic Lookups

**"How many building permits were issued in 2024?"**
- Exercises: `count(*)`, date filtering with `issueddate`
- SoQL: `SELECT count(*) WHERE issueddate >= '2024-01-01' AND issueddate < '2025-01-01'`

**"Show me the 10 most expensive construction projects permitted this year"**
- Exercises: `ORDER BY DESC`, `LIMIT`, date filtering
- SoQL: `SELECT permitnum, description, estprojectcost, originaladdress1, issueddate WHERE issueddate >= '2025-01-01' ORDER BY estprojectcost DESC LIMIT 10`

## Aggregations

**"What's the average project cost by permit class?"**
- Exercises: `avg()`, `GROUP BY`
- SoQL: `SELECT permitclass, count(*) as cnt, avg(estprojectcost) as avg_cost GROUP BY permitclass ORDER BY avg_cost DESC`

**"How has the number of permits issued per year changed since 2018?"**
- Exercises: `date_trunc_y()`, time series aggregation
- SoQL: `SELECT date_trunc_y(issueddate) as year, count(*) as cnt WHERE issueddate >= '2018-01-01' GROUP BY year ORDER BY year`

## Filtering

**"Show me all solar panel installations in the last two years"**
- Exercises: `LIKE` text search, date filtering
- SoQL: `SELECT permitnum, description, estprojectcost, originaladdress1 WHERE description LIKE '%solar%' AND issueddate >= '2023-01-01' ORDER BY issueddate DESC`

**"What demolition permits have been issued in ZIP code 98103?"**
- Exercises: multi-condition WHERE, text matching
- SoQL: `SELECT permitnum, description, estprojectcost, originaladdress1, issueddate WHERE permittypedesc = 'Demolition' AND originalzip = '98103' ORDER BY issueddate DESC`

## Analysis Questions

**"Which ZIP codes have the most construction activity?"**
- Exercises: aggregation, ranking
- SoQL: `SELECT originalzip, count(*) as cnt, sum(estprojectcost) as total_cost GROUP BY originalzip ORDER BY cnt DESC LIMIT 20`

**"What's the average plan review time for commercial vs residential permits?"**
- Exercises: conditional aggregation, GROUP BY
- SoQL: `SELECT permitclass, avg(totaldaysplanreview) as avg_review_days, count(*) as cnt GROUP BY permitclass`

**"How many housing units have been added in Seattle each year since 2015?"**
- Exercises: `sum()`, time series, housing-specific columns
- SoQL: `SELECT date_trunc_y(issueddate) as year, sum(housingunitsadded) as units_added WHERE issueddate >= '2015-01-01' AND housingunitsadded > 0 GROUP BY year ORDER BY year`

## Multi-Query Questions

**"Compare the construction boom in Ballard vs Capitol Hill — which neighborhood has more permits and higher total investment?"**
- This requires multiple queries (one per ZIP or address pattern) and synthesis
- The tool will make 2-3 SODA queries and combine the results

**"What percentage of commercial permits get completed within a year of being issued?"**
- Requires querying both issued and completed permits with date math
