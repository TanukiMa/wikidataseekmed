# Wikidata Category Finder Guide

`find_wikidata_categories.py`を使って、キーワードからWikidata医療概念を検索し、`config.yaml`に追加する方法を説明します。

このツールは、Wikidata Web APIのみを使用し、SPARQL使用を最小限に抑えています。

## 基本的な使い方

```bash
# シンプルな検索
python find_wikidata_categories.py "cancer"

# 医療関連のみ
python find_wikidata_categories.py "neurology" --medical-only

# 検索数を制限
python find_wikidata_categories.py "disease" --limit 20

# YAML形式で出力
python find_wikidata_categories.py "cardiology" --output yaml
```

## config.yamlへの追加手順

1. カテゴリを検索：
   ```bash
   python find_wikidata_categories.py "oncology" --medical-only --output yaml
   ```

2. 出力をコピーして`config.yaml`に追加

3. データを取得：
   ```bash
   python wikidataseekmed_api_optimized.py --small
   ```

## 利用可能なオプション

- `--medical-only`: 医療関連の項目のみ表示
- `--limit N`: 検索結果の最大数を制限（デフォルト: 50）
- `--output {table,yaml,json}`: 出力形式を指定（デフォルト: table）

詳細は実行時のヘルプを参照：
```bash
python find_wikidata_categories.py --help
```

## Web APIの利点

このツールは、Wikidata Web API（`wbsearchentities`および`wbgetentities`）のみを使用します：

- **SPARQL不要**: レート制限が緩やか
- **高速**: タイムアウトが少ない
- **シンプル**: エラーハンドリングが容易
- **Wikidataに優しい**: APIコール間に0.5秒の待機時間を設定
