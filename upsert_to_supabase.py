#!/usr/bin/env python3
"""
Upsert Wikidata medical terms to Supabase
Supports both JSON and CSV formats
Uses environment variables for authentication (GitHub Actions compatible)
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupabaseUploader:
    """Upload medical terms data to Supabase"""

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client

        Args:
            supabase_url: Supabase project URL (from SUPABASE_URL env var)
            supabase_key: Supabase anon/service key (from SUPABASE_KEY env var)
        """
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Missing Supabase credentials. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = "medical_terms"
        logger.info(f"Connected to Supabase: {supabase_url}")

    def load_data_from_json(self, json_path: str) -> List[Dict[str, Any]]:
        """
        Load data from JSON file

        Args:
            json_path: Path to JSON file

        Returns:
            List of dictionaries containing medical terms
        """
        logger.info(f"Loading data from JSON: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # If JSON has categories structure
            records = []
            for category, items in data.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item['source_category'] = category
                            records.append(item)
                        else:
                            records.append({'data': item, 'source_category': category})
        else:
            raise ValueError(f"Unexpected JSON structure: {type(data)}")

        logger.info(f"Loaded {len(records)} records from JSON")
        return records

    def load_data_from_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        Load data from CSV file

        Args:
            csv_path: Path to CSV file

        Returns:
            List of dictionaries containing medical terms
        """
        logger.info(f"Loading data from CSV: {csv_path}")

        df = pd.read_csv(csv_path)

        # Replace NaN with None for proper JSON serialization
        df = df.where(pd.notna(df), None)

        records = df.to_dict('records')

        logger.info(f"Loaded {len(records)} records from CSV")
        return records

    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize record to match Supabase table schema

        Args:
            record: Raw record from CSV/JSON

        Returns:
            Normalized record
        """
        # Expected schema fields
        normalized = {
            'qid': record.get('qid'),
            'en_label': record.get('en_label') or record.get('label_en'),
            'ja_label': record.get('ja_label') or record.get('label_ja'),
            'en_description': record.get('en_description') or record.get('description_en'),
            'ja_description': record.get('ja_description') or record.get('description_ja'),
            'category_en': record.get('category_en') or record.get('source_category'),
            'category_ja': record.get('category_ja'),
            'mesh_id': record.get('mesh_id'),
            'icd10': record.get('icd10'),
            'icd11': record.get('icd11'),
            'icd9': record.get('icd9'),
            'snomed_id': record.get('snomed_id'),
            'umls_id': record.get('umls_id'),
        }

        # Remove None values to avoid overwriting existing data with null
        # Only keep fields that have actual values
        normalized = {k: v for k, v in normalized.items() if v is not None and v != ''}

        # QID is required
        if 'qid' not in normalized or not normalized['qid']:
            raise ValueError(f"Missing required field 'qid' in record: {record}")

        return normalized

    def upsert_batch(self, records: List[Dict[str, Any]], batch_size: int = 100) -> Dict[str, int]:
        """
        Upsert records to Supabase in batches

        Args:
            records: List of records to upsert
            batch_size: Number of records per batch (default: 100)

        Returns:
            Dictionary with success and error counts
        """
        total = len(records)
        success_count = 0
        error_count = 0

        logger.info(f"Starting upsert of {total} records in batches of {batch_size}")

        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            try:
                # Normalize all records in batch
                normalized_batch = []
                for record in batch:
                    try:
                        normalized = self.normalize_record(record)
                        normalized_batch.append(normalized)
                    except ValueError as e:
                        logger.warning(f"Skipping invalid record: {e}")
                        error_count += 1

                if not normalized_batch:
                    logger.warning(f"Batch {batch_num}/{total_batches}: No valid records")
                    continue

                # Upsert to Supabase
                # on_conflict='qid' means: if QID exists, update; otherwise insert
                response = self.client.table(self.table_name).upsert(
                    normalized_batch,
                    on_conflict='qid'
                ).execute()

                batch_success = len(normalized_batch)
                success_count += batch_success

                logger.info(
                    f"Batch {batch_num}/{total_batches}: "
                    f"Upserted {batch_success} records "
                    f"(Total: {success_count}/{total})"
                )

            except Exception as e:
                logger.error(f"Batch {batch_num}/{total_batches} failed: {e}")
                error_count += len(batch)

        return {
            'total': total,
            'success': success_count,
            'error': error_count
        }

    def get_table_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the table (for debugging)

        Returns:
            Table information or None if error
        """
        try:
            # Get a sample row to understand the schema
            response = self.client.table(self.table_name).select("*").limit(1).execute()
            logger.info(f"Table '{self.table_name}' exists with {len(response.data)} sample rows")
            return response.data
        except Exception as e:
            logger.error(f"Could not fetch table info: {e}")
            return None


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Upsert Wikidata medical terms to Supabase'
    )
    parser.add_argument(
        'input_file',
        help='Input file path (JSON or CSV)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for upsert operations (default: 100)'
    )
    parser.add_argument(
        '--table-name',
        default='medical_terms',
        help='Supabase table name (default: medical_terms)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Load and validate data without uploading'
    )

    args = parser.parse_args()

    # Get Supabase credentials from environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        logger.error(
            "Missing Supabase credentials!\n"
            "Set environment variables:\n"
            "  export SUPABASE_URL='https://xxxxx.supabase.co'\n"
            "  export SUPABASE_KEY='your-anon-or-service-key'\n"
            "\n"
            "For GitHub Actions, add these as secrets:\n"
            "  SUPABASE_URL\n"
            "  SUPABASE_KEY"
        )
        sys.exit(1)

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)

    # Determine file type
    file_ext = input_path.suffix.lower()
    if file_ext not in ['.json', '.csv']:
        logger.error(f"Unsupported file type: {file_ext}. Use .json or .csv")
        sys.exit(1)

    try:
        # Initialize uploader
        uploader = SupabaseUploader(supabase_url, supabase_key)
        uploader.table_name = args.table_name

        # Check table exists
        uploader.get_table_info()

        # Load data
        if file_ext == '.json':
            records = uploader.load_data_from_json(args.input_file)
        else:  # .csv
            records = uploader.load_data_from_csv(args.input_file)

        if not records:
            logger.warning("No records found in input file")
            sys.exit(0)

        # Show sample record
        logger.info(f"Sample record: {json.dumps(records[0], indent=2, ensure_ascii=False)}")

        if args.dry_run:
            logger.info("DRY RUN: Skipping upload")
            logger.info(f"Would upload {len(records)} records")
            sys.exit(0)

        # Upsert data
        result = uploader.upsert_batch(records, batch_size=args.batch_size)

        # Print summary
        logger.info("=" * 60)
        logger.info("UPLOAD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total records: {result['total']}")
        logger.info(f"Successfully upserted: {result['success']}")
        logger.info(f"Errors: {result['error']}")
        logger.info("=" * 60)

        if result['error'] > 0:
            logger.warning(f"{result['error']} records failed to upload")
            sys.exit(1)
        else:
            logger.info("All records uploaded successfully!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
