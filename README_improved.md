# Wikidata Medical Terms Extractor - 改善版

## 概要
WikidataからEN-JA医療用語ペアを抽出するツールの改善版です。

## 主な改善点

### 1. **セキュリティの向上**
- SPARQLクエリのパラメータ化によるインジェクション対策
- QID形式の検証
- キーワードのサニタイズ

### 2. **リソース管理**
- ファイルハンドラの適切な管理
- pathlib使用による安全なパス操作
- メモリ効率の改善

### 3. **設定の外部化**
- YAML設定ファイルによる柔軟な設定管理
- カテゴリ、タイムアウト、リトライ回数を簡単に変更可能

### 4. **型安全性**
- Type hintsの追加
- Dataclassによる構造化されたデータ管理

### 5. **エラーハンドリング**
- エラータイプ別の適切な処理
- リトライロジックの統合
- 詳細なエラーログ

### 6. **コードの保守性**
- 重複コードの削減
- 関数の単一責任原則
- f-string使用による可読性向上

### 7. **パフォーマンス**
- 指数バックオフによる効率的なリトライ
- 適切な待機時間の設定

## インストール

```bash
pip install -r requirements.txt
```

## 設定ファイル

`config.yaml`で以下を設定できます：

- **API設定**: エンドポイント、タイムアウト
- **クエリ設定**: バッチサイズ、リトライ回数、待機時間
- **カテゴリ定義**: small/medium/largeの各カテゴリ
- **日本語名マッピング**: カテゴリの日本語名
- **出力設定**: 保存するファイル形式

### config.yamlの例

```yaml
api:
  endpoint: "https://query.wikidata.org/sparql"
  timeout: 600

query:
  batch_size: 1000
  max_retries: 5
  retry_wait_504_base: 10  # 504エラー時の基本待機秒数

categories:
  small:
    Q12136: "disease"
    Q12140: "medication"
    # ...

output:
  save_full_csv: true
  save_bilingual_csv: true
```

## 使用方法

### 基本的な実行

```bash
# Small scale (5カテゴリ)
python wikidataseekmed_improved.py --small --limit 2000 --log logs/small.log

# Medium scale (15カテゴリ)
python wikidataseekmed_improved.py --medium --limit 5000 --batch-size 500 --log logs/medium.log

# Large scale (30+カテゴリ)
python wikidataseekmed_improved.py --large --limit 0 --log logs/large.log
```

### カテゴリ発見モード

```bash
# カテゴリを発見してから抽出
python wikidataseekmed_improved.py --small --discover --limit 1000 --log logs/discover.log

# カテゴリ発見のみ（抽出しない）
python wikidataseekmed_improved.py --medium --discover-only --discover-limit 200
```

### カスタム設定ファイルの使用

```bash
python wikidataseekmed_improved.py --small --config my_config.yaml --log logs/test.log
```

### 504タイムアウトエラーが発生する場合

```bash
# バッチサイズを小さくする
python wikidataseekmed_improved.py --small --limit 1000 --batch-size 200 --log logs/safe.log

# さらに小さく
python wikidataseekmed_improved.py --medium --limit 500 --batch-size 100 --log logs/safer.log
```

## コマンドラインオプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--small` | Small scale (5カテゴリ) | - |
| `--medium` | Medium scale (15カテゴリ) | - |
| `--large` | Large scale (30+カテゴリ) | - |
| `--config` | 設定ファイルのパス | config.yaml |
| `--limit` | カテゴリごとの最大アイテム数 (0=無制限) | 2000 |
| `--batch-size` | クエリごとのアイテム数 | 設定ファイルから |
| `--log` | ログファイルのパス | None |
| `--discover` | 抽出前にカテゴリを発見 | False |
| `--discover-only` | カテゴリ発見のみ（抽出しない） | False |
| `--discover-limit` | 発見するカテゴリの最大数 | 設定ファイルから |

## 出力ファイル

`output/`ディレクトリに以下が生成されます：

1. **完全なCSV**: 全データ（`{prefix}_medical_terms_full_{timestamp}.csv`）
2. **EN-JAペアCSV**: 英日バイリンガルペアのみ（`{prefix}_en_ja_pairs_{timestamp}.csv`）
3. **カテゴリ別CSV**: カテゴリごとのファイル（`by_category_{timestamp}/`）
4. **JSON**: 全データのJSON形式（`{prefix}_medical_terms_{timestamp}.json`）
5. **レポート**: 統計情報（`{prefix}_report_{timestamp}.txt`）

## トラブルシューティング

### 504 Gateway Timeout エラー

**原因**: クエリが複雑すぎるか、サーバーが過負荷

**解決策**:
1. `--batch-size`を減らす（100-300を試す）
2. `--limit`を減らす
3. `config.yaml`の`retry_wait_504_base`を増やす
4. Wikidataダンプの使用を検討: https://dumps.wikimedia.org/wikidatawiki/entities/

### ネットワークエラー

**解決策**:
1. インターネット接続を確認
2. `config.yaml`の`max_retries`を増やす
3. `api.timeout`を増やす

### メモリ不足

**解決策**:
1. `--limit`を減らす
2. カテゴリを分割して実行

## 設定のカスタマイズ例

### 504エラーが頻発する環境向け

```yaml
query:
  batch_size: 200  # デフォルト1000から減少
  max_retries: 8   # リトライ回数を増加
  retry_wait_504_base: 20  # 待機時間を増加
  retry_wait_max: 900  # 最大待機時間を15分に
```

### 高速ネットワーク環境向け

```yaml
query:
  batch_size: 2000
  wait_between_batches: 0.5  # 待機時間を短縮
  wait_between_categories: 1
```

## ログファイル

ログファイルには以下が記録されます：

- 実行されたSPARQLクエリ
- レスポンス詳細
- エラーとスタックトレース
- リトライ情報
- 統計情報

ログレベル:
- **DEBUG**: 全詳細（ファイルのみ）
- **INFO**: 一般情報（ファイルのみ）
- **ERROR**: エラー（ファイルとコンソール）

## データ品質分析

実行後、以下の品質分析が表示されます：

1. 基本統計（総レコード数、ユニークQID数）
2. 言語カバレッジ（英語・日本語ラベルの割合）
3. 説明文カバレッジ
4. 外部IDカバレッジ（MeSH, ICD-10, SNOMED CT等）
5. カテゴリ別アイテム数
6. EN-JAバイリンガルペア数

## ライセンス

Wikidataのデータは CC0 ライセンスです。
このツール自体のライセンスは、元のコードの著作権者に従います。

## 変更履歴

### v2.0 (Improved版)
- YAML設定ファイルのサポート
- Type hints追加
- セキュリティ改善（クエリパラメータ化）
- エラーハンドリングの改善
- コードの重複削減
- リソース管理の改善
- pathlib使用
- f-string使用
- dataclass使用

### v1.0 (オリジナル)
- 基本機能の実装
