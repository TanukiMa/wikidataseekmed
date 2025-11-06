# LLM Translation Guide

This guide explains how to use multiple LLM models to automatically generate Japanese labels for medical terms that only have English labels.

## Overview

The system uses HuggingFace's Inference API to query multiple LLM models in parallel. Each model suggests a Japanese translation, and the system selects the best one using voting, consensus, or confidence-based strategies.

### Architecture

```
┌─────────────────────┐
│  medical_terms      │ ← Terms with en_label but no ja_label
│  (en_label only)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LLM Translation    │
│  Generator          │
│  ┌────────────────┐ │
│  │ Llama-3        │ │ → Suggestion 1
│  │ Mistral        │ │ → Suggestion 2
│  │ Gemma          │ │ → Suggestion 3
│  └────────────────┘ │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  llm_translations   │ ← Store all suggestions
│  (multiple models)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Selection Strategy │
│  • Voting           │ ← Most models agree
│  • Consensus        │ ← Minimum N models agree
│  • Confidence       │ ← Highest confidence score
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  medical_terms      │ ← Update ja_label
│  (ja_label added)   │
└─────────────────────┘
```

## Setup

### 1. Database Schema

Run the LLM translation schema extension:

```bash
# In Supabase SQL Editor, execute:
cat supabase_llm_translation_schema.sql
```

This creates:
- `llm_translations` table: Store translations from each model
- `translation_jobs` table: Track batch translation jobs
- Helper views: `terms_needing_ja_translation`, `translation_consensus`
- Helper functions: `get_best_translation()`, `apply_best_translation()`

### 2. HuggingFace Token

Get a HuggingFace API token:

1. Go to https://huggingface.co/settings/tokens
2. Create a new token (read access is sufficient)
3. Save the token (starts with `hf_`)

### 3. GitHub Secrets

Add to your repository secrets:

```
HF_TOKEN: hf_xxxxxxxxxxxxx
SUPABASE_URL: https://xxxxx.supabase.co
SUPABASE_KEY: your-supabase-key
```

## Usage

### Local Usage

#### Generate Translations

```bash
# Set environment variables
export HF_TOKEN='hf_xxxxx'
export SUPABASE_URL='https://xxxxx.supabase.co'
export SUPABASE_KEY='your-key'

# Generate translations for all terms missing Japanese labels
python generate_ja_labels_with_llm.py

# Limit to first 10 terms
python generate_ja_labels_with_llm.py --limit 10

# Use specific models
python generate_ja_labels_with_llm.py \
  --models "meta-llama/Meta-Llama-3-8B-Instruct" "mistralai/Mistral-7B-Instruct-v0.3"

# Translate a specific QID
python generate_ja_labels_with_llm.py --qid Q12136

# Dry run (don't save to database)
python generate_ja_labels_with_llm.py --limit 5 --skip-save
```

#### Apply Translations

```bash
# Apply using voting strategy (majority wins)
python apply_llm_translations.py --strategy voting

# Apply using consensus (require at least 2 models to agree)
python apply_llm_translations.py --strategy consensus --min-consensus 2

# Apply using confidence scores
python apply_llm_translations.py --strategy confidence

# Dry run (show what would be applied)
python apply_llm_translations.py --strategy voting --dry-run

# Apply to specific QID
python apply_llm_translations.py --qid Q12136 --strategy voting

# Limit number of terms
python apply_llm_translations.py --strategy voting --limit 100
```

### GitHub Actions Usage

#### Run Translation Workflow

1. Go to **Actions** tab in GitHub
2. Select "Generate Japanese Labels with LLMs"
3. Click "Run workflow"
4. Configure parameters:
   - **limit**: Number of terms (leave empty for all)
   - **models**: Space-separated model names
   - **apply_strategy**: voting, consensus, or confidence
   - **min_consensus**: Minimum agreement for consensus
   - **dry_run**: Check this to generate without applying
5. Click "Run workflow"

## Translation Strategies

### 1. Voting (Default)

Selects the translation suggested by the most models.

**Example:**
```
Llama-3:  "糖尿病"
Mistral:  "糖尿病"
Gemma:    "糖尿疾患"

Result: "糖尿病" (2 out of 3 models)
```

**Use when:** You want a democratic approach where majority wins.

### 2. Consensus

Requires a minimum number of models to agree before applying.

