#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pypdf"]
# ///
"""選定論文の PDF を取得し、全文テキストを書き出す。

要点の構造化（analysis.md）は LLM（paper-analyzer）が SKILL.md の規約に従って行う。
本スクリプトは PDF→素テキストの機械的処理に専念する。
"""

import argparse
import json
import os
import sys
import time
import urllib.request


def load_selected(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("selected") is False:
        raise SystemExit(f"選定不能のため解析対象がありません: {data.get('reason', '理由不明')}")
    pdf_url = data.get("pdf_url")
    arxiv_id = data.get("arxiv_id")
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    if not pdf_url:
        raise SystemExit("selected.json に pdf_url も arxiv_id もありません")
    return pdf_url, arxiv_id


def download_pdf(url: str, dest: str, retries: int = 3, backoff: float = 3.0):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-lens/pdf-extract"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(dest, "wb") as f:
                    f.write(resp.read())
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise SystemExit(f"PDF のダウンロードに失敗しました ({url}): {last_err}")


def extract_text(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf が未導入です。`python3 -m pip install pypdf` を実行してください。")

    reader = PdfReader(pdf_path)
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"--- page {i} ---\n{text}")
    return "\n\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="選定論文の PDF を取得しテキスト化する")
    parser.add_argument("--selected", required=True, help="selected.json のパス")
    parser.add_argument("--out", required=True, help="全文テキストの出力先パス")
    args = parser.parse_args(argv)

    pdf_url, arxiv_id = load_selected(args.selected)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tmp_pdf = args.out + ".pdf"
    download_pdf(pdf_url, tmp_pdf)

    text = extract_text(tmp_pdf)
    if not text.strip():
        raise SystemExit("PDF からテキストを抽出できませんでした（スキャン画像 PDF の可能性）。")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)

    try:
        os.remove(tmp_pdf)
    except OSError:
        pass

    print(f"テキスト抽出完了 ({arxiv_id or pdf_url}) -> {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
