#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""arXiv API から候補論文のメタデータ群を取得し、機械可読な JSON 群として保存する。

標準ライブラリのみで動作する（urllib + xml.etree）。出力フォーマットは
SKILL.md「候補メタデータの保存フォーマット」を唯一の契約とする。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"

DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
DEFAULT_MAX_RESULTS = 30


def _norm_ws(text: str) -> str:
    """改行・連続空白を単一スペースに正規化する。"""
    return re.sub(r"\s+", " ", (text or "").strip())


def _split_id_version(raw_id: str):
    """Atom id (http://arxiv.org/abs/2401.12345v2) を (arxiv_id, version) に分解する。"""
    tail = raw_id.rstrip("/").split("/")[-1]
    m = re.match(r"^(.*?)(v\d+)?$", tail)
    if not m:
        return tail, ""
    return m.group(1), (m.group(2) or "")


def build_query_url(categories, max_results):
    cat_query = "+OR+".join(f"cat:{c}" for c in categories)
    params = (
        f"search_query={cat_query}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&start=0&max_results={int(max_results)}"
    )
    # search_query 内の + はクエリ演算子なので urlencode せずそのまま使う。
    return f"{ARXIV_API}?{params}"


def fetch(url: str, retries: int = 3, backoff: float = 3.0) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-lens/arxiv-fetch"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"arXiv API への問い合わせに失敗しました: {last_err}")


def parse_entries(xml_text: str):
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = (entry.findtext(f"{ATOM}id") or "").strip()
        arxiv_id, version = _split_id_version(raw_id)

        categories = [
            c.attrib.get("term", "")
            for c in entry.findall(f"{ATOM}category")
            if c.attrib.get("term")
        ]
        # primary_category があれば先頭に寄せる
        primary = entry.find("{http://arxiv.org/schemas/atom}primary_category")
        if primary is not None:
            term = primary.attrib.get("term")
            if term and term in categories:
                categories.remove(term)
                categories.insert(0, term)

        authors = [
            _norm_ws(a.findtext(f"{ATOM}name") or "")
            for a in entry.findall(f"{ATOM}author")
        ]
        authors = [a for a in authors if a]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        for link in entry.findall(f"{ATOM}link"):
            if link.attrib.get("title") == "pdf" and link.attrib.get("href"):
                pdf_url = link.attrib["href"]

        papers.append({
            "arxiv_id": arxiv_id,
            "version": version,
            "title": _norm_ws(entry.findtext(f"{ATOM}title") or ""),
            "authors": authors,
            "summary": _norm_ws(entry.findtext(f"{ATOM}summary") or ""),
            "categories": categories,
            "published": (entry.findtext(f"{ATOM}published") or "").strip(),
            "updated": (entry.findtext(f"{ATOM}updated") or "").strip(),
            "abs_url": abs_url,
            "pdf_url": pdf_url,
        })
    return papers


def main(argv=None):
    parser = argparse.ArgumentParser(description="arXiv から候補論文メタデータを取得する")
    parser.add_argument("--out-dir", required=True, help="出力先ディレクトリ（例 work/<run-id>/papers）")
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES),
                        help="カンマ区切りの arXiv カテゴリ（既定: cs.AI,cs.LG,cs.CL）")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS,
                        help="取得件数（既定: 30）")
    args = parser.parse_args(argv)

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if not categories:
        categories = DEFAULT_CATEGORIES

    url = build_query_url(categories, args.max_results)
    xml_text = fetch(url)
    papers = parse_entries(xml_text)

    os.makedirs(args.out_dir, exist_ok=True)
    index = []
    for p in papers:
        if not p["arxiv_id"]:
            continue
        with open(os.path.join(args.out_dir, f"{p['arxiv_id']}.json"), "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        index.append({
            "arxiv_id": p["arxiv_id"],
            "title": p["title"],
            "published": p["published"],
            "updated": p["updated"],
        })

    index.sort(key=lambda x: x["published"], reverse=True)
    with open(os.path.join(args.out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"取得 {len(index)} 件 -> {os.path.abspath(args.out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
