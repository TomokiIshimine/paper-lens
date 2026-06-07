---
name: write-article
description: arXiv から新着論文を取得し、未解説の 1 本を選定して日本語解説記事を全自動で生成・検証・公開するワークフロー。論文解説記事を量産・自動生成したいとき、スケジュール実行やコンテキストに応じた自走発火で arXiv の新着を記事化したいときに使う。人間の承認ゲートを持たず、ファクトチェック・レビューの収束までメインが自走させる。
argument-hint: [検索条件（任意。カテゴリ・件数等。省略時はスキル内既定値）]
---

# write-article — arXiv 論文解説記事の全自動生成ワークフロー

## 目的

arXiv から新着論文を取得し、未解説の 1 本を選定して日本語解説記事を全自動で生成・検証・公開する。人間の承認ゲートなしで、メインが全 10 ステップをオーケストレーションする。

ステップ構成は次の 2 段構え（各ステップの詳細は `## 実行手順` を真実源とし、ここでは全体像のみ示す）。

- Step 1〜4: 取得 → 選定 → 解析 → 執筆で記事ドラフトを作る。
- Step 5: 記事本文の観点別レビューループ。
- Step 6: インフォグラフィック生成＋画像の観点別レビューループ。
- Step 7: 出力＋ドキュメント更新で `output/<記事>.md`（Markdown・dedup 照合キー）を確定する。
- Step 8〜10: 確定 Markdown を入力に、HTML 執筆 → HTML レビューループ → GitHub Pages 公開（commit→push）でリッチ HTML 記事ページを `main` ブランチへ全自動公開する。

記事本文（Step 5）・インフォグラフィック（Step 6）・HTML（Step 9）はいずれも「観点別レビュー → FAIL 再生成 → 全観点 PASS まで反復」の品質保証ゲートを備える（観点リスト・反復上限は各 Step 見出しに記載）。

## 実行前提

- **起動方法とトリガー条件**: `/write-article [検索条件]` の明示起動に加え、Claude Code の自主判断による自動発火を許容する。スケジュール実行や「arXiv の新着論文を記事化したい」という文脈で発火する。引数（検索条件）は任意で、省略時は取得サブエージェント側スキルの既定値を用いる。
- **`disable-model-invocation`**: 未指定（frontmatter にキーを置かない＝自動呼び出しを許可する）。
  - 選択理由: 全自動運用・Claude Code の自主判断発火という中核要件を満たすため、明示呼び出し専用にしない。kit 標準は明示呼び出し専用（`disable-model-invocation: true`）だが、本ワークフローは自主発火要件のため強制しない。
- **承認ゲートなし（全自動）**: 本ワークフローは全自動要件のため `AskUserQuestion` を一切発火しない。検証ループも人間介在なしでメインが収束させる。緩和策として fact-check 観点を必須レビュー観点に含め、`output/` への公開は合格時のみとする。

## 共通契約への準拠

- メイン側の作法は `/workflow-orchestration` の契約に従う。横断的なメインの作法（限定 Read 契約・絶対パス引き回し・サブエージェント実行モード・戻り値形式・整合チェック失敗時の中断ポリシー・メインがしないこと）は本スキルでは **再掲しない**。
- 観点別並列レビュー → FAIL ファイル再生成 → 合格まで反復（**Step 5 の記事本文検証ループ・Step 6 のインフォグラフィック検証ループの両方**）の契約は `/multi-aspect-review` に従う。観点別レビュアー／再生成 author／オーケストレーターの 3 役の責務・PASS/FAIL ループ手順は本スキルでは **再掲しない**。
- インフォグラフィックの設計・品質基準・画像内テキストの根拠規約・スタイル統一仕様・各観点（`image-fact` / `image-coverage` / `image-legibility` / `image-consistency`）の判定基準は `/infographic-design`（How スキル）を単一の真実源とする。Step 6 の生成側（`article-image-generator`）・レビュー側（`image-reviewer`）が同一基準を共有し、本スキルでは判定基準を **再掲しない**。
- HTML デザイン・レイアウト・コンポーネント・共有外部 CSS（`docs/assets/style.css`）・記事一覧トップ `index.html` 規約・公開元ディレクトリ規約・公開手順（add→commit→push・`origin main` 固定・force 禁止）・HTML レビューの観点別判定基準（`design-consistency` / `readability` / `infographic-richness`）は `/html-page-design`（How スキル）を単一の真実源とする。Step 8〜10 の生成側（`article-html-author`）・レビュー側（`html-reviewer`）が同一基準を共有し、本スキルでは判定基準・CSS 実体・公開手順を **再掲しない**（`/infographic-design` の記述と同型）。Step 9 の HTML レビューループ自体は `/multi-aspect-review` 契約に従う（Step 5/6 と同一参照）。
- 本ワークフローは設計サイクル（draft → ユーザー承認 → apply → revise）および承認ゲートを **持たない** ため、`/proposal-design-cycle` は参照しない。
- 以下の各セクションでは、本ワークフロー固有の差分（自スキル内での `<run-id>` 採番・限定 Read 契約の固定見出しテーブル・反復制御の差分など）のみを列挙する。

