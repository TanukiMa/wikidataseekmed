# 新機能追加: 日本語カテゴリ→英語カテゴリ＋Q number変換

## 🎉 追加された機能

### 1. 完全一致検索 (`--exact`)

日本語のカテゴリ名を指定すると、対応する英語カテゴリとQ numberを返します。

```bash
python wikidata_category_finder.py --exact "病気"
```

**出力:**
```
🎯 Finding exact match for Japanese category: '病気'
--------------------------------------------------------------------------------
✅ Found exact match!

📋 Exact Match Result:
================================================================================

🏷️  Q Number: Q12136
   🇯🇵 日本語: 病気
   🇬🇧 English: disease

   📝 説明(JA): 生物の正常な状態が損なわれた状態
   📝 説明(EN): abnormal condition negatively affecting organisms

================================================================================
✅ Result: Q12136 | 病気 → disease
================================================================================
```

### 2. バッチ処理 (`--batch`)

テキストファイルに記載された複数の日本語カテゴリを一括で変換します。

```bash
python wikidata_category_finder.py --batch sample_japanese_categories.txt --export-csv
```

**テキストファイルの形式:**
```
# コメント行は無視されます
病気
医薬品
症状
感染症
がん
```

**出力:**
```
📚 Batch finding 5 Japanese categories
================================================================================

[1/5] Processing: 病気
🎯 Finding exact match for Japanese category: '病気'
✅ Found exact match!
   ✅ Q12136: 病気 → disease

[2/5] Processing: 医薬品
🎯 Finding exact match for Japanese category: '医薬品'
✅ Found exact match!
   ✅ Q12140: 医薬品 → medication

[3/5] Processing: 症状
✅ Q169872: 症状 → symptom

[4/5] Processing: 感染症
✅ Q18123741: 感染症 → infectious disease

[5/5] Processing: がん
✅ Q12124: がん → cancer

================================================================================
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

## 📖 使用例

### 例1: 単一カテゴリの変換

```bash
# 病気
python wikidata_category_finder.py --exact "病気"
# 結果: Q12136 | 病気 → disease

# 医薬品
python wikidata_category_finder.py --exact "医薬品"
# 結果: Q12140 | 医薬品 → medication

# 症状
python wikidata_category_finder.py --exact "症状"
# 結果: Q169872 | 症状 → symptom
```

### 例2: バッチ処理でCSV作成

```bash
# 1. テキストファイルを作成
cat > medical_categories.txt << 'EOF'
病気
医薬品
症状
感染症
がん
希少疾患
精神疾患
神経疾患
遺伝子
タンパク質
手術
医療検査
診断
細菌
ウイルス
EOF

# 2. バッチ処理してCSVにエクスポート
python wikidata_category_finder.py --batch medical_categories.txt --export-csv

# 3. 結果を確認
cat output/category_mapping.csv
```

**出力CSV:**
```csv
QID,Japanese_Label,English_Label,Japanese_Description,English_Description,Instance_Of,Subclass_Of
Q12136,病気,disease,生物の正常な状態が損なわれた状態,abnormal condition negatively affecting organisms,,
Q12140,医薬品,medication,,,Wikimedia category,
Q169872,症状,symptom,,,Wikimedia category,
...
```

### 例3: JSONとCSV両方にエクスポート

```bash
python wikidata_category_finder.py --exact "病気" --export-json --export-csv
```

**JSON (output/category_mapping.json):**
```json
[
  {
    "qid": "Q12136",
    "japanese": "病気",
    "english": "disease",
    "description_ja": "生物の正常な状態が損なわれた状態",
    "description_en": "abnormal condition negatively affecting organisms",
    "instance_of": [],
    "subclass_of": []
  }
]
```

## 🔄 既存機能との違い

| 機能 | コマンド | 動作 | 用途 |
|-----|---------|------|------|
| 部分一致検索 | `--search "病気"` | 「病気」を含む全カテゴリを検索 | カテゴリの探索 |
| **完全一致検索** ⭐ NEW | `--exact "病気"` | 「病気」と完全一致するカテゴリのみ | 英訳とQ numberの取得 |
| **バッチ処理** ⭐ NEW | `--batch file.txt` | ファイル内の全カテゴリを一括変換 | 大量変換 |

## 💡 実用例

### 医学用語の英訳リスト作成

```bash
# 1. 日本語カテゴリリストを作成
cat > ja_categories.txt << 'EOF'
病気
感染症
ウイルス感染症
細菌感染症
寄生虫感染症
がん
肺がん
乳がん
胃がん
大腸がん
白血病
医薬品
抗生物質
ワクチン
鎮痛剤
症状
発熱
咳
頭痛
EOF

