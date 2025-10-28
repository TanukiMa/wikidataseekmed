# Wikidata Category Finder - 使い方ガイド

## 概要

日本語のWikidataカテゴリから対応する英語カテゴリを探し出すツールです。

## Wikidataのカテゴリとサブカテゴリについて

### Wikidataのカテゴリ構造

**はい、Wikidataにはサブカテゴリが設定されています！**

Wikidataでは、以下のプロパティで階層構造を表現します：

1. **P279 (subclass of)** - サブクラス関係
   - 例: 「感染症」は「病気」のサブクラス
   - 医学的な分類階層を表現

2. **P31 (instance of)** - インスタンス関係
   - 例: あるカテゴリが「Wikimediaカテゴリ」のインスタンス

3. **P361 (part of)** - 部分関係
   - 階層的な包含関係

### 例: 医学カテゴリの階層

```
医学 (Medicine)
├─ 病気 (Disease) - P279 subclass of
│  ├─ 感染症 (Infectious disease)
│  ├─ 遺伝性疾患 (Genetic disorder)
│  └─ がん (Cancer)
│     ├─ 肺がん (Lung cancer)
│     └─ 乳がん (Breast cancer)
├─ 医薬品 (Medication)
│  ├─ 抗生物質 (Antibiotic)
│  └─ ワクチン (Vaccine)
└─ 医療処置 (Medical procedure)
   ├─ 手術 (Surgery)
   └─ 診断 (Diagnosis)
```

## インストール

```bash
# 既存のrequirements.txtでOK（新しい依存関係なし）
pip install -r requirements.txt
```

## 基本的な使い方

### 1. 日本語キーワードで検索（部分一致）

```bash
# 「医学」というキーワードでカテゴリを検索
python wikidata_category_finder.py --search "医学"

# 「病気」で検索、結果を20件に制限
python wikidata_category_finder.py --search "病気" --limit 20

# 「がん」で検索してCSVにエクスポート
python wikidata_category_finder.py --search "がん" --export-csv
```

### 2. 日本語カテゴリから英語カテゴリとQ numberを取得（完全一致）⭐ NEW

```bash
# 「病気」の英語カテゴリとQ numberを取得
python wikidata_category_finder.py --exact "病気"

# 「医薬品」の英語カテゴリとQ numberを取得
python wikidata_category_finder.py --exact "医薬品"

# 「感染症」を検索してCSVにエクスポート
python wikidata_category_finder.py --exact "感染症" --export-csv
```

**出力例:**
```
🎯 Finding exact match for Japanese category: '病気'
✅ Found exact match!

📋 Exact Match Result:
================================================================================

🏷️  Q Number: Q12136
   🇯🇵 日本語: 病気
   🇬🇧 English: disease

================================================================================
✅ Result: Q12136 | 病気 → disease
================================================================================
```

### 3. バッチ処理（複数の日本語カテゴリを一括変換）⭐ NEW

```bash
# テキストファイルから複数のカテゴリを一括処理
python wikidata_category_finder.py --batch sample_japanese_categories.txt

# 結果をCSVにエクスポート
python wikidata_category_finder.py --batch sample_japanese_categories.txt --export-csv
```

**sample_japanese_categories.txt の例:**
```
病気
医薬品
症状
感染症
がん
```

**出力例:**
```
📚 Batch finding 5 Japanese categories
================================================================================

[1/5] Processing: 病気
✅ Q12136: 病気 → disease

[2/5] Processing: 医薬品
✅ Q12140: 医薬品 → medication

...

📊 Summary: Found 5/5 categories
================================================================================

📊 Batch Results:
================================================================================
QID          Japanese                  English                       
--------------------------------------------------------------------------------
Q12136       病気                      disease                       
Q12140       医薬品                    medication                    
Q169872      症状                      symptom                       
Q18123741    感染症                    infectious disease            
Q12124       がん                      cancer                        
================================================================================
```

### 4. 特定のQIDを調査

```bash
# Q12136 (disease) の詳細を表示
python wikidata_category_finder.py --qid Q12136 --show-details

# サブカテゴリを表示（1階層）
python wikidata_category_finder.py --qid Q12136 --show-subcategories

# サブカテゴリを2階層まで表示
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 2

# 3階層まで（注意: 時間がかかります）
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 3
```