### 検証ループ共通の再生成規約（Step 5 / Step 6b / Step 9 で共有）

3 つの検証ループ（記事本文・インフォグラフィック・HTML）の再生成フローは、いずれも `/multi-aspect-review` のオーケストレーター契約に従い、以下を共通規約とする。各 Step ではこれを再掲せず、Step 固有の差分（観点リスト・宣言順・対象ファイル・反復上限・引数の実値）だけを書く。

- 全観点 PASS なら次 Step へ進み、1 つでも FAIL があれば再生成へ回す。
- `review-report-path` は **単数の絶対パス 1 本** を渡す（改行区切りの複数渡しをしない）。観点別レポート 1 本につき該当 author 1 起動。
- 渡すレポートの選定: その author の担当ファイルを FAIL 指摘した観点の今 iteration レポート群を候補とし、複数候補がある場合は当該 Step の `<…-review-aspects>` 宣言順で **最初に現れた観点のレポート 1 本だけ** を選ぶ。
- 再生成後は `<iteration>` を進めて並列レビューに戻る。
- 反復上限到達時は `/multi-aspect-review` 標準のユーザー警告＋手動修正委譲を採らず、**最終周回レポートをログに残してパイプラインを打ち切る（自動リトライなし）**。打ち切り時は `output/` への公開・push を行わない（合格時のみ公開）。反復上限は Step ごとに `## 実行手順` で指定する。

### 限定 Read 契約の固定見出しテーブル

メインがサブの生成物から Read してよいのは、本テーブルに列挙した見出しのみ。本文全読は禁止。

| 用途 | 対象ファイル | 抜粋する見出し |
|---|---|---|
| Step 5 レビュー結果の集約（PASS/FAIL は戻り値で取得済み、判定根拠の確認時のみ） | `work/<run-id>/review-<iteration>_<aspect>.md` | `## 判定` |
| Step 6 画像レビュー結果の判定根拠確認（PASS/FAIL は戻り値で取得済み、判定根拠の確認時のみ） | `work/<run-id>/image-review-<iteration>_<aspect>.md` | `## 判定` |
| Step 9 HTML レビュー結果の判定根拠確認（PASS/FAIL は戻り値で取得済み、判定根拠の確認時のみ） | `work/<run-id>/html-review-<iteration>_<aspect>.md` | `## 判定` |
| 公開記事のタイトル等メタ確認（ユーザー報告用） | `output/<記事ファイル>` | `# `（記事タイトル行） |

レビュー判定（PASS/FAIL）の取得は観点別レビュアーの戻り値で完結する（`/multi-aspect-review` 契約）。レポート本文の全読はしない。

公開 URL（ユーザー報告用）は Step 10 の `article-html-author` 戻り値で取得するため、公開 URL のために新規ファイルを Read しない（テーブルへの行追加は不要）。

## 実行手順

`<run-id>` は本スキル起動時に起動時刻ベースの一意 ID として 1 度採番し、以降のステップ全体で固定値として保持する。各ステップ間で受け渡す絶対パスは `<…>` 記法で内部保持する。

### Step 1 取得（paper-fetcher）

- 起動: `paper-fetcher`
- 引数: 検索条件（`/write-article` の引数。省略時はスキル内既定値）、out=`work/<run-id>/papers/`
- 戻り値: `work/<run-id>/papers/`（候補メタデータ群のディレクトリ絶対パス）

### Step 2 選定（paper-selector）

- 起動: `paper-selector`
- 引数: `work/<run-id>/papers/`、`output/`（既存記事履歴）、out=`work/<run-id>/selected.json`
- 戻り値: `work/<run-id>/selected.json`（選定論文 1 本の絶対パス）

### Step 3 解析（paper-analyzer）

- 起動: `paper-analyzer`
- 引数: `work/<run-id>/selected.json`、out=`work/<run-id>/analysis.md`
- 戻り値: `work/<run-id>/analysis.md`（解析結果・要点の絶対パス）

