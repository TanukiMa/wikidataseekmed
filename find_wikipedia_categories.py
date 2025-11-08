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

    def get_category_members(
        self,
        category_title: str,
        limit: int = 100,
        member_type: str = 'page'
    ) -> List[Dict[str, Any]]:
        """
        Get members of a Wikipedia category

        Args:
            category_title: Category title (e.g., "Category:Skin cancer")
            limit: Maximum members to retrieve
            member_type: Type of members ('page', 'subcat', or 'file')

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
        '--language',
        default='en',
        help='Wikipedia language code (default: en)'
    )
    parser.add_argument(
        '--output',
        choices=['table', 'list'],
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
        else:
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
                        member_type='page'
                    )

                    if members:
                        print(f"   Members (showing {len(members)}):")
                        for member in members[:args.show_members]:
                            print(f"     - {member['title']}")

            print("\n" + "=" * 80)
            print("USAGE:")
            print("  1. Choose a category from above")
            print("  2. Use the exact category name (e.g., 'Category:Skin_cancer')")
            print("  3. Get members with: --show-members 50")
            print("=" * 80)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
