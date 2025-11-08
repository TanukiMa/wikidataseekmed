# Supabase データ管理設計

連日実行してデータを管理する場合の推奨設計パターン

## 1. データベーススキーマ設計

### パターンA: シンプル（単一テーブル + UPSERT）

**推奨度: ⭐⭐⭐⭐⭐**（小〜中規模データ向け）

```sql
-- メインテーブル
CREATE TABLE medical_terms (
    qid TEXT PRIMARY KEY,  -- Q12136 など
    en_label TEXT,
    ja_label TEXT,
    en_description TEXT,
    category_en TEXT,
    category_ja TEXT,
    category_qid TEXT,
    mesh_id TEXT,
    icd_10 TEXT,
    icd_11 TEXT,
    snomed_ct TEXT,
    umls_cui TEXT,

    -- メタデータ
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    update_count INTEGER DEFAULT 1,

    -- 変更検出用
    data_hash TEXT  -- データのハッシュ値（変更検出）
);

-- インデックス
CREATE INDEX idx_category ON medical_terms(category_en);
CREATE INDEX idx_updated ON medical_terms(last_updated_at);
CREATE INDEX idx_labels ON medical_terms(en_label, ja_label);
```

**運用方法:**
```python
# UPSERT: 既存なら更新、なければ挿入
INSERT INTO medical_terms (qid, en_label, ja_label, ...)
VALUES ('Q12136', 'diabetes', '糖尿病', ...)
ON CONFLICT (qid)
DO UPDATE SET
    en_label = EXCLUDED.en_label,
    ja_label = EXCLUDED.ja_label,
    last_updated_at = NOW(),
    update_count = medical_terms.update_count + 1,
    data_hash = EXCLUDED.data_hash
WHERE medical_terms.data_hash != EXCLUDED.data_hash;  -- 変更があった場合のみ
```

**メリット:**
- シンプル
- パフォーマンス良好
- 運用が簡単

**デメリット:**
- 変更履歴が残らない

---

### パターンB: 履歴管理（メインテーブル + 履歴テーブル）

**推奨度: ⭐⭐⭐⭐**（変更追跡が重要な場合）

```sql
-- メインテーブル（現在の状態）
CREATE TABLE medical_terms (
    qid TEXT PRIMARY KEY,
    en_label TEXT,
    ja_label TEXT,
    en_description TEXT,
    category_en TEXT,
    category_ja TEXT,
    category_qid TEXT,
    mesh_id TEXT,
    icd_10 TEXT,
    icd_11 TEXT,
    snomed_ct TEXT,
    umls_cui TEXT,

    -- メタデータ
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1
);

-- 変更履歴テーブル
CREATE TABLE medical_terms_history (
    id BIGSERIAL PRIMARY KEY,
    qid TEXT NOT NULL,

    -- 変更内容
    change_type TEXT,  -- 'INSERT', 'UPDATE', 'DELETE'
    changed_fields JSONB,  -- 変更されたフィールドのみ
    old_values JSONB,  -- 変更前の値
    new_values JSONB,  -- 変更後の値

    -- メタデータ
    changed_at TIMESTAMP DEFAULT NOW(),
    batch_id TEXT  -- 実行バッチID（日付など）
);

-- インデックス
CREATE INDEX idx_history_qid ON medical_terms_history(qid);
CREATE INDEX idx_history_batch ON medical_terms_history(batch_id);
CREATE INDEX idx_history_date ON medical_terms_history(changed_at);
```

**運用方法:**
```python
# 1. 変更検出
old_data = SELECT * FROM medical_terms WHERE qid = 'Q12136'
new_data = {...}  # Wikidataから取得

# 2. 差分検出
if old_data != new_data:
    # 3. 履歴に記録
    INSERT INTO medical_terms_history (qid, change_type, old_values, new_values, batch_id)
    VALUES ('Q12136', 'UPDATE', old_data::jsonb, new_data::jsonb, '2025-11-08')

    # 4. メインテーブル更新
    UPDATE medical_terms SET ... WHERE qid = 'Q12136'
```

**メリット:**
- 完全な変更履歴
- 監査可能
- ロールバック可能

**デメリット:**
- ストレージ使用量増加
- 実装がやや複雑

---

### パターンC: タイムスタンプスナップショット

**推奨度: ⭐⭐⭐**（完全な履歴が必要な場合）