**Example (min_consensus=2):**
```
Llama-3:  "糖尿病"
Mistral:  "糖尿病"
Gemma:    "糖尿疾患"

Result: "糖尿病" (2 models agree, meets minimum)
```

**Example (min_consensus=3):**
```
Llama-3:  "糖尿病"
Mistral:  "糖尿病"
Gemma:    "糖尿疾患"

Result: SKIP (no translation has 3 votes)
```

**Use when:** You want high confidence and are willing to skip terms with disagreement.

### 3. Confidence

Selects the translation with the highest confidence score (if available).

**Note:** Not all models provide confidence scores. Falls back to voting if unavailable.

**Use when:** Models provide good confidence scores and you trust them.

## Recommended Models

### Free Tier Models (HuggingFace)

**General Purpose:**
- `meta-llama/Meta-Llama-3-8B-Instruct` - Good multilingual capabilities
- `mistralai/Mistral-7B-Instruct-v0.3` - Strong instruction following
- `google/gemma-2-9b-it` - Good for translations

**Specialized:**
- `microsoft/Phi-3-mini-4k-instruct` - Fast, lightweight
- `HuggingFaceH4/zephyr-7b-beta` - Good reasoning

### Note on Model Availability

Some models may require waiting time if not loaded. The system will skip models that timeout.

## Database Queries

### View Terms Needing Translation

```sql
SELECT * FROM terms_needing_ja_translation
LIMIT 20;
```

### Count Terms by Context Availability

```sql
SELECT
    external_id_count,
    COUNT(*) as term_count
FROM translation_candidates_with_context
GROUP BY external_id_count
ORDER BY external_id_count DESC;
```

### View Translations for a Term

```sql
SELECT
    model_name,
    suggested_ja_label,
    confidence_score,
    generation_time_ms,
    status,
    created_at
FROM llm_translations
WHERE qid = 'Q12136'
ORDER BY created_at;
```

### View Consensus Translations

```sql
SELECT * FROM translation_consensus
WHERE model_count >= 2
LIMIT 20;
```

### Get Best Translation for a Term

```sql
SELECT * FROM get_best_translation('Q12136');
```

### Apply Best Translations (SQL)

```sql
-- Apply best translation to a single term
SELECT apply_best_translation('Q12136');

-- Apply to all terms with translations
SELECT apply_best_translation(qid)
FROM (
    SELECT DISTINCT qid
    FROM llm_translations
    WHERE status != 'rejected'
) AS terms;
```

### View Translation Job History

```sql
SELECT
    id,
    started_at,
    completed_at,
    status,
    models_used,
    total_terms,
    terms_processed,
    translations_generated,
    average_generation_time_ms,
    execution_environment
FROM translation_jobs
ORDER BY started_at DESC
LIMIT 10;
```

### Translation Quality Report

```sql
WITH translation_stats AS (
    SELECT
        qid,
        COUNT(DISTINCT suggested_ja_label) as unique_suggestions,
        COUNT(*) as total_translations,
        ARRAY_AGG(DISTINCT model_name) as models,
        MODE() WITHIN GROUP (ORDER BY suggested_ja_label) as most_common
    FROM llm_translations
    WHERE status != 'rejected'
    GROUP BY qid
)
SELECT
    CASE
        WHEN unique_suggestions = 1 THEN 'Unanimous'
        WHEN unique_suggestions <= total_translations / 2 THEN 'Strong Consensus'
        ELSE 'Disagreement'
    END as agreement_level,
    COUNT(*) as term_count
FROM translation_stats
GROUP BY agreement_level
ORDER BY term_count DESC;
```

## Prompt Engineering

The system builds prompts using:
- English label
- English description (if available)
- Category
- External medical codes (MeSH, ICD-10, ICD-11, SNOMED, UMLS)

**Example Prompt:**
```
You are a medical terminology expert. Translate the following medical term from English to Japanese.

English Term: diabetes mellitus
Category: disease
Description: metabolic disorder characterized by high blood sugar

External Medical Codes:
MeSH ID: D003920
ICD-10: E10-E14
ICD-11: 5A10
SNOMED CT: 73211009
UMLS: C0011849

Provide ONLY the Japanese translation of the term, without any explanation or additional text.
The translation should be:
- Medically accurate
- Commonly used in Japanese medical contexts
- Consistent with the external medical codes provided

Japanese translation:
```

## Cost and Performance

### HuggingFace Free Tier

- **Rate Limits:** Varies by model (typically 100-300 requests/hour)
- **Cost:** Free for public models
- **Latency:** 2-10 seconds per request (varies by model load)

