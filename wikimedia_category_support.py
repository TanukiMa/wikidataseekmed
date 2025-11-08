#!/usr/bin/env python3
"""
Wikimedia Category Support for wikidataseekmed_api_optimized.py

This module adds support for Wikipedia categories (Q4167836) by:
1. Detecting if a QID is a Wikimedia category
2. Fetching category members from Wikipedia
3. Getting Wikidata QIDs for those members
"""

import requests
import logging
from typing import List, Dict, Any, Optional


class WikimediaCategoryHandler:
    """Handle Wikipedia category member retrieval"""

    def __init__(self, language: str = 'en', logger: Optional[logging.Logger] = None):
        self.language = language
        self.api_url = f"https://{language}.wikipedia.org/w/api.php"
        self.logger = logger or logging.getLogger(__name__)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikidataSeekMed/1.0 (WikimediaCategory Handler)'
        })

    def get_category_title(self, qid: str) -> Optional[str]:
        """
        Get Wikipedia category title from Wikidata QID

        Args:
            qid: Wikidata QID of the category

        Returns:
            Category title (e.g., "Category:Cardiology") or None
        """
        wikidata_api = "https://www.wikidata.org/w/api.php"

        params = {
            'action': 'wbgetentities',
            'ids': qid,
            'props': 'sitelinks',
            'sitefilter': f'{self.language}wiki',
            'format': 'json'
        }

        try:
            response = self.session.get(wikidata_api, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'entities' in data and qid in data['entities']:
                entity = data['entities'][qid]
                sitelinks = entity.get('sitelinks', {})
                enwiki = sitelinks.get(f'{self.language}wiki', {})
                title = enwiki.get('title')

                if title and title.startswith('Category:'):
                    return title

            return None

        except Exception as e:
            self.logger.error(f"Failed to get category title for {qid}: {e}")
            return None

    def get_category_members_with_qids(
        self,
        category_title: str,
        limit: int = 500
    ) -> List[str]:
        """
        Get Wikidata QIDs of all members in a Wikipedia category

        Args:
            category_title: Category title (e.g., "Category:Cardiology")
            limit: Maximum members to retrieve

        Returns:
            List of Wikidata QIDs
        """
        self.logger.info(f"Fetching members of {category_title} from Wikipedia...")

        all_members = []
        continue_token = None

        while len(all_members) < limit:
            params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': category_title,
                'cmlimit': min(500, limit - len(all_members)),  # API max is 500
                'cmtype': 'page',  # Only pages, not subcategories
                'format': 'json'
            }

            if continue_token:
                params['cmcontinue'] = continue_token

            try:
                response = self.session.get(self.api_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                members = data.get('query', {}).get('categorymembers', [])
                all_members.extend(members)

                # Check for continuation
                if 'continue' in data and len(all_members) < limit:
                    continue_token = data['continue']['cmcontinue']
                else:
                    break

            except Exception as e:
                self.logger.error(f"Failed to get category members: {e}")
                break

        self.logger.info(f"Found {len(all_members)} members in {category_title}")

        # Get Wikidata QIDs for all members
        if all_members:
            page_titles = [m['title'] for m in all_members]
            qid_map = self.get_wikidata_qids_for_titles(page_titles)

            # Return only QIDs
            qids = [qid for qid in qid_map.values() if qid]
            self.logger.info(f"Found {len(qids)} members with Wikidata QIDs")
            return qids

        return []

    def get_wikidata_qids_for_titles(
        self,
        page_titles: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        Get Wikidata QIDs for Wikipedia page titles

        Args:
            page_titles: List of Wikipedia page titles

        Returns:
            Dictionary mapping page title to QID (or None)
        """
        qid_map = {}
        batch_size = 50  # Wikipedia API limit

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
                self.logger.error(f"Failed to get QIDs for batch: {e}")

        return qid_map


def is_wikimedia_category(qid: str, sparql_executor) -> bool:
    """
    Check if QID is a Wikimedia category (Q4167836)

    Args:
        qid: Wikidata QID to check
        sparql_executor: Function that executes SPARQL query

    Returns:
        True if QID is a Wikimedia category
    """
    query = f"""
    ASK {{
      wd:{qid} wdt:P31 wd:Q4167836 .
    }}
    """

    try:
        result = sparql_executor(query, f"Check if {qid} is Wikimedia category")
        return result.get('boolean', False)
    except Exception:
        return False


# Integration example for wikidataseekmed_api_optimized.py
"""
Add this to MedicalTermsExtractor class:

def get_category_qids(self, category_qid: str, limit: Optional[int] = None,
                     exclude_qids: Optional[List[str]] = None) -> List[str]:
    # Check if this is a Wikimedia category
    from wikimedia_category_support import is_wikimedia_category, WikimediaCategoryHandler

    if is_wikimedia_category(category_qid, self.execute_sparql_with_retry):
        self.logger.info(f"{category_qid} is a Wikimedia category - fetching from Wikipedia")

        handler = WikimediaCategoryHandler(logger=self.logger)
        category_title = handler.get_category_title(category_qid)

        if category_title:
            return handler.get_category_members_with_qids(category_title, limit=limit or 500)
        else:
            self.logger.warning(f"Could not find Wikipedia category for {category_qid}")
            return []

    # Otherwise, use normal Wikidata class query
    # ... existing code ...
"""
