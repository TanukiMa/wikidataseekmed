#!/usr/bin/env python3
"""
Extract Missing Label Items from Wikidata Medical Terms Data

This tool extracts items with missing English or Japanese labels from
generated CSV or JSON files, preparing them for LLM-based label filling.

Usage:
    python extract_missing_labels.py input.csv
    python extract_missing_labels.py input.json --format json
    python extract_missing_labels.py input.csv --missing-type en
    python extract_missing_labels.py input.csv --output-dir missing_labels/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd


class MissingLabelExtractor:
    """Extract items with missing labels for LLM processing"""

    def __init__(self, input_file: str, output_dir: str = "missing_labels"):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

    def load_data(self) -> pd.DataFrame:
        """Load data from CSV or JSON"""
        print(f"Loading data from: {self.input_file}")

        if self.input_file.suffix.lower() == '.json':
            df = pd.read_json(self.input_file)
        elif self.input_file.suffix.lower() == '.csv':
            df = pd.read_csv(self.input_file, encoding='utf-8-sig')
        else:
            raise ValueError(f"Unsupported file format: {self.input_file.suffix}")

        # Ensure string type for label columns and replace NaN with empty string
        if 'en_label' in df.columns:
            df['en_label'] = df['en_label'].fillna('').astype(str)
        if 'ja_label' in df.columns:
            df['ja_label'] = df['ja_label'].fillna('').astype(str)

        print(f"  Total records: {len(df)}")
        return df

    def analyze_missing_labels(self, df: pd.DataFrame) -> Dict[str, int]:
        """Analyze missing label patterns"""
        stats = {
            'total': len(df),
            'en_missing': 0,
            'ja_missing': 0,
            'both_missing': 0,
            'any_missing': 0,
            'en_only': 0,
            'ja_only': 0,
            'both_present': 0,
        }

        # Count missing patterns
        en_empty = (df['en_label'] == '') | (df['en_label'].isna())
        ja_empty = (df['ja_label'] == '') | (df['ja_label'].isna())

        stats['en_missing'] = en_empty.sum()
        stats['ja_missing'] = ja_empty.sum()
        stats['both_missing'] = (en_empty & ja_empty).sum()
        stats['any_missing'] = (en_empty | ja_empty).sum()
        stats['en_only'] = ((~en_empty) & ja_empty).sum()
        stats['ja_only'] = (en_empty & (~ja_empty)).sum()
        stats['both_present'] = ((~en_empty) & (~ja_empty)).sum()

        return stats

    def extract_missing_en(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract items missing English labels"""
        en_empty = (df['en_label'] == '') | (df['en_label'].isna())
        return df[en_empty].copy()

    def extract_missing_ja(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract items missing Japanese labels"""
        ja_empty = (df['ja_label'] == '') | (df['ja_label'].isna())
        return df[ja_empty].copy()

    def extract_missing_both(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract items missing both labels"""
        en_empty = (df['en_label'] == '') | (df['en_label'].isna())
        ja_empty = (df['ja_label'] == '') | (df['ja_label'].isna())
        return df[en_empty & ja_empty].copy()

    def extract_missing_any(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract items missing any label (EN or JA or both)"""
        en_empty = (df['en_label'] == '') | (df['en_label'].isna())
        ja_empty = (df['ja_label'] == '') | (df['ja_label'].isna())
        return df[en_empty | ja_empty].copy()

    def save_results(self, df: pd.DataFrame, suffix: str,
                    format: str = 'csv') -> Optional[Path]:
        """Save extracted results"""
        if len(df) == 0:
            print(f"  No items with {suffix} - skipping")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = self.input_file.stem

        if format == 'csv':
            output_file = self.output_dir / f"{base_name}_missing_{suffix}_{timestamp}.csv"
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
        elif format == 'json':
            output_file = self.output_dir / f"{base_name}_missing_{suffix}_{timestamp}.json"
            df.to_json(output_file, orient='records', force_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported output format: {format}")

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"  {suffix}: {output_file} ({len(df)} items, {file_size_mb:.2f} MB)")

        return output_file

    def create_llm_prompt_template(self, df: pd.DataFrame, missing_type: str) -> str:
        """Create a template file for LLM label filling"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        template_file = self.output_dir / f"llm_prompt_template_{missing_type}_{timestamp}.txt"

        with open(template_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LLM Label Filling Prompt Template\n")
            f.write("=" * 80 + "\n\n")

            if missing_type == 'en':
                f.write("Task: Fill missing English labels\n\n")
                f.write("Instructions:\n")
                f.write("1. For each item, provide an appropriate English label\n")
                f.write("2. Use the Japanese label and description as context\n")
                f.write("3. Consider the category for domain-specific terminology\n")
                f.write("4. Maintain consistency with medical terminology standards\n\n")

            elif missing_type == 'ja':
                f.write("Task: Fill missing Japanese labels\n\n")
                f.write("Instructions:\n")
                f.write("1. For each item, provide an appropriate Japanese label\n")
                f.write("2. Use the English label and description as context\n")
                f.write("3. Consider the category for domain-specific terminology\n")
                f.write("4. Use standard Japanese medical terminology\n\n")

            elif missing_type == 'both':
                f.write("Task: Fill missing English and Japanese labels\n\n")
                f.write("Instructions:\n")
                f.write("1. For each item, provide both English and Japanese labels\n")
                f.write("2. Use external IDs (MeSH, ICD, SNOMED, UMLS) as reference\n")
                f.write("3. Consider the category for domain-specific terminology\n")
                f.write("4. Maintain consistency with medical terminology standards\n\n")

            f.write("Sample entries (first 5):\n")
            f.write("=" * 80 + "\n\n")

            for idx, row in df.head(5).iterrows():
                f.write(f"Item {idx + 1}:\n")
                f.write(f"  QID: {row.get('qid', 'N/A')}\n")
                f.write(f"  Category: {row.get('category_en', 'N/A')} ({row.get('category_ja', 'N/A')})\n")
                f.write(f"  EN Label: {row.get('en_label', '[MISSING]')}\n")
                f.write(f"  JA Label: {row.get('ja_label', '[MISSING]')}\n")
                f.write(f"  EN Description: {row.get('en_description', 'N/A')}\n")
                f.write(f"  JA Description: {row.get('ja_description', 'N/A')}\n")

                # External IDs
                ext_ids = []
                for id_field, id_name in [('mesh_id', 'MeSH'), ('icd10', 'ICD-10'),
                                          ('icd11', 'ICD-11'), ('snomed_id', 'SNOMED'),
                                          ('umls_id', 'UMLS')]:
                    value = row.get(id_field, '')
                    if value and value != 'nan' and str(value) != '':
                        ext_ids.append(f"{id_name}: {value}")

                if ext_ids:
                    f.write(f"  External IDs: {', '.join(ext_ids)}\n")

                f.write("\n")

            f.write("=" * 80 + "\n")
            f.write(f"Total items to process: {len(df)}\n")

        print(f"  LLM prompt template: {template_file}")
        return str(template_file)

    def extract_and_save_all(self, missing_type: str = 'all',
                            output_format: str = 'csv') -> Dict[str, Path]:
        """Extract and save all missing label patterns"""
        df = self.load_data()

        print("\n" + "=" * 80)
        print("Missing Label Analysis")
        print("=" * 80)

        stats = self.analyze_missing_labels(df)

        print(f"\nTotal items: {stats['total']}")
        print(f"\nMissing label patterns:")
        print(f"  English missing: {stats['en_missing']} ({stats['en_missing']/stats['total']*100:.1f}%)")
        print(f"  Japanese missing: {stats['ja_missing']} ({stats['ja_missing']/stats['total']*100:.1f}%)")
        print(f"  Both missing: {stats['both_missing']} ({stats['both_missing']/stats['total']*100:.1f}%)")
        print(f"  Any missing: {stats['any_missing']} ({stats['any_missing']/stats['total']*100:.1f}%)")
        print(f"\nLabel coverage patterns:")
        print(f"  English only: {stats['en_only']} ({stats['en_only']/stats['total']*100:.1f}%)")
        print(f"  Japanese only: {stats['ja_only']} ({stats['ja_only']/stats['total']*100:.1f}%)")
        print(f"  Both present: {stats['both_present']} ({stats['both_present']/stats['total']*100:.1f}%)")

        print("\n" + "=" * 80)
        print("Extracting missing label items...")
        print("=" * 80 + "\n")

        saved_files = {}

        if missing_type in ['all', 'en']:
            df_missing_en = self.extract_missing_en(df)
            if len(df_missing_en) > 0:
                file = self.save_results(df_missing_en, 'en_label', output_format)
                if file:
                    saved_files['en'] = file
                    self.create_llm_prompt_template(df_missing_en, 'en')

        if missing_type in ['all', 'ja']:
            df_missing_ja = self.extract_missing_ja(df)
            if len(df_missing_ja) > 0:
                file = self.save_results(df_missing_ja, 'ja_label', output_format)
                if file:
                    saved_files['ja'] = file
                    self.create_llm_prompt_template(df_missing_ja, 'ja')

        if missing_type in ['all', 'both']:
            df_missing_both = self.extract_missing_both(df)
            if len(df_missing_both) > 0:
                file = self.save_results(df_missing_both, 'both_labels', output_format)
                if file:
                    saved_files['both'] = file
                    self.create_llm_prompt_template(df_missing_both, 'both')

        if missing_type in ['all', 'any']:
            df_missing_any = self.extract_missing_any(df)
            if len(df_missing_any) > 0:
                file = self.save_results(df_missing_any, 'any_label', output_format)
                if file:
                    saved_files['any'] = file

        print("\n" + "=" * 80)
        print("Extraction completed!")
        print("=" * 80)
        print(f"\nOutput directory: {self.output_dir}")
        print(f"Files saved: {len(saved_files)}")

        return saved_files


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Extract items with missing labels from Wikidata medical terms data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all missing label patterns from CSV
  python extract_missing_labels.py output/small_medical_terms_api_optimized_20250105_123456.csv

  # Extract only items missing English labels
  python extract_missing_labels.py output/small_en_ja_pairs_api_20250105_123456.csv --missing-type en

  # Extract from JSON and output as JSON
  python extract_missing_labels.py output/small_medical_terms_api_20250105_123456.json --format json

  # Specify custom output directory
  python extract_missing_labels.py input.csv --output-dir llm_input/

Missing types:
  all   - Extract all patterns (default)
  en    - Only items missing English labels
  ja    - Only items missing Japanese labels
  both  - Only items missing both labels
  any   - Any items missing at least one label
        """
    )

    parser.add_argument('input_file', type=str,
                       help='Input CSV or JSON file')
    parser.add_argument('--missing-type', type=str, default='all',
                       choices=['all', 'en', 'ja', 'both', 'any'],
                       help='Type of missing labels to extract (default: all)')
    parser.add_argument('--format', type=str, default='csv',
                       choices=['csv', 'json'],
                       help='Output format (default: csv)')
    parser.add_argument('--output-dir', type=str, default='missing_labels',
                       help='Output directory (default: missing_labels)')

    return parser.parse_args()


def main():
    """Main function"""
    print("=" * 80)
    print("Wikidata Medical Terms - Missing Label Extractor")
    print("=" * 80)

    args = parse_arguments()

    try:
        extractor = MissingLabelExtractor(
            input_file=args.input_file,
            output_dir=args.output_dir
        )

        extractor.extract_and_save_all(
            missing_type=args.missing_type,
            output_format=args.format
        )

    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
