#!/usr/bin/env python3
"""
Find Wikipedia categories by keyword

Search for Wikipedia categories and list their members.
Useful for finding appropriate Category:$name for data extraction.
"""

import argparse
import logging
import sys
from typing import List, Dict, Any, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WikipediaCategoryFinder:
    """Search for Wikipedia categories and their members"""

    def __init__(self, language: str = 'en'):
        self.language = language
        self.api_url = f"https://{language}.wikipedia.org/w/api.php"

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikipediaCategoryFinder/1.0 (https://github.com/wikidataseekmed)'
        })

    def search_categories(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for Wikipedia categories by keyword

        Args:
            keyword: Search keyword
            limit: Maximum results

        Returns:
            List of category information
        """
        logger.info(f"Searching for categories matching '{keyword}'...")

        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': keyword,
            'srnamespace': 14,  # Category namespace
            'srlimit': limit,
            'format': 'json'
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get('query', {}).get('search', [])
            logger.info(f"Found {len(results)} categories")

            categories = []
            for result in results:
                cat_info = {
                    'title': result['title'],
                    'pageid': result['pageid'],
                    'snippet': result.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', '')
                }
                categories.append(cat_info)

            return categories

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_wikidata_qids(self, page_titles: List[str]) -> Dict[str, Optional[str]]:
        """
        Get Wikidata QIDs for Wikipedia page titles

        Args:
            page_titles: List of Wikipedia page titles

        Returns:
            Dictionary mapping page title to QID (or None if no QID)
        """
        if not page_titles:
            return {}

        # Wikipedia API can handle up to 50 titles per request
        batch_size = 50
        qid_map = {}

        for i in range(0, len(page_titles), batch_size):
            batch = page_titles[i:i + batch_size]

            params = {
                'action': 'query',
                'titles': '|'.join(batch),
                'prop': 'pageprops',
                'ppprop': 'wikibase_item',
                'format': 'json'
            }

            try:
                response = self.session.get(self.api_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                pages = data.get('query', {}).get('pages', {})
                for page_data in pages.values():
                    title = page_data.get('title')
                    qid = page_data.get('pageprops', {}).get('wikibase_item')
                    if title:
                        qid_map[title] = qid

            except Exception as e:
                logger.error(f"Failed to get QIDs for batch: {e}")

        return qid_map

    def get_category_members(
        self,
        category_title: str,
        limit: int = 100,
        member_type: str = 'page',
        include_qids: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get members of a Wikipedia category

        Args:
            category_title: Category title (e.g., "Category:Skin cancer")
            limit: Maximum members to retrieve
            member_type: Type of members ('page', 'subcat', or 'file')
            include_qids: Whether to fetch Wikidata QIDs for members

        Returns:
            List of member information
        """
        logger.info(f"Getting members of {category_title}...")

        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': category_title,
            'cmlimit': min(limit, 500),  # API max is 500
            'cmtype': member_type,
            'format': 'json'
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            members = data.get('query', {}).get('categorymembers', [])
            logger.info(f"Found {len(members)} members")

            # Get QIDs if requested
            if include_qids and members:
                page_titles = [m['title'] for m in members]
                qid_map = self.get_wikidata_qids(page_titles)

                for member in members:
                    member['qid'] = qid_map.get(member['title'])

            return members

        except Exception as e:
            logger.error(f"Failed to get members: {e}")
            return []

    def get_category_info(self, category_title: str) -> Dict[str, Any]:
        """
        Get information about a category including member counts

        Args:
            category_title: Category title

        Returns:
            Category information
        """
        params = {
            'action': 'query',
            'titles': category_title,
            'prop': 'categoryinfo',
            'format': 'json'
        }

        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            pages = data.get('query', {}).get('pages', {})
            page_data = next(iter(pages.values()))

            cat_info = page_data.get('categoryinfo', {})

            return {
                'title': category_title,
                'pages': cat_info.get('pages', 0),
                'subcats': cat_info.get('subcats', 0),
                'files': cat_info.get('files', 0),
                'total': cat_info.get('size', 0)
            }

        except Exception as e:
            logger.error(f"Failed to get category info: {e}")
            return {
                'title': category_title,
                'pages': 0,
                'subcats': 0,
                'files': 0,
                'total': 0
            }


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Find Wikipedia categories by keyword'
    )
    parser.add_argument(
        'keyword',
        help='Keyword to search for (e.g., "skin cancer", "cardiovascular disease")'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of categories to show (default: 20)'
    )
    parser.add_argument(
        '--show-members',
        type=int,
        metavar='N',
        help='Show N members of each category'
    )
    parser.add_argument(
        '--with-qids',
        action='store_true',
        help='Include Wikidata QIDs for category members'
    )
    parser.add_argument(
        '--language',
        default='en',
        help='Wikipedia language code (default: en)'
    )
    parser.add_argument(
        '--output',
        choices=['table', 'list', 'yaml'],
        default='table',
        help='Output format (default: table)'
    )

    args = parser.parse_args()

    try:
        finder = WikipediaCategoryFinder(language=args.language)

        # Search for categories
        categories = finder.search_categories(
            keyword=args.keyword,
            limit=args.limit
        )

        if not categories:
            logger.error("No categories found")
            sys.exit(1)

        # Get category info for each
        category_details = []
        for cat in categories:
            info = finder.get_category_info(cat['title'])
            cat.update(info)
            category_details.append(cat)

        # Output results
        if args.output == 'list':
            for cat in category_details:
                print(cat['title'])

        elif args.output == 'yaml':
            # YAML output for config.yaml
            all_members = []
            for cat in category_details:
                if cat['pages'] > 0:
                    members = finder.get_category_members(
                        category_title=cat['title'],
                        limit=args.show_members or 500,
                        member_type='page',
                        include_qids=True
                    )
                    all_members.extend(members)

            if all_members:
                print("# Medical terms from Wikipedia categories")
                print("# Copy to config.yaml\n")
                for member in all_members:
                    qid = member.get('qid')
                    title = member.get('title')
                    if qid:
                        print(f"  {qid}: \"{title}\"")
                    else:
                        print(f"  # No QID: \"{title}\"")
            else:
                logger.warning("No members with QIDs found")

        else:  # table
            print("\n" + "=" * 80)
            print(f"WIKIPEDIA CATEGORIES FOR: '{args.keyword}'")
            print("=" * 80)

            for i, cat in enumerate(category_details, 1):
                title = cat['title']
                pages = cat['pages']
                subcats = cat['subcats']
                total = cat['total']

                print(f"\n{i}. {title}")
                print(f"   Pages: {pages}, Subcategories: {subcats}, Total: {total}")

                if args.show_members and pages > 0:
                    members = finder.get_category_members(
                        category_title=title,
                        limit=args.show_members,
                        member_type='page',
                        include_qids=args.with_qids
                    )

                    if members:
                        print(f"   Members (showing {len(members)}):")
                        for member in members[:args.show_members]:
                            qid = member.get('qid')
                            member_title = member['title']
                            if args.with_qids:
                                qid_str = f" [{qid}]" if qid else " [No QID]"
                                print(f"     - {member_title}{qid_str}")
                            else:
                                print(f"     - {member_title}")

            print("\n" + "=" * 80)
            print("USAGE:")
            print("  1. Choose a category from above")
            print("  2. Use --show-members N --with-qids to see QIDs")
            print("  3. Use --output yaml to get config.yaml format")
            print("=" * 80)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
