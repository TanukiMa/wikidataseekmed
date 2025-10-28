# Wikidata Medical Tools - プロジェクトサマリー

## 📦 プロジェクト概要

Wikidataから医療用語とカテゴリ情報を抽出するPythonツール群です。

## 🗂️ ファイル構成

### メインツール

1. **wikidataseekmed_improved.py** (47KB)
   - WikidataからEN-JA医療用語ペアを抽出
   - 改善版（セキュリティ、型安全性、保守性向上）
   - 詳細: README_improved.md

2. **wikidata_category_finder.py** (21KB) ⭐ NEW
   - 日本語カテゴリから英語カテゴリを検索
   - **完全一致検索で英語カテゴリ＋Q numberを取得** ⭐ NEW
   - **複数カテゴリのバッチ処理** ⭐ NEW
   - サブカテゴリの階層探索機能
   - 詳細: CATEGORY_FINDER_GUIDE.md, NEW_FEATURES.md

### 設定ファイル

3. **config.yaml** (3.6KB)
   - カテゴリ定義、タイムアウト、リトライ回数などを設定
   - 環境別に簡単にカスタマイズ可能

4. **requirements.txt** (48B)
   - 必要なパッケージ: pandas, SPARQLWrapper, pyyaml

### ドキュメント

5. **README_improved.md** (6.7KB)
   - 改善版医療用語抽出ツールの使い方

6. **CATEGORY_FINDER_GUIDE.md** (9.9KB)
   - カテゴリ検索ツールの使い方
   - 実行例と出力サンプル

7. **WIKIDATA_CATEGORIES_EXPLAINED.md** (8.7KB)
   - Wikidataのカテゴリとサブカテゴリの技術解説
   - SPARQLクエリの詳細

8. **IMPROVEMENTS.md** (11KB)
   - 10の問題点と解決策の詳細説明
   - コード比較

9. **QUICKSTART.md** (2.8KB)
   - クイックスタートガイド

10. **NEW_FEATURES.md** (5.7KB) ⭐ NEW
    - 新機能の詳細説明（完全一致検索、バッチ処理）
    - 実用例とサンプルコード

### ユーティリティ

11. **demo_category_finder.sh** (3.0KB)
    - カテゴリ検索ツールのデモスクリプト
    - 実行例とよく使うQIDの一覧

12. **sample_japanese_categories.txt** ⭐ NEW
    - バッチ処理用のサンプルファイル
    - コメント付きカテゴリリスト

### レガシー

13. **wikidataseekmed.py** (46KB)
    - オリジナル版（参照用）

## 🚀 セットアップ

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# または
pip install pandas>=1.3.0 SPARQLWrapper>=2.0.0 pyyaml>=5.4.0
```

## 📖 使い方

### ツール1: 医療用語抽出

```bash
# Small scaleテスト
python wikidataseekmed_improved.py --small --limit 100 --log logs/test.log

# Medium scale
python wikidataseekmed_improved.py --medium --limit 500 --batch-size 300 --log logs/medium.log

# カテゴリ発見モード
python wikidataseekmed_improved.py --small --discover --limit 1000
```

### ツール2: カテゴリ検索 ⭐ NEW

```bash
# 日本語キーワードで検索（部分一致）
python wikidata_category_finder.py --search "病気" --limit 20

# 日本語カテゴリから英語＋Q numberを取得（完全一致）⭐ NEW
python wikidata_category_finder.py --exact "病気"
python wikidata_category_finder.py --exact "医薬品"

# 複数カテゴリを一括変換（バッチ処理）⭐ NEW
python wikidata_category_finder.py --batch sample_japanese_categories.txt --export-csv

# サブカテゴリを探索
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 2

# CSVにエクスポート
python wikidata_category_finder.py --exact "医学" --export-csv

# 組み合わせ
python wikidata_category_finder.py --search "がん" --show-subcategories --export-json
```

## 🎯 主な機能

### wikidataseekmed_improved.py

- ✅ 医療用語の英日ペア抽出
- ✅ カテゴリ別データ取得
- ✅ MeSH, ICD-10, SNOMED CTなどの外部ID取得
- ✅ データ品質分析
- ✅ CSV/JSON出力
- ✅ 504エラー対策（リトライ、バックオフ）

### wikidata_category_finder.py ⭐ NEW

- ✅ 日本語キーワードでカテゴリ検索（部分一致）
- ✅ **日本語カテゴリ→英語カテゴリ＋Q number変換（完全一致）** ⭐ NEW
- ✅ **複数カテゴリの一括変換（バッチ処理）** ⭐ NEW
- ✅ 英語カテゴリとのマッピング
- ✅ サブカテゴリの階層探索（P279 subclass of）
- ✅ カテゴリ詳細情報取得
- ✅ CSV/JSON出力
- ✅ 循環参照対策

## 🔍 Wikidataのカテゴリについて

### サブカテゴリは設定されています！

Wikidataでは **P279 (subclass of)** プロパティでサブカテゴリを表現：

```
Q12136 (disease/病気)
├─ Q18123741 (infectious disease/感染症) [P279]
├─ Q929833 (rare disease/希少疾患) [P279]
├─ Q18965518 (mental disorder/精神疾患) [P279]
└─ Q12124 (cancer/がん) [P279]
    ├─ Q47912 (lung cancer/肺がん) [P279]
    └─ Q128581 (breast cancer/乳がん) [P279]
