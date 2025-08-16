# Site Mapper

A lightweight Streamlit app to map a website, filter out non-page assets, explore high-level sections, and visualize structure with an interactive treemap. It uses the Firecrawl API to discover URLs and provides an interface to refine, analyze, and export the results.

## Features
- Normalize any input like `www.example.com` or `https://example.com/path` to a valid base URL
- Optionally include subdomains and/or discover via sitemap
- Pages-only mode to exclude assets (images, CSS/JS, docs, media, archives, fonts, binaries)
- Dashboard-style stats: URL count, average depth, max depth, elapsed time, login page detection
- Table of contents (top-level sections) and full URL table with depth
- CSV export of the final URL list
- Interactive treemap visualization of site structure using Plotly

## Requirements
- Python 3.9+ (3.10 or newer recommended)
- A Firecrawl API key

## Quick start (macOS, zsh)

1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Create a `.env` file in the project root and add your API key

```bash
# .env
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
# Optional: override if using a different endpoint
FIRECRAWL_BASE_URL=https://api.firecrawl.dev
```

4) Run the app

```bash
streamlit run app.py
```

Streamlit will open a local URL (e.g., http://localhost:8501). If it does not open automatically, copy the URL from the terminal.

## How it works
- The app calls `POST /v1/map` on the Firecrawl API with your base URL and discovery options
- The response contains discovered links which are then filtered to internal URLs for the host (and optionally subdomains)
- Asset files can be excluded using the Pages-only option
- The resulting URL set is analyzed for depth, grouped by top-level section, and visualized as a treemap

## Environment variables
- `FIRECRAWL_API_KEY` (required): Your Firecrawl API key
- `FIRECRAWL_BASE_URL` (optional): Base URL for the Firecrawl API, defaults to `https://api.firecrawl.dev`

Values are loaded from `.env` via `python-dotenv`.

## Usage
1) Enter a Base URL (with or without scheme). Placeholder suggests: `www.example.com`
2) Configure Discovery options:
   - Include subdomains
   - Use sitemap (enables discovery via sitemaps)
   - Sitemap only (only return URLs from sitemaps)
   - Filter to site pages (no assets)
   - Preserve query/fragment in URLs
3) Click “Map Site”
4) Review results: metrics, table of contents, URLs table, download CSV, and treemap

## Output details
- Metrics
  - URLs: total count after filtering
  - Avg depth: average number of path segments
  - Max depth: maximum number of path segments
  - Elapsed: total time spent mapping
  - Login page detected: basic heuristic search for common login patterns
- Table of contents: counts by top-level path segment
- URLs table: final URL list with depth; downloadable as CSV
- Treemap: hierarchical visualization aggregated by host and path segments

## Customization
- Asset extensions: update `ASSET_EXTS` in `app.py` to tune “pages-only” detection
- Discovery limit: currently set to 10,000 in the sidebar; adjust if needed
- Timeout: HTTP client timeout is 120 seconds inside `call_firecrawl_map`

## Troubleshooting
- “API key is missing in .env”
  - Ensure `.env` contains `FIRECRAWL_API_KEY` and that you restarted the app after editing
- HTTP errors/timeouts
  - Verify the API key is valid and the Firecrawl API is reachable from your network
  - Large sites can take longer; try enabling “Use sitemap” or narrowing scope
- No URLs found
  - Check that the base URL is correct and publicly accessible
  - Try enabling sitemap discovery

## Known limitations
- Depth is based on path segments only and does not account for redirects or canonicalization
- “Login page detected” is a simple heuristic and may produce false positives/negatives
- Mapping very large sites may take time; consider using sitemap-only when available

## Project structure
```
app.py         # Streamlit application
README.md      # This file
requirements.txt
```

## License
Provide your preferred license here (e.g., MIT).