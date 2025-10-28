# Wikidataのカテゴリとサブカテゴリ - 技術解説

## Wikidataにおけるカテゴリ構造

### はい、Wikidataにはサブカテゴリがあります！

Wikidataでは、以下のプロパティを使って階層構造を表現します：

## 主要なプロパティ

### 1. P279 (subclass of) - サブクラス関係

**最も重要なプロパティ**で、カテゴリの階層を表現します。

```sparql
# 例: 感染症は病気のサブクラス
?item wdt:P279 wd:Q12136 .  # Q12136 = disease
```

**具体例:**
```
Q12136 (disease/病気)
  ├─ Q18123741 (infectious disease/感染症) [P279]
  ├─ Q929833 (rare disease/希少疾患) [P279]
  ├─ Q18965518 (mental disorder/精神疾患) [P279]
  └─ Q12124 (cancer/がん) [P279]
      ├─ Q47912 (lung cancer/肺がん) [P279]
      └─ Q128581 (breast cancer/乳がん) [P279]
```

### 2. P31 (instance of) - インスタンス関係

カテゴリページ自体が「Wikimediaカテゴリ」のインスタンスであることを示します。

```sparql
# Wikimediaカテゴリの検索
?item wdt:P31 wd:Q4167836 .  # Q4167836 = Wikimedia category
```

### 3. P361 (part of) - 部分関係

全体と部分の関係を表現します。

```sparql
# 例: 心臓病学は医学の一部
wd:Q10379 wdt:P361 wd:Q11190 .  # 心臓病学 part of 医学
```

### 4. その他の関連プロパティ

