# Supabase Setup Guide

This guide explains how to sync Wikidata medical terms to Supabase using the provided scripts and GitHub Actions workflow.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Supabase Setup](#supabase-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Local Usage](#local-usage)
- [GitHub Actions Usage](#github-actions-usage)
- [Troubleshooting](#troubleshooting)

## Overview

This project provides:
- **`upsert_to_supabase.py`**: Python script to upload CSV/JSON data to Supabase
- **`supabase_schema.sql`**: Database schema for the medical terms table
- **`.github/workflows/sync-to-supabase.yml`**: Automated workflow for periodic syncing

## Prerequisites

1. **Supabase Account**: Sign up at https://supabase.com
2. **Python 3.11+**: For running scripts locally
3. **GitHub Repository**: For automated syncing

## Supabase Setup

### Step 1: Create a Supabase Project

1. Go to https://app.supabase.com
2. Click "New Project"
3. Fill in project details:
   - **Name**: `wikidata-medical-terms` (or your preferred name)
   - **Database Password**: Use a strong password (save it securely)
   - **Region**: Choose closest to your users
4. Click "Create new project" and wait for setup to complete

### Step 2: Create the Database Table

1. In your Supabase project dashboard, go to **SQL Editor**
2. Click "New query"
3. Copy the contents of `supabase_schema.sql` into the editor
4. Click "Run" to execute the SQL

This creates:
- `medical_terms` table with proper schema
- Indexes for fast searching
- Triggers for automatic timestamp updates

### Step 3: Get API Credentials

1. In Supabase dashboard, go to **Settings** → **API**
2. Copy the following:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon/public key**: Starts with `eyJhbG...`

**Security Note**: For production, consider using a **service_role** key instead of anon key for better security. The service_role key bypasses Row Level Security (RLS).

## GitHub Secrets Configuration

### Add Secrets to Your Repository

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click "New repository secret"
4. Add two secrets:

**SUPABASE_URL**
```
https://xxxxx.supabase.co
```

**SUPABASE_KEY**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Local Usage

### Install Dependencies

```bash
pip install -r requirements.txt
pip install supabase
```

### Set Environment Variables

**On Linux/macOS:**
```bash
export SUPABASE_URL='https://xxxxx.supabase.co'
export SUPABASE_KEY='your-anon-or-service-key'
```

**On Windows (PowerShell):**
```powershell
$env:SUPABASE_URL = 'https://xxxxx.supabase.co'
$env:SUPABASE_KEY = 'your-anon-or-service-key'
```

### Run the Uploader

**Upload from CSV:**
```bash
python upsert_to_supabase.py output/small_en_ja_pairs_20251106_123456.csv
```

**Upload from JSON:**
```bash
python upsert_to_supabase.py output/small_medical_terms_full_20251106_123456.json
```

**Dry run (validate without uploading):**
```bash
python upsert_to_supabase.py output/data.csv --dry-run
```

**Custom batch size:**
```bash
python upsert_to_supabase.py output/data.csv --batch-size 50
```

**Custom table name:**
```bash
python upsert_to_supabase.py output/data.csv --table-name my_medical_terms
```

## GitHub Actions Usage

### Manual Trigger

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Select "Sync Medical Terms to Supabase" workflow
4. Click "Run workflow"
5. Select options:
   - **Dataset size**: `small`, `medium`, or `large`
   - **Limit**: Optional number of terms (leave empty for all)
6. Click "Run workflow"

### Automatic Scheduling

The workflow runs automatically every Sunday at 00:00 UTC.

To change the schedule, edit `.github/workflows/sync-to-supabase.yml`:

```yaml
schedule:
  # Run daily at 2:00 AM UTC
  - cron: '0 2 * * *'
```

Cron format: `minute hour day_of_month month day_of_week`

### Workflow Steps

The workflow:
1. Fetches medical terms from Wikidata using `wikidataseekmed_api_optimized.py`
2. Finds the latest generated CSV file
3. Uploads data to Supabase using `upsert_to_supabase.py`
4. Saves CSV and logs as artifacts for debugging

## Database Schema

### Table: `medical_terms`

| Column | Type | Description |
|--------|------|-------------|
| `qid` | TEXT (PK) | Wikidata QID (e.g., Q12136) |
| `en_label` | TEXT | English label/name |
| `ja_label` | TEXT | Japanese label/name |
| `en_description` | TEXT | English description |
| `ja_description` | TEXT | Japanese description |
| `category_en` | TEXT | Category (e.g., "disease") |
| `category_ja` | TEXT | Category in Japanese |
| `mesh_id` | TEXT | MeSH identifier |
| `icd10` | TEXT | ICD-10 code |
| `icd11` | TEXT | ICD-11 code |
| `icd9` | TEXT | ICD-9 code |
| `snomed_id` | TEXT | SNOMED CT identifier |
| `umls_id` | TEXT | UMLS CUI |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

### Upsert Behavior

The script uses `upsert` with `on_conflict='qid'`:
- If a QID already exists → **Update** the record
- If a QID is new → **Insert** a new record

This ensures idempotency: running the script multiple times is safe.

## Example Queries

### Full-Text Search (English)

```sql
SELECT qid, en_label, category_en
FROM medical_terms
WHERE to_tsvector('english', en_label) @@ to_tsquery('english', 'diabetes')
LIMIT 10;
```

### Search by Category

```sql
SELECT qid, en_label, ja_label
FROM medical_terms
WHERE category_en = 'disease'
ORDER BY en_label
LIMIT 20;
```

### Find Terms with ICD-10 Codes

```sql
SELECT qid, en_label, icd10
FROM medical_terms
WHERE icd10 IS NOT NULL
ORDER BY icd10;
```

### Count by Category

```sql
SELECT category_en, COUNT(*) as count
FROM medical_terms
GROUP BY category_en
ORDER BY count DESC;
```

### Recently Updated

```sql
SELECT qid, en_label, updated_at
FROM medical_terms
ORDER BY updated_at DESC
LIMIT 50;
```

## Troubleshooting

### Error: Missing Supabase credentials

**Problem**: `SUPABASE_URL` or `SUPABASE_KEY` not set.

**Solution**:
- For local: Set environment variables (see [Local Usage](#local-usage))
- For GitHub Actions: Add secrets (see [GitHub Secrets Configuration](#github-secrets-configuration))

### Error: Table 'medical_terms' does not exist

**Problem**: Table not created in Supabase.

**Solution**: Run `supabase_schema.sql` in Supabase SQL Editor.

### Error: Could not connect to Supabase

**Problem**: Network issues or incorrect URL.

**Solution**:
- Verify `SUPABASE_URL` is correct (should start with `https://`)
- Check internet connection
- Verify Supabase project is active

### Error: Unauthorized / Invalid API key

**Problem**: Incorrect or expired API key.

**Solution**:
- Get a fresh key from Supabase dashboard → Settings → API
- For production, use `service_role` key instead of `anon` key
- Update GitHub secrets with new key

### Workflow fails with timeout

**Problem**: Dataset too large, workflow exceeds 120 minutes.

**Solution**:
- Use `--limit` parameter to reduce dataset size
- Increase `timeout-minutes` in workflow file
- Split into multiple runs by category

### Partial upload (some records fail)

**Problem**: Invalid data in some records.

**Solution**:
- Check workflow artifacts for error logs
- Run locally with `--dry-run` to validate data
- Review CSV/JSON for missing `qid` fields

## Performance Tips

### Batch Size

Default batch size is 100 records per request. Adjust based on your needs:

- **Larger batches (500-1000)**: Faster for clean data, but all fail if one record is invalid
- **Smaller batches (10-50)**: Slower but more resilient to errors

```bash
python upsert_to_supabase.py data.csv --batch-size 500
```

### Database Indexes

The schema includes indexes for:
- Full-text search (English and Japanese)
- Category filtering
- External ID lookups

These are automatically created by `supabase_schema.sql`.

## Security Best Practices

1. **Use Service Role Key for CI/CD**: More secure than anon key
2. **Enable Row Level Security (RLS)**: Uncomment RLS policies in `supabase_schema.sql`
3. **Rotate Keys Regularly**: Update keys every 90 days
4. **Use GitHub Environments**: For additional approval workflows
5. **Monitor API Usage**: Check Supabase dashboard for unusual activity

## Support

For issues:
- Check the [Troubleshooting](#troubleshooting) section
- Review GitHub Actions logs
- Check Supabase logs in Dashboard → Logs

## License

This setup is part of the wikidataseekmed project.