```

詳細: WIKIDATA_CATEGORIES_EXPLAINED.md

## 📊 よく使う医療カテゴリ QID

| QID | 日本語 | English |
|-----|--------|---------|
| Q12136 | 病気 | disease |
| Q12140 | 医薬品 | medication |
| Q169872 | 症状 | symptom |
| Q18123741 | 感染症 | infectious disease |
| Q12124 | がん | cancer |
| Q8054 | タンパク質 | protein |
| Q7187 | 遺伝子 | gene |
| Q796194 | 手術 | surgery |
| Q1059392 | 医学検査 | medical test |

## 🛠️ 改善点（wikidataseekmed_improved.py）

元のコードから以下を改善：

1. ✅ セキュリティ（SPARQLインジェクション対策）
2. ✅ 設定の外部化（YAML）
3. ✅ 型安全性（Type hints）
4. ✅ エラーハンドリング（タイプ別処理）
5. ✅ リソース管理（pathlib、適切なファイル管理）
6. ✅ コード重複削減
7. ✅ 保守性向上（f-string、dataclass）
8. ✅ ユーザー入力検証
9. ✅ グローバル状態管理
10. ✅ パフォーマンス最適化

詳細: IMPROVEMENTS.md

## 💡 使用例

### 例1: 病気カテゴリの全体像を把握

```bash
# カテゴリを検索
python wikidata_category_finder.py --search "病気" --limit 5

# サブカテゴリを2階層まで探索
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 2

# 病気カテゴリの用語を抽出
python wikidataseekmed_improved.py --small --limit 1000 --log logs/disease.log
```

### 例2: 医学翻訳用の用語集作成

```bash
# 各カテゴリを検索してエクスポート
python wikidata_category_finder.py --search "病気" --export-csv
python wikidata_category_finder.py --search "医薬品" --export-csv
python wikidata_category_finder.py --search "症状" --export-csv

# 見つけたQIDで用語抽出
python wikidataseekmed_improved.py --medium --limit 5000 --export-csv
```

### 例3: 特定疾患の詳細調査

```bash
# がんカテゴリのサブカテゴリを調査
python wikidata_category_finder.py --qid Q12124 --show-subcategories --depth 3 --export-json

# がん関連用語を抽出
# config.yamlにQ12124を追加してから実行
python wikidataseekmed_improved.py --small --limit 2000
```

## 📁 出力ファイル

### wikidataseekmed_improved.py の出力

```
output/
├── small_medical_terms_full_20250127_123456.csv
├── small_en_ja_pairs_20250127_123456.csv
├── small_medical_terms_20250127_123456.json
├── small_report_20250127_123456.txt
└── by_category_20250127_123456/
    ├── disease.csv
    ├── medication.csv
    └── ...
```

### wikidata_category_finder.py の出力

```
output/
├── category_mapping.json
└── category_mapping.csv
```

## 🔧 トラブルシューティング

### 依存関係エラー

```bash
pip install -r requirements.txt
```

### 504 Gateway Timeout

```bash
# config.yamlを編集
query:
  batch_size: 200  # 1000から減らす
  max_retries: 8
  retry_wait_504_base: 20

# またはコマンドラインで
python wikidataseekmed_improved.py --small --batch-size 200
```

### カテゴリが見つからない

```bash
# 短いキーワードを試す
python wikidata_category_finder.py --search "医"

# 英語でも検索可能
python wikidata_category_finder.py --search "medicine"
```

## 📚 ドキュメント詳細

| ファイル | 内容 |
|---------|------|
| QUICKSTART.md | すぐに始める |
| README_improved.md | 医療用語抽出ツールの詳細 |
| CATEGORY_FINDER_GUIDE.md | カテゴリ検索ツールの詳細 |
| WIKIDATA_CATEGORIES_EXPLAINED.md | Wikidataカテゴリの技術解説 |
| IMPROVEMENTS.md | コード改善の詳細 |

## 🎉 まとめ

このプロジェクトは、Wikidataから医療情報を効率的に抽出するための2つのツールを提供：

1. **wikidataseekmed_improved.py**: 医療用語の英日ペアを大量抽出
2. **wikidata_category_finder.py**: カテゴリとその階層構造を探索

両ツールを組み合わせることで、医療分野の包括的なデータ収集が可能です。

---

**質問: WikiDataにはサブカテゴリは設定されていますか？**

**回答: はい！** Wikidataには **P279 (subclass of)** プロパティを使った豊富なサブカテゴリ体系があります。`wikidata_category_finder.py`でこの階層構造を簡単に探索できます。

詳細は WIKIDATA_CATEGORIES_EXPLAINED.md をご覧ください。
