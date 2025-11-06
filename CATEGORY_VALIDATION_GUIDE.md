# カテゴリ検証と除外機能ガイド

## 概要

Wikidataから医療用語を抽出する際、以下の機能が追加されました：

1. **カテゴリQID検証機能** - 指定したQIDが実際にWikidataカテゴリかを確認
2. **サブカテゴリ除外機能** - 特定のサブカテゴリを結果から除外

## 1. カテゴリQID検証機能

### 機能説明

`config.yaml`で指定したQIDが実際にWikidataの有効なカテゴリ（Q4167836のインスタンス）であるかを確認する機能です。

### 使用方法

```python
from wikidataseekmed_api_optimized import MedicalTermsExtractor, Config

config = Config.from_yaml('config.yaml')
extractor = MedicalTermsExtractor(config)

# カテゴリQIDを検証
is_valid = extractor.validate_category_qid('Q12136')  # disease
print(f"Q12136 is valid category: {is_valid}")  # True

is_valid = extractor.validate_category_qid('Q5')  # human (not a category)
print(f"Q5 is valid category: {is_valid}")  # False
```

### 検証の仕組み

SPARQLクエリを使用してWikidataに問い合わせ：

```sparql
ASK {
  wd:Q12136 wdt:P31 wd:Q4167836 .
}
```

- `wd:Q4167836` = Wikimedia category
- `wdt:P31` = instance of
- 結果: True/False

## 2. サブカテゴリ除外機能

### 問題

例：`Q18123741`（infectious disease）を指定すると、**ヒト以外の感染症**も含まれてしまう。

### 解決策

特定のサブカテゴリを除外リストに追加することで、結果から除外できます。

### config.yamlでの設定

```yaml
# Exclusion lists
exclude_qids:
  Q18123741:  # infectious disease
    - Q82069695  # plant disease (植物の病気を除外)
    - Q2[...]    # animal disease (動物の病気を除外)

  Q12136:  # disease (別の例)
    - Q18965518  # mental disorder (精神疾患を除外したい場合)
```

### 使用例

#### 例1: ヒトの感染症のみ取得

```yaml
categories:
  small:
    Q18123741: "infectious disease"

exclude_qids:
  Q18123741:
    - Q82069695  # plant disease
    - Q5462000   # veterinary disease (動物の病気)
```

実行：
```bash
python wikidataseekmed_api_optimized.py --small --limit 1000 --log logs/human_infectious_only.log
```

出力例：
```
Category: infectious disease (感染症)
  Excluding: 2 sub-categories
  Phase 1: Discovering QIDs via SPARQL...
  Found 850 QIDs (植物・動物の病気を除外)
```

#### 例2: 複数カテゴリで除外

```yaml
exclude_qids:
  Q18123741:  # infectious disease
    - Q82069695  # plant disease

  Q12136:  # disease
    - Q18123741  # infectious disease (別のカテゴリで取得する場合)
    - Q929833    # rare disease (希少疾患を別扱いする場合)

  Q12140:  # medication
    - Q28885102  # veterinary drug (動物用医薬品を除外)
```

### 生成されるSPARQLクエリ

除外リストが設定されると、以下のようなクエリが生成されます：

```sparql
SELECT DISTINCT ?item WHERE {
  ?item wdt:P31/wdt:P279* wd:Q18123741 .

  FILTER NOT EXISTS {
    ?item wdt:P31/wdt:P279* wd:Q82069695 .
  }

  FILTER NOT EXISTS {
    ?item wdt:P31/wdt:P279* wd:Q5462000 .
  }
}
LIMIT 100
OFFSET 0
```

**説明：**
- Q18123741（infectious disease）のインスタンスまたはサブクラスを取得
- ただし、Q82069695（plant disease）のインスタンスまたはサブクラスは除外
- ただし、Q5462000（veterinary disease）のインスタンスまたはサブクラスは除外

## 3. 除外すべきQIDの見つけ方

### 方法1: Wikidata検索

1. https://www.wikidata.org/ にアクセス
2. 除外したいカテゴリ名で検索（例："plant disease"）
3. QIDを確認（例：Q82069695）

### 方法2: 既存データの分析

```bash
# 抽出後のデータを確認
python extract_missing_labels.py output/small_medical_terms_*.csv --missing-type any

# category_enカラムを確認して、不要なサブカテゴリを特定
```

