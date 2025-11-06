# Missing Labels Extraction Guide

## 概要

`extract_missing_labels.py` は、Wikidataから取得した医療用語データから、英語・日本語ラベルが欠けている項目を抽出するツールです。抽出されたデータは、LLMを使用してラベルを補完する際の入力として使用できます。

## 使用方法

### 基本的な使い方

```bash
# 生成されたCSVからすべての欠損パターンを抽出
python extract_missing_labels.py output/small_medical_terms_api_optimized_20250105_123456.csv
```

### オプション指定

```bash
# 英語ラベルが欠けている項目のみ抽出
python extract_missing_labels.py output/data.csv --missing-type en

# 日本語ラベルが欠けている項目のみ抽出
python extract_missing_labels.py output/data.csv --missing-type ja

# 両方のラベルが欠けている項目のみ抽出
python extract_missing_labels.py output/data.csv --missing-type both

# いずれかのラベルが欠けている項目すべて
python extract_missing_labels.py output/data.csv --missing-type any

# JSON形式で出力
python extract_missing_labels.py output/data.json --format json

# 出力ディレクトリを指定
python extract_missing_labels.py output/data.csv --output-dir llm_input/
```

## 出力ファイル

### 1. 抽出されたデータファイル

ツールは以下のファイルを生成します：

```
missing_labels/
├── input_missing_en_label_20250105_123456.csv      # 英語ラベル欠損
├── input_missing_ja_label_20250105_123456.csv      # 日本語ラベル欠損
├── input_missing_both_labels_20250105_123456.csv   # 両方欠損
├── input_missing_any_label_20250105_123456.csv     # いずれか欠損
├── llm_prompt_template_en_20250105_123456.txt      # LLMプロンプトテンプレート（英語）
├── llm_prompt_template_ja_20250105_123456.txt      # LLMプロンプトテンプレート（日本語）
└── llm_prompt_template_both_20250105_123456.txt    # LLMプロンプトテンプレート（両方）
```

### 2. LLMプロンプトテンプレート

各欠損パターンに対して、LLMでラベルを補完するためのプロンプトテンプレートが生成されます。

**テンプレートの内容例:**

```
================================================================================
LLM Label Filling Prompt Template
================================================================================

Task: Fill missing Japanese labels

Instructions:
1. For each item, provide an appropriate Japanese label
2. Use the English label and description as context
3. Consider the category for domain-specific terminology
4. Use standard Japanese medical terminology

Sample entries (first 5):
================================================================================

Item 1:
  QID: Q12136
  Category: disease (病気)
  EN Label: disease
  JA Label: [MISSING]
  EN Description: abnormal condition negatively affecting organisms
  JA Description: N/A
  External IDs: MeSH: D004194, ICD-10: A00-Z99, UMLS: C0012634

...
```

## 出力統計

実行時に以下の統計情報が表示されます：

```
================================================================================
Missing Label Analysis
================================================================================

Total items: 13427

Missing label patterns:
  English missing: 500 (3.7%)
  Japanese missing: 10557 (78.6%)
  Both missing: 471 (3.5%)
  Any missing: 10586 (78.8%)

Label coverage patterns:
  English only: 10086 (75.1%)
  Japanese only: 29 (0.2%)
  Both present: 2841 (21.2%)

================================================================================
Extracting missing label items...
================================================================================

  en_label: missing_labels/data_missing_en_label_20250105_123456.csv (500 items, 0.12 MB)
  LLM prompt template: missing_labels/llm_prompt_template_en_20250105_123456.txt
  ja_label: missing_labels/data_missing_ja_label_20250105_123456.csv (10557 items, 2.45 MB)
  LLM prompt template: missing_labels/llm_prompt_template_ja_20250105_123456.txt
  both_labels: missing_labels/data_missing_both_labels_20250105_123456.csv (471 items, 0.11 MB)
  LLM prompt template: missing_labels/llm_prompt_template_both_20250105_123456.txt
```

## LLMでラベルを補完する手順

### ステップ1: 欠損項目を抽出

```bash
python extract_missing_labels.py output/small_medical_terms_api_optimized_20250105_123456.csv
```

### ステップ2: LLMプロンプトテンプレートを確認

生成された `llm_prompt_template_*.txt` ファイルを開いて、タスク内容とサンプルを確認します。

### ステップ3: LLMに処理を依頼

#### 方法A: バッチ処理（大量データ向け）