```sql
-- スナップショットテーブル（日付ごとの全データ）
CREATE TABLE medical_terms_snapshots (
    qid TEXT,
    snapshot_date DATE,  -- 実行日
    en_label TEXT,
    ja_label TEXT,
    en_description TEXT,
    category_en TEXT,
    mesh_id TEXT,
    icd_10 TEXT,

    -- メタデータ
    captured_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (qid, snapshot_date)
);

-- 最新ビュー
CREATE VIEW medical_terms_latest AS
SELECT DISTINCT ON (qid) *
FROM medical_terms_snapshots
ORDER BY qid, snapshot_date DESC;
```

**運用方法:**
```python
# 毎日全データを新しいスナップショットとして保存
for term in extracted_terms:
    INSERT INTO medical_terms_snapshots (qid, snapshot_date, ...)
    VALUES ('Q12136', '2025-11-08', ...)
```

**メリット:**
- 任意の日付のデータを参照可能
- シンプル

**デメリット:**
- ストレージ使用量が最大
- 変更がなくても全件保存

---

## 2. 推奨実装パターン

### 🏆 推奨: パターンB（メイン + 履歴）のハイブリッド

```sql
-- === 1. メインテーブル（現在の状態） ===
CREATE TABLE medical_terms (
    qid TEXT PRIMARY KEY,

    -- ラベル
    en_label TEXT,
    ja_label TEXT,
    en_description TEXT,
    ja_description TEXT,

    -- カテゴリ
    category_en TEXT,
    category_ja TEXT,
    category_qid TEXT,

    -- 外部ID
    mesh_id TEXT,
    icd_10 TEXT,
    icd_11 TEXT,
    icd_9 TEXT,
    snomed_ct TEXT,
    umls_cui TEXT,

    -- メタデータ
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    last_checked_at TIMESTAMP DEFAULT NOW(),  -- 最終確認日時
    update_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,  -- データが現在も有効か

    -- 変更検出
    data_hash TEXT  -- MD5(全フィールド)
);

-- === 2. 変更履歴テーブル ===
CREATE TABLE change_history (
    id BIGSERIAL PRIMARY KEY,
    qid TEXT NOT NULL REFERENCES medical_terms(qid),

    -- 変更内容
    change_type TEXT CHECK (change_type IN ('INSERT', 'UPDATE', 'DELETE', 'NO_CHANGE')),
    changed_fields TEXT[],  -- ['en_label', 'ja_label']

    -- 変更値（JSONBで柔軟に）
    before_data JSONB,
    after_data JSONB,

    -- バッチ情報
    batch_id TEXT NOT NULL,  -- 'daily_2025-11-08'
    batch_run_at TIMESTAMP DEFAULT NOW(),

    -- メタデータ
    created_at TIMESTAMP DEFAULT NOW()
);

-- === 3. 実行ログテーブル ===
CREATE TABLE extraction_runs (
    batch_id TEXT PRIMARY KEY,  -- 'daily_2025-11-08'

    -- 実行情報
    run_started_at TIMESTAMP DEFAULT NOW(),
    run_completed_at TIMESTAMP,
    status TEXT CHECK (status IN ('running', 'completed', 'failed')),

    -- 統計
    total_items_processed INTEGER,
    items_inserted INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    items_unchanged INTEGER DEFAULT 0,
    items_deleted INTEGER DEFAULT 0,

    -- エラー
    error_message TEXT,

    -- 設定
    config JSONB  -- 実行時のconfig.yaml
);

-- === 4. インデックス ===
CREATE INDEX idx_medical_category ON medical_terms(category_en);
CREATE INDEX idx_medical_updated ON medical_terms(last_updated_at);
CREATE INDEX idx_medical_active ON medical_terms(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_history_qid ON change_history(qid);
CREATE INDEX idx_history_batch ON change_history(batch_id);
CREATE INDEX idx_history_type ON change_history(change_type);
```

---

## 3. Python実装例

### データ取得 → Supabase保存の流れ

