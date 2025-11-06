#!/usr/bin/env python3
"""
Apply LLM-generated Japanese labels to medical_terms table.

Supports multiple selection strategies:
- voting: Select translation suggested by most models
- consensus: Require multiple models to agree
- confidence: Select based on confidence score
- manual: Review and select manually
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Optional
from collections import Counter

from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranslationApplicator:
    """Apply LLM translations to medical terms"""

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize applicator

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Initialized translation applicator")

    def get_translations_for_term(self, qid: str) -> List[Dict[str, Any]]:
        """
        Get all LLM translations for a term

        Args:
            qid: Term QID

        Returns:
            List of translation dictionaries
        """
        try:
            response = self.client.table('llm_translations').select('*').eq('qid', qid).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching translations for {qid}: {e}")
            return []

    def select_by_voting(self, translations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select translation by majority vote

        Args:
            translations: List of translation dictionaries

        Returns:
            Selected translation or None
        """
        if not translations:
            return None

        # Count votes for each unique translation
        vote_counts = Counter(t['suggested_ja_label'] for t in translations)

        # Get most common translation
        most_common = vote_counts.most_common(1)[0]
        winning_translation = most_common[0]
        vote_count = most_common[1]

        # Find the first translation object with this text
        selected = next(
            (t for t in translations if t['suggested_ja_label'] == winning_translation),
            None
        )

        if selected:
            logger.info(f"  Voting: '{winning_translation}' ({vote_count}/{len(translations)} votes)")

        return selected

    def select_by_consensus(
        self,
        translations: List[Dict[str, Any]],
        min_agreement: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        Select translation only if multiple models agree

        Args:
            translations: List of translation dictionaries
            min_agreement: Minimum number of models that must agree

        Returns:
            Selected translation or None
        """
        if not translations:
            return None

        # Count votes
        vote_counts = Counter(t['suggested_ja_label'] for t in translations)

        # Check if any translation meets minimum agreement
        for translation_text, count in vote_counts.most_common():
            if count >= min_agreement:
                selected = next(
                    (t for t in translations if t['suggested_ja_label'] == translation_text),
                    None
                )

                logger.info(f"  Consensus: '{translation_text}' ({count} models agree)")
                return selected

        logger.info(f"  Consensus: No agreement (minimum {min_agreement} required)")
        return None

    def select_by_confidence(self, translations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select translation with highest confidence score

        Args:
            translations: List of translation dictionaries

        Returns:
            Selected translation or None
        """
        if not translations:
            return None

        # Filter translations with confidence scores
        with_confidence = [t for t in translations if t.get('confidence_score') is not None]

        if not with_confidence:
            logger.warning("  No translations with confidence scores, falling back to voting")
            return self.select_by_voting(translations)

        # Select highest confidence
        selected = max(with_confidence, key=lambda t: t['confidence_score'])

        logger.info(f"  Confidence: '{selected['suggested_ja_label']}' (score: {selected['confidence_score']:.3f})")

        return selected

    def apply_translation(
        self,
        qid: str,
        translation: Dict[str, Any],
        strategy: str
    ) -> bool:
        """
        Apply selected translation to medical_terms table

        Args:
            qid: Term QID
            translation: Translation dictionary
            strategy: Selection strategy used

        Returns:
            True if successful
        """
        try:
            # Update medical_terms
            update_data = {
                'ja_label': translation['suggested_ja_label'],
                'ja_label_source': 'llm',
                'ja_label_selected_from': translation['model_name'],
                'ja_label_auto_generated': True,
                'ja_label_verified': False,
            }

            self.client.table('medical_terms').update(update_data).eq('qid', qid).execute()

            # Mark translation as selected
            self.client.table('llm_translations').update({
                'status': 'selected'
            }).eq('id', translation['id']).execute()

            logger.info(f"  ✓ Applied translation to {qid}")

            return True

        except Exception as e:
            logger.error(f"  ✗ Failed to apply translation to {qid}: {e}")
            return False

    def apply_all(
        self,
        strategy: str = 'voting',
        min_consensus: int = 2,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Apply translations to all terms

        Args:
            strategy: Selection strategy (voting, consensus, confidence)
            min_consensus: Minimum agreement for consensus strategy
            limit: Maximum number of terms to process
            dry_run: Don't actually apply, just report

        Returns:
            Statistics dictionary
        """
        # Get all QIDs with translations
        try:
            query = self.client.table('llm_translations').select('qid').order('qid')
            if limit:
                query = query.limit(limit * 10)  # Fetch more to account for duplicates

            response = query.execute()
            all_qids = list(set(t['qid'] for t in response.data))[:limit] if limit else list(set(t['qid'] for t in response.data))

            logger.info(f"Found {len(all_qids)} terms with LLM translations")

        except Exception as e:
            logger.error(f"Error fetching QIDs: {e}")
            return {}

        stats = {
            'total': len(all_qids),
            'applied': 0,
            'skipped': 0,
            'failed': 0,
        }

        for i, qid in enumerate(all_qids, 1):
            logger.info(f"\n[{i}/{len(all_qids)}] Processing {qid}")

            # Get translations
            translations = self.get_translations_for_term(qid)

            if not translations:
                logger.warning(f"  No translations found")
                stats['skipped'] += 1
                continue

            logger.info(f"  Found {len(translations)} translations from models:")
            for t in translations:
                logger.info(f"    - {t['model_name']}: {t['suggested_ja_label']}")

            # Select translation
            selected = None

            if strategy == 'voting':
                selected = self.select_by_voting(translations)
            elif strategy == 'consensus':
                selected = self.select_by_consensus(translations, min_agreement=min_consensus)
            elif strategy == 'confidence':
                selected = self.select_by_confidence(translations)
            else:
                logger.error(f"Unknown strategy: {strategy}")
                stats['failed'] += 1
                continue

            if not selected:
                logger.warning(f"  No translation selected")
                stats['skipped'] += 1
                continue

            # Apply translation
            if dry_run:
                logger.info(f"  DRY RUN: Would apply '{selected['suggested_ja_label']}'")
                stats['applied'] += 1
            else:
                if self.apply_translation(qid, selected, strategy):
                    stats['applied'] += 1
                else:
                    stats['failed'] += 1

        return stats


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Apply LLM-generated translations to medical terms'
    )
    parser.add_argument(
        '--strategy',
        choices=['voting', 'consensus', 'confidence'],
        default='voting',
        help='Translation selection strategy (default: voting)'
    )
    parser.add_argument(
        '--min-consensus',
        type=int,
        default=2,
        help='Minimum models that must agree for consensus strategy (default: 2)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of terms to process'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report what would be done without applying'
    )
    parser.add_argument(
        '--qid',
        help='Apply translation for specific QID only'
    )

    args = parser.parse_args()

    # Get Supabase credentials
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        logger.error(
            "Missing Supabase credentials!\n"
            "Set environment variables:\n"
            "  export SUPABASE_URL='https://xxxxx.supabase.co'\n"
            "  export SUPABASE_KEY='your-key'"
        )
        sys.exit(1)

    try:
        applicator = TranslationApplicator(supabase_url, supabase_key)

        if args.qid:
            # Process single QID
            logger.info(f"Processing QID: {args.qid}")

            translations = applicator.get_translations_for_term(args.qid)

            if not translations:
                logger.error(f"No translations found for {args.qid}")
                sys.exit(1)

            logger.info(f"Found {len(translations)} translations:")
            for t in translations:
                logger.info(f"  - {t['model_name']}: {t['suggested_ja_label']}")

            # Select
            if args.strategy == 'voting':
                selected = applicator.select_by_voting(translations)
            elif args.strategy == 'consensus':
                selected = applicator.select_by_consensus(translations, min_agreement=args.min_consensus)
            else:
                selected = applicator.select_by_confidence(translations)

            if not selected:
                logger.error("No translation selected")
                sys.exit(1)

            # Apply
            if args.dry_run:
                logger.info(f"DRY RUN: Would apply '{selected['suggested_ja_label']}'")
            else:
                applicator.apply_translation(args.qid, selected, args.strategy)

            sys.exit(0)

        else:
            # Process all
            stats = applicator.apply_all(
                strategy=args.strategy,
                min_consensus=args.min_consensus,
                limit=args.limit,
                dry_run=args.dry_run
            )

            # Print summary
            logger.info("\n" + "=" * 60)
            logger.info("APPLICATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total terms: {stats['total']}")
            logger.info(f"Applied: {stats['applied']}")
            logger.info(f"Skipped: {stats['skipped']}")
            logger.info(f"Failed: {stats['failed']}")
            logger.info("=" * 60)

            sys.exit(0 if stats['failed'] == 0 else 1)

    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
