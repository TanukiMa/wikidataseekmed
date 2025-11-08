#!/usr/bin/env python3
"""
Find Wikidata medical concepts by keyword

Search for Wikidata medical concept classes (disease, medication, etc.)
related to a keyword and suggest QIDs for config.yaml expansion.

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
    """Search for Wikidata medical concepts by keyword using Web API"""

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

        # Class-level instance types (P31 values that indicate a class/type)
        self.class_qids = {
            'Q16889133',   # class
            'Q112193867',  # class of disease
            'Q55931203',   # second-order class
            'Q24017414',   # disease type
            'Q21146257',   # group or class of diseases
            'Q2057971',    # variable-order class
            'Q101352',     # family name (for taxonomic groups)
            'Q16521',      # taxon (for biological classifications)
            'Q930752',     # medical specialty
            'Q11862829',   # academic discipline
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
            limit: Maximum results (0 = no limit, fetches all available)

        Returns:
            List of search results
        """
        logger.info(f"Searching for '{keyword}' in Wikidata...")

        all_results = []
        continue_offset = 0
        max_per_request = 50  # Wikidata API limit per request

        while True:
            # If limit is set and we've reached it, stop
            if limit > 0 and len(all_results) >= limit:
                break

            # Calculate how many to fetch this round
            fetch_count = max_per_request
            if limit > 0:
                remaining = limit - len(all_results)
                fetch_count = min(max_per_request, remaining)

            params = {
                'action': 'wbsearchentities',
                'search': keyword,
                'language': language,
                'limit': fetch_count,
                'format': 'json',
                'type': 'item',
                'continue': continue_offset
            }

            try:
                response = self.session.get(self.api_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                results = data.get('search', [])

                if not results:
                    # No more results
                    break

                all_results.extend(results)

                # Check if there are more results (continue token)
                if 'search-continue' in data:
                    continue_offset = data['search-continue']

                    # If limit=0, continue fetching
                    if limit == 0:
                        logger.info(f"Fetched {len(all_results)} results so far, continuing...")
                        time.sleep(0.5)  # Be nice to the API
                    else:
                        # If we have a limit and haven't reached it yet, continue
                        if len(all_results) < limit:
                            time.sleep(0.5)
                        else:
                            break
                else:
                    # No more results available
                    break

            except Exception as e:
                logger.error(f"Search failed: {e}")
                break

        logger.info(f"Found {len(all_results)} total results")
        return all_results

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

    def get_concept_details(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a Wikidata item using Web API

        Args:
            qid: Wikidata QID

        Returns:
            Item details or None
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

        # Get instance of (P31) info
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

    def is_class_level(self, instance_of_qids: List[str]) -> bool:
        """
        Check if item is a class-level concept based on P31 values

        Args:
            instance_of_qids: List of P31 (instance of) QIDs

        Returns:
            True if this is a class-level concept
        """
        return any(qid in self.class_qids for qid in instance_of_qids)

    def find_concepts(
        self,
        keyword: str,
        medical_only: bool = False,
        class_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find Wikidata medical concepts by keyword using Web API

        Args:
            keyword: Search keyword
            medical_only: Only show medical-related items
            class_only: Only show class-level concepts (not individual instances)
            limit: Maximum results to fetch

        Returns:
            List of concept information
        """
        # Search for keyword
        search_results = self.search_by_keyword(keyword, limit=limit)

        if not search_results:
            logger.warning("No results found")
            return []

        concepts = []

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

            details = self.get_concept_details(qid)

            if not details:
                continue

            # Filter by class level if requested
            if class_only:
                if not self.is_class_level(details['instance_of_qids']):
                    continue

            # Check if medical (with full description)
            is_medical = self.is_medical_related(
                f"{details['label_en']} {details['description_en']}"
            )

            # Check if class level
            is_class = self.is_class_level(details['instance_of_qids'])

            concept_info = {
                'qid': qid,
                'label': details['label_en'],
                'label_ja': details['label_ja'],
                'description': details['description_en'],
                'instance_of': details['instance_of'],
                'instance_of_qids': details['instance_of_qids'],
                'is_medical': is_medical,
                'is_class': is_class
            }

            concepts.append(concept_info)

            # Be nice to the API
            time.sleep(0.5)

        return concepts

    def format_for_config(self, concepts: List[Dict[str, Any]]) -> str:
        """
        Format concepts for config.yaml

        Args:
            concepts: List of concept information

        Returns:
            Formatted YAML string
        """
        lines = []
        lines.append("# Medical concepts found for your keyword")
        lines.append("# Copy the ones you want to config.yaml")
        lines.append("")

        for concept in concepts:
            label = concept['label']
            qid = concept['qid']
            desc = concept['description']

            lines.append(f"  {qid}: \"{label}\"  # {desc}")

        return "\n".join(lines)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Find Wikidata medical concepts by keyword (using Web API)'
    )
    parser.add_argument(
        'keyword',
        help='Keyword to search for (e.g., "cancer", "cardiovascular", "neurology")'
    )
    parser.add_argument(
        '--medical-only',
        action='store_true',
        help='Only show medical-related items'
    )
    parser.add_argument(
        '--include-all',
        action='store_true',
        help='Include all items (default: only class-level concepts)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of results to fetch (default: 50, 0 = no limit)'
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

        # Default: class-only (unless --include-all is specified)
        class_only = not args.include_all

        # Find concepts
        concepts = finder.find_concepts(
            keyword=args.keyword,
            medical_only=args.medical_only,
            class_only=class_only,
            limit=args.limit
        )

        if not concepts:
            logger.error("No medical concepts found")
            sys.exit(1)

        # Output results
        if args.output == 'yaml':
            print(finder.format_for_config(concepts))

        elif args.output == 'json':
            import json
            print(json.dumps(concepts, indent=2, ensure_ascii=False))

        else:  # table
            print("\n" + "=" * 80)
            print(f"WIKIDATA MEDICAL CONCEPTS FOR: '{args.keyword}'")
            print("=" * 80)
            print("Legend: 🏥 = Medical  📚 = Class-level")
            if class_only:
                print("Showing: Class-level concepts only (use --include-all to show all)")
            else:
                print("Showing: All items (including individual instances)")
            print("=" * 80)

            print(f"\n✓ Found {len(concepts)} medical concepts:")
            print("-" * 80)

            for concept in concepts:
                qid = concept['qid']
                label = concept['label']
                label_ja = concept.get('label_ja', '')
                desc = concept['description'][:60] + "..." if len(concept['description']) > 60 else concept['description']
                instance_of = concept.get('instance_of', '')
                medical = "🏥 " if concept['is_medical'] else "   "
                is_class = concept.get('is_class', False)
                class_marker = "📚 " if is_class else "   "

                print(f"{medical}{class_marker}{qid}: {label}")
                if label_ja:
                    print(f"         (ja: {label_ja})")
                if desc:
                    print(f"         {desc}")
                if instance_of:
                    print(f"         Instance of: {instance_of}")
                print()

            # Show config.yaml format
            print("\n" + "-" * 80)
            print("CONFIG.YAML FORMAT:")
            print("-" * 80)
            print(finder.format_for_config(concepts))

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
