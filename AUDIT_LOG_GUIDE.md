# Audit Log and Change History Guide

This guide explains how to use the audit log system to track changes to medical terms data in Supabase.

## Overview

The audit system consists of two tables:

1. **`sync_history`** - Tracks each synchronization execution
2. **`audit_log`** - Tracks all changes to individual medical terms records

Changes are automatically logged using PostgreSQL triggers, so you don't need to manually track them.

## Tables

### sync_history Table

Tracks each sync execution from Wikidata to Supabase.

| Column | Description |
|--------|-------------|
| `id` | Unique sync execution ID |
| `sync_started_at` | When the sync started |
| `sync_completed_at` | When the sync completed |
| `status` | running, completed, or failed |
| `dataset_size` | small, medium, or large |
| `source_file` | CSV/JSON filename |
| `total_records` | Total number of records |
| `records_inserted` | Number of records inserted |
| `records_updated` | Number of records updated |
| `records_failed` | Number of records that failed |
| `execution_environment` | github_actions or local |
| `github_run_id` | GitHub Actions run ID |
| `github_actor` | User who triggered the workflow |
| `error_message` | Error message if failed |

### audit_log Table

Tracks all INSERT, UPDATE, and DELETE operations on `medical_terms`.

| Column | Description |
|--------|-------------|
| `id` | Unique audit log ID |
| `qid` | Wikidata QID of changed record |
| `operation` | INSERT, UPDATE, or DELETE |
| `changed_at` | Timestamp of change |
| `changed_fields` | Array of field names that changed |
| `old_values` | Previous values (JSONB) |
| `new_values` | New values (JSONB) |
| `sync_history_id` | Link to sync_history (if applicable) |
| `changed_by` | User/system that made the change |

## Querying the Audit Log

### View Recent Sync Executions

```sql
SELECT
    id,
    sync_started_at,
    sync_completed_at,
    status,
    dataset_size,
    total_records,
    records_inserted,
    records_updated,
    records_failed,
    execution_environment,
    github_actor
FROM sync_history
ORDER BY sync_started_at DESC
LIMIT 20;
```

### View All Changes from Last Sync

```sql
-- Get the most recent sync
SELECT a.qid, a.operation, a.changed_at, a.changed_fields,
       m.en_label, m.ja_label, m.category_en
FROM audit_log a
LEFT JOIN medical_terms m ON a.qid = m.qid
WHERE a.sync_history_id = (
    SELECT id FROM sync_history
    ORDER BY sync_started_at DESC
    LIMIT 1
)
ORDER BY a.changed_at DESC;
```

### View Change History for a Specific Term

```sql
SELECT
    operation,
    changed_at,
    changed_fields,
    old_values,
    new_values,
    sync_history_id
FROM audit_log
WHERE qid = 'Q12136'  -- Replace with your QID
ORDER BY changed_at DESC;
```

### View Recent Changes (All Terms)

```sql
SELECT
    a.qid,
    a.operation,
    a.changed_at,
    a.changed_fields,
    m.en_label,
    m.category_en
FROM audit_log a
LEFT JOIN medical_terms m ON a.qid = m.qid
ORDER BY a.changed_at DESC
LIMIT 100;
```

### Count Changes by Operation Type

```sql
SELECT
    operation,
    COUNT(*) as count
FROM audit_log
GROUP BY operation
ORDER BY count DESC;
```

### Find Terms with Most Updates

```sql
SELECT
    qid,
    COUNT(*) as update_count,
    MAX(changed_at) as last_updated
FROM audit_log
WHERE operation = 'UPDATE'
GROUP BY qid
ORDER BY update_count DESC
LIMIT 20;
```

### View Changes in Specific Time Range

```sql
SELECT
    a.qid,
    a.operation,
    a.changed_at,
    a.changed_fields,
    m.en_label
FROM audit_log a
LEFT JOIN medical_terms m ON a.qid = m.qid
WHERE a.changed_at >= NOW() - INTERVAL '7 days'
ORDER BY a.changed_at DESC;
```

### View Failed Syncs

```sql
SELECT
    id,
    sync_started_at,
    dataset_size,
    total_records,
    records_failed,
    error_message,
    github_run_id
FROM sync_history
WHERE status = 'failed'
ORDER BY sync_started_at DESC;
```

### Compare Values Before and After Update

```sql
SELECT
    qid,
    changed_at,
    changed_fields,
    old_values->>'en_label' as old_en_label,
    new_values->>'en_label' as new_en_label,
    old_values->>'icd10' as old_icd10,
    new_values->>'icd10' as new_icd10
FROM audit_log
WHERE operation = 'UPDATE'
  AND 'en_label' = ANY(changed_fields)
ORDER BY changed_at DESC
LIMIT 20;
```

### Sync Performance Statistics

```sql
SELECT
    DATE(sync_started_at) as sync_date,
    COUNT(*) as sync_count,
    SUM(total_records) as total_records,
    SUM(records_inserted) as total_inserted,
    SUM(records_updated) as total_updated,
    AVG(EXTRACT(EPOCH FROM (sync_completed_at - sync_started_at))) as avg_duration_seconds
FROM sync_history
WHERE status = 'completed'
GROUP BY DATE(sync_started_at)
ORDER BY sync_date DESC;
```

## Creating a Public API View

If you want to expose change history via an API, create a view with RLS:

