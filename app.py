import os
import re
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from collections import Counter

# Load env
load_dotenv()
API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()
BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev").rstrip("/")

ASSET_EXTS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".css", ".js", ".map",
    ".json", ".xml", ".rss", ".atom",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".gz", ".tar", ".tgz", ".rar", ".7z",
    ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4", ".mov", ".avi",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".dmg", ".exe", ".bin", ".apk",
)

# App chrome
st.set_page_config(page_title="Site Mapper", layout="wide")
st.title("Site Mapper")
st.caption("Map a site, optionally filter to pages-only, view dashboard stats, and render a hierarchical treemap.")

if not API_KEY:
    st.error("API key is missing in .env (FIRECRAWL_API_KEY)")

@st.cache_data(show_spinner=False)
def call_firecrawl_map(url: str, include_subdomains: bool, limit: int, use_sitemap: bool, sitemap_only: bool) -> dict:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "url": url,
        "includeSubdomains": include_subdomains,
        # Toggle sitemap discovery via UI
        "ignoreSitemap": not bool(use_sitemap),
        "sitemapOnly": bool(use_sitemap and sitemap_only),
        "limit": limit,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{BASE_URL}/v1/map", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def _normalize_path(path: str) -> str:
    path = re.sub(r"/+", "/", path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return path


def normalize_input_url(raw: str) -> str:
    """Normalize user input like 'york.com' or 'york.com/home' to a full https URL.
    Raises ValueError if it cannot be parsed into a valid host.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Please enter a domain or URL, e.g. example.com or https://example.com/path")
    # Prepend scheme if missing
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        s = "https://" + s.lstrip("/")
    pu = urlsplit(s)
    # Handle cases like 'https://york.com/home' or 'https://york.com'
    if not pu.netloc:
        raise ValueError("Invalid domain/URL. Try like example.com or https://example.com/path")
    path = _normalize_path(pu.path)
    return urlunsplit((pu.scheme.lower(), pu.netloc.lower(), path, "", ""))


# Updated: removed section filters parameter

def normalize_pages_only(urls: list[str], base_host: str, include_subdomains: bool, preserve_qf: bool) -> list[str]:
    out = []
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        pu = urlsplit(u)
        if pu.scheme not in ("http", "https"):
            continue
        host = pu.netloc.lower()
        # host filter
        if not (host == base_host or (include_subdomains and host.endswith("." + base_host))):
            continue
        path = _normalize_path(pu.path)
        lower = path.lower()
        # assets/pages-only rule
        if any(lower.endswith(ext) for ext in ASSET_EXTS):
            continue
        if "." in lower and not lower.endswith((".html", ".htm", ".php")):
            continue
        query = pu.query if preserve_qf else ""
        frag = pu.fragment if preserve_qf else ""
        out.append(urlunsplit((pu.scheme, host, path, query, frag)))
    return sorted(set(out))


# Updated: removed `filters` param and section filtering

def normalize_internal_all(urls: list[str], base_host: str, include_subdomains: bool, preserve_qf: bool) -> list[str]:
    out = []
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        pu = urlsplit(u)
        if pu.scheme not in ("http", "https"):
            continue
        host = pu.netloc.lower()
        # host filter
        if not (host == base_host or (include_subdomains and host.endswith("." + base_host))):
            continue
        path = _normalize_path(pu.path)
        query = pu.query if preserve_qf else ""
        frag = pu.fragment if preserve_qf else ""
        out.append(urlunsplit((pu.scheme, host, path, query, frag)))
    return sorted(set(out))


def compute_depth(url: str) -> int:
    path = urlsplit(url).path or "/"
    segs = [s for s in path.split("/") if s]
    return len(segs)


def looks_like_login(url: str) -> bool:
    p = urlsplit(url)
    s = (p.path + "?" + (p.query or "")).lower()
    tokens = [
        "login", "sign-in", "signin", "wp-login", "user/login", "users/login",
        "account/login", "my-account", "auth", "session/new", "wp-admin", "/admin/login",
    ]
    return any(t in s for t in tokens)


def render_treemap_go_from_urls(urls: list[str], levels: int):
    # Build unique node ids with aggregated counts so parent == sum(children)
    levels = max(2, int(levels))
    counts: Counter[tuple[str, ...]] = Counter()

    # Track a representative URL for each node, and detect whether a leaf maps to exactly one URL
    example_url: dict[tuple[str, ...], str] = {}
    leaf_first_url: dict[tuple[str, ...], str] = {}
    leaf_multi: set[tuple[str, ...]] = set()

    for u in urls:
        pu = urlsplit(u)
        host = pu.netloc or "/"
        parts = [s for s in (pu.path or "/").split("/") if s]
        chain = [host] + parts
        k = min(levels, len(chain))
        for i in range(k):
            node = tuple(chain[: i + 1])
            counts[node] += 1
            # store a representative URL for this node
            if node not in example_url:
                example_url[node] = u
        # leaf node at current level depth
        leaf_node = tuple(chain[:k])
        if leaf_node in leaf_first_url:
            leaf_multi.add(leaf_node)
        else:
            leaf_first_url[leaf_node] = u

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[int] = []
    customdata: list[str] = []

    nodes_sorted = sorted(counts.keys(), key=lambda t: (len(t), t))
    id_map: dict[tuple[str, ...], str] = {node: "|" + "|".join(node) for node in nodes_sorted}

    def node_prefix_url(node: tuple[str, ...]) -> str:
        ex = example_url.get(node)
        scheme = urlsplit(ex).scheme if ex else "https"
        host = node[0] if node else ""
        path = "/" + "/".join(node[1:]) if len(node) > 1 else "/"
        return f"{scheme}://{host}{path}"

    for node in nodes_sorted:
        nid = id_map[node]
        parent = "" if len(node) == 1 else id_map[node[:-1]]
        label = node[-1] if node[-1] else "/"
        ids.append(nid)
        labels.append(label)
        parents.append(parent)
        values.append(int(counts[node]))
        # Build hover text
        if node in leaf_first_url and node not in leaf_multi:
            hover = leaf_first_url[node]
        else:
            hover = f"{counts[node]} URLs under {node_prefix_url(node)}"
        customdata.append(hover)

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            customdata=customdata,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=700)
    st.plotly_chart(fig, use_container_width=True)


# Sidebar (minimal controls)
with st.sidebar:
    base_url = st.text_input(
        "Base URL",
        value="",
        placeholder="www.example.com",
        help="Enter a domain or URL. Scheme is optional; we'll assume https.",
    )
    # Discovery options
    with st.expander("Discovery options", expanded=False):
        include_subdomains = st.checkbox("Include subdomains", value=False)
        use_sitemap = st.checkbox("Use sitemap", value=False, help="Allow sitemap discovery for broader coverage.")
        sitemap_only = st.checkbox("Sitemap only", value=False, disabled=not use_sitemap, help="Only return URLs from sitemaps.")
        pages_only = st.checkbox("Filter to site pages (no assets)", value=True)
        preserve_qf = st.checkbox("Preserve query/fragment in URLs", value=False)
        # Fixed limit to a generous default
        limit = 10000
    # Filter options removed

# Helper: top-level section for TOC

def first_section(url: str) -> str:
    path = urlsplit(url).path or "/"
    segs = [s for s in path.split("/") if s]
    return segs[0] if segs else "/"


def build_toc_df(urls: list[str]) -> pd.DataFrame:
    if not urls:
        return pd.DataFrame(columns=["section", "count"])
    sections = [first_section(u) for u in urls]
    s = pd.Series(sections).value_counts().reset_index()
    s.columns = ["section", "count"]
    return s

col1, _ = st.columns([1, 3])
with col1:
    run = st.button("Map Site", type="primary")

state = st.session_state
if "urls" not in state:
    state.urls = []
    state.host = ""
    state.stats = {}

if run:
    if not base_url.strip():
        st.warning("Enter a base URL")
    elif not API_KEY:
        st.error("API key missing in .env")
    else:
        try:
            normalized_url = normalize_input_url(base_url)
            host = urlsplit(normalized_url).netloc.lower()
            t0 = time.time()
            data = call_firecrawl_map(normalized_url, include_subdomains, int(limit), use_sitemap, sitemap_only)
            elapsed = time.time() - t0
            links = data.get("links") or data.get("data") or []

            # Updated: no section filters
            if pages_only:
                urls = normalize_pages_only(links, host, include_subdomains, preserve_qf)
            else:
                urls = normalize_internal_all(links, host, include_subdomains, preserve_qf)

            depths = [compute_depth(u) for u in urls]
            n_pages = len(urls)
            avg_depth = float(pd.Series(depths).mean()) if n_pages else 0.0
            max_depth = int(pd.Series(depths).max()) if n_pages else 0
            login_found = any(looks_like_login(u) for u in urls)

            state.urls = urls
            state.host = host
            state.stats = {
                "count": n_pages,
                "avg_depth": avg_depth,
                "max_depth": max_depth,
                "elapsed": elapsed,
                "login": "Yes" if login_found else "No",
                "pages_only": pages_only,
            }

            # Dashboard-like stats
            st.success("Mapping complete")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("URLs", f"{n_pages}")
            m2.metric("Avg depth", f"{avg_depth:.2f}")
            m3.metric("Max depth", f"{max_depth}")
            m4.metric("Elapsed", f"{elapsed:.2f}s")
            m5.metric("Login page detected", state.stats["login"]) 

            # Table of contents (top-level sections)
            st.subheader("Table of contents")
            toc_df = build_toc_df(urls)
            st.dataframe(toc_df, use_container_width=True, height=260)

            # URL table
            st.subheader("URLs")
            st.dataframe(pd.DataFrame({"url": urls, "depth": depths}), use_container_width=True, height=420)
            st.download_button("Download CSV", pd.DataFrame({"url": urls}).to_csv(index=False), file_name="siteurls.csv", mime="text/csv")

            # Treemap (deepest possible)
            max_segments = 1
            for u in urls:
                max_segments = max(max_segments, 1 + compute_depth(u))
            st.subheader("Treemap")
            render_treemap_go_from_urls(urls, max_segments)
        except ValueError as ve:
            st.error(str(ve))
        except Exception as e:
            st.exception(e)
