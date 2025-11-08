# Wikidata Category Finder Guide

`find_wikidata_categories.py`を使って、キーワードからWikidataカテゴリを検索し、`config.yaml`に追加する方法を説明します。

## 基本的な使い方

```bash
# シンプルな検索
python find_wikidata_categories.py "cancer"

# 医療関連のみ
python find_wikidata_categories.py "neurology" --medical-only

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

詳細は実行時のヘルプを参照：
```bash
python find_wikidata_categories.py --help
```