```python
import pandas as pd
import openai  # または他のLLM APIライブラリ

# データを読み込み
df = pd.read_csv('missing_labels/data_missing_ja_label_20250105_123456.csv')

# 各項目に対してLLMでラベルを生成
for idx, row in df.iterrows():
    prompt = f"""
    Please provide a Japanese medical term label for the following item:

    English: {row['en_label']}
    Description: {row['en_description']}
    Category: {row['category_en']}
    External IDs: MeSH={row['mesh_id']}, ICD-10={row['icd10']}

    Provide only the Japanese label without explanation.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    df.at[idx, 'ja_label'] = response.choices[0].message.content.strip()

# 結果を保存
df.to_csv('missing_labels/data_filled_ja_labels.csv', index=False, encoding='utf-8-sig')
```

#### 方法B: 対話的処理（少数データ向け）

1. プロンプトテンプレートをLLM（Claude, ChatGPT等）にコピー
2. サンプルを参考に、残りのデータを処理
3. 結果を元のCSVにマージ

### ステップ4: 元データにマージ

```python
import pandas as pd

# 元のデータ
df_original = pd.read_csv('output/small_medical_terms_api_optimized_20250105_123456.csv')

# 補完されたラベル
df_filled = pd.read_csv('missing_labels/data_filled_ja_labels.csv')

# QIDをキーにマージ
df_merged = df_original.merge(
    df_filled[['qid', 'ja_label']],
    on='qid',
    how='left',
    suffixes=('', '_filled')
)

# 欠けていた部分を補完
df_merged['ja_label'] = df_merged['ja_label'].fillna(df_merged['ja_label_filled'])
df_merged = df_merged.drop(columns=['ja_label_filled'])

# 保存
df_merged.to_csv('output/small_medical_terms_complete.csv', index=False, encoding='utf-8-sig')
```

## 実用例

### 例1: 日本語ラベルを優先的に補完

```bash
# 日本語ラベル欠損項目を抽出
python extract_missing_labels.py output/data.csv --missing-type ja

# → missing_labels/data_missing_ja_label_*.csv が生成される
# → LLMで日本語ラベルを補完
# → 元データにマージ
```

### 例2: カテゴリ別に処理

```python
import pandas as pd

# カテゴリ別にデータを読み込み
df = pd.read_csv('output/by_category_*/disease.csv')

# disease カテゴリの欠損ラベルを抽出
python extract_missing_labels.py output/by_category_*/disease.csv --missing-type ja

# LLMで医学用語に特化した補完を実施
```

## ヒント

### 効率的なLLM処理

1. **バッチサイズを調整**: 一度に10-50項目ずつ処理
2. **外部IDを活用**: MeSH, ICD, SNOMED等のIDを参照情報として提供
3. **カテゴリ別に処理**: 専門用語の一貫性を保つ
4. **人間によるレビュー**: LLMの出力を必ず確認

### データ品質チェック

```python
import pandas as pd

# 補完後のデータを確認
df = pd.read_csv('output/small_medical_terms_complete.csv')

# 欠損が残っていないか確認
en_missing = (df['en_label'] == '') | (df['en_label'].isna())
ja_missing = (df['ja_label'] == '') | (df['ja_label'].isna())

print(f"EN labels missing: {en_missing.sum()}")
print(f"JA labels missing: {ja_missing.sum()}")

# 補完されたラベルの例を確認
print(df[df['ja_label'].notna()].head(10))
```

## トラブルシューティング

### Q: "FileNotFoundError" が発生する

A: 入力ファイルのパスが正しいか確認してください。

```bash
# ファイルの存在確認
ls -l output/*.csv
```

### Q: 出力ファイルが空

A: 入力データに欠損ラベルがない可能性があります。`--missing-type all` で確認してください。

### Q: LLMの出力形式が不適切

A: プロンプトを調整するか、後処理でクリーニングしてください。

```python
# ラベルのクリーニング例
df['ja_label'] = df['ja_label'].str.strip()
df['ja_label'] = df['ja_label'].str.replace(r'^[「『]|[」』]$', '', regex=True)
```

## まとめ

このツールを使用することで：

1. ✅ 欠損ラベルを系統的に抽出
2. ✅ LLMでの補完準備を自動化
3. ✅ データ品質の可視化
4. ✅ 効率的なラベル補完ワークフロー

欠損データを補完することで、より完全な医療用語データベースを構築できます。