### Step 4 執筆（article-writer）

- 起動: `article-writer`
- 引数: `work/<run-id>/analysis.md`、out=`work/<run-id>/article.md`
- 戻り値: `work/<run-id>/article.md`（記事ドラフトの絶対パス）

### Step 5 検証ループ（article-reviewer × 観点数 / article-writer 再生成）

`/multi-aspect-review` 契約と「検証ループ共通の再生成規約」に従う。本 Step 固有の差分は以下。

- **観点リスト**: `<review-aspects>` = `fact-check` / `readability` / `structure` の 3 観点（`fact-check` を必須観点として含む）。**宣言順** = `fact-check` → `readability` → `structure`。
- **対象ファイル**（author の担当ファイル）: `work/<run-id>/article.md`（再生成 author = `article-writer`）。
- **反復上限**: 5 周。
- **並列レビュー**: 各観点について `article-reviewer` を単一メッセージ内で並列 spawn する。
  - 引数: review-aspect=`<aspect>`、`work/<run-id>/article.md`、`work/<run-id>/analysis.md`、out=`work/<run-id>/review-<iteration>_<aspect>.md`、（2 周目以降）previous-review-path=`work/<run-id>/review-<前 iteration>_<aspect>.md`
  - 戻り値: `<レポート絶対パス> PASS|FAIL`
- **再生成**（`article-writer` を再生成モードで起動）の引数: review-report-path=選定した 1 本の絶対パス（`work/<run-id>/review-<iteration>_<選定観点>.md`）、regeneration-log-path=`work/<run-id>/regeneration-<iteration>.log`。戻り値: `work/<run-id>/article.md`（再生成され上書きされた絶対パス）。
- 全観点 PASS で Step 6 へ進む。

### Step 6 インフォグラフィック生成＋検証ループ（article-image-generator / image-reviewer × 観点数）

Step 5 の検証ループが全観点 PASS で収束し本文が確定した直後に起動する。確定本文から記事の主題・キーポイントを抽出してインフォグラフィック 1 枚を生成し（6a）、記事本文と同等の観点別レビューループで品質を保証する（6b）。本ステップの画像設計・品質基準・画像内テキストの根拠規約・スタイル統一仕様・各観点の判定基準は `/infographic-design`（How スキル）を単一の真実源として参照する（生成側・レビュー側が同一基準を共有）。

#### Step 6a 初回生成

- 起動: `article-image-generator`（通常起動）
- 引数: 確定 `work/<run-id>/article.md`、out=`work/<run-id>/images/cover.png`、（任意）image-design-log=`work/<run-id>/image-design.log`
- 戻り値: `work/<run-id>/images/cover.png`（生成・保存したインフォグラフィック PNG の絶対パス。未生成時は中断レポート）

#### Step 6b 検証ループ（image-reviewer × 観点数 / article-image-generator 再生成）

`/multi-aspect-review` 契約と「検証ループ共通の再生成規約」に従う。各観点の判定基準は `/infographic-design` に集約する（本スキルには判定基準を再掲しない）。本 Step 固有の差分は以下。

- **観点リスト**: `<image-review-aspects>` = `image-fact` / `image-coverage` / `image-legibility` / `image-consistency` の 4 観点（`image-fact` を必須観点として含む）。**宣言順** = `image-fact` → `image-coverage` → `image-legibility` → `image-consistency`。観点識別子のリストと宣言順・反復制御は本 SKILL.md が保持する。
- **対象ファイル**（author の担当ファイル）: `work/<run-id>/images/cover.png`（再生成 author = `article-image-generator`）。
- **反復上限**: 5 周（Step 5 と統一）。
- **並列レビュー**: 各観点について `image-reviewer` を単一メッセージ内で並列 spawn する。
  - 引数: review-aspect=`<aspect>`、cover=`work/<run-id>/images/cover.png`、`work/<run-id>/article.md`、`work/<run-id>/analysis.md`（`image-fact` 観点の素材根拠）、out=`work/<run-id>/image-review-<iteration>_<aspect>.md`、（2 周目以降）previous-review-path=`work/<run-id>/image-review-<前 iteration>_<aspect>.md`
  - 戻り値: `<レポート絶対パス> PASS|FAIL`
