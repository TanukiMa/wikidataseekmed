#!/usr/bin/env python3
"""
Find Wikidata categories by keyword

Search for Wikidata categories related to a keyword and suggest QIDs
for config.yaml expansion.

Uses Web API primarily to avoid SPARQL rate limits.
"""

import argparse
import logging
import sys
import time
from typing import List, Dict, Any, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WikidataCategoryFinder:
    """Search for Wikidata categories by keyword using Web API"""

    def __init__(self):
        self.api_url = "https://www.wikidata.org/w/api.php"

        # For API requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikidataCategoryFinder/1.0 (https://github.com/wikidataseekmed)'
        })

        # Medical-related keywords to prioritize results
        self.medical_keywords = {
            'medical', 'medicine', 'health', 'healthcare', 'disease', 'diagnosis',
            'treatment', 'therapy', 'clinical', 'patient', 'drug', 'medication',
            'pharmaceutical', 'surgery', 'anatomical', 'pathology', 'syndrome',
            'symptom', 'protein', 'gene', 'biological', 'organism', 'infection',
            'cancer', 'disorder', 'condition', 'procedure', 'test'
        }

    def search_by_keyword(
        self,
        keyword: str,
        language: str = 'en',
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search Wikidata by keyword using Search API

        Args:
            keyword: Search keyword
            language: Language code (en, ja, etc.)
            limit: Maximum results

        Returns:
            List of search results
        """
        logger.info(f"Searching for '{keyword}' in Wikidata...")

        params = {
            'action': 'wbsearchentities',
            'search': keyword,
            'language': language,
            'limit': limit,
            'format': 'json',
            'type': 'item'
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get('search', [])
            logger.info(f"Found {len(results)} results")

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_entity_data(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get entity data using wbgetentities API

        Args:
            qid: Wikidata QID

        Returns:
            Entity data or None
        """
        params = {
            'action': 'wbgetentities',
            'ids': qid,
            'props': 'labels|descriptions|claims',
            'languages': 'en|ja',
            'format': 'json',
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'entities' in data and qid in data['entities']:
                return data['entities'][qid]

            return None

        except Exception as e:
            logger.error(f"Failed to get entity data for {qid}: {e}")
            return None

    def is_category_via_api(self, entity_data: Dict[str, Any]) -> bool:
        """
        Check if entity is a Wikidata category via API

        Args:
            entity_data: Entity data from wbgetentities

        Returns:
            True if entity is instance of Q4167836 (Wikimedia category)
        """
        if not entity_data or 'claims' not in entity_data:
            return False

        # Check P31 (instance of)
        p31_claims = entity_data.get('claims', {}).get('P31', [])

        for claim in p31_claims:
            if claim.get('mainsnak', {}).get('snaktype') == 'value':
                value = claim['mainsnak'].get('datavalue', {})
                if value.get('type') == 'wikibase-entityid':
                    qid = value.get('value', {}).get('id')
                    if qid == 'Q4167836':  # Wikimedia category
                        return True

        return False

    def get_category_details(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a category using Web API

        Args:
            qid: Wikidata QID

        Returns:
            Category details or None
        """
        entity_data = self.get_entity_data(qid)

        if not entity_data:
            return None

        # Extract labels
        labels = entity_data.get('labels', {})
        en_label = labels.get('en', {}).get('value', 'N/A')
        ja_label = labels.get('ja', {}).get('value', '')

        # Extract descriptions
        descriptions = entity_data.get('descriptions', {})
        en_description = descriptions.get('en', {}).get('value', '')
        ja_description = descriptions.get('ja', {}).get('value', '')

        # Check if it's a category
        is_category = self.is_category_via_api(entity_data)

        # Get instance of info
        instance_of = []
        instance_of_qids = []
        p31_claims = entity_data.get('claims', {}).get('P31', [])

        for claim in p31_claims[:3]:  # First 3 instances
            if claim.get('mainsnak', {}).get('snaktype') == 'value':
                value = claim['mainsnak'].get('datavalue', {})
                if value.get('type') == 'wikibase-entityid':
                    instance_qid = value.get('value', {}).get('id')
                    instance_of_qids.append(instance_qid)

                    # Try to get label
                    instance_data = self.get_entity_data(instance_qid)
                    if instance_data:
                        instance_label = instance_data.get('labels', {}).get('en', {}).get('value', instance_qid)
                        instance_of.append(instance_label)
                    else:
                        instance_of.append(instance_qid)

        return {
            'qid': qid,
            'label_en': en_label,
            'label_ja': ja_label,
            'description_en': en_description,
            'description_ja': ja_description,
            'is_category': is_category,
            'instance_of': ', '.join(instance_of) if instance_of else '',
            'instance_of_qids': instance_of_qids
        }

    def is_medical_related(self, text: str) -> bool:
        """
        Check if text contains medical-related keywords

        Args:
            text: Text to check

        Returns:
            True if medical-related
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.medical_keywords)

    def find_categories(
        self,
        keyword: str,
        medical_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find Wikidata categories by keyword using Web API

        Args:
            keyword: Search keyword
            medical_only: Only show medical-related categories
            limit: Maximum results to fetch

        Returns:
            List of category information
        """
        # Search for keyword
        search_results = self.search_by_keyword(keyword, limit=limit)

        if not search_results:
            logger.warning("No results found")
            return []

        categories = []

        for i, result in enumerate(search_results):
            qid = result['id']
            label = result.get('label', 'N/A')
            description = result.get('description', '')

            # Quick filter by medical keywords if requested
            if medical_only:
                combined_text = f"{label} {description}"
                if not self.is_medical_related(combined_text):
                    continue

            # Get details via API
            logger.info(f"Checking {i+1}/{len(search_results)}: {qid} ({label})")

            details = self.get_category_details(qid)

            if not details:
                continue

            # Check if medical (with full description)
            is_medical = self.is_medical_related(
                f"{details['label_en']} {details['description_en']}"
            )

            category_info = {
                'qid': qid,
                'label': details['label_en'],
                'label_ja': details['label_ja'],
                'description': details['description_en'],
                'is_category': details['is_category'],
                'instance_of': details['instance_of'],
                'is_medical': is_medical
            }

            categories.append(category_info)

            # Be nice to the API
            time.sleep(0.5)

        return categories

    def format_for_config(self, categories: List[Dict[str, Any]]) -> str:
        """
        Format categories for config.yaml

        Args:
            categories: List of category information

        Returns:
            Formatted YAML string
        """
        lines = []
        lines.append("# Categories found for your keyword")
        lines.append("# Copy the ones you want to config.yaml")
        lines.append("")

        for cat in categories:
            if cat['is_category']:
                label = cat['label']
                qid = cat['qid']
                desc = cat['description']

                lines.append(f"  {qid}: \"{label}\"  # {desc}")

        return "\n".join(lines)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Find Wikidata categories by keyword (using Web API)'
    )
    parser.add_argument(
        'keyword',
        help='Keyword to search for (e.g., "cancer", "cardiovascular", "neurology")'
    )
    parser.add_argument(
        '--medical-only',
        action='store_true',
        help='Only show medical-related categories'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of results to fetch (default: 50)'
    )
    parser.add_argument(
        '--output',
        choices=['table', 'yaml', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    args = parser.parse_args()

    try:
        finder = WikidataCategoryFinder()

        # Find categories
        categories = finder.find_categories(
            keyword=args.keyword,
            medical_only=args.medical_only,
            limit=args.limit
        )

        if not categories:
            logger.error("No categories found")
            sys.exit(1)

        # Filter to only categories
        actual_categories = [c for c in categories if c['is_category']]
        non_categories = [c for c in categories if not c['is_category']]

        # Output results
        if args.output == 'yaml':
            print(finder.format_for_config(actual_categories))

        elif args.output == 'json':
            import json
            print(json.dumps(actual_categories, indent=2, ensure_ascii=False))

        else:  # table
            print("\n" + "=" * 80)
            print(f"WIKIDATA CATEGORIES FOR: '{args.keyword}'")
            print("=" * 80)

            if actual_categories:
                print(f"\n✓ Found {len(actual_categories)} categories:")
                print("-" * 80)

                for cat in actual_categories:
                    qid = cat['qid']
                    label = cat['label']
                    label_ja = cat.get('label_ja', '')
                    desc = cat['description'][:60] + "..." if len(cat['description']) > 60 else cat['description']
                    medical = "🏥 " if cat['is_medical'] else "   "

                    print(f"{medical}{qid}: {label}")
                    if label_ja:
                        print(f"      (ja: {label_ja})")
                    if desc:
                        print(f"      {desc}")
                    print()

                # Show config.yaml format
                print("\n" + "-" * 80)
                print("CONFIG.YAML FORMAT:")
                print("-" * 80)
                print(finder.format_for_config(actual_categories))

            if non_categories:
                print(f"\n(Note: {len(non_categories)} non-category items were found but not shown)")

            print("\n" + "=" * 80)
            print("USAGE:")
            print("  1. Copy the QIDs you want from above")
            print("  2. Add them to config.yaml under 'categories:'")
            print("  3. Run: python wikidataseekmed_api_optimized.py")
            print("=" * 80)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