### 方法3: SPARQLクエリで確認

https://query.wikidata.org/ で以下を実行：

```sparql
SELECT ?subclass ?subclassLabel WHERE {
  ?subclass wdt:P279* wd:Q18123741 .  # infectious diseaseのサブクラス
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ja". }
}
LIMIT 100
```

結果から除外したいものを特定。

## 4. 実用例

### 例1: ヒトの感染症のみ

**問題：** Q18123741で植物・動物の感染症も含まれる

**解決：**

```yaml
exclude_qids:
  Q18123741:
    - Q82069695   # plant disease
    - Q5462000    # veterinary disease
    - Q18639649   # fish disease
```

### 例2: 精神疾患を別カテゴリで管理

**問題：** Q12136（disease）に精神疾患も含まれる

**解決：**

```yaml
categories:
  small:
    Q12136: "disease"
    Q18965518: "mental disorder"  # 別途取得

exclude_qids:
  Q12136:
    - Q18965518  # mental disorder (Q12136から除外)
```

### 例3: 先天性疾患と後天性疾患を分離

```yaml
categories:
  medium:
    Q929833: "rare disease"
    Q18123741: "infectious disease"

exclude_qids:
  Q929833:
    - Q18123741  # infectious disease (重複を避ける)
  Q18123741:
    - Q929833    # rare disease (重複を避ける)
```

## 5. トラブルシューティング

### Q: 除外が効いていない

**確認項目：**

1. config.yamlの構文が正しいか
   ```yaml
   exclude_qids:
     Q18123741:  # コロン必須
       - Q82069695  # ハイフンとスペース必須
   ```

2. QIDが正しいか（Qで始まる数字）

3. ログファイルで確認
   ```bash
   grep "Excluding" logs/test.log
   ```

   表示されるべき：
   ```
   Excluding 2 QIDs: ['Q82069695', 'Q5462000']
   ```

### Q: 除外しすぎて結果が少ない

**対策：**

1. 除外リストを確認
   ```yaml
   exclude_qids:
     Q18123741:
       # - Q82069695  # コメントアウトして無効化
   ```

2. 段階的に追加
   - 最初は1つだけ除外
   - 結果を確認してから追加

### Q: カテゴリ検証エラー

```
Failed to validate category Q12136: ...
```

**原因：**
- ネットワークエラー
- SPARQLエンドポイントのタイムアウト

**対策：**
- リトライされるので待つ
- ログを確認して問題を特定

## 6. パフォーマンスへの影響

### 除外フィルタの追加

- **SPARQL クエリの複雑度:** わずかに増加
- **実行時間:** ほぼ変わらず（除外QIDが10個未満の場合）
- **結果数:** 減少（除外した分）

### 測定例

```
除外なし:
  Total queries: 20
  Items collected: 5000
  Time: 120 seconds

除外あり (3 QIDs):
  Total queries: 20
  Items collected: 4500 (10%減少)
  Time: 122 seconds (2秒増加)
```

## 7. ベストプラクティス

### 推奨

✅ 除外リストは最小限に（5個未満推奨）
✅ コメントで除外理由を記載
✅ テスト実行で結果を確認してから本番実行
✅ ログファイルで除外が適用されているか確認

### 非推奨

❌ 大量のQIDを除外（パフォーマンス低下）
❌ 重複するカテゴリを両方取得（データ重複）
❌ テストなしで本番実行

## 8. まとめ

### 新機能

| 機能 | 用途 | 設定場所 |
|------|------|---------|
| カテゴリQID検証 | 無効なQIDを検出 | Pythonコード |
| サブカテゴリ除外 | 不要なサブカテゴリを除外 | config.yaml |

### 活用シーン

1. **ヒト特化データ**: 動物・植物の疾患を除外
2. **カテゴリ分離**: 重複を避けて別々に管理
3. **精密抽出**: 必要な項目のみを取得

### 使用例

```bash
# 1. config.yamlで除外リストを設定
vim config.yaml

# 2. 実行
python wikidataseekmed_api_optimized.py --small --limit 1000 --log logs/test.log

# 3. ログで確認
grep "Excluding" logs/test.log

# 4. 結果を確認
python extract_missing_labels.py output/small_medical_terms_*.csv
```

これで、より精密な医療用語データベースを構築できます！
