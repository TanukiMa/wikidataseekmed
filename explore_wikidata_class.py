#!/usr/bin/env python3
"""
Explore Wikidata class structure

Investigate how many items belong to a Wikidata class via:
- P31 (instance of): Direct instances
- P279 (subclass of): Subclasses and their hierarchy

This helps understand which approach to use for data extraction.
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


class WikidataClassExplorer:
    """Explore Wikidata class structure"""

    def __init__(self):
        self.sparql_url = "https://query.wikidata.org/sparql"
        self.api_url = "https://www.wikidata.org/w/api.php"

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikidataClassExplorer/1.0 (https://github.com/wikidataseekmed)'
        })

    def get_entity_info(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get basic information about a Wikidata entity

        Args:
            qid: Wikidata QID

        Returns:
            Entity information
        """
        params = {
            'action': 'wbgetentities',
            'ids': qid,
            'props': 'labels|descriptions|claims',
            'languages': 'en|ja',
            'format': 'json'
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'entities' in data and qid in data['entities']:
                entity = data['entities'][qid]

                labels = entity.get('labels', {})
                descriptions = entity.get('descriptions', {})

                return {
                    'qid': qid,
                    'label_en': labels.get('en', {}).get('value', 'N/A'),
                    'label_ja': labels.get('ja', {}).get('value', ''),
                    'description_en': descriptions.get('en', {}).get('value', ''),
                    'description_ja': descriptions.get('ja', {}).get('value', '')
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get entity info for {qid}: {e}")
            return None

    def count_instances(self, qid: str) -> int:
        """
        Count direct instances (P31) of a class

        Args:
            qid: Wikidata QID

        Returns:
            Number of instances
        """
        query = f"""
        SELECT (COUNT(?item) as ?count) WHERE {{
          ?item wdt:P31 wd:{qid} .
        }}
        """

        try:
            response = self.session.get(
                self.sparql_url,
                params={'query': query, 'format': 'json'},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            results = data.get('results', {}).get('bindings', [])
            if results:
                return int(results[0]['count']['value'])

            return 0

        except Exception as e:
            logger.error(f"Failed to count instances: {e}")
            return 0

    def count_subclasses(self, qid: str) -> int:
        """
        Count direct subclasses (P279) of a class

        Args:
            qid: Wikidata QID

        Returns:
            Number of subclasses
        """
        query = f"""
        SELECT (COUNT(?item) as ?count) WHERE {{
          ?item wdt:P279 wd:{qid} .
        }}
        """

        try:
            response = self.session.get(
                self.sparql_url,
                params={'query': query, 'format': 'json'},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            results = data.get('results', {}).get('bindings', [])
            if results:
                return int(results[0]['count']['value'])

            return 0

        except Exception as e:
            logger.error(f"Failed to count subclasses: {e}")
            return 0

    def count_all_instances_recursive(self, qid: str) -> int:
        """
        Count all instances including those of subclasses (P31/P279*)

        Args:
            qid: Wikidata QID

        Returns:
            Number of all instances
        """
        query = f"""
        SELECT (COUNT(?item) as ?count) WHERE {{
          ?item wdt:P31/wdt:P279* wd:{qid} .
        }}
        """

        try:
            response = self.session.get(
                self.sparql_url,
                params={'query': query, 'format': 'json'},
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

            results = data.get('results', {}).get('bindings', [])
            if results:
                return int(results[0]['count']['value'])

            return 0

        except Exception as e:
            logger.error(f"Failed to count all instances: {e}")
            return 0

    def get_sample_instances(self, qid: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get sample direct instances (P31)

        Args:
            qid: Wikidata QID
            limit: Maximum samples

        Returns:
            List of sample items
        """
        query = f"""
        SELECT ?item ?itemLabel WHERE {{
          ?item wdt:P31 wd:{qid} .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }}
        LIMIT {limit}
        """

        try:
            response = self.session.get(
                self.sparql_url,
                params={'query': query, 'format': 'json'},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            results = data.get('results', {}).get('bindings', [])
            samples = []
            for r in results:
                item_qid = r['item']['value'].split('/')[-1]
                label = r['itemLabel']['value']
                samples.append({'qid': item_qid, 'label': label})

            return samples

        except Exception as e:
            logger.error(f"Failed to get sample instances: {e}")
            return []

    def get_sample_subclasses(self, qid: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get sample direct subclasses (P279)

        Args:
            qid: Wikidata QID
            limit: Maximum samples

        Returns:
            List of sample subclasses
        """
        query = f"""
        SELECT ?item ?itemLabel WHERE {{
          ?item wdt:P279 wd:{qid} .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }}
        LIMIT {limit}
        """

        try:
            response = self.session.get(
                self.sparql_url,
                params={'query': query, 'format': 'json'},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            results = data.get('results', {}).get('bindings', [])
            samples = []
            for r in results:
                item_qid = r['item']['value'].split('/')[-1]
                label = r['itemLabel']['value']
                samples.append({'qid': item_qid, 'label': label})

            return samples

        except Exception as e:
            logger.error(f"Failed to get sample subclasses: {e}")
            return []


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Explore Wikidata class structure (P31 vs P279)'
    )
    parser.add_argument(
        'qid',
        help='Wikidata QID to explore (e.g., Q192102 for skin cancer)'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=10,
        help='Number of sample items to show (default: 10)'
    )

    args = parser.parse_args()

    try:
        explorer = WikidataClassExplorer()

        # Get entity info
        logger.info(f"Getting information for {args.qid}...")
        entity_info = explorer.get_entity_info(args.qid)

        if not entity_info:
            logger.error(f"Could not find entity {args.qid}")
            sys.exit(1)

        print("\n" + "=" * 80)
        print(f"WIKIDATA CLASS EXPLORER: {args.qid}")
        print("=" * 80)
        print(f"Label (EN): {entity_info['label_en']}")
        if entity_info['label_ja']:
            print(f"Label (JA): {entity_info['label_ja']}")
        print(f"Description: {entity_info['description_en']}")
        print("=" * 80)

        # Count instances
        logger.info("Counting direct instances (P31)...")
        instance_count = explorer.count_instances(args.qid)
        print(f"\n📊 Direct instances (P31 = {args.qid}): {instance_count:,}")

        # Count subclasses
        logger.info("Counting direct subclasses (P279)...")
        subclass_count = explorer.count_subclasses(args.qid)
        print(f"📊 Direct subclasses (P279 = {args.qid}): {subclass_count:,}")

        # Count all instances recursively
        logger.info("Counting all instances recursively (P31/P279*)...")
        all_count = explorer.count_all_instances_recursive(args.qid)
        print(f"📊 All instances recursively (P31/P279* = {args.qid}): {all_count:,}")

        print("\n" + "-" * 80)
        print("INTERPRETATION:")
        print("-" * 80)

        if instance_count > 0:
            print(f"✓ This class has {instance_count:,} direct instances")
            print(f"  Query: SELECT ?item WHERE {{ ?item wdt:P31 wd:{args.qid} }}")

        if subclass_count > 0:
            print(f"✓ This class has {subclass_count:,} direct subclasses")
            print(f"  Query: SELECT ?item WHERE {{ ?item wdt:P279 wd:{args.qid} }}")

        if all_count > instance_count + subclass_count:
            print(f"✓ Including subclass hierarchy gives {all_count:,} total items")
            print(f"  Query: SELECT ?item WHERE {{ ?item wdt:P31/wdt:P279* wd:{args.qid} }}")

        # Show samples
        if instance_count > 0:
            logger.info(f"Getting sample instances...")
            samples = explorer.get_sample_instances(args.qid, args.samples)
            if samples:
                print("\n" + "-" * 80)
                print(f"SAMPLE DIRECT INSTANCES (P31 = {args.qid}):")
                print("-" * 80)
                for s in samples:
                    print(f"  - {s['qid']}: {s['label']}")

        if subclass_count > 0:
            logger.info(f"Getting sample subclasses...")
            samples = explorer.get_sample_subclasses(args.qid, args.samples)
            if samples:
                print("\n" + "-" * 80)
                print(f"SAMPLE DIRECT SUBCLASSES (P279 = {args.qid}):")
                print("-" * 80)
                for s in samples:
                    print(f"  - {s['qid']}: {s['label']}")

        print("\n" + "=" * 80)
        print("RECOMMENDATION:")
        print("=" * 80)

        if all_count > instance_count * 2:
            print("⚠ Use P31/P279* to capture all related items")
            print(f"  This will get {all_count:,} items instead of just {instance_count:,}")
        elif instance_count > 100:
            print("✓ P31 (instance of) alone is sufficient")
            print(f"  This class has {instance_count:,} direct instances")
        else:
            print("ℹ Small class - both approaches will work")

        print("=" * 80)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
