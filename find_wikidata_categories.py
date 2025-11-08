#!/usr/bin/env python3
"""
Find Wikidata categories by keyword

Search for Wikidata categories related to a keyword and suggest QIDs
for config.yaml expansion.
"""

import argparse
import logging
import sys
import time
from typing import List, Dict, Any, Optional
import requests
from SPARQLWrapper import SPARQLWrapper, JSON

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WikidataCategoryFinder:
    """Search for Wikidata categories by keyword"""

    def __init__(self):
        self.api_url = "https://www.wikidata.org/w/api.php"
        self.sparql_endpoint = "https://query.wikidata.org/sparql"
        self.sparql = SPARQLWrapper(self.sparql_endpoint)
        self.sparql.setReturnFormat(JSON)
        self.sparql.addCustomHttpHeader('User-Agent', 'WikidataCategoryFinder/1.0 (https://github.com/wikidataseekmed)')

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

    def verify_is_category(self, qid: str) -> Dict[str, Any]:
        """
        Verify if a QID is a Wikidata category

        Args:
            qid: Wikidata QID

        Returns:
            Dictionary with verification results
        """
        query = f"""
        ASK {{
          wd:{qid} wdt:P31 wd:Q4167836 .
        }}
        """

        self.sparql.setQuery(query)

        try:
            results = self.sparql.query().convert()
            is_category = results.get('boolean', False)

            return {
                'qid': qid,
                'is_category': is_category
            }

        except Exception as e:
            logger.error(f"Verification failed for {qid}: {e}")
            return {'qid': qid, 'is_category': False}

    def get_category_details(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a category

        Args:
            qid: Wikidata QID

        Returns:
            Category details or None
        """
        query = f"""
        SELECT ?item ?itemLabel ?itemDescription ?instanceOf ?instanceOfLabel
        WHERE {{
          BIND(wd:{qid} AS ?item)

          OPTIONAL {{
            ?item wdt:P31 ?instanceOf .
          }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,ja" .
          }}
        }}
        LIMIT 1
        """

        self.sparql.setQuery(query)

        try:
            results = self.sparql.query().convert()
            bindings = results['results']['bindings']

            if bindings:
                binding = bindings[0]

                return {
                    'qid': qid,
                    'label_en': binding.get('itemLabel', {}).get('value', 'N/A'),
                    'description': binding.get('itemDescription', {}).get('value', ''),
                    'instance_of': binding.get('instanceOfLabel', {}).get('value', ''),
                    'instance_of_qid': binding.get('instanceOf', {}).get('value', '').split('/')[-1] if binding.get('instanceOf') else ''
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get details for {qid}: {e}")
            return None

    def count_category_items(self, qid: str, timeout_sec: int = 30) -> int:
        """
        Count number of items in a category

        Args:
            qid: Category QID
            timeout_sec: Query timeout

        Returns:
            Number of items (0 if failed)
        """
        query = f"""
        SELECT (COUNT(DISTINCT ?item) as ?count)
        WHERE {{
          ?item wdt:P31/wdt:P279* wd:{qid} .
        }}
        """

        self.sparql.setQuery(query)
        self.sparql.setTimeout(timeout_sec)

        try:
            results = self.sparql.query().convert()
            bindings = results['results']['bindings']

            if bindings:
                count = int(bindings[0].get('count', {}).get('value', 0))
                return count

            return 0

        except Exception as e:
            logger.warning(f"Could not count items for {qid}: {e}")
            return 0

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

    def search_categories_by_sparql(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for categories using SPARQL (more accurate)

        Args:
            keyword: Search keyword
            limit: Maximum results

        Returns:
            List of category information
        """
        logger.info(f"Searching categories via SPARQL for '{keyword}'...")

        query = f"""
        SELECT DISTINCT ?item ?itemLabel ?itemDescription
        WHERE {{
          ?item wdt:P31 wd:Q4167836 .  # instance of: Wikimedia category

          # Search in label or description
          {{
            ?item rdfs:label ?label .
            FILTER(CONTAINS(LCASE(?label), "{keyword.lower()}"))
          }}
          UNION
          {{
            ?item schema:description ?desc .
            FILTER(CONTAINS(LCASE(?desc), "{keyword.lower()}"))
          }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,ja" .
          }}
        }}
        LIMIT {limit}
        """

        self.sparql.setQuery(query)

        try:
            results = self.sparql.query().convert()
            bindings = results['results']['bindings']

            categories = []
            for binding in bindings:
                qid = binding['item']['value'].split('/')[-1]
                label = binding.get('itemLabel', {}).get('value', 'N/A')
                description = binding.get('itemDescription', {}).get('value', '')

                categories.append({
                    'qid': qid,
                    'label': label,
                    'description': description,
                    'is_category': True,
                    'instance_of': 'Wikimedia category',
                    'instance_of_qid': 'Q4167836',
                    'is_medical': self.is_medical_related(f"{label} {description}")
                })

            logger.info(f"Found {len(categories)} categories via SPARQL")
            return categories

        except Exception as e:
            logger.error(f"SPARQL search failed: {e}")
            return []

    def find_categories(
        self,
        keyword: str,
        verify: bool = True,
        count_items: bool = False,
        medical_only: bool = False,
        use_sparql: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find Wikidata categories by keyword

        Args:
            keyword: Search keyword
            verify: Verify each result is actually a category
            count_items: Count items in each category (slow)
            medical_only: Only show medical-related categories
            use_sparql: Use SPARQL search (more accurate for categories)

        Returns:
            List of category information
        """
        # Try SPARQL search first if requested
        if use_sparql:
            categories = self.search_categories_by_sparql(keyword)

            if categories:
                # Filter by medical if requested
                if medical_only:
                    categories = [c for c in categories if c['is_medical']]

                # Count items if requested
                if count_items:
                    for cat in categories:
                        logger.info(f"Counting items in {cat['qid']}...")
                        cat['item_count'] = self.count_category_items(cat['qid'])
                        time.sleep(1)

                return categories

            logger.warning("SPARQL search returned no results, falling back to API search")

        # Fallback to API search
        search_results = self.search_by_keyword(keyword)

        if not search_results:
            logger.warning("No results found")
            return []

        categories = []

        for result in search_results:
            qid = result['id']
            label = result.get('label', 'N/A')
            description = result.get('description', '')

            # Filter by medical keywords if requested
            if medical_only:
                combined_text = f"{label} {description}"
                if not self.is_medical_related(combined_text):
                    continue

            # Get details
            details = self.get_category_details(qid)

            if not details:
                continue

            # Verify if it's a category
            if verify:
                verification = self.verify_is_category(qid)
                is_category = verification['is_category']
            else:
                # Quick check: instance of Q4167836 in description
                is_category = details['instance_of_qid'] == 'Q4167836'

            category_info = {
                'qid': qid,
                'label': details['label_en'],
                'description': details['description'],
                'is_category': is_category,
                'instance_of': details['instance_of'],
                'is_medical': self.is_medical_related(f"{details['label_en']} {details['description']}")
            }

            # Count items if requested
            if count_items and is_category:
                logger.info(f"Counting items in {qid}...")
                category_info['item_count'] = self.count_category_items(qid)
                time.sleep(1)  # Be nice to the server

            categories.append(category_info)

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
        description='Find Wikidata categories by keyword'
    )
    parser.add_argument(
        'keyword',
        help='Keyword to search for (e.g., "cancer", "cardiovascular", "neurology")'
    )
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip category verification (faster but less accurate)'
    )
    parser.add_argument(
        '--count-items',
        action='store_true',
        help='Count items in each category (slow)'
    )
    parser.add_argument(
        '--medical-only',
        action='store_true',
        help='Only show medical-related categories'
    )
    parser.add_argument(
        '--output',
        choices=['table', 'yaml', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    parser.add_argument(
        '--no-sparql',
        action='store_true',
        help='Don\'t use SPARQL search (use API search only)'
    )

    args = parser.parse_args()

    try:
        finder = WikidataCategoryFinder()

        # Find categories
        categories = finder.find_categories(
            keyword=args.keyword,
            verify=not args.no_verify,
            count_items=args.count_items,
            medical_only=args.medical_only,
            use_sparql=not args.no_sparql
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
                    desc = cat['description'][:60] + "..." if len(cat['description']) > 60 else cat['description']
                    medical = "🏥 " if cat['is_medical'] else "   "

                    print(f"{medical}{qid}: {label}")
                    if desc:
                        print(f"      {desc}")

                    if 'item_count' in cat:
                        print(f"      Items: {cat['item_count']:,}")

                    print()

                # Show config.yaml format
                print("\n" + "-" * 80)
                print("CONFIG.YAML FORMAT:")
                print("-" * 80)
                print(finder.format_for_config(actual_categories))

            if non_categories:
                print(f"\n✗ Found {len(non_categories)} non-category items:")
                print("-" * 80)

                for item in non_categories[:5]:  # Show first 5
                    print(f"  {item['qid']}: {item['label']}")
                    print(f"      Instance of: {item['instance_of']}")
                    print()

                if len(non_categories) > 5:
                    print(f"  ... and {len(non_categories) - 5} more")

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