### 5. 検索とサブカテゴリの組み合わせ

```bash
# 「医療」で検索して、各カテゴリのサブカテゴリも表示
python wikidata_category_finder.py --search "医療" --show-subcategories --depth 1

# 詳細情報も含めて表示
python wikidata_category_finder.py --search "医療" --show-details --show-subcategories
```

### 6. エクスポート

```bash
# JSONにエクスポート
python wikidata_category_finder.py --search "医学" --export-json

# CSVにエクスポート
python wikidata_category_finder.py --search "医学" --export-csv

# 両方にエクスポート
python wikidata_category_finder.py --search "医学" --export-json --export-csv
```

## 実行例と出力

### 例1: 「病気」で検索

```bash
python wikidata_category_finder.py --search "病気" --limit 5
```

**出力例:**
```
================================================================================
🔍 Wikidata Category Finder - Japanese to English Mapping
================================================================================

🔍 Searching for categories with Japanese keyword: '病気'
--------------------------------------------------------------------------------
✅ Found 5 categories

📋 Search Results (5 categories):
================================================================================

[1] 🏷️  Q12136
   🇯🇵 日本語: 病気
   🇬🇧 English: disease
   📝 説明: 生物の正常な状態が損なわれた状態
   📝 Description: abnormal condition negatively affecting organisms

[2] 🏷️  Q18123741
   🇯🇵 日本語: 感染症
   🇬🇧 English: infectious disease
   📝 説明: 病原体による感染症
   
...
```

### 例2: サブカテゴリ探索

```bash
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 2
```

**出力例:**
```
🔎 Finding subcategories of Q12136 (depth: 2)...
--------------------------------------------------------------------------------

📊 Level 1:
  Found 15 subcategories

📊 Level 2:
  Found 48 subcategories

📂 Subcategory Hierarchy:
================================================================================

📁 Level 1 (15 subcategories):
------------------------------------------------------------

  🏷️  Q18123741
     🇯🇵 日本語: 感染症
     🇬🇧 English: infectious disease

  🏷️  Q929833
     🇯🇵 日本語: 希少疾患
     🇬🇧 English: rare disease
     
  ...
```

## 出力ファイル

### JSON形式 (category_mapping.json)

```json
[
  {
    "qid": "Q12136",
    "japanese": "病気",
    "english": "disease",
    "description_ja": "生物の正常な状態が損なわれた状態",
    "description_en": "abnormal condition negatively affecting organisms",
    "instance_of": ["Wikimedia category"],
    "subclass_of": ["medical concept"]
  }
]
```

### CSV形式 (category_mapping.csv)

| QID | Japanese_Label | English_Label | Japanese_Description | English_Description | Instance_Of | Subclass_Of |
|-----|----------------|---------------|---------------------|---------------------|-------------|-------------|
| Q12136 | 病気 | disease | ... | ... | Wikimedia category | medical concept |

## よくある使用例

### 単一カテゴリの英訳とQ number取得 ⭐ NEW

```bash
# 1つの日本語カテゴリから英語とQ numberを取得
python wikidata_category_finder.py --exact "病気"
python wikidata_category_finder.py --exact "医薬品"
python wikidata_category_finder.py --exact "症状"
```

### 複数カテゴリの一括変換 ⭐ NEW

```bash
# テキストファイルを作成
cat > my_categories.txt << EOF
病気
医薬品
症状
感染症
がん
希少疾患
精神疾患
遺伝子
タンパク質
EOF

# 一括処理してCSVにエクスポート
python wikidata_category_finder.py --batch my_categories.txt --export-csv

# 結果: output/category_mapping.csv に保存される
```

### 医学カテゴリの全体像を把握

```bash
# 「医学」カテゴリとそのサブカテゴリを2階層まで探索
python wikidata_category_finder.py --search "医学" --limit 1 --show-subcategories --depth 2 --export-json
```

### 特定疾患のカテゴリ体系を調査

```bash
# がんのサブカテゴリを調査
python wikidata_category_finder.py --search "がん" --show-subcategories --depth 2
```

### 医療用語の英訳リストを作成

