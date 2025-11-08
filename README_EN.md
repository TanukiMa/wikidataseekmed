# WikidataSeekMed

A toolkit for extracting medical terms from Wikidata and generating bilingual (English-Japanese) dictionaries

## Overview

WikidataSeekMed is a Python toolkit that extracts medical-related terms (diseases, medications, symptoms, etc.) from Wikidata and generates datasets with English and Japanese labels. It minimizes SPARQL usage and leverages the Wikidata Web API for stable operation.

## Key Features

- **Medical Term Extraction**: Extract medical terms like diseases, medications, and symptoms from Wikidata
- **Bilingual Dictionaries**: Generate English-Japanese label pairs
- **Multiple Output Formats**: Export data in JSON, CSV, and YAML formats
- **Category Organization**: Classify data by categories (diseases, medications, etc.)
- **Wikipedia Category Support**: Automatically fetch Wikidata QIDs from Wikipedia categories

## Requirements

- Python 3.8 or higher
- Internet connection (for Wikidata API access)

## Installation

```bash
# Clone the repository
git clone https://github.com/TanukiMa/wikidataseekmed.git
cd wikidataseekmed

# Install dependencies
pip install -r requirements.txt
```

## Tools Overview

### 1. wikidataseekmed.py (Main Script)

Extract medical terms from Wikidata and generate datasets.

**Basic Usage:**

```bash
# Extract data from small categories
python wikidataseekmed.py --small

# Extract data from medium categories
python wikidataseekmed.py --medium

# Check counts only (no data extraction)
python wikidataseekmed.py --small --count-only

# Extract specific categories only
python wikidataseekmed.py --small --categories Q12136,Q12140
```

**Output Files:**
- `{size}_medical_terms_{timestamp}.json` - All data (JSON)
- `{size}_medical_terms_full_{timestamp}.csv` - All data (CSV)
- `{size}_en_ja_pairs_{timestamp}.csv` - English-Japanese pairs only
- `{size}_report_{timestamp}.txt` - Extraction report
- `by_category_{timestamp}/` - Category-wise CSV files

### 2. find_wikidata_categories.py (Medical Concept Search)

Search for medical-related Wikidata class QIDs by keyword. Useful for finding categories to add to config.yaml.

**Usage:**

```bash
# Search for medical concepts
python find_wikidata_categories.py "cardiology" --medical-only

# Change number of results
python find_wikidata_categories.py "cancer" --limit 20

# Include non-class items
python find_wikidata_categories.py "internal medicine" --include-all
```

**Example Output:**
```
✓ Found 1 medical concepts:
--------------------------------------------------------------------------------
🏥 📚 Q10379: cardiology
         (ja: 循環器学)
         branch of medicine dealing with disorders of the heart...
         Instance of: medical specialty, academic discipline

CONFIG.YAML FORMAT:
  Q10379: "cardiology"
```

### 3. find_wikipedia_categories.py (Wikipedia Category Search)

Retrieve Wikidata QIDs from Wikipedia categories.

**Usage:**

```bash
# Search Wikipedia categories
python find_wikipedia_categories.py "skin cancer" --limit 10

# Show sample category members
python find_wikipedia_categories.py "cardiology" --show-members 20
```

**Example Output:**
```
Category: Skin cancer
QID: Q3542010
Members: 156
Sample members: Melanoma, Basal-cell carcinoma, Squamous-cell carcinoma...
```

### 4. explore_wikidata_class.py (Class Structure Analysis)

Analyze Wikidata class structure and display instance/subclass counts.

**Usage:**

```bash
# Analyze a class structure
python explore_wikidata_class.py Q12136

# Analyze multiple classes
python explore_wikidata_class.py Q12136 Q12140 Q169872
```

**Example Output:**
```
Q12136 (disease):
  📊 Direct instances (P31): 2,986
  📊 Direct subclasses (P279): 1,863
  📊 All recursive (P31/P279*): 15,652

  💡 Recommendation: Use P31/P279* to capture all related items
```

## Configuration File (config.yaml)

Configure extraction categories in `config.yaml`.

```yaml
categories:
  small:
    Q12136: "disease"           # diseases
    Q12140: "medication"        # medications
    Q169872: "symptom"          # symptoms
    Q179630: "syndrome"         # syndromes

  medium:
    Q12136: "disease"
    Q12140: "medication"
    Q169872: "symptom"
    Q4915012: "biological pathway"
    Q7187: "gene"

  large:
    # More comprehensive categories
```

### How to Add Categories

1. **Search for medical concepts:**
   ```bash
   python find_wikidata_categories.py "nephrology" --medical-only
   ```

2. **Add found QID to config.yaml:**
   ```yaml
   Q121601: "nephrology"
   ```

3. **Extract data:**
   ```bash
   python wikidataseekmed.py --small
   ```

## Workflow Examples

### Adding a New Medical Field

1. **Search for appropriate Wikidata class:**
   ```bash
   python find_wikidata_categories.py "dermatology" --medical-only
   ```

2. **Check class structure (optional):**
   ```bash
   python explore_wikidata_class.py Q171171
   ```

3. **Add to config.yaml:**
   ```yaml
   Q171171: "dermatology"
   ```

4. **Extract data:**
   ```bash
   python wikidataseekmed.py --small
   ```

### Extracting from Wikipedia Categories

1. **Search for Wikipedia categories:**
   ```bash
   python find_wikipedia_categories.py "infectious diseases" --limit 5
   ```

2. **Add category QID to config.yaml:**
   ```yaml
   Q8148: "infectious disease category"
   ```

3. **Extract data:**
   ```bash
   python wikidataseekmed.py --small
   ```

   Both Wikidata classes and Wikipedia categories are supported.

## Troubleshooting

### Q: "Query timeout" error occurs

**A:** The SPARQL query is timing out. Check the count with `--count-only`. If too large, consider a different category.

### Q: Specific category returns 0 results

**A:** Check the following:
1. Verify the QID is correct
   ```bash
   python explore_wikidata_class.py Q12345
   ```
2. Make sure you're not confusing Wikimedia categories with Wikidata classes
3. Check actual count with `--count-only`

### Q: Japanese labels are not retrieved

**A:** Japanese labels may not be registered in Wikidata. The output data includes English labels and other identifiers (MeSH ID, ICD-10, etc.).

### Q: API rate limit error occurs

**A:** You've hit the Wikidata API rate limit. Wait a while before retrying. The script includes a 0.5-second delay between requests, but be cautious with large datasets.

## Output Data Format

### JSON Format
```json
{
  "Q8447": {
    "qid": "Q8447",
    "en_label": "diabetes",
    "ja_label": "糖尿病",
    "en_description": "metabolic disorder",
    "category": "disease",
    "mesh_id": "D003920",
    "icd_10": "E11"
  }
}
```

### CSV Format
```csv
qid,en_label,ja_label,en_description,category,mesh_id,icd_10
Q8447,diabetes,糖尿病,metabolic disorder,disease,D003920,E11
```

## License

This project is released under the MIT License.

## Acknowledgments

- Data Source: [Wikidata](https://www.wikidata.org/)
- Medical Ontologies: MeSH, ICD-10, SNOMED CT

## Related Documentation

- [日本語README](./README.md)
- [Wikidata SPARQL Examples](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/queries/examples)