- **再生成**（`article-image-generator` を再生成モードで起動）の引数: review-report-path=選定した 1 本の絶対パス（`work/<run-id>/image-review-<iteration>_<選定観点>.md`）、regeneration-log-path=`work/<run-id>/image-regeneration-<iteration>.log`。戻り値: `work/<run-id>/images/cover.png`（再生成され上書きされた絶対パス）。
- 全観点 PASS で Step 7 へ進む。

### Step 7 出力＋ドキュメント更新（doc-updater）

- 起動: `doc-updater`
- 引数: 合格 `work/<run-id>/article.md`、cover-image=`work/<run-id>/images/cover.png`
- 戻り値: `output/<記事ファイル>`（公開記事の絶対パス。記事冒頭にインフォグラフィック参照行を含む。構成変更が生じた場合は `docs/` も追従更新される）
- 公開時、doc-updater は記事タイトル直後（記事の一番最初＝記事冒頭）に `cover.png` を参照する画像行を挿入する。「記事の一番最初に画像 1 枚」という要望を満たす配置は記事冒頭（タイトル直後）に一意に固定する。

### Step 8 HTML 執筆（article-html-author 通常起動）

Step 7 で `output/<記事>.md`（Markdown・dedup 照合キー）が確定した直後に起動する。確定 Markdown とカバー画像を入力に、`/html-page-design` 準拠のリッチ HTML 記事ページと記事一覧トップ `index.html`（Pages エントリ）を執筆する。本文ファクトは Step 5 で確定済みのため、本ステップ以降は事実・主張を改変せず HTML 整形・デザイン適用に限る。

- 起動: `article-html-author`（通常＝HTML 執筆起動）
- 引数: 確定 `output/<記事>.md`（絶対パス）、cover=`output/images/<記事ファイル名>-cover.png`（公開物カバー画像。`/html-page-design` の埋め込み規約に従い公開元へ配置）
- 戻り値: `docs/articles/<記事スラッグ>.html` と更新済み `docs/index.html`（必要時 `docs/assets/style.css` 配備）の絶対パス群
- HTML 未生成（中断レポート）の場合は Step 9/10 へ進まず打ち切る（「失敗時のリカバリ」参照）。

### Step 9 HTML 検証ループ（html-reviewer × 観点数 / article-html-author 再生成）

`/multi-aspect-review` 契約と「検証ループ共通の再生成規約」に従う。各観点の判定基準は `/html-page-design` の `## 観点別判定基準` に集約する（本スキルには判定基準を再掲しない）。本文ファクトは Step 5 で確定済みのため HTML 工程では再点検しない。本 Step 固有の差分は以下。

- **観点リスト**: `<html-review-aspects>` = `design-consistency` / `readability` / `infographic-richness` の 3 観点。**宣言順** = `design-consistency` → `readability` → `infographic-richness`。観点識別子のリストと宣言順・反復制御は本 SKILL.md が保持する。各観点の判定基準実体は `/html-page-design` の `## 観点別判定基準` に集約する（本 SKILL.md に再掲しない）。
- **対象ファイル**（author の担当ファイル）: 対象記事 HTML `docs/articles/<記事スラッグ>.html`（再生成 author = `article-html-author`）。
- **反復上限**: **2 周**（Step 5/6 の 5 周より低コスト）。
- **並列レビュー**: 各観点について `html-reviewer` を単一メッセージ内で並列 spawn する。
  - 引数: review-aspect=`<aspect>`、対象記事 HTML（`docs/articles/<記事スラッグ>.html`）、共有 CSS（`docs/assets/style.css`）、out=`work/<run-id>/html-review-<iteration>_<aspect>.md`、（2 周目以降）previous-review-path=`work/<run-id>/html-review-<前 iteration>_<aspect>.md`
  - 戻り値: `<レポート絶対パス> PASS|FAIL`
- **再生成**（`article-html-author` を再生成モードで起動）の引数: review-report-path=選定した 1 本の絶対パス（`work/<run-id>/html-review-<iteration>_<選定観点>.md`）、regeneration-log-path=`work/<run-id>/html-regeneration-<iteration>.log`。戻り値: 再生成され上書きされた記事 HTML の絶対パス。**再生成時点では push しない**（合格後に Step 10 で push）。
- 全観点 PASS で Step 10 へ進む。

### Step 10 公開（article-html-author の公開起動 / commit→push）

全工程（Step 5/6＋Step 9）合格時のみ起動する。`article-html-author` が記事 HTML・`docs/index.html`・`docs/assets/style.css` を add→commit→push（`origin main` 固定・force push 禁止）で GitHub Pages へ公開する。

