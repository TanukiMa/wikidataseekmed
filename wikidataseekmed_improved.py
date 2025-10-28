"""
Wikidata Medical Terms Extractor (Improved Version)

This tool extracts medical terminology from Wikidata with English and Japanese labels.
Improvements:
- YAML-based configuration
- Type hints
- Better error handling
- Resource management
- Reduced code duplication
- Security improvements

Usage:
  python wikidataseekmed_improved.py --small --limit 2000 --log logs/debug.log
  python wikidataseekmed_improved.py --medium --limit 5000 --batch-size 500 --log medium.log
"""

from typing import Dict, List, Optional, Any, Tuple
from SPARQLWrapper import SPARQLWrapper, JSON
from http.client import IncompleteRead
from urllib.error import URLError, HTTPError
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
import pandas as pd
import time
import socket
import logging
import traceback
import argparse
import yaml


@dataclass
class QueryStats:
    """Statistics for query execution"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_retries: int = 0
    total_items: int = 0
    timeout_504_errors: int = 0
    network_errors: int = 0
    other_errors: int = 0
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_queries == 0:
            return 0.0
        return round(self.successful_queries / self.total_queries * 100, 1)


@dataclass
class Config:
    """Configuration data class"""
    api_endpoint: str
    api_user_agent: str
    api_timeout: int
    batch_size: int
    max_retries: int
    max_empty_batches: int
    wait_between_categories: int
    wait_between_batches: int
    retry_wait_base: int
    retry_wait_504_base: int
    retry_wait_network_base: int
    retry_wait_max: int
    categories: Dict[str, Dict[str, str]]
    category_names_ja: Dict[str, str]
    medical_keywords: List[str]
    discovery_default_limit: int
    discovery_max_limit: int
    output_directory: str
    save_full_csv: bool
    save_bilingual_csv: bool
    save_category_csvs: bool
    save_json: bool
    save_report: bool
    
    @classmethod
    def from_yaml(cls, config_path: str = "config.yaml") -> "Config":
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(
            api_endpoint=data['api']['endpoint'],
            api_user_agent=data['api']['user_agent'],
            api_timeout=data['api']['timeout'],
            batch_size=data['query']['batch_size'],
            max_retries=data['query']['max_retries'],
            max_empty_batches=data['query']['max_empty_batches'],
            wait_between_categories=data['query']['wait_between_categories'],
            wait_between_batches=data['query']['wait_between_batches'],
            retry_wait_base=data['query']['retry_wait_base'],
            retry_wait_504_base=data['query']['retry_wait_504_base'],
            retry_wait_network_base=data['query']['retry_wait_network_base'],
            retry_wait_max=data['query']['retry_wait_max'],
            categories=data['categories'],
            category_names_ja=data['category_names_ja'],
            medical_keywords=data['medical_keywords'],
            discovery_default_limit=data['discovery']['default_limit'],
            discovery_max_limit=data['discovery']['max_limit'],
            output_directory=data['output']['directory'],
            save_full_csv=data['output']['save_full_csv'],
            save_bilingual_csv=data['output']['save_bilingual_csv'],
            save_category_csvs=data['output']['save_category_csvs'],
            save_json=data['output']['save_json'],
            save_report=data['output']['save_report'],
        )


class SPARQLQueryBuilder:
    """SPARQL query builder with parameterization to prevent injection"""
    
    @staticmethod
    def build_discovery_query(keywords: List[str], limit: int) -> str:
        """Build category discovery query with safe keyword filtering"""
        # Sanitize keywords to prevent injection
        safe_keywords = [SPARQLQueryBuilder._sanitize_keyword(kw) for kw in keywords]
        
        # Build filter clauses
        filter_clauses = [f'CONTAINS(LCASE(?enLabel), "{kw}")' for kw in safe_keywords]
        filter_clause = " || ".join(filter_clauses)
        
        query = f"""
        SELECT DISTINCT ?category ?enLabel ?jaLabel WHERE {{
          ?category wdt:P31 wd:Q4167836 .
          ?category rdfs:label ?enLabel FILTER(LANG(?enLabel) = "en") .
          OPTIONAL {{ ?category rdfs:label ?jaLabel FILTER(LANG(?jaLabel) = "ja") }}
          FILTER({filter_clause})
        }}
        LIMIT {int(limit)}
        """
        return query
    
    @staticmethod
    def build_batch_query(category_qid: str, batch_size: int, offset: int) -> str:
        """Build batch fetch query with safe parameters"""
        # Validate QID format
        if not SPARQLQueryBuilder._is_valid_qid(category_qid):
            raise ValueError(f"Invalid QID format: {category_qid}")
        
        # Ensure numeric parameters are integers
        batch_size = int(batch_size)
        offset = int(offset)
        
        query = f"""
        SELECT DISTINCT ?item ?enLabel ?jaLabel ?enDescription ?jaDescription 
               ?meshId ?icd10 ?icd9 ?snomedId ?umlsId
        WHERE {{
          ?item wdt:P31/wdt:P279* wd:{category_qid} .
          
          ?item rdfs:label ?enLabel .
          FILTER(LANG(?enLabel) = "en")
          
          OPTIONAL {{
            ?item rdfs:label ?jaLabel .
            FILTER(LANG(?jaLabel) = "ja")
          }}
          
          OPTIONAL {{
            ?item schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }}
          
          OPTIONAL {{
            ?item schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }}
          
          OPTIONAL {{ ?item wdt:P486 ?meshId }}
          OPTIONAL {{ ?item wdt:P494 ?icd10 }}
          OPTIONAL {{ ?item wdt:P493 ?icd9 }}
          OPTIONAL {{ ?item wdt:P5806 ?snomedId }}
          OPTIONAL {{ ?item wdt:P2892 ?umlsId }}
        }}
        LIMIT {batch_size}
        OFFSET {offset}
        """
        return query
    
    @staticmethod
    def _sanitize_keyword(keyword: str) -> str:
        """Sanitize keyword to prevent SPARQL injection"""
        # Remove quotes and special characters
        return keyword.replace('"', '').replace("'", '').replace('\\', '').strip()
    
    @staticmethod
    def _is_valid_qid(qid: str) -> bool:
        """Validate QID format (Q followed by digits)"""
        import re
        return bool(re.match(r'^Q\d+$', qid))


class MedicalTermsExtractor:
    """Extract medical terms from Wikidata with improved error handling and resource management"""
    
    def __init__(self, config: Config, log_file: Optional[str] = None):
        """Initialize extractor with configuration"""
        self.config = config
        self.stats = QueryStats()
        
        # Initialize SPARQL wrapper
        self.sparql = SPARQLWrapper(config.api_endpoint)
        self.sparql.setReturnFormat(JSON)
        self.sparql.addCustomHttpHeader("User-Agent", config.api_user_agent)
        self.sparql.setTimeout(config.api_timeout)
        
        # Setup logging
        self.logger = self._setup_logging(log_file)
    
    def _setup_logging(self, log_file: Optional[str]) -> logging.Logger:
        """Setup logging with proper resource management"""
        logger = logging.getLogger('WikidataExtractor')
        logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # File handler
            fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            
            # Console handler (errors only)
            ch = logging.StreamHandler()
            ch.setLevel(logging.ERROR)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)
            
            logger.addHandler(fh)
            logger.addHandler(ch)
            
            logger.info("=" * 60)
            logger.info("Wikidata Medical Terms Extractor - Log Started")
            logger.info("=" * 60)
            logger.info(f"Log file: {log_file}")
            logger.info(f"Batch size: {self.config.batch_size}")
            logger.info(f"Max retries: {self.config.max_retries}")
        else:
            logger.addHandler(logging.NullHandler())
        
        return logger
    
    def discover_medical_categories(self, limit: Optional[int] = None) -> Dict[str, str]:
        """Discover medical categories from Wikidata"""
        if limit is None:
            limit = self.config.discovery_default_limit
        limit = min(limit, self.config.discovery_max_limit)
        
        print("\n" + "=" * 60)
        print("Discovering Medical Categories from Wikidata")
        print("=" * 60)
        
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("MEDICAL CATEGORY DISCOVERY")
        self.logger.info("=" * 60)
        
        discovered = {}
        
        try:
            query = SPARQLQueryBuilder.build_discovery_query(
                self.config.medical_keywords, 
                limit
            )
            
            self.logger.info("Discovery query:")
            self.logger.debug(query)
            
            print(f"\nSearching for medical categories...")
            print(f"Keywords: {', '.join(self.config.medical_keywords[:10])}...")
            
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            bindings = results["results"]["bindings"]
            
            print(f"Found {len(bindings)} potential medical categories")
            self.logger.info(f"Found {len(bindings)} categories")
            
            for binding in bindings:
                qid = binding['category']['value'].split('/')[-1]
                en_label = binding.get('enLabel', {}).get('value', '')
                ja_label = binding.get('jaLabel', {}).get('value', '')
                
                # Normalize category name
                if en_label.startswith('Category:'):
                    en_label = en_label[9:].strip()
                
                discovered[qid] = en_label
                
                if ja_label and en_label not in self.config.category_names_ja:
                    self.config.category_names_ja[en_label] = ja_label
                
                self.logger.info(f"  {qid}: {en_label}" + 
                               (f" ({ja_label})" if ja_label else ""))
            
            # Display summary
            print("\nDiscovered categories summary:")
            print("-" * 60)
            for i, (qid, name) in enumerate(list(discovered.items())[:20]):
                ja_name = self.config.category_names_ja.get(name, "")
                display = f"  {qid}: {name}"
                if ja_name:
                    display += f" ({ja_name})"
                print(display)
            
            if len(discovered) > 20:
                print(f"  ... and {len(discovered) - 20} more")
            
            print("-" * 60)
            
        except Exception as e:
            print(f"Error during discovery: {e}")
            self.logger.error(f"Discovery error: {e}")
            self.logger.error(traceback.format_exc())
        
        return discovered
    
    def save_discovered_categories(self, discovered: Dict[str, str], 
                                   filename: str = "discovered_categories.csv") -> None:
        """Save discovered categories to CSV"""
        if not discovered:
            print("No categories to save")
            return
        
        output_dir = Path(self.config.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / filename
        
        rows = [
            {
                'qid': qid,
                'category_en': en_name,
                'category_ja': self.config.category_names_ja.get(en_name, "")
            }
            for qid, en_name in discovered.items()
        ]
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"\nDiscovered categories saved to: {filepath}")
        self.logger.info(f"Saved discovered categories to: {filepath}")
    
    def _calculate_retry_wait(self, retry_count: int, error_type: str) -> int:
        """Calculate wait time for retry with exponential backoff"""
        if error_type == '504':
            # Exponential backoff for 504 errors
            wait = min(self.config.retry_wait_max, 
                      (3 ** retry_count) * self.config.retry_wait_504_base)
        elif error_type == 'network':
            # Exponential backoff for network errors
            wait = min(self.config.retry_wait_max, 
                      (2 ** retry_count) * self.config.retry_wait_network_base)
        else:
            # Linear backoff for other errors
            wait = (retry_count + 1) * self.config.retry_wait_base
        
        return int(wait)
    
    def execute_sparql_with_retry(self, query: str, category_name: str, 
                                  offset: int, batch_size: int, 
                                  retry_count: int = 0) -> Dict[str, Any]:
        """Execute SPARQL query with retry mechanism"""
        self.stats.total_queries += 1
        
        self.logger.info("")
        self.logger.info("-" * 60)
        self.logger.info("SPARQL Query Execution")
        self.logger.info("-" * 60)
        self.logger.info(f"Category: {category_name}")
        self.logger.info(f"Offset: {offset}")
        self.logger.info(f"Batch Size: {batch_size}")
        self.logger.info(f"Query Number: {self.stats.total_queries}")
        self.logger.debug(f"Query:\n{query}")
        self.logger.info("-" * 60)
        
        start_time = time.time()
        
        try:
            self.sparql.setQuery(query)
            self.logger.info(f"Sending HTTP Request to: {self.config.api_endpoint}")
            
            results = self.sparql.query().convert()
            elapsed_time = time.time() - start_time
            bindings = results["results"]["bindings"]
            
            self.logger.info("")
            self.logger.info("Response:")
            self.logger.info(f"  Results: {len(bindings)} items")
            self.logger.info(f"  Elapsed Time: {elapsed_time:.2f} seconds")
            
            if bindings:
                self.logger.info("  Sample (first 3 items):")
                for i, binding in enumerate(bindings[:3]):
                    item_id = binding.get('item', {}).get('value', '').split('/')[-1]
                    en_label = binding.get('enLabel', {}).get('value', '')
                    ja_label = binding.get('jaLabel', {}).get('value', '')
                    self.logger.info(f"    [{i+1}] {item_id} | EN: {en_label} | JA: {ja_label}")
            
            self.logger.info("-" * 60)
            
            self.stats.successful_queries += 1
            self.stats.total_items += len(bindings)
            
            return results
            
        except HTTPError as e:
            return self._handle_http_error(e, query, category_name, offset, 
                                          batch_size, retry_count)
        
        except (IncompleteRead, URLError, socket.timeout) as e:
            return self._handle_network_error(e, query, category_name, offset, 
                                             batch_size, retry_count)
        
        except Exception as e:
            return self._handle_general_error(e, query, category_name, offset, 
                                             batch_size, retry_count)
    
    def _handle_http_error(self, error: HTTPError, query: str, category_name: str,
                          offset: int, batch_size: int, retry_count: int) -> Dict[str, Any]:
        """Handle HTTP errors with specific logic for 504"""
        self.stats.failed_queries += 1
        self._log_error(error, retry_count + 1, category_name, offset)
        
        if error.code == 504:
            self.stats.timeout_504_errors += 1
            
            if retry_count < self.config.max_retries:
                self.stats.total_retries += 1
                wait_time = self._calculate_retry_wait(retry_count, '504')
                
                print(f"504 Gateway Timeout (attempt {retry_count + 1}/{self.config.max_retries})")
                print("Query too complex or server overloaded.")
                print("Consider reducing --batch-size or --limit")
                print(f"Waiting {wait_time} seconds before retry...")
                
                self.logger.warning(f"504 Gateway Timeout - Retrying after {wait_time} seconds...")
                self.logger.warning("Suggestion: Reduce batch size or query complexity")
                
                time.sleep(wait_time)
                return self.execute_sparql_with_retry(query, category_name, offset, 
                                                     batch_size, retry_count + 1)
            else:
                self._log_504_exhausted()
                raise
        else:
            self.stats.other_errors += 1
            return self._retry_or_raise(error, query, category_name, offset, 
                                       batch_size, retry_count, 'http')
    
    def _handle_network_error(self, error: Exception, query: str, category_name: str,
                             offset: int, batch_size: int, retry_count: int) -> Dict[str, Any]:
        """Handle network errors"""
        self.stats.failed_queries += 1
        self.stats.network_errors += 1
        self._log_error(error, retry_count + 1, category_name, offset)
        
        return self._retry_or_raise(error, query, category_name, offset, 
                                   batch_size, retry_count, 'network')
    
    def _handle_general_error(self, error: Exception, query: str, category_name: str,
                             offset: int, batch_size: int, retry_count: int) -> Dict[str, Any]:
        """Handle general errors"""
        self.stats.failed_queries += 1
        self.stats.other_errors += 1
        self._log_error(error, retry_count + 1, category_name, offset)
        
        return self._retry_or_raise(error, query, category_name, offset, 
                                   batch_size, retry_count, 'general')
    
    def _retry_or_raise(self, error: Exception, query: str, category_name: str,
                       offset: int, batch_size: int, retry_count: int, 
                       error_type: str) -> Dict[str, Any]:
        """Generic retry logic"""
        if retry_count < self.config.max_retries:
            self.stats.total_retries += 1
            wait_time = self._calculate_retry_wait(retry_count, error_type)
            
            error_name = type(error).__name__
            if hasattr(error, 'code'):
                error_name = f"HTTP Error {error.code}"
            
            print(f"{error_name} (attempt {retry_count + 1}/{self.config.max_retries})")
            print(f"Waiting {wait_time} seconds before retry...")
            
            self.logger.warning(f"Retrying after {wait_time} seconds...")
            
            time.sleep(wait_time)
            return self.execute_sparql_with_retry(query, category_name, offset, 
                                                 batch_size, retry_count + 1)
        else:
            self.logger.error("Max retries reached. Giving up on this batch.")
            raise
    
    def _log_error(self, error: Exception, retry_count: int, 
                   category_name: str, offset: int) -> None:
        """Log error details"""
        self.logger.error("")
        self.logger.error("!" * 60)
        self.logger.error("ERROR OCCURRED")
        self.logger.error("!" * 60)
        self.logger.error(f"Category: {category_name}")
        self.logger.error(f"Offset: {offset}")
        self.logger.error(f"Retry Attempt: {retry_count}")
        self.logger.error(f"Error Type: {type(error).__name__}")
        self.logger.error(f"Error Message: {error}")
        self.logger.error("")
        self.logger.error("Traceback:")
        self.logger.error(traceback.format_exc())
        self.logger.error("!" * 60)
    
    def _log_504_exhausted(self) -> None:
        """Log when 504 retries are exhausted"""
        self.logger.error("Max retries reached for 504 error.")
        self.logger.error("Recommendation: Use smaller batch size or download Wikidata dumps")
        self.logger.error("Dumps available at: https://dumps.wikimedia.org/wikidatawiki/entities/")
        
        print("\n" + "!" * 60)
        print("PERSISTENT 504 TIMEOUT ERROR")
        print("!" * 60)
        print("The query is too complex for the Wikidata server.")
        print("\nSuggestions:")
        print("1. Reduce --batch-size (try 100-300)")
        print("2. Reduce --limit per category")
        print("3. Use Wikidata dumps for offline processing:")
        print("   https://dumps.wikimedia.org/wikidatawiki/entities/")
        print("4. Check service status: https://status.wikimedia.org/")
        print("!" * 60 + "\n")
    
    def fetch_batch(self, category_qid: str, category_name: str, 
                   offset: int, batch_size: int) -> List[Dict[str, Any]]:
        """Fetch one batch of data"""
        query = SPARQLQueryBuilder.build_batch_query(category_qid, batch_size, offset)
        results = self.execute_sparql_with_retry(query, category_name, offset, batch_size)
        return results["results"]["bindings"]
    
    def fetch_terms_by_category(self, category_qid: str, category_name_en: str, 
                               limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Fetch medical terms from specified category with pagination"""
        category_name_ja = self.config.category_names_ja.get(category_name_en, category_name_en)
        
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info(f"Starting Category: {category_name_en} ({category_qid})")
        self.logger.info(f"Japanese: {category_name_ja}")
        self.logger.info("=" * 60)
        
        print("\n" + "=" * 60)
        print(f"Category: {category_name_en} ({category_name_ja})")
        print("=" * 60)
        
        all_terms = []
        offset = 0
        consecutive_empty = 0
        
        effective_limit = limit if limit is not None else 1000000
        
        self.logger.info(f"Limit: {effective_limit}")
        self.logger.info(f"Batch Size: {self.config.batch_size}")
        
        while offset < effective_limit:
            try:
                remaining = effective_limit - offset
                current_batch_size = min(self.config.batch_size, remaining)
                
                print(f"  Fetching... offset={offset} (current: {len(all_terms)} items)", end='\r')
                
                bindings = self.fetch_batch(category_qid, category_name_en, offset, current_batch_size)
                
                if not bindings:
                    consecutive_empty += 1
                    self.logger.warning(f"Empty batch received. Consecutive empty: {consecutive_empty}")
                    
                    if consecutive_empty >= self.config.max_empty_batches:
                        print("\n  No more results. Category completed.")
                        self.logger.info("Category completed (consecutive empty batches)")
                        break
                    
                    offset += current_batch_size
                    continue
                
                consecutive_empty = 0
                
                for result in bindings:
                    term = {
                        'qid': result['item']['value'].split('/')[-1],
                        'category_en': category_name_en,
                        'category_ja': category_name_ja,
                        'category_qid': category_qid,
                        'en_label': result.get('enLabel', {}).get('value', ''),
                        'ja_label': result.get('jaLabel', {}).get('value', ''),
                        'en_description': result.get('enDescription', {}).get('value', ''),
                        'ja_description': result.get('jaDescription', {}).get('value', ''),
                        'mesh_id': result.get('meshId', {}).get('value', ''),
                        'icd10': result.get('icd10', {}).get('value', ''),
                        'icd9': result.get('icd9', {}).get('value', ''),
                        'snomed_id': result.get('snomedId', {}).get('value', ''),
                        'umls_id': result.get('umlsId', {}).get('value', ''),
                    }
                    all_terms.append(term)
                
                if len(bindings) < current_batch_size:
                    print("\n  Last batch received.")
                    self.logger.info("Last batch received (partial batch)")
                    break
                
                offset += current_batch_size
                time.sleep(self.config.wait_between_batches)
                
            except Exception as e:
                print(f"\n  Batch fetch failed (offset={offset}): {e}")
                self.logger.error(f"Batch fetch failed at offset {offset}. Skipping category.")
                self.logger.error(traceback.format_exc())
                print("  Skipping this category and continuing...")
                break
        
        print(f"\n  Completed: {len(all_terms)} items")
        
        self.logger.info("")
        self.logger.info(f"Category Completed: {category_name_en}")
        self.logger.info(f"Total items collected: {len(all_terms)}")
        self.logger.info("=" * 60)
        
        return all_terms
    
    def extract_all(self, categories: Dict[str, str], 
                   limit_per_category: Optional[int] = None) -> pd.DataFrame:
        """Extract medical terms from all categories"""
        all_terms = []
        
        print("\n" + "=" * 60)
        print(f"Medical Terms Extraction: {len(categories)} categories")
        if limit_per_category is None or limit_per_category == 0:
            print("Per category: Unlimited (practical limit: 1M items)")
        else:
            print(f"Per category max: {limit_per_category} items")
        print(f"Batch size: {self.config.batch_size} items")
        print("=" * 60)
        
        self.logger.info("")
        self.logger.info("#" * 60)
        self.logger.info("EXTRACTION START")
        self.logger.info("#" * 60)
        self.logger.info(f"Total Categories: {len(categories)}")
        self.logger.info(f"Limit per Category: {limit_per_category if limit_per_category else 'Unlimited'}")
        
        start_time = time.time()
        
        for idx, (qid, name_en) in enumerate(categories.items(), 1):
            name_ja = self.config.category_names_ja.get(name_en, name_en)
            print(f"\n[{idx}/{len(categories)}] {name_en} ({name_ja})")
            
            terms = self.fetch_terms_by_category(qid, name_en, limit_per_category)
            all_terms.extend(terms)
            
            if idx < len(categories):
                time.sleep(self.config.wait_between_categories)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("Extraction completed")
        print(f"Total items: {len(all_terms)}")
        print(f"Elapsed time: {elapsed_time/60:.1f} minutes")
        print("=" * 60 + "\n")
        
        self._log_extraction_summary(len(all_terms), elapsed_time)
        
        df = pd.DataFrame(all_terms)
        
        if len(df) == 0:
            print("Warning: No data collected.")
            self.logger.warning("No data collected!")
            return df
        
        # Remove duplicates
        original_count = len(df)
        df = df.drop_duplicates(subset=['qid'])
        duplicates_removed = original_count - len(df)
        
        if duplicates_removed > 0:
            print(f"Duplicates removed: {duplicates_removed}")
            print(f"Unique items: {len(df)}\n")
            
            self.logger.info("")
            self.logger.info(f"Duplicates removed: {duplicates_removed}")
            self.logger.info(f"Unique items: {len(df)}")
        
        return df
    
    def _log_extraction_summary(self, total_items: int, elapsed_time: float) -> None:
        """Log extraction summary"""
        self.logger.info("")
        self.logger.info("#" * 60)
        self.logger.info("EXTRACTION COMPLETED")
        self.logger.info("#" * 60)
        self.logger.info(f"Total Items Collected: {total_items}")
        self.logger.info(f"Elapsed Time: {elapsed_time/60:.1f} minutes")
        self.logger.info("")
        self.logger.info("Statistics:")
        self.logger.info(f"  Total Queries: {self.stats.total_queries}")
        self.logger.info(f"  Successful Queries: {self.stats.successful_queries}")
        self.logger.info(f"  Failed Queries: {self.stats.failed_queries}")
        self.logger.info(f"  Total Retries: {self.stats.total_retries}")
        self.logger.info(f"  Total Items Retrieved: {self.stats.total_items}")
        self.logger.info("")
        self.logger.info("Error Breakdown:")
        self.logger.info(f"  504 Gateway Timeout: {self.stats.timeout_504_errors}")
        self.logger.info(f"  Network Errors: {self.stats.network_errors}")
        self.logger.info(f"  Other Errors: {self.stats.other_errors}")
        
        success_rate = self.stats.success_rate()
        if success_rate > 0:
            self.logger.info("")
            self.logger.info(f"  Success Rate: {success_rate}%")
        self.logger.info("#" * 60)
    
    def analyze_data_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Analyze data quality"""
        if len(df) == 0:
            print("No data available. Skipping analysis.")
            return pd.DataFrame()
        
        print("\n" + "=" * 60)
        print("Data Quality Analysis")
        print("=" * 60 + "\n")
        
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("DATA QUALITY ANALYSIS")
        self.logger.info("=" * 60)
        
        # Basic statistics
        print("1. Basic Statistics:")
        print(f"   Total records: {len(df)}")
        self.logger.info(f"Total Records: {len(df)}")
        
        print(f"   Unique QIDs: {df['qid'].nunique()}")
        self.logger.info(f"Unique QIDs: {df['qid'].nunique()}")
        
        # Language coverage
        print("\n2. Language Coverage:")
        has_en = (df['en_label'].notna() & (df['en_label'] != '')).sum()
        has_ja = (df['ja_label'].notna() & (df['ja_label'] != '')).sum()
        
        en_pct = has_en / len(df) * 100
        ja_pct = has_ja / len(df) * 100
        
        print(f"   English labels: {has_en} ({en_pct:.1f}%)")
        print(f"   Japanese labels: {has_ja} ({ja_pct:.1f}%)")
        
        self.logger.info(f"English Labels: {has_en} ({en_pct:.1f}%)")
        self.logger.info(f"Japanese Labels: {has_ja} ({ja_pct:.1f}%)")
        
        # Description coverage
        print("\n3. Description Coverage:")
        has_en_desc = (df['en_description'].notna() & (df['en_description'] != '')).sum()
        has_ja_desc = (df['ja_description'].notna() & (df['ja_description'] != '')).sum()
        
        print(f"   English descriptions: {has_en_desc} ({has_en_desc/len(df)*100:.1f}%)")
        print(f"   Japanese descriptions: {has_ja_desc} ({has_ja_desc/len(df)*100:.1f}%)")
        
        # External ID coverage
        print("\n4. External ID Coverage:")
        external_ids = [
            ('mesh_id', 'MeSH'),
            ('icd10', 'ICD-10'),
            ('icd9', 'ICD-9'),
            ('snomed_id', 'SNOMED CT'),
            ('umls_id', 'UMLS')
        ]
        
        for col, name in external_ids:
            count = (df[col].notna() & (df[col] != '')).sum()
            pct = count / len(df) * 100
            print(f"   {name}: {count} ({pct:.1f}%)")
            self.logger.info(f"{name}: {count} ({pct:.1f}%)")
        
        # Category breakdown
        print("\n5. Items by Category:")
        self.logger.info("")
        self.logger.info("Category Breakdown:")
        category_counts = df['category_en'].value_counts().sort_values(ascending=False)
        
        for category, count in category_counts.items():
            cat_ja = self.config.category_names_ja.get(category, category)
            print(f"   {category} ({cat_ja}): {count}")
            self.logger.info(f"  {category}: {count}")
        
        # Bilingual pairs
        print("\n6. English-Japanese Pairs:")
        bilingual = df[(df['en_label'] != '') & (df['ja_label'] != '')]
        bi_pct = len(bilingual) / len(df) * 100
        
        print(f"   Bilingual pairs: {len(bilingual)} ({bi_pct:.1f}%)")
        self.logger.info(f"Bilingual Pairs: {len(bilingual)} ({bi_pct:.1f}%)")
        
        print("\n" + "=" * 60 + "\n")
        self.logger.info("=" * 60)
        
        return bilingual
    
    def save_results(self, df: pd.DataFrame, prefix: str = "small") -> Dict[str, Optional[Path]]:
        """Save results as CSV and JSON with proper path handling"""
        if len(df) == 0:
            print("No data to save. Skipping.")
            self.logger.warning("No data to save")
            return {}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(self.config.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("Saving results...\n")
        self.logger.info("")
        self.logger.info("Saving results...")
        
        saved_files = {}
        
        # Full CSV
        if self.config.save_full_csv:
            full_csv = output_dir / f"{prefix}_medical_terms_full_{timestamp}.csv"
            df.to_csv(full_csv, index=False, encoding='utf-8-sig')
            file_size_mb = full_csv.stat().st_size / (1024 * 1024)
            print(f"   Full CSV: {full_csv} ({file_size_mb:.2f} MB)")
            self.logger.info(f"Full CSV: {full_csv} ({file_size_mb:.2f} MB)")
            saved_files['full_csv'] = full_csv
        
        # EN-JA pairs CSV
        bilingual_df = df[(df['en_label'] != '') & (df['ja_label'] != '')].copy()
        if self.config.save_bilingual_csv and len(bilingual_df) > 0:
            bilingual_csv = output_dir / f"{prefix}_en_ja_pairs_{timestamp}.csv"
            cols_to_save = ['en_label', 'ja_label', 'category_en', 'category_ja', 
                          'en_description', 'ja_description', 'qid']
            bilingual_df[cols_to_save].to_csv(bilingual_csv, index=False, encoding='utf-8-sig')
            file_size_mb = bilingual_csv.stat().st_size / (1024 * 1024)
            print(f"   EN-JA pairs CSV: {bilingual_csv} ({len(bilingual_df)} pairs, {file_size_mb:.2f} MB)")
            self.logger.info(f"EN-JA pairs CSV: {bilingual_csv} ({len(bilingual_df)} pairs, {file_size_mb:.2f} MB)")
            saved_files['bilingual_csv'] = bilingual_csv
        
        # Category CSVs
        if self.config.save_category_csvs:
            category_dir = output_dir / f"by_category_{timestamp}"
            category_dir.mkdir(parents=True, exist_ok=True)
            
            for category in df['category_en'].unique():
                cat_df = df[df['category_en'] == category]
                safe_name = category.replace('/', '_').replace('\\', '_').replace(' ', '_')
                cat_file = category_dir / f"{safe_name}.csv"
                cat_df.to_csv(cat_file, index=False, encoding='utf-8-sig')
            
            cat_count = len(df['category_en'].unique())
            print(f"   Category CSVs: {category_dir}/ ({cat_count} files)")
            self.logger.info(f"Category CSVs: {category_dir}/ ({cat_count} files)")
            saved_files['category_dir'] = category_dir
        
        # JSON
        if self.config.save_json:
            json_file = output_dir / f"{prefix}_medical_terms_{timestamp}.json"
            df.to_json(json_file, orient='records', force_ascii=False, indent=2)
            file_size_mb = json_file.stat().st_size / (1024 * 1024)
            print(f"   JSON: {json_file} ({file_size_mb:.2f} MB)")
            self.logger.info(f"JSON: {json_file} ({file_size_mb:.2f} MB)")
            saved_files['json'] = json_file
        
        # Report
        if self.config.save_report:
            report_file = output_dir / f"{prefix}_report_{timestamp}.txt"
            self._save_report(df, bilingual_df, report_file, prefix)
            print(f"   Report: {report_file}")
            self.logger.info(f"Report: {report_file}")
            saved_files['report'] = report_file
        
        print("\nSave completed!\n")
        self.logger.info("")
        self.logger.info("All results saved successfully")
        
        return saved_files
    
    def _save_report(self, df: pd.DataFrame, bilingual_df: pd.DataFrame, 
                    report_file: Path, prefix: str) -> None:
        """Save extraction report"""
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("Wikidata Medical Terms Extraction Report\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Scale: {prefix}\n")
            f.write(f"Total items: {len(df)}\n")
            f.write(f"EN-JA pairs: {len(bilingual_df)}\n")
            
            if len(df) > 0:
                f.write(f"Bilingual ratio: {len(bilingual_df)/len(df)*100:.1f}%\n\n")
            
            f.write("Statistics:\n")
            f.write(f"  Total queries: {self.stats.total_queries}\n")
            f.write(f"  Successful: {self.stats.successful_queries}\n")
            f.write(f"  Failed: {self.stats.failed_queries}\n")
            f.write(f"  Retries: {self.stats.total_retries}\n\n")
            
            f.write("Error Breakdown:\n")
            f.write(f"  504 Gateway Timeout: {self.stats.timeout_504_errors}\n")
            f.write(f"  Network Errors: {self.stats.network_errors}\n")
            f.write(f"  Other Errors: {self.stats.other_errors}\n\n")
            
            f.write("Items by category:\n")
            for category, count in df['category_en'].value_counts().items():
                cat_ja = self.config.category_names_ja.get(category, category)
                f.write(f"  {category} ({cat_ja}): {count}\n")
            
            f.write("\nLanguage coverage:\n")
            has_ja = (df['ja_label'].notna() & (df['ja_label'] != '')).sum()
            ja_pct = has_ja / len(df) * 100 if len(df) > 0 else 0
            f.write(f"  Japanese labels: {has_ja} ({ja_pct:.1f}%)\n")
            
            f.write("\nExternal ID coverage:\n")
            external_ids = [
                ('mesh_id', 'MeSH'),
                ('icd10', 'ICD-10'),
                ('snomed_id', 'SNOMED CT'),
                ('umls_id', 'UMLS')
            ]
            for col, name in external_ids:
                count = (df[col].notna() & (df[col] != '')).sum()
                pct = count / len(df) * 100 if len(df) > 0 else 0
                f.write(f"  {name}: {count} ({pct:.1f}%)\n")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Wikidata Medical Terms Extractor (Improved Version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic extraction:
    python %(prog)s --small --limit 2000 --log logs/small.log
    python %(prog)s --medium --limit 5000 --batch-size 500 --log logs/medium.log
    python %(prog)s --large --limit 0 --log logs/large.log
  
  Discover medical categories:
    python %(prog)s --small --discover --limit 1000 --log logs/discover.log
    python %(prog)s --medium --discover-only --discover-limit 200
  
  Use custom config:
    python %(prog)s --small --config my_config.yaml --log logs/test.log
        """
    )
    
    size_group = parser.add_mutually_exclusive_group(required=True)
    size_group.add_argument('--small', action='store_true', help='Small test (5 categories)')
    size_group.add_argument('--medium', action='store_true', help='Medium test (15 categories)')
    size_group.add_argument('--large', action='store_true', help='Large test (30+ categories)')
    
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='Configuration file path (default: config.yaml)')
    parser.add_argument('--limit', type=int, default=2000, 
                       help='Max items per category (0 for unlimited, default: 2000)')
    parser.add_argument('--batch-size', type=int, default=None,
                       help='Items per query (default: from config, reduce to 100-300 for 504 timeouts)')
    parser.add_argument('--log', type=str, default=None,
                       help='Log file path (e.g., logs/debug.log)')
    parser.add_argument('--discover', action='store_true',
                       help='Discover medical categories from Wikidata before extraction')
    parser.add_argument('--discover-only', action='store_true',
                       help='Only discover categories, do not extract terms')
    parser.add_argument('--discover-limit', type=int, default=None,
                       help='Maximum categories to discover (default: from config)')
    
    return parser.parse_args()