```python
import hashlib
import json
from datetime import datetime
from supabase import create_client, Client

class SupabaseMedicalTermsManager:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.batch_id = f"daily_{datetime.now().strftime('%Y-%m-%d')}"

    def calculate_hash(self, term_data: dict) -> str:
        """データのハッシュ値を計算（変更検出用）"""
        # 重要なフィールドのみでハッシュ生成
        hash_fields = {
            'en_label': term_data.get('en_label'),
            'ja_label': term_data.get('ja_label'),
            'en_description': term_data.get('en_description'),
            'mesh_id': term_data.get('mesh_id'),
            'icd_10': term_data.get('icd_10'),
        }
        hash_str = json.dumps(hash_fields, sort_keys=True)
        return hashlib.md5(hash_str.encode()).hexdigest()

    def start_batch(self, config: dict):
        """バッチ実行開始"""
        self.supabase.table('extraction_runs').insert({
            'batch_id': self.batch_id,
            'status': 'running',
            'config': config
        }).execute()

    def process_term(self, term_data: dict) -> str:
        """1件のデータを処理（UPSERT + 履歴記録）"""
        qid = term_data['qid']
        new_hash = self.calculate_hash(term_data)

        # 1. 既存データを取得
        existing = self.supabase.table('medical_terms').select('*').eq('qid', qid).execute()

        if not existing.data:
            # === 新規挿入 ===
            term_data['data_hash'] = new_hash
            term_data['first_seen_at'] = datetime.now().isoformat()
            term_data['last_updated_at'] = datetime.now().isoformat()
            term_data['last_checked_at'] = datetime.now().isoformat()

            self.supabase.table('medical_terms').insert(term_data).execute()

            # 履歴記録
            self.supabase.table('change_history').insert({
                'qid': qid,
                'change_type': 'INSERT',
                'changed_fields': list(term_data.keys()),
                'after_data': term_data,
                'batch_id': self.batch_id
            }).execute()

            return 'INSERT'
        else:
            old_data = existing.data[0]
            old_hash = old_data.get('data_hash')

            if old_hash != new_hash:
                # === 更新 ===
                changed_fields = []
                before_data = {}
                after_data = {}

                for key in term_data.keys():
                    if term_data.get(key) != old_data.get(key):
                        changed_fields.append(key)
                        before_data[key] = old_data.get(key)
                        after_data[key] = term_data.get(key)

                # メインテーブル更新
                term_data['data_hash'] = new_hash
                term_data['last_updated_at'] = datetime.now().isoformat()
                term_data['last_checked_at'] = datetime.now().isoformat()
                term_data['update_count'] = old_data.get('update_count', 0) + 1

                self.supabase.table('medical_terms').update(term_data).eq('qid', qid).execute()

                # 履歴記録
                self.supabase.table('change_history').insert({
                    'qid': qid,
                    'change_type': 'UPDATE',
                    'changed_fields': changed_fields,
                    'before_data': before_data,
                    'after_data': after_data,
                    'batch_id': self.batch_id
                }).execute()

                return 'UPDATE'
            else:
                # === 変更なし ===
                # last_checked_at のみ更新
                self.supabase.table('medical_terms').update({
                    'last_checked_at': datetime.now().isoformat()
                }).eq('qid', qid).execute()

                return 'NO_CHANGE'

    def complete_batch(self, stats: dict):
        """バッチ実行完了"""
        self.supabase.table('extraction_runs').update({
            'status': 'completed',
            'run_completed_at': datetime.now().isoformat(),
            'total_items_processed': stats['total'],
            'items_inserted': stats['inserted'],
            'items_updated': stats['updated'],
            'items_unchanged': stats['unchanged']
        }).eq('batch_id', self.batch_id).execute()

    def mark_deleted_items(self, current_qids: list):
        """今回取得されなかったアイテムを無効化"""
        # 過去にあったが今回なかったアイテム
        all_qids = self.supabase.table('medical_terms').select('qid').execute()
        existing_qids = {row['qid'] for row in all_qids.data}
        deleted_qids = existing_qids - set(current_qids)

        for qid in deleted_qids:
            self.supabase.table('medical_terms').update({
                'is_active': False,
                'last_checked_at': datetime.now().isoformat()
            }).eq('qid', qid).execute()

            self.supabase.table('change_history').insert({
                'qid': qid,
                'change_type': 'DELETE',
                'batch_id': self.batch_id
            }).execute()

# === 使用例 ===
def main():
    # 1. データ抽出
    df = extract_medical_terms()  # wikidataseekmed.py の処理

    # 2. Supabase管理開始
    manager = SupabaseMedicalTermsManager(
        supabase_url='https://xxx.supabase.co',
        supabase_key='your-key'
    )

    # 3. バッチ開始
    manager.start_batch(config={'scale': 'small', 'limit': 0})

    # 4. 各データを処理
    stats = {'total': 0, 'inserted': 0, 'updated': 0, 'unchanged': 0}
    current_qids = []

    for _, row in df.iterrows():
        term_data = row.to_dict()
        result = manager.process_term(term_data)

        stats['total'] += 1
        stats[result.lower()] += 1
        current_qids.append(term_data['qid'])

    # 5. 削除検出
    manager.mark_deleted_items(current_qids)

    # 6. バッチ完了
    manager.complete_batch(stats)

    print(f"Batch {manager.batch_id} completed:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Unchanged: {stats['unchanged']}")
```