```sql
-- Create a read-only view for external access
CREATE OR REPLACE VIEW public_change_history AS
SELECT
    a.qid,
    a.operation,
    a.changed_at,
    a.changed_fields,
    m.en_label,
    m.ja_label,
    m.category_en,
    m.category_ja
FROM audit_log a
LEFT JOIN medical_terms m ON a.qid = m.qid
WHERE a.changed_at >= NOW() - INTERVAL '30 days'  -- Last 30 days only
ORDER BY a.changed_at DESC;

-- Allow public read access to the view
ALTER VIEW public_change_history SET (security_invoker = true);
GRANT SELECT ON public_change_history TO anon, authenticated;
```

Then query via Supabase client:

```javascript
const { data, error } = await supabase
  .from('public_change_history')
  .select('*')
  .limit(100);
```

## Creating a Sync Summary View

```sql
CREATE OR REPLACE VIEW sync_summary AS
SELECT
    sh.id,
    sh.sync_started_at,
    sh.sync_completed_at,
    sh.status,
    sh.dataset_size,
    sh.total_records,
    sh.records_inserted,
    sh.records_updated,
    sh.records_failed,
    sh.execution_environment,
    sh.github_actor,
    COUNT(DISTINCT a.qid) as unique_terms_changed,
    EXTRACT(EPOCH FROM (sh.sync_completed_at - sh.sync_started_at)) as duration_seconds
FROM sync_history sh
LEFT JOIN audit_log a ON a.sync_history_id = sh.id
GROUP BY sh.id
ORDER BY sh.sync_started_at DESC;

GRANT SELECT ON sync_summary TO anon, authenticated;
```

Query this view:

```sql
SELECT * FROM sync_summary
WHERE status = 'completed'
ORDER BY sync_started_at DESC
LIMIT 10;
```

## Monitoring via Supabase Dashboard

### Enable Real-time for audit_log

1. Go to Supabase Dashboard → Database → Replication
2. Enable replication for `audit_log` table
3. Subscribe to changes in your application:

```javascript
const subscription = supabase
  .channel('audit-changes')
  .on('postgres_changes',
    { event: 'INSERT', schema: 'public', table: 'audit_log' },
    (payload) => {
      console.log('New change detected:', payload.new);
    }
  )
  .subscribe();
```

### Create Dashboard Queries

Save these queries in Supabase SQL Editor for quick access:

**Recent Activity (Last 24h)**
```sql
SELECT COUNT(*) as total_changes,
       COUNT(DISTINCT qid) as unique_terms,
       COUNT(CASE WHEN operation = 'INSERT' THEN 1 END) as inserts,
       COUNT(CASE WHEN operation = 'UPDATE' THEN 1 END) as updates,
       COUNT(CASE WHEN operation = 'DELETE' THEN 1 END) as deletes
FROM audit_log
WHERE changed_at >= NOW() - INTERVAL '24 hours';
```

**Latest Sync Status**
```sql
SELECT
    sync_started_at,
    status,
    total_records,
    records_inserted + records_updated as successful,
    records_failed,
    ROUND(100.0 * (records_inserted + records_updated) / NULLIF(total_records, 0), 2) as success_rate
FROM sync_history
ORDER BY sync_started_at DESC
LIMIT 1;
```

## Cleanup Old Audit Logs

To prevent the audit_log table from growing too large, you can periodically clean up old records:

```sql
-- Delete audit logs older than 90 days
DELETE FROM audit_log
WHERE changed_at < NOW() - INTERVAL '90 days';

-- Or keep only the last 1 million records
DELETE FROM audit_log
WHERE id NOT IN (
    SELECT id FROM audit_log
    ORDER BY changed_at DESC
    LIMIT 1000000
);
```

Consider setting up a scheduled function (using pg_cron or Supabase Edge Functions) to run this periodically.

## Best Practices

1. **Regular Monitoring**: Check sync_history regularly to ensure syncs are completing successfully

2. **Alert on Failures**: Set up alerts for failed syncs:
   ```sql
   SELECT * FROM sync_history
   WHERE status = 'failed'
   AND sync_started_at >= NOW() - INTERVAL '1 day';
   ```

3. **Track Specific Terms**: For important terms, create a saved query to monitor changes

4. **Archive Old Logs**: Move old audit_log records to cold storage after 90 days

5. **Index Performance**: The schema includes indexes, but add custom indexes if needed:
   ```sql
   CREATE INDEX idx_audit_log_custom
   ON audit_log(qid, changed_at DESC)
   WHERE operation = 'UPDATE';
   ```

## Example: External API for Change Feed

Create a Supabase Edge Function to expose recent changes:

```typescript
// supabase/functions/change-feed/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
  )

  // Get recent changes
  const { data, error } = await supabase
    .from('audit_log')
    .select(`
      qid,
      operation,
      changed_at,
      changed_fields,
      medical_terms (en_label, ja_label, category_en)
    `)
    .order('changed_at', { ascending: false })
    .limit(100)

  if (error) throw error

  return new Response(JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json' },
  })
})
```

Deploy and access: `https://your-project.supabase.co/functions/v1/change-feed`

## Support

For issues with the audit log system:
- Check PostgreSQL trigger is enabled: `\d+ medical_terms` in SQL Editor
- Verify tables exist: `\dt` to list all tables
- Check for errors in sync_history table's error_message column