### Estimated Processing Time

- **10 terms × 3 models = 30 requests** → ~1-2 minutes
- **100 terms × 3 models = 300 requests** → ~10-20 minutes
- **1000 terms × 3 models = 3000 requests** → May hit rate limits, run in batches

### Tips for Large Datasets

1. **Use `--limit`** to process in batches
2. **Run overnight** for large datasets
3. **Use fewer models** if time-constrained
4. **Check rate limits** in HuggingFace dashboard

## Troubleshooting

### Model is Loading (503 Error)

**Problem:** Model shows "503: Model is loading"

**Solution:**
- Wait a few minutes and try again
- Use a different model
- Pre-warm the model by visiting its page on HuggingFace

### Rate Limit Exceeded

**Problem:** "429: Too Many Requests"

**Solution:**
- Wait for the rate limit window to reset (usually 1 hour)
- Use fewer models
- Process in smaller batches with `--limit`

### Low Quality Translations

**Problem:** Models generate poor translations

**Solution:**
- Use consensus strategy with `--min-consensus 3`
- Add more context in the prompt (edit `build_prompt()` method)
- Use better models
- Manually review and correct using Supabase dashboard

### Empty Translations

**Problem:** Some models return empty strings

**Solution:**
- Models may not understand the medical term
- Check if external IDs are available (more context = better results)
- Try different models
- Translations are automatically skipped if empty

## Manual Review and Correction

### Review Auto-Generated Labels

```sql
-- View terms with auto-generated labels
SELECT
    qid,
    en_label,
    ja_label,
    ja_label_selected_from,
    ja_label_verified
FROM medical_terms
WHERE ja_label_auto_generated = TRUE
  AND ja_label_verified = FALSE
ORDER BY updated_at DESC
LIMIT 100;
```

### Mark as Verified

```sql
UPDATE medical_terms
SET
    ja_label_verified = TRUE,
    ja_label_verification_date = NOW()
WHERE qid = 'Q12136';
```

### Correct Translation

```sql
UPDATE medical_terms
SET
    ja_label = '正しい日本語訳',
    ja_label_source = 'manual',
    ja_label_verified = TRUE,
    ja_label_verification_date = NOW(),
    ja_label_notes = 'Corrected by human reviewer'
WHERE qid = 'Q12136';
```

### Reject LLM Translation

```sql
-- Mark LLM translation as rejected
UPDATE llm_translations
SET status = 'rejected'
WHERE qid = 'Q12136'
  AND model_name = 'model-that-gave-bad-translation';

-- Revert to no Japanese label
UPDATE medical_terms
SET
    ja_label = NULL,
    ja_label_source = NULL,
    ja_label_selected_from = NULL,
    ja_label_auto_generated = FALSE
WHERE qid = 'Q12136';
```

## Best Practices

1. **Start Small:** Test with `--limit 10` first
2. **Use Consensus:** For critical medical terms, require 2-3 models to agree
3. **Review Results:** Manually verify auto-generated labels before publishing
4. **Track Quality:** Monitor translation_consensus view for disagreements
5. **Provide Context:** Terms with more external IDs get better translations
6. **Iterate:** If results are poor, try different models or adjust prompts

## Advanced Usage

### Custom Prompt Template

Edit `generate_ja_labels_with_llm.py`:

```python
def build_prompt(self, term: Dict[str, Any]) -> str:
    # Your custom prompt logic here
    return custom_prompt
```

### Add Custom Models

```bash
python generate_ja_labels_with_llm.py \
  --models "your-org/your-model" "another-org/another-model"
```

### Batch Processing Script

```bash
#!/bin/bash
# Process 1000 terms in batches of 100

for i in {0..9}; do
    echo "Processing batch $i..."
    python generate_ja_labels_with_llm.py --limit 100
    python apply_llm_translations.py --strategy consensus --min-consensus 2 --limit 100
    sleep 3600  # Wait 1 hour between batches for rate limits
done
```

## Support

For issues:
- Check HuggingFace model status: https://status.huggingface.co
- Review logs in GitHub Actions
- Check Supabase logs for database errors
- Verify API tokens are valid

## References

- HuggingFace Inference API: https://huggingface.co/docs/api-inference/
- Supabase Functions: https://supabase.com/docs/guides/database/functions
- LLM Best Practices: https://platform.openai.com/docs/guides/prompt-engineering
