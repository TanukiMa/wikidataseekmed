"""
Wikidata Category Finder - Japanese to English Category Mapping

This tool finds English equivalents of Japanese Wikidata categories and explores
the category hierarchy (subcategories).

Usage:
  python wikidata_category_finder.py --search "医学"
  python wikidata_category_finder.py --search "病気" --show-subcategories
  python wikidata_category_finder.py --qid Q12136 --depth 2
"""

from typing import Dict, List, Optional, Set, Tuple
from SPARQLWrapper import SPARQLWrapper, JSON
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError
import argparse
import json
import yaml
import time
import socket
import traceback
import random


@dataclass
class CategoryInfo:
    """Category information data class"""
    qid: str
    label_ja: str
    label_en: str
    description_ja: str = ""
    description_en: str = ""
    instance_of: List[str] = field(default_factory=list)
    subclass_of: List[str] = field(default_factory=list)
    has_subcategories: bool = False
    subcategory_count: int = 0


class WikidataCategoryFinder:
    """Find and explore Wikidata categories with Japanese-English mapping"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the category finder"""
        self.sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        self.sparql.setReturnFormat(JSON)
        # Load config if available
        self.config = self._load_config(config_path)
        
        # User-Agent per WDQS policy (include contact URL/email)
        ua_name = "WikidataCategoryFinder/1.0"
        ua_contact = None
        try:
            if self.config and isinstance(self.config, dict):
                ua = self.config.get('user_agent', {})
                ua_name = ua.get('name', ua_name)
                ua_contact = ua.get('contact')
        except Exception:
            pass
        if ua_contact:
            self.sparql.addCustomHttpHeader("User-Agent", f"{ua_name} (+{ua_contact})")
        else:
            self.sparql.addCustomHttpHeader("User-Agent", ua_name)
        # Encourage gzip
        try:
            self.sparql.addCustomHttpHeader("Accept-Encoding", "gzip")
        except Exception:
            pass
        
        # Endpoint timeout config (default 60s)
        timeout_sec = 60
        try:
            if self.config and isinstance(self.config, dict):
                timeout_sec = int(self.config.get('query', {}).get('timeout_sec', timeout_sec))
        except Exception:
            pass
        self.sparql.setTimeout(timeout_sec)
        # Prefer POST to avoid URL length issues
        try:
            self.sparql.setMethod('POST')
        except Exception:
            pass
        
        # Rate limiter: default 1.0s between queries (<=1 QPS)
        self._last_query_time: Optional[float] = None
        self._min_interval_sec: float = 1.0
        try:
            if self.config and isinstance(self.config, dict):
                rl = self.config.get('rate_limit', {})
                self._min_interval_sec = float(rl.get('min_interval_sec', self._min_interval_sec))
        except Exception:
            pass
    
    def _rate_limit(self) -> None:
        """Ensure we don't exceed allowed QPS to avoid HTTP 429."""
        now = time.time()
        if self._last_query_time is None:
            self._last_query_time = now
            return
        elapsed = now - self._last_query_time
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
        self._last_query_time = time.time()

        self._min_interval_sec: float = 0.25
        try:
            if self.config and isinstance(self.config, dict):
                rl = self.config.get('rate_limit', {})
                self._min_interval_sec = float(rl.get('min_interval_sec', self._min_interval_sec))
        except Exception:
            pass

    
    def _load_config(self, config_path: str) -> Optional[Dict]:
        """Load configuration file"""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        except Exception as e:
            print(f"Note: Could not load config file: {e}")
        return None
    
    def search_categories_by_japanese_label(self, keyword: str, 
                                           limit: int = 50, 
                                           max_retries: int = 3) -> List[CategoryInfo]:
        """
        Search Wikidata categories by Japanese label
        
        Args:
            keyword: Japanese keyword to search for
            limit: Maximum number of results
            max_retries: Maximum number of retry attempts on timeout
        
        Returns:
            List of CategoryInfo objects
        """
        # Sanitize keyword
        safe_keyword = keyword.replace('"', '').replace("'", '').replace('\\', '').strip()
        
        query = f"""
        SELECT DISTINCT ?item ?jaLabel ?enLabel ?jaDescription ?enDescription
        WHERE {{
          ?item wdt:P31 wd:Q4167836 .  # instance of Wikimedia category
          ?item rdfs:label ?jaLabel .
          FILTER(LANG(?jaLabel) = "ja")
          FILTER(CONTAINS(LCASE(?jaLabel), "{safe_keyword.lower()}"))
          
          OPTIONAL {{
            ?item rdfs:label ?enLabel .
            FILTER(LANG(?enLabel) = "en")
          }}
          
          OPTIONAL {{
            ?item schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }}
          
          OPTIONAL {{
            ?item schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }}
        }}
        LIMIT {int(limit)}
        """
        
        print(f"\n🔍 Searching for categories with Japanese keyword: '{keyword}'")
        print("-" * 80)
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = (2 ** attempt) + random.uniform(0, 0.5)
                    print(f"⏳ Retry attempt {attempt + 1}/{max_retries} after {wait_time:.1f}s...")
                    time.sleep(wait_time)
                
                self._rate_limit()
                self.sparql.setQuery(query)
                results = self.sparql.query().convert()
                bindings = results["results"]["bindings"]
                
                categories = []
                for binding in bindings:
                    qid = binding['item']['value'].split('/')[-1]
                    ja_label = binding.get('jaLabel', {}).get('value', '')
                    en_label = binding.get('enLabel', {}).get('value', '')
                    ja_desc = binding.get('jaDescription', {}).get('value', '')
                    en_desc = binding.get('enDescription', {}).get('value', '')
                    
                    # Remove "Category:" prefix if present
                    if ja_label.startswith('Category:'):
                        ja_label = ja_label[9:].strip()
                    if en_label.startswith('Category:'):
                        en_label = en_label[9:].strip()
                    
                    category = CategoryInfo(
                        qid=qid,
                        label_ja=ja_label,
                        label_en=en_label,
                        description_ja=ja_desc,
                        description_en=en_desc
                    )
                    categories.append(category)
                
                print(f"✅ Found {len(categories)} categories")
                return categories
                
            except socket.timeout as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Query timeout (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    print(f"❌ Search timeout after {max_retries} attempts")
                    print(f"💡 Try using --exact for specific category name")
                    return []
            
            except HTTPError as e:
                if e.code == 504:
                    if attempt < max_retries - 1:
                        print(f"⚠️  Wikidata server timeout (HTTP 504) (attempt {attempt + 1}/{max_retries})")
                        continue
                    else:
                        print(f"❌ Server timeout after {max_retries} attempts")
                        print(f"💡 Try with smaller --limit or try again later")
                        return []
                else:
                    print(f"❌ HTTP Error {e.code}: {e.reason}")
                    return []
                    
            except Exception as e:
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    if attempt < max_retries - 1:
                        print(f"⚠️  Timeout (attempt {attempt + 1}/{max_retries})")
                        continue
                    else:
                        print(f"❌ Timeout after {max_retries} attempts")
                        return []
                else:
                    print(f"❌ Error during search: {e}")
                    traceback.print_exc()
                    return []
        
        return []
    
    def find_exact_japanese_category(self, ja_category: str, max_retries: int = 3) -> Optional[CategoryInfo]:
        """
        Find exact match for Japanese category name and get English equivalent with Q number
        
        Args:
            ja_category: Exact Japanese category name (e.g., "病気", "医学", "医薬品")
            max_retries: Maximum number of retry attempts on timeout
        
        Returns:
            CategoryInfo object with English label and QID, or None if not found
        """
        # Sanitize input
        safe_category = ja_category.replace('"', '').replace("'", '').replace('\\', '').strip()
        
        # Remove "Category:" prefix if present
        if safe_category.startswith('Category:'):
            safe_category = safe_category[9:].strip()
        
        query = f"""
        SELECT DISTINCT ?item ?jaLabel ?enLabel ?jaDescription ?enDescription
        WHERE {{
          ?item wdt:P31 wd:Q4167836 .  # instance of Wikimedia category
          ?item rdfs:label ?jaLabel .
          FILTER(LANG(?jaLabel) = "ja")
          FILTER(LCASE(?jaLabel) = "{safe_category.lower()}" || 
                 LCASE(?jaLabel) = "category:{safe_category.lower()}")
          
          OPTIONAL {{
            ?item rdfs:label ?enLabel .
            FILTER(LANG(?enLabel) = "en")
          }}
          
          OPTIONAL {{
            ?item schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }}
          
          OPTIONAL {{
            ?item schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }}
        }}
        LIMIT 1
        """
        
        print(f"\n🎯 Finding exact match for Japanese category: '{ja_category}'")
        print("-" * 80)
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = (2 ** attempt) + random.uniform(0, 0.5)  # jitter to reduce thundering herd
                    print(f"⏳ Retry attempt {attempt + 1}/{max_retries} after {wait_time:.1f}s...")
                    time.sleep(wait_time)
                
                self._rate_limit()
                self.sparql.setQuery(query)
                results = self.sparql.query().convert()
                bindings = results["results"]["bindings"]
                
                if not bindings:
                    print(f"❌ No exact match found for '{ja_category}'")
                    print(f"💡 Try partial search with: --search \"{ja_category}\"")
                    return None
                
                binding = bindings[0]
                qid = binding['item']['value'].split('/')[-1]
                ja_label = binding.get('jaLabel', {}).get('value', '')
                en_label = binding.get('enLabel', {}).get('value', '')
                ja_desc = binding.get('jaDescription', {}).get('value', '')
                en_desc = binding.get('enDescription', {}).get('value', '')
                
                # Remove "Category:" prefix if present
                if ja_label.startswith('Category:'):
                    ja_label = ja_label[9:].strip()
                if en_label.startswith('Category:'):
                    en_label = en_label[9:].strip()
                
                category = CategoryInfo(
                    qid=qid,
                    label_ja=ja_label,
                    label_en=en_label,
                    description_ja=ja_desc,
                    description_en=en_desc
                )
                
                print(f"✅ Found exact match!")
                return category
                
            except socket.timeout as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Query timeout (attempt {attempt + 1}/{max_retries})")
                    print(f"   Network may be slow or Wikidata server is busy")
                    continue
                else:
                    print(f"❌ Query timeout after {max_retries} attempts")
                    print(f"💡 Suggestions:")
                    print(f"   1. Try partial search: --search \"{ja_category}\"")
                    print(f"   2. Check your internet connection")
                    print(f"   3. Try again later")
                    return None
            
            except HTTPError as e:
                if e.code == 504:  # Gateway Timeout
                    if attempt < max_retries - 1:
                        print(f"⚠️  Wikidata server timeout (HTTP 504) (attempt {attempt + 1}/{max_retries})")
                        print(f"   The server is busy, retrying...")
                        continue
                    else:
                        print(f"❌ Wikidata server timeout after {max_retries} attempts")
                        print(f"💡 Suggestions:")
                        print(f"   1. Try partial search: --search \"{ja_category}\"")
                        print(f"   2. Try again in a few minutes")
                        print(f"   3. Use Wikidata Web UI: https://www.wikidata.org/")
                        return None
                else:
                    print(f"❌ HTTP Error {e.code}: {e.reason}")
                    return None
                    
            except Exception as e:
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    if attempt < max_retries - 1:
                        print(f"⚠️  Timeout error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                        continue
                    else:
                        print(f"❌ Timeout after {max_retries} attempts: {error_msg}")
                        print(f"💡 Try partial search with: --search \"{ja_category}\"")
                        return None
                else:
                    print(f"❌ Error during exact search: {e}")
                    traceback.print_exc()
                    return None
        
        return None
    
    def batch_find_japanese_categories(self, ja_categories: List[str]) -> List[CategoryInfo]:
        """
        Find exact matches for multiple Japanese category names
        
        Args:
            ja_categories: List of Japanese category names
        
        Returns:
            List of CategoryInfo objects
        """
        print(f"\n📚 Batch finding {len(ja_categories)} Japanese categories")
        print("=" * 80)
        
        results = []
        
        for i, ja_cat in enumerate(ja_categories, 1):
            print(f"\n[{i}/{len(ja_categories)}] Processing: {ja_cat}")
            
            category = self.find_exact_japanese_category(ja_cat)
            
            if category:
                results.append(category)
                print(f"   ✅ {category.qid}: {category.label_ja} → {category.label_en}")
            else:
                print(f"   ❌ Not found")
            
            # Rate limiting
            if i < len(ja_categories):
                time.sleep(0.5)
        
        print(f"\n{'=' * 80}")
        print(f"📊 Summary: Found {len(results)}/{len(ja_categories)} categories")
        print("=" * 80)
        
        return results
    
    def get_category_details(self, qid: str) -> Optional[CategoryInfo]:
        """
        Get detailed information about a specific category
        
        Args:
            qid: Wikidata QID (e.g., "Q12136")
        
        Returns:
            CategoryInfo object or None
        """
        query = f"""
        SELECT DISTINCT ?jaLabel ?enLabel ?jaDescription ?enDescription
                ?instanceOf ?instanceOfLabel ?subclassOf ?subclassOfLabel
        WHERE {{
          wd:{qid} rdfs:label ?jaLabel .
          FILTER(LANG(?jaLabel) = "ja")
          
          OPTIONAL {{
            wd:{qid} rdfs:label ?enLabel .
            FILTER(LANG(?enLabel) = "en")
          }}
          
          OPTIONAL {{
            wd:{qid} schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }}
          
          OPTIONAL {{
            wd:{qid} schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }}
          
          OPTIONAL {{
            wd:{qid} wdt:P31 ?instanceOf .
            ?instanceOf rdfs:label ?instanceOfLabel .
            FILTER(LANG(?instanceOfLabel) = "en")
          }}
          
          OPTIONAL {{
            wd:{qid} wdt:P279 ?subclassOf .
            ?subclassOf rdfs:label ?subclassOfLabel .
            FILTER(LANG(?subclassOfLabel) = "en")
          }}
        }}
        """
        
        try:
            self._rate_limit()
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            bindings = results["results"]["bindings"]
            
            if not bindings:
                return None
            
            first = bindings[0]
            ja_label = first.get('jaLabel', {}).get('value', '')
            en_label = first.get('enLabel', {}).get('value', '')
            ja_desc = first.get('jaDescription', {}).get('value', '')
            en_desc = first.get('enDescription', {}).get('value', '')
            
            # Collect instance_of and subclass_of
            instance_of_list = []
            subclass_of_list = []
            
            for binding in bindings:
                if 'instanceOfLabel' in binding:
                    instance_of_list.append(binding['instanceOfLabel']['value'])
                if 'subclassOfLabel' in binding:
                    subclass_of_list.append(binding['subclassOfLabel']['value'])
            
            return CategoryInfo(
                qid=qid,
                label_ja=ja_label,
                label_en=en_label,
                description_ja=ja_desc,
                description_en=en_desc,
                instance_of=list(set(instance_of_list)),
                subclass_of=list(set(subclass_of_list))
            )
            
        except Exception as e:
            print(f"❌ Error getting category details: {e}")
            return None
    
    def find_subcategories(self, qid: str, depth: int = 1) -> Dict[str, List[CategoryInfo]]:
        """
        Find subcategories of a given category
        
        Wikidata uses P279 (subclass of) for hierarchical relationships.
        
        Args:
            qid: Parent category QID
            depth: How many levels deep to search (1-3 recommended)
        
        Returns:
            Dictionary with depth levels as keys and category lists as values
        """
        print(f"\n🔎 Finding subcategories of {qid} (depth: {depth})...")
        print("-" * 80)
        
        all_subcategories: Dict[int, List[CategoryInfo]] = {}
        visited: Set[str] = {qid}
        
        for level in range(1, depth + 1):
            print(f"\n📊 Level {level}:")
            
            # Get QIDs to search at this level
            if level == 1:
                parent_qids = [qid]
            else:
                parent_qids = [cat.qid for cat in all_subcategories.get(level - 1, [])]
            
            if not parent_qids:
                break
            
            level_subcategories = []
            
            for parent_qid in parent_qids:
                subcats = self._get_direct_subcategories(parent_qid)
                
                # Filter out already visited
                new_subcats = [cat for cat in subcats if cat.qid not in visited]
                
                for cat in new_subcats:
                    visited.add(cat.qid)
                    level_subcategories.append(cat)
            
            if level_subcategories:
                all_subcategories[level] = level_subcategories
                print(f"  Found {len(level_subcategories)} subcategories")
            else:
                print(f"  No subcategories found")
                break
            
            # Respect rate limits
            if level < depth:
                # Sleep at least 1s between levels to be conservative
                time.sleep(max(1, int(self._min_interval_sec)))
        
        return all_subcategories
    
    def _get_direct_subcategories(self, parent_qid: str, limit: int = 100) -> List[CategoryInfo]:
        """
        Get direct subcategories (subclasses) of a parent category
        
        Args:
            parent_qid: Parent category QID
            limit: Maximum results
        
        Returns:
            List of CategoryInfo objects
        """
        query = f"""
        SELECT DISTINCT ?item ?jaLabel ?enLabel ?jaDescription ?enDescription
        WHERE {{
          ?item wdt:P279 wd:{parent_qid} .  # subclass of parent
          
          OPTIONAL {{
            ?item rdfs:label ?jaLabel .
            FILTER(LANG(?jaLabel) = "ja")
          }}
          
          OPTIONAL {{
            ?item rdfs:label ?enLabel .
            FILTER(LANG(?enLabel) = "en")
          }}
          
          OPTIONAL {{
            ?item schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }}
          
          OPTIONAL {{
            ?item schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }}
        }}
        LIMIT {int(limit)}
        """
        
        try:
            self._rate_limit()
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            bindings = results["results"]["bindings"]
            
            subcategories = []
            for binding in bindings:
                qid = binding['item']['value'].split('/')[-1]
                ja_label = binding.get('jaLabel', {}).get('value', '')
                en_label = binding.get('enLabel', {}).get('value', '')
                ja_desc = binding.get('jaDescription', {}).get('value', '')
                en_desc = binding.get('enDescription', {}).get('value', '')
                
                category = CategoryInfo(
                    qid=qid,
                    label_ja=ja_label,
                    label_en=en_label,
                    description_ja=ja_desc,
                    description_en=en_desc
                )
                subcategories.append(category)
            
            return subcategories
            
        except Exception as e:
            print(f"  ⚠️  Error getting subcategories for {parent_qid}: {e}")
            return []
    
    def display_category(self, category: CategoryInfo, indent: int = 0) -> None:
        """Display category information in a formatted way"""
        prefix = "  " * indent
        
        print(f"{prefix}🏷️  {category.qid}")
        print(f"{prefix}   🇯🇵 日本語: {category.label_ja}")
        print(f"{prefix}   🇬🇧 English: {category.label_en if category.label_en else '(no English label)'}")
        
        if category.description_ja:
            desc_ja = category.description_ja[:60] + "..." if len(category.description_ja) > 60 else category.description_ja
            print(f"{prefix}   📝 説明: {desc_ja}")
        
        if category.description_en:
            desc_en = category.description_en[:60] + "..." if len(category.description_en) > 60 else category.description_en
            print(f"{prefix}   📝 Description: {desc_en}")
        
        if category.instance_of:
            print(f"{prefix}   📌 Instance of: {', '.join(category.instance_of[:3])}")
        
        if category.subclass_of:
            print(f"{prefix}   🔗 Subclass of: {', '.join(category.subclass_of[:3])}")
        
        print()
    
    def save_results(self, categories: List[CategoryInfo], 
                    filename: str = "category_mapping.json") -> None:
        """Save category mapping to JSON file"""
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        
        data = [
            {
                'qid': cat.qid,
                'japanese': cat.label_ja,
                'english': cat.label_en,
                'description_ja': cat.description_ja,
                'description_en': cat.description_en,
                'instance_of': cat.instance_of,
                'subclass_of': cat.subclass_of,
            }
            for cat in categories
        ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Results saved to: {filepath}")
    
    def export_to_csv(self, categories: List[CategoryInfo], 
                     filename: str = "category_mapping.csv") -> None:
        """Export category mapping to CSV file"""
        import pandas as pd
        
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        
        data = [
            {
                'QID': cat.qid,
                'Japanese_Label': cat.label_ja,
                'English_Label': cat.label_en,
                'Japanese_Description': cat.description_ja,
                'English_Description': cat.description_en,
                'Instance_Of': '; '.join(cat.instance_of),
                'Subclass_Of': '; '.join(cat.subclass_of),
            }
            for cat in categories
        ]
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"📊 CSV exported to: {filepath}")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Wikidata Category Finder - Find English equivalents of Japanese categories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by Japanese keyword (partial match)
  python %(prog)s --search "医学" --limit 20
  python %(prog)s --search "病気" --export-csv
  
  # Find exact Japanese category name and get English equivalent
  python %(prog)s --exact "病気"
  python %(prog)s --exact "医薬品"
  python %(prog)s --exact "感染症" --export-csv
  
  # Batch processing from file
  python %(prog)s --batch japanese_categories.txt --export-csv
  
  # Get details and subcategories for a specific QID
  python %(prog)s --qid Q12136 --show-details
  python %(prog)s --qid Q12136 --show-subcategories --depth 2
  
  # Combined search and subcategories
  python %(prog)s --search "医療" --limit 10 --show-subcategories
  
  # Export results
  python %(prog)s --exact "病気" --export-json --export-csv
        """
    )
    
    parser.add_argument('--search', type=str,
                       help='Japanese keyword to search for in category labels (partial match)')
    parser.add_argument('--exact', type=str,
                       help='Find exact Japanese category name and get English equivalent with Q number')
    parser.add_argument('--batch', type=str,
                       help='File containing list of Japanese categories (one per line) for batch processing')
    parser.add_argument('--qid', type=str,
                       help='Specific Wikidata QID to explore (e.g., Q12136)')
    parser.add_argument('--limit', type=int, default=50,
                       help='Maximum number of search results (default: 50)')
    parser.add_argument('--show-details', action='store_true',
                       help='Show detailed information about categories')
    parser.add_argument('--show-subcategories', action='store_true',
                       help='Show subcategories (uses P279 subclass relationship)')
    parser.add_argument('--depth', type=int, default=1,
                       help='Depth for subcategory search (1-3, default: 1)')
    parser.add_argument('--export-json', action='store_true',
                       help='Export results to JSON file')
    parser.add_argument('--export-csv', action='store_true',
                       help='Export results to CSV file')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='Configuration file path')
    
    return parser.parse_args()


def main() -> None:
    """Main function"""
    print("=" * 80)
    print("🔍 Wikidata Category Finder - Japanese to English Mapping")
    print("=" * 80)
    
    args = parse_arguments()
    
    # Validate input
    if not args.search and not args.qid and not args.exact and not args.batch:
        print("\n❌ Error: Please specify --search, --exact, --batch, or --qid")
        print("   Example: python wikidata_category_finder.py --search \"医学\"")
        print("   Example: python wikidata_category_finder.py --exact \"病気\"")
        print("   Example: python wikidata_category_finder.py --batch categories.txt")
        print("   Example: python wikidata_category_finder.py --qid Q12136")
        return
    
    # Initialize finder
    finder = WikidataCategoryFinder(config_path=args.config)
    
    all_categories = []
    
    # Exact match mode (NEW)
    if args.exact:
        category = finder.find_exact_japanese_category(args.exact)
        
        if category:
            print("\n📋 Exact Match Result:")
            print("=" * 80)
            print()
            
            # Display in a clear format
            print(f"🏷️  Q Number: {category.qid}")
            print(f"   🇯🇵 日本語: {category.label_ja}")
            print(f"   🇬🇧 English: {category.label_en if category.label_en else '(no English label)'}")
            print()
            
            if category.description_ja:
                desc_ja = category.description_ja[:80] + "..." if len(category.description_ja) > 80 else category.description_ja
                print(f"   📝 説明(JA): {desc_ja}")
            
            if category.description_en:
                desc_en = category.description_en[:80] + "..." if len(category.description_en) > 80 else category.description_en
                print(f"   📝 説明(EN): {desc_en}")
            
            print()
            print("=" * 80)
            print(f"✅ Result: {category.qid} | {category.label_ja} → {category.label_en}")
            print("=" * 80)
            
            all_categories.append(category)
        else:
            print(f"\n💡 Suggestion: Try partial search with --search \"{args.exact}\"")
    
    # Batch mode (NEW)
    elif args.batch:
        batch_file = Path(args.batch)
        
        if not batch_file.exists():
            print(f"\n❌ Error: File not found: {args.batch}")
            return
        
        # Read Japanese categories from file
        with open(batch_file, 'r', encoding='utf-8') as f:
            ja_categories = [
                line.strip() 
                for line in f 
                if line.strip() and not line.strip().startswith('#')
            ]
        
        if not ja_categories:
            print(f"\n❌ Error: No categories found in file: {args.batch}")
            return
        
        print(f"\n📁 Reading from: {args.batch}")
        print(f"   Found {len(ja_categories)} categories to process")
        
        results = finder.batch_find_japanese_categories(ja_categories)
        all_categories.extend(results)
        
        # Display results table
        if results:
            print("\n📊 Batch Results:")
            print("=" * 80)
            print(f"{'QID':<12} {'Japanese':<25} {'English':<30}")
            print("-" * 80)
            for cat in results:
                ja_label = cat.label_ja[:24] if len(cat.label_ja) > 24 else cat.label_ja
                en_label = cat.label_en[:29] if len(cat.label_en) > 29 else cat.label_en
                print(f"{cat.qid:<12} {ja_label:<25} {en_label:<30}")
            print("=" * 80)
    
    # Search by Japanese keyword
    elif args.search:
        categories = finder.search_categories_by_japanese_label(
            args.search, 
            limit=args.limit
        )
        
        if categories:
            print(f"\n📋 Search Results ({len(categories)} categories):")
            print("=" * 80)
            
            for i, category in enumerate(categories, 1):
                print(f"\n[{i}] ", end="")
                finder.display_category(category)
                
                # Get details if requested
                if args.show_details:
                    detailed = finder.get_category_details(category.qid)
                    if detailed:
                        category.instance_of = detailed.instance_of
                        category.subclass_of = detailed.subclass_of
            
            all_categories.extend(categories)
        else:
            print(f"\n❌ No categories found for '{args.search}'")
    
    # Explore specific QID
    if args.qid:
        print(f"\n🔎 Exploring QID: {args.qid}")
        print("=" * 80)
        
        category = finder.get_category_details(args.qid)
        
        if category:
            finder.display_category(category)
            all_categories.append(category)
            
            # Show subcategories if requested
            if args.show_subcategories:
                subcats_by_level = finder.find_subcategories(args.qid, depth=args.depth)
                
                if subcats_by_level:
                    print("\n📂 Subcategory Hierarchy:")
                    print("=" * 80)
                    
                    for level, subcats in sorted(subcats_by_level.items()):
                        print(f"\n{'  ' * (level - 1)}📁 Level {level} ({len(subcats)} subcategories):")
                        print(f"{'  ' * (level - 1)}{'-' * 60}")
                        
                        for subcat in subcats[:10]:  # Show first 10 per level
                            finder.display_category(subcat, indent=level)
                        
                        if len(subcats) > 10:
                            print(f"{'  ' * level}... and {len(subcats) - 10} more\n")
                        
                        all_categories.extend(subcats)
                else:
                    print("\n📭 No subcategories found")
        else:
            print(f"\n❌ Category {args.qid} not found")
    
    # Export results
    if all_categories:
        if args.export_json:
            finder.save_results(all_categories, "category_mapping.json")
        
        if args.export_csv:
            finder.export_to_csv(all_categories, "category_mapping.csv")
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Summary:")
        print("=" * 80)
        print(f"  Total categories found: {len(all_categories)}")
        
        with_en = sum(1 for cat in all_categories if cat.label_en)
        print(f"  With English labels: {with_en} ({with_en/len(all_categories)*100:.1f}%)")
        
        with_ja = sum(1 for cat in all_categories if cat.label_ja)
        print(f"  With Japanese labels: {with_ja} ({with_ja/len(all_categories)*100:.1f}%)")
        
        print("\n" + "=" * 80)
        print("✅ Done!")
        print("=" * 80)


if __name__ == "__main__":
    main()