```bash
# 「医療」関連カテゴリを検索してCSVにエクスポート
python wikidata_category_finder.py --search "医療" --limit 100 --export-csv

# 「薬」関連カテゴリ
python wikidata_category_finder.py --search "薬" --limit 100 --export-csv

# 「症状」関連カテゴリ
python wikidata_category_finder.py --search "症状" --limit 100 --export-csv
```

## コマンドラインオプション一覧

| オプション | 説明 | 例 |
|-----------|------|---|
| `--search` | 日本語キーワードで検索（部分一致） | `--search "医学"` |
| `--exact` ⭐ NEW | 日本語カテゴリ名で完全一致検索、英語とQ numberを取得 | `--exact "病気"` |
| `--batch` ⭐ NEW | テキストファイルから複数カテゴリを一括処理 | `--batch categories.txt` |
| `--qid` | 特定のQIDを指定 | `--qid Q12136` |
| `--limit` | 検索結果の最大件数 | `--limit 50` |
| `--show-details` | 詳細情報を表示 | `--show-details` |
| `--show-subcategories` | サブカテゴリを表示 | `--show-subcategories` |
| `--depth` | サブカテゴリの探索深度 | `--depth 2` |
| `--export-json` | JSON形式でエクスポート | `--export-json` |
| `--export-csv` | CSV形式でエクスポート | `--export-csv` |
| `--config` | 設定ファイルのパス | `--config my_config.yaml` |

## Wikidataでのカテゴリプロパティ

### 主要なプロパティ

1. **P279 (subclass of)** - サブクラス関係
   ```
   感染症 --P279--> 病気
   ```

2. **P31 (instance of)** - インスタンス関係
   ```
   Category:感染症 --P31--> Wikimedia category
   ```

3. **P361 (part of)** - 部分関係
   ```
   心臓病学 --P361--> 医学
   ```

4. **P171 (parent taxon)** - 生物分類の親
   ```
   （生物学的分類で使用）
   ```

### このツールが使用するプロパティ

- **検索**: `rdfs:label` (ラベル) を使用
- **カテゴリ判定**: `P31 = Q4167836` (Wikimediaカテゴリ)
- **サブカテゴリ**: `P279` (subclass of) を使用

## 注意事項

### パフォーマンス

- **depth=1**: 高速（数秒）
- **depth=2**: 中速（10-30秒）
- **depth=3**: 低速（1-5分）、大量のクエリが発生

### レート制限

Wikidata SPARQLエンドポイントには使用制限があります：

- 連続クエリの間に1秒のスリープを入れています
- 大量のデータを取得する場合は注意

### サブカテゴリの数

- 「病気」のような大カテゴリは数百のサブカテゴリを持つ場合があります
- `--depth 3` は非常に時間がかかる可能性があります

## トラブルシューティング

### タイムアウトエラー

```bash
# depthを減らす
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 1

# limitを減らす
python wikidata_category_finder.py --search "医学" --limit 10
```

### 結果が見つからない

```bash
# 部分一致なので、短いキーワードを試す
python wikidata_category_finder.py --search "医"

# 英語で試す（英語ラベルからも検索可能）
python wikidata_category_finder.py --search "medicine"
```

## 実用例

### 医学翻訳のための用語集作成

```bash
# 病気関連
python wikidata_category_finder.py --search "病気" --limit 50 --export-csv
python wikidata_category_finder.py --search "疾患" --limit 50 --export-csv

# 薬関連
python wikidata_category_finder.py --search "薬" --limit 50 --export-csv
python wikidata_category_finder.py --search "医薬品" --limit 50 --export-csv

# 結果をマージして用語集を作成
```

### 医学カテゴリの階層構造を理解

```bash
# 医学の全体像
python wikidata_category_finder.py --qid Q11190 --show-subcategories --depth 2 --export-json

# 特定分野の詳細
python wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 3
```

## 関連リソース

- Wikidata SPARQL: https://query.wikidata.org/
- Wikidata プロパティ一覧: https://www.wikidata.org/wiki/Wikidata:List_of_properties
- P279 (subclass of): https://www.wikidata.org/wiki/Property:P279

## 次のステップ

1. 基本検索を試す
2. 興味のあるカテゴリのサブカテゴリを探索
3. 結果をエクスポートして分析
4. 医療用語抽出ツールと組み合わせて使用