def get_category_selection(args: argparse.Namespace, config: Config, 
                          discovered: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Get category selection based on arguments and user input"""
    # Base categories
    if args.small:
        base_categories = config.categories['small']
    elif args.medium:
        base_categories = config.categories['medium']
    else:
        base_categories = config.categories['large']
    
    # If no discovery, return base categories
    if not discovered:
        return base_categories
    
    # Ask user for preference
    print("\n" + "=" * 60)
    print("Use discovered categories for extraction?")
    print("=" * 60)
    print("Options:")
    print("  1. Use only predefined categories (default)")
    print("  2. Use only discovered categories")
    print("  3. Use both predefined and discovered")
    print("")
    
    while True:
        choice = input("Enter choice (1/2/3) [1]: ").strip() or "1"
        
        if choice == "1":
            print("Using predefined categories only")
            return base_categories
        elif choice == "2":
            print("Using discovered categories only")
            return discovered
        elif choice == "3":
            print("Using both predefined and discovered categories")
            return {**base_categories, **discovered}
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


def main() -> None:
    """Main function"""
    print("=" * 60)
    print("Wikidata Medical Terms Extractor (Improved)")
    print("(English categories with EN-JA pairs)")
    print("=" * 60)
    
    args = parse_arguments()
    
    # Load configuration
    try:
        config = Config.from_yaml(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create a config.yaml file or specify --config path")
        return
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return
    
    # Override batch size if specified
    if args.batch_size is not None:
        config.batch_size = args.batch_size
    
    # Determine scale
    if args.small:
        size_name = "small"
        size_label = "Small"
        category_count = 5
    elif args.medium:
        size_name = "medium"
        size_label = "Medium"
        category_count = 15
    else:
        size_name = "large"
        size_label = "Large"
        category_count = "30+"
    
    limit_label = "Unlimited" if args.limit == 0 else f"{args.limit} items"
    
    print("\nConfiguration:")
    print(f"  Config file: {args.config}")
    print(f"  Scale: {size_label} ({category_count} categories)")
    print(f"  Per category: {limit_label}")
    print(f"  Batch size: {config.batch_size} items")
    print(f"  Log file: {args.log if args.log else 'None'}")
    print("")
    
    # Estimate time
    if args.small and args.limit <= 2000:
        est_time = "10-20 minutes"
    elif args.medium and args.limit <= 5000:
        est_time = "1-2 hours"
    elif args.large or args.limit == 0:
        est_time = "Several hours or more"
    else:
        est_time = "Varies"
    
    print(f"Estimated time: {est_time}")
    print("=" * 60)
    
    # Initialize extractor
    extractor = MedicalTermsExtractor(config=config, log_file=args.log)
    
    # Category discovery mode
    discovered = None
    if args.discover or args.discover_only:
        discover_limit = args.discover_limit if args.discover_limit else config.discovery_default_limit
        discovered = extractor.discover_medical_categories(limit=discover_limit)
        
        if discovered:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extractor.save_discovered_categories(
                discovered, 
                filename=f"discovered_medical_categories_{timestamp}.csv"
            )
        
        if args.discover_only:
            print("\n" + "=" * 60)
            print("Discovery completed!")
            print("=" * 60)
            print(f"\nTotal discovered: {len(discovered)} categories")
            print("Check output/discovered_medical_categories_*.csv")
            return
    
    # Get categories to use
    categories = get_category_selection(args, config, discovered)
    
    # Extract terms
    limit = None if args.limit == 0 else args.limit
    df = extractor.extract_all(categories, limit_per_category=limit)
    
    # Analyze quality
    bilingual_df = extractor.analyze_data_quality(df)
    
    # Show sample
    if len(bilingual_df) > 0:
        print("Sample data (EN-JA pairs, first 5):")
        print("=" * 80)
        sample = bilingual_df[['en_label', 'ja_label', 'category_en']].head()
        for idx, row in sample.iterrows():
            en_part = row['en_label'][:30].ljust(30)
            ja_part = row['ja_label'][:20].ljust(20)
            cat_part = f"[{row['category_en']}]"
            print(f"  {en_part} <-> {ja_part} {cat_part}")
        print("=" * 80 + "\n")
    
    # Save results
    files = extractor.save_results(df, prefix=size_name)
    
    print("=" * 60)
    print("Extraction completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Check CSV files in output folder")
    print("2. Review data quality")
    if args.log:
        print(f"3. Check log file: {args.log}")
    print("")


if __name__ == "__main__":
    main()