---

## 4. 便利なクエリ例

### 変更履歴の確認

```sql
-- 最近の変更一覧
SELECT
    qid,
    change_type,
    changed_fields,
    batch_id,
    created_at
FROM change_history
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- 特定のQIDの変更履歴
SELECT
    qid,
    change_type,
    before_data->>'en_label' as old_label,
    after_data->>'en_label' as new_label,
    batch_id,
    created_at
FROM change_history
WHERE qid = 'Q12136'
ORDER BY created_at DESC;

-- ラベルが変更されたアイテム
SELECT DISTINCT qid, batch_id
FROM change_history
WHERE 'en_label' = ANY(changed_fields)
  AND created_at > NOW() - INTERVAL '30 days';
```

### 統計分析

```sql
-- バッチ実行サマリー
SELECT
    batch_id,
    run_started_at,
    run_completed_at,
    items_inserted,
    items_updated,
    items_unchanged,
    total_items_processed
FROM extraction_runs
ORDER BY run_started_at DESC
LIMIT 10;

-- カテゴリ別データ数
SELECT
    category_en,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_count
FROM medical_terms
GROUP BY category_en
ORDER BY count DESC;

-- 最近更新されたアイテム
SELECT
    qid,
    en_label,
    ja_label,
    category_en,
    last_updated_at,
    update_count
FROM medical_terms
WHERE last_updated_at > NOW() - INTERVAL '7 days'
ORDER BY last_updated_at DESC;
```

---

## 5. 運用フロー

### 日次実行の推奨フロー

```bash
#!/bin/bash
# daily_extraction.sh

DATE=$(date +%Y-%m-%d)
LOG_FILE="logs/extraction_${DATE}.log"

echo "=== Starting daily extraction: $DATE ===" | tee -a $LOG_FILE

# 1. データ抽出
python wikidataseekmed.py --small --limit 0 2>&1 | tee -a $LOG_FILE

# 2. Supabaseへアップロード
python upload_to_supabase.py \
    --input "output/small_medical_terms_*.json" \
    --batch-id "daily_${DATE}" \
    2>&1 | tee -a $LOG_FILE

# 3. 統計レポート生成
python generate_stats_report.py \
    --batch-id "daily_${DATE}" \
    --output "reports/report_${DATE}.html" \
    2>&1 | tee -a $LOG_FILE

echo "=== Completed: $DATE ===" | tee -a $LOG_FILE
```

### Cron設定例

```cron
# 毎日午前2時に実行
0 2 * * * /home/user/wikidataseekmed/daily_extraction.sh
```

---

## 6. パフォーマンス最適化

### バッチUPSERT（高速化）

```python
def batch_upsert(self, terms: list, batch_size=100):
    """バッチでUPSERTを実行（高速）"""
    for i in range(0, len(terms), batch_size):
        batch = terms[i:i+batch_size]

        # Supabaseのupsert機能を使用
        self.supabase.table('medical_terms').upsert(
            batch,
            on_conflict='qid'  # qidが重複した場合は更新
        ).execute()
```

### インデックス最適化

```sql
-- 頻繁に検索するフィールドにインデックス
CREATE INDEX idx_medical_en_label ON medical_terms USING gin(en_label gin_trgm_ops);
CREATE INDEX idx_medical_ja_label ON medical_terms USING gin(ja_label gin_trgm_ops);

-- 部分インデックス（アクティブなデータのみ）
CREATE INDEX idx_medical_active_category
    ON medical_terms(category_en)
    WHERE is_active = TRUE;
```

---

## 7. まとめ

### ✅ 推奨構成

1. **メインテーブル**: 現在の状態を保存
2. **変更履歴テーブル**: 全ての変更を記録
3. **実行ログテーブル**: バッチ実行の統計
4. **ハッシュベース変更検出**: 効率的な差分検出
5. **UPSERT**: 追加・更新を統一処理
6. **is_active フラグ**: 論理削除

### 📊 メリット

- ✅ 完全な監査証跡
- ✅ 任意の時点へのロールバック可能
- ✅ 変更傾向の分析が可能
- ✅ パフォーマンス良好
- ✅ 運用が簡単

### 🎯 次のステップ

1. Supabaseプロジェクト作成
2. スキーマ実装（上記SQL実行）
3. Python実装（SupabaseMedicalTermsManager）
4. テスト実行
5. 日次cron設定
