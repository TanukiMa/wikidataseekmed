# 改善版クイックスタートガイド

## 新規ファイル

1. **config.yaml** (3.6KB) - 設定ファイル
2. **wikidataseekmed_improved.py** (47KB) - 改善版メインコード
3. **README_improved.md** (6.7KB) - 使い方ガイド
4. **IMPROVEMENTS.md** (11KB) - 改善点詳細説明
5. **requirements.txt** (更新) - PyYAML追加

## セットアップ（初回のみ）

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# または個別に
pip install pandas>=1.3.0 SPARQLWrapper>=2.0.0 pyyaml>=5.4.0
```

## すぐに使う

```bash
# Small scale テスト（推奨）
python wikidataseekmed_improved.py --small --limit 100 --log logs/test.log

# Medium scale
python wikidataseekmed_improved.py --medium --limit 500 --batch-size 300 --log logs/medium.log
```

## 設定のカスタマイズ

`config.yaml`を編集：

```yaml
# 504エラーが出る場合
query:
  batch_size: 200  # デフォルト1000から減らす
  max_retries: 8   # リトライ回数を増やす
  retry_wait_504_base: 20  # 待機時間を長く

# カテゴリを追加
categories:
  small:
    Q12136: "disease"
    Q12345: "your_category"  # 追加
```

## 主な改善点

1. **セキュリティ**: SPARQLインジェクション対策
2. **設定外部化**: config.yamlで簡単カスタマイズ
3. **型安全**: Type hintsで開発時エラー検出
4. **エラー処理**: タイプ別の適切なハンドリング
5. **保守性**: コード重複削減、f-string使用
6. **リソース管理**: pathlib、適切なファイル管理

## トラブルシューティング

### ModuleNotFoundError: No module named 'yaml'
```bash
pip install pyyaml
```

### 504 Gateway Timeout
```bash
# バッチサイズを小さく
python wikidataseekmed_improved.py --small --batch-size 100 --limit 200
```

### config.yamlが見つからない
```bash
# カレントディレクトリに config.yaml があることを確認
ls -la config.yaml

# または明示的に指定
python wikidataseekmed_improved.py --small --config /path/to/config.yaml
```

## 次のステップ

1. README_improved.md - 詳細な使い方
2. IMPROVEMENTS.md - 改善点の技術的詳細
3. config.yaml - 全設定オプションの確認

## 比較: 旧版 vs 改善版

| 実行方法 | 旧版 | 改善版 |
|---------|------|--------|
| 基本実行 | `python wikidataseekmed.py --small --limit 2000` | `python wikidataseekmed_improved.py --small --limit 2000` |
| カスタマイズ | コード編集が必要 | config.yaml編集のみ |
| 設定ファイル | なし | あり（config.yaml） |
| 型安全性 | なし | Type hints完備 |
| セキュリティ | 基本的 | 入力検証・サニタイズ |

---

**推奨**: まず改善版で `--small --limit 100` からテストして、動作確認後に規模を拡大してください。