- **P910**: カテゴリの主題 (category's main topic)
- **P971**: カテゴリ結合 (category combines topics)
- **P425**: 対象分野 (field of this profession)

## このツールの実装方法

### カテゴリ検索クエリ

```sparql
SELECT DISTINCT ?item ?jaLabel ?enLabel
WHERE {
  ?item wdt:P31 wd:Q4167836 .        # Wikimediaカテゴリ
  ?item rdfs:label ?jaLabel .
  FILTER(LANG(?jaLabel) = "ja")
  FILTER(CONTAINS(LCASE(?jaLabel), "医学"))
  
  OPTIONAL {
    ?item rdfs:label ?enLabel .
    FILTER(LANG(?enLabel) = "en")
  }
}
LIMIT 50
```

### サブカテゴリ検索クエリ

```sparql
SELECT DISTINCT ?item ?jaLabel ?enLabel
WHERE {
  ?item wdt:P279 wd:Q12136 .         # Q12136のサブクラス
  
  OPTIONAL {
    ?item rdfs:label ?jaLabel .
    FILTER(LANG(?jaLabel) = "ja")
  }
  
  OPTIONAL {
    ?item rdfs:label ?enLabel .
    FILTER(LANG(?enLabel) = "en")
  }
}
LIMIT 100
```

## 階層探索のアルゴリズム

### 深さ優先探索 (DFS)

```python
def find_subcategories(qid: str, depth: int = 1):
    """
    depth階層までサブカテゴリを探索
    
    depth=1: 直接のサブカテゴリのみ
    depth=2: サブカテゴリとそのサブカテゴリ
    depth=3: 3階層まで
    """
    all_subcategories = {}
    visited = {qid}  # 循環参照を防ぐ
    
    for level in range(1, depth + 1):
        if level == 1:
            parents = [qid]
        else:
            parents = [cat.qid for cat in all_subcategories[level-1]]
        
        level_subcats = []
        for parent in parents:
            subcats = get_direct_subcategories(parent)
            new_subcats = [cat for cat in subcats if cat.qid not in visited]
            
            for cat in new_subcats:
                visited.add(cat.qid)
                level_subcats.append(cat)
        
        if level_subcats:
            all_subcategories[level] = level_subcats
    
    return all_subcategories
```

### 循環参照の処理

Wikidataでは循環参照が存在する可能性があるため、`visited` セットで管理：

```python
visited: Set[str] = {qid}  # 訪問済みQID

if cat.qid not in visited:
    visited.add(cat.qid)
    # 処理
```

## Wikidataカテゴリの特徴

### 1. 多言語対応

各カテゴリは複数言語のラベルを持ちます：

```json
{
  "qid": "Q12136",
  "labels": {
    "ja": "病気",
    "en": "disease",
    "fr": "maladie",
    "de": "Krankheit",
    ...
  }
}
```

### 2. 多重継承

1つのカテゴリが複数の親を持つことができます：

```
Q18123741 (infectious disease/感染症)
  ├─ P279: Q12136 (disease/病気)
  └─ P279: Q18123738 (pathogenic infection/病原性感染)
```

### 3. 説明文 (description)

ラベルに加えて説明文も多言語で提供：

```json
{
  "qid": "Q12136",
  "descriptions": {
    "ja": "生物の正常な状態が損なわれた状態",
    "en": "abnormal condition negatively affecting organisms"
  }
}
```

## パフォーマンス考慮事項

### クエリの複雑さ

| 探索深度 | クエリ数 | 予想時間 | 推奨用途 |
|---------|---------|---------|---------|
| depth=1 | 1-10 | 数秒 | 基本的な探索 |
| depth=2 | 10-100 | 10-30秒 | 中規模探索 |
| depth=3 | 100-1000+ | 1-5分 | 詳細な分析 |

### レート制限への対応

```python
# クエリ間にスリープを入れる
time.sleep(1)  # 1秒待機

# タイムアウト設定
self.sparql.setTimeout(60)  # 60秒
```

## 実データ例: 病気カテゴリの階層

### Level 0: 病気 (Q12136)

```
🏷️  Q12136
   🇯🇵 日本語: 病気
   🇬🇧 English: disease
```

### Level 1: 病気のサブクラス（一部）

```
├─ Q18123741: 感染症 (infectious disease)
├─ Q929833: 希少疾患 (rare disease)
├─ Q18965518: 精神疾患 (mental disorder)
├─ Q18556609: 神経疾患 (neurological disorder)
├─ Q12124: がん (cancer)
├─ Q389735: 心血管疾患 (cardiovascular disease)
├─ Q18123738: 遺伝性疾患 (genetic disorder)
└─ Q15328: 自己免疫疾患 (autoimmune disease)
```

### Level 2: 感染症のサブクラス（一部）

```
Q18123741 (感染症)
├─ Q18123756: ウイルス感染症 (viral infectious disease)
│  ├─ Q12204: インフルエンザ (influenza)
│  ├─ Q84263196: COVID-19
│  └─ Q154874: エボラ出血熱 (Ebola)
├─ Q18123760: 細菌感染症 (bacterial infectious disease)
│  ├─ Q12204: 結核 (tuberculosis)
│  └─ Q133780: 肺炎 (pneumonia)
└─ Q18123764: 寄生虫感染症 (parasitic infectious disease)
```

## コードの主要機能

### 1. CategoryInfo データクラス

```python
@dataclass
class CategoryInfo:
    qid: str                           # WikidataのQID
    label_ja: str                      # 日本語ラベル
    label_en: str                      # 英語ラベル
    description_ja: str = ""           # 日本語説明
    description_en: str = ""           # 英語説明
    instance_of: List[str] = []        # インスタンス関係
    subclass_of: List[str] = []        # サブクラス関係
    has_subcategories: bool = False    # サブカテゴリの有無
    subcategory_count: int = 0         # サブカテゴリ数
```

### 2. 主要メソッド

| メソッド | 機能 |
|---------|------|
| `search_categories_by_japanese_label()` | 日本語キーワードで検索 |
| `get_category_details()` | カテゴリの詳細情報取得 |
| `find_subcategories()` | サブカテゴリの階層探索 |
| `_get_direct_subcategories()` | 直接のサブカテゴリ取得 |
| `display_category()` | カテゴリ情報の表示 |
| `save_results()` | JSON形式で保存 |
| `export_to_csv()` | CSV形式で保存 |

## SPARQLクエリの最適化

### バッチ処理

```sparql
# 複数の親カテゴリのサブクラスを一度に取得
SELECT DISTINCT ?item ?parent ?jaLabel ?enLabel
WHERE {
  VALUES ?parent { wd:Q12136 wd:Q12140 wd:Q169872 }
  ?item wdt:P279 ?parent .
  # ラベル取得
}
```

### OPTIONAL句の活用

```sparql
# 日本語ラベルがない場合もエラーにならない
OPTIONAL {
  ?item rdfs:label ?jaLabel .
  FILTER(LANG(?jaLabel) = "ja")
}
```

## エラーハンドリング

### タイムアウト対策

```python
try:
    self.sparql.setTimeout(60)
    results = self.sparql.query().convert()
except Exception as e:
    print(f"Query timeout or error: {e}")
    return []
```

### 循環参照の防止

```python
visited: Set[str] = {qid}

for cat in subcategories:
    if cat.qid not in visited:
        visited.add(cat.qid)
        process(cat)
```

## まとめ

### Wikidataのカテゴリ体系の特徴

1. ✅ **サブカテゴリあり**: P279 (subclass of) で表現
2. ✅ **多階層**: 複数レベルの階層構造
3. ✅ **多言語**: 日本語・英語などの対応ラベル
4. ✅ **多重継承**: 複数の親カテゴリを持てる
5. ✅ **豊富なメタデータ**: 説明文、関連プロパティ

### このツールでできること

- 🔍 日本語キーワードからカテゴリを検索
- 🌐 英語カテゴリとのマッピング
- 📂 サブカテゴリの階層的探索
- 💾 結果のJSON/CSV出力
- 📊 カテゴリ体系の可視化

### 推奨される使い方

1. まず `--search` で興味のあるカテゴリを見つける
2. QIDを確認して `--qid` で詳細探索
3. `--show-subcategories` で階層を理解
4. `--export-csv` で結果を保存・分析