# 2. 一括変換
python wikidata_category_finder.py --batch ja_categories.txt --export-csv

# 3. Excelで開いて確認
open output/category_mapping.csv
```

### config.yamlへのカテゴリ追加

```bash
# 1. 興味のあるカテゴリのQ numberを取得
python wikidata_category_finder.py --exact "希少疾患"
# 結果: Q929833 | 希少疾患 → rare disease

# 2. config.yamlに追加
vim config.yaml

# categories:
#   custom:
#     Q929833: "rare disease"  # 追加
```

## ⚠️ 注意事項

### 完全一致の条件

- カテゴリ名は大文字小文字を区別しません
- 「Category:」接頭辞は自動で処理されます
- 部分一致では見つからない場合があります

### 見つからない場合

```bash
# 完全一致で見つからない
python wikidata_category_finder.py --exact "医療"
# ❌ No exact match found for '医療'
# 💡 Try partial search with: --search "医療"

# 部分一致で探す
python wikidata_category_finder.py --search "医療" --limit 10
# ✅ 複数の候補が表示される
```

## 🔧 トラブルシューティング

### Q1: バッチ処理で一部のカテゴリが見つからない

**原因:** Wikidataに該当カテゴリがない、または名称が異なる

**解決策:**
```bash
# 部分一致で確認
python wikidata_category_finder.py --search "探したいカテゴリ"
```

### Q2: 大量のカテゴリを処理したい

**推奨:** 50-100カテゴリずつに分割

```bash
# ファイルを分割
split -l 50 large_categories.txt batch_

# 順次処理
for file in batch_*; do
  python wikidata_category_finder.py --batch "$file" --export-csv
  sleep 5
done
```

### Q3: タイムアウトエラーが発生する ⭐ NEW

```
❌ Error during exact search: The read operation timed out
```

**原因:**
- ネットワークの遅延
- Wikidataサーバーの負荷
- 複雑なクエリ

**解決策:**

#### 方法1: 自動リトライを活用（既に実装済み v2.1）

ツールは自動的に3回までリトライします！待つだけで成功する場合があります。

```bash
# 実行すると自動でリトライ
python wikidata_category_finder.py --exact "疫学"

# 出力例:
# ⚠️  Query timeout (attempt 1/3)
# ⏳ Retry attempt 2/3 after 2s...
# ⚠️  Query timeout (attempt 2/3)
# ⏳ Retry attempt 3/3 after 4s...
# ✅ Found exact match!  # 成功！
```

#### 方法2: 部分一致検索を使う

```bash
# タイムアウトする場合
python wikidata_category_finder.py --exact "疫学"

# 代わりにこちらを試す
python wikidata_category_finder.py --search "疫学" --limit 10
```

#### 方法3: 時間をおいて再試行

```bash
# 数分待ってから再試行
sleep 300  # 5分待機
python wikidata_category_finder.py --exact "疫学"
```

#### 方法4: Wikidata Web UIで確認してQIDを取得

1. https://www.wikidata.org/ で検索
2. Q numberを確認（例: Q133212）
3. QIDで直接アクセス

```bash
python wikidata_category_finder.py --qid Q133212
```

**詳細**: TROUBLESHOOTING.md を参照

## 📚 関連ドキュメント

- **CATEGORY_FINDER_GUIDE.md** - 全機能の使い方ガイド
- **sample_japanese_categories.txt** - バッチ処理のサンプルファイル
- **WIKIDATA_CATEGORIES_EXPLAINED.md** - カテゴリ構造の技術解説

## まとめ

新機能により、以下が可能になりました：

✅ 日本語カテゴリ名から英語カテゴリ名とQ numberを簡単に取得  
✅ 複数カテゴリの一括変換（バッチ処理）  
✅ CSV/JSON形式での結果エクスポート  
✅ 医学翻訳、用語集作成、config.yaml編集などに活用  

従来の部分一致検索と組み合わせることで、より効率的なカテゴリ探索が可能です！
