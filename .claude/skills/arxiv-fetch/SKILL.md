---
name: arxiv-fetch
description: arXiv を検索して候補論文のメタデータ群を取得する手法と、候補メタデータの構造・arXiv 識別子・新着判定・未解説判定の扱いを内包する How スキル。論文収集（paper-fetcher）と論文選定（paper-selector）の両工程から名指しで呼び出される。検索条件の既定値もここに集約する。
disable-model-invocation: true
---

# arxiv-fetch — arXiv 検索・候補メタデータ取得

arXiv API から候補論文のメタデータを取得し、後続工程が機械的に扱える形式で保存する手法を定義する。論文の収集（検索→保存）と選定（新着・未解説判定）の両方が依拠する共通リファレンス。

## このスキルが規定すること

1. arXiv API の叩き方（`scripts/fetch_arxiv.py`）
2. 検索条件の既定値
3. 候補メタデータの保存フォーマット（後続工程の機械可読インターフェース）
4. arXiv 識別子・新着判定・未解説判定の扱い

## 実行環境

- ランタイム: Python 3.9+
- 実行は `uv run`（プロジェクト共通の実行方法に揃える）。依存ライブラリはなく（標準ライブラリ `urllib` / `xml.etree.ElementTree` のみで arXiv Atom API を扱う）、スクリプト先頭の PEP 723 ブロックで `dependencies = []` を宣言している。メイン環境を汚さない。

## 検索条件の既定値

`/write-article` の引数で検索条件が明示されない場合は以下を既定値とする。

- カテゴリ: `cs.AI`, `cs.LG`, `cs.CL`（AI・機械学習・自然言語処理）
- 取得件数: 30 件
- 並び順: 投稿日時の新しい順（`submittedDate` 降順）

明示された場合はそれを優先する。カテゴリ・件数は `scripts/fetch_arxiv.py` の引数で上書きできる。

## 候補メタデータの保存フォーマット（機械可読インターフェース）

`scripts/fetch_arxiv.py` は出力先ディレクトリ（`work/<run-id>/papers/`）配下に次を生成する。後続の選定工程はこのフォーマットを唯一の前提として読む。

- `papers/<arxiv_id>.json` — 論文 1 本ごとのメタデータ。フィールド:
  - `arxiv_id`: バージョンを除いた arXiv 識別子（例 `2401.12345`）
  - `version`: 取得時点の最新バージョン（例 `v2`）
  - `title`: タイトル（改行・連続空白は単一スペースに正規化済み）
  - `authors`: 著者名の配列
  - `summary`: アブストラクト
  - `categories`: arXiv カテゴリの配列（先頭が primary）
  - `published`: 初版投稿日時（ISO8601）
  - `updated`: 最終更新日時（ISO8601）
  - `abs_url`: 論文ページ URL（例 `https://arxiv.org/abs/2401.12345`）
  - `pdf_url`: PDF の URL（例 `https://arxiv.org/pdf/2401.12345`）
- `papers/index.json` — 候補一覧。`arxiv_id` / `title` / `published` / `updated` を持つオブジェクトの配列を、`published` 降順で並べたもの。選定工程はまずこれを読んで候補全体を把握する。

## arXiv 識別子・新着判定・未解説判定の扱い

- **識別子の正規化**: arXiv の Atom `id` は `http://arxiv.org/abs/2401.12345v2` 形式で末尾にバージョンが付く。`arxiv_id` はバージョンを除いた `2401.12345` を正準キーとして扱う。同一論文の同定・重複排除はこの `arxiv_id` で行う。
- **新着判定**: 新しさは `published`（初版投稿日時）の降順で評価する。`index.json` は既にこの順で並んでいるため、選定では先頭に近いものほど新しい。
- **未解説判定**: ある `arxiv_id` が既に解説済みかは、`output/` 配下の公開記事に当該 `arxiv_id` が含まれるかで判断する。公開記事は frontmatter に `arxiv_id` を持つ（`japanese-tech-writing` の記事フォーマット規約）。`output/` 内の記事 frontmatter の `arxiv_id` 集合に含まれる候補は「解説済み」とみなして選定対象から除外する。

## 使い方

### 収集（候補メタデータ取得）

出力先ディレクトリを指定して実行する。`<categories>` / `<max-results>` は省略時に上記既定値を用いる。

```bash
uv run .claude/skills/arxiv-fetch/scripts/fetch_arxiv.py \
  --out-dir "work/<run-id>/papers" \
  [--categories cs.AI,cs.LG,cs.CL] \
  [--max-results 30]
```

実行後、`papers/index.json` と `papers/<arxiv_id>.json` 群が生成される。生成先ディレクトリの絶対パスを収集結果として扱う。

### 選定（新着・未解説の 1 本選び）

選定工程はスクリプトを再実行せず、既に保存された `papers/index.json` と `papers/<arxiv_id>.json` を読み、`output/` の既存記事 frontmatter（`arxiv_id`）と突き合わせて、未解説かつ最も新しい 1 本を選ぶ。選定結果は `selected.json` として、対象論文の `<arxiv_id>.json` の全フィールドをそのまま写し取って書き出す（後続の解析工程が `pdf_url` / `arxiv_id` / `title` を参照するため）。候補が空・全件解説済みで選定不能な場合は `{"selected": false, "reason": "<理由>"}` を書き出す。