- 起動: `article-html-author`（公開起動）
- 引数: 公開対象（記事 HTML・`docs/index.html`・`docs/assets/style.css`）。`origin main` 固定。
- 戻り値: GitHub Pages 公開 URL を単一行で取得。
- push 失敗（認証 / 非 fast-forward / コンフリクト）時は自動 retry・force をせず、中断レポートで打ち切る（「失敗時のリカバリ」参照）。
- 補足: Step 8 の HTML 執筆と Step 10 の公開を `article-html-author` の単一エージェント内で連続実行する設計でも、Step 9 合格後に公開専用起動を分ける設計でもよい。いずれの場合も **push は Step 9 合格時のみ行う** ことを本 SKILL.md の一意の規範とする（Step 9 未収束・打ち切り時は push しない）。

## 失敗時のリカバリ

- いずれかのサブエージェントが整合チェック失敗（入力不一致・引数 XOR 違反等）で中断レポートを返した場合、メインは後続ステップへ進まずに当該ステップで停止し、中断内容をログに残す。自動補正・自動進行はしない。
- Step 5 が反復上限到達で打ち切られた場合は、最終周回の全観点レビューレポート絶対パスをログに残し、`output/` への公開を行わずに終了する。
- Step 6a の画像生成が失敗（PNG 未生成・codex 終了非ゼロ・article-image-generator が中断レポートを返した）場合は、インフォグラフィックを必須要素とみなし、Step 6b・Step 7 へ進まずにパイプラインを打ち切る。未生成である旨と画像設計ログ（`work/<run-id>/image-design.log` があればその絶対パス）を最終ログに残し、`output/` への公開は行わない（合格時のみ公開の既存方針を維持）。
- Step 6b の画像検証ループが反復上限到達で打ち切られた場合は、最終周回の全観点画像レビューレポート絶対パスをログに残し、`output/` への公開を行わずに終了する。
- Step 8（HTML 執筆）が失敗（HTML 未生成・article-html-author が中断レポートを返した）した場合は、HTML 未生成の旨と理由をログに残し、Step 9/10 へ進まずに打ち切る。push は行わない。`output/*.md` は Step 7 で出力済みのため、dedup 照合キーは保全される旨を明示する。
- Step 9（HTML 検証ループ）が反復上限到達で打ち切られた場合は、最終周回の全観点 HTML レビューレポート絶対パスをログに残し、push（公開）を行わずに終了する。`output/*.md` の dedup 照合キーは保全される。
- Step 10（push）失敗（認証 / 非 fast-forward / コンフリクト）時は、自動 retry・force をせず中断レポートで打ち切る。HTML は生成済みだが未公開である旨、`output/*.md` の dedup 照合キーは保全される旨をログに明示する。

## ユーザーへ返す内容

- 合格して公開された場合: GitHub Pages 公開 URL（Step 10 の `article-html-author` 戻り値）、出力 HTML の絶対パス（記事 HTML `docs/articles/<記事スラッグ>.html`・`docs/index.html`）、`output/<記事ファイル>` の絶対パスと記事タイトル（限定 Read で取得）、選定論文（`work/<run-id>/selected.json` 由来）、記事本文（Step 5）・インフォグラフィック（Step 6b）・HTML（Step 9）それぞれのレビュー反復回数、生成・公開したインフォグラフィックの絶対パス（`work/<run-id>/images/cover.png`）を報告する。
- Step 5（記事本文）の反復上限で打ち切られた場合: 打ち切りの旨、最終周回の FAIL 観点とレビューレポート絶対パス群、`output/` 未公開である旨を報告する。
- Step 6b（インフォグラフィック）の反復上限で打ち切られた場合: 打ち切りの旨、最終周回の FAIL 画像観点と画像レビューレポート絶対パス群、`output/` 未公開である旨を報告する。
- 画像生成失敗（Step 6a）で打ち切った場合: 打ち切りの旨、インフォグラフィックが未生成である旨、画像設計ログ（あれば `work/<run-id>/image-design.log` の絶対パス）、`output/` へ未公開である旨を報告する。
- Step 9（HTML 検証ループ）の反復上限で打ち切られた場合: 打ち切りの旨、最終周回の FAIL 観点と HTML レビューレポート絶対パス群、未公開（push 未実施）である旨を報告する。
- Step 10（push）失敗で打ち切った場合: 打ち切りの旨、HTML は生成済みだが未公開である旨、push 失敗理由を報告する。
- 途中ステップで中断した場合: 中断ステップ・中断理由・中断レポート絶対パスを報告する。
