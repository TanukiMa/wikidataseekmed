"""
Wikidata Medical Terms Extractor (English categories with EN-JA pairs)
Usage: 
  python wikidataseekmed.py --small --limit 2000 --log logs/debug.log
  python wikidataseekmed.py --medium --limit 5000 --batch-size 500 --log medium.log
"""

from SPARQLWrapper import SPARQLWrapper, JSON
import pandas as pd
import time
from datetime import datetime
import os
import argparse
from http.client import IncompleteRead
from urllib.error import URLError, HTTPError
import socket
import logging
import traceback

class MedicalTermsExtractor:
    def __init__(self, batch_size=1000, max_retries=5, log_file=None):
        self.sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        self.sparql.setReturnFormat(JSON)
        self.sparql.addCustomHttpHeader("User-Agent", "MedicalTermsExtractor/1.0")
        self.sparql.setTimeout(600)  # 10 minutes timeout for complex queries
        
        self.batch_size = batch_size
        self.max_retries = max_retries
        
        self.setup_logging(log_file)
        
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_retries': 0,
            'total_items': 0,
            'timeout_504_errors': 0,
            'network_errors': 0,
            'other_errors': 0,
        }
        
        # English category definitions (small scale)
        self.small_test_categories = {
            'Q12136': 'disease',
            'Q12140': 'medication',
            'Q169872': 'symptom',
            'Q796194': 'surgery',
            'Q1059392': 'medical test',
        }
        
        # English category definitions (medium scale)
        self.medium_test_categories = {
            'Q12136': 'disease',
            'Q12140': 'medication',
            'Q169872': 'symptom',
            'Q796194': 'surgery',
            'Q1059392': 'medical test',
            'Q8054': 'protein',
            'Q7187': 'gene',
            'Q4936952': 'anatomical structure',
            'Q18123741': 'infectious disease',
            'Q11173': 'chemical compound',
            'Q2095549': 'medical procedure',
            'Q10876': 'bacteria',
            'Q808': 'virus',
            'Q179661': 'therapeutic agent',
            'Q12139612': 'medical device',
        }
        
        # English category definitions (large scale)
        self.large_test_categories = {
            'Q12136': 'disease',
            'Q18123741': 'infectious disease',
            'Q929833': 'rare disease',
            'Q18965518': 'mental disorder',
            'Q18556609': 'neurological disorder',
            'Q4936952': 'anatomical structure',
            'Q24060765': 'organ',
            'Q28845870': 'tissue',
            'Q7644128': 'cell type',
            'Q12140': 'medication',
            'Q179661': 'therapeutic agent',
            'Q128581': 'antibiotic',
            'Q206159': 'vaccine',
            'Q169872': 'symptom',
            'Q1441305': 'medical sign',
            'Q7187': 'gene',
            'Q8054': 'protein',
            'Q417841': 'protein',
            'Q11173': 'chemical compound',
            'Q59199015': 'enzyme',
            'Q178593': 'hormone',
            'Q1059392': 'medical test',
            'Q55788567': 'medical imaging',
            'Q11190': 'biomarker',
            'Q796194': 'surgery',
            'Q2095549': 'medical procedure',
            'Q10876': 'bacteria',
            'Q808': 'virus',
            'Q764': 'fungus',
            'Q37763': 'parasite',
            'Q12139612': 'medical device',
        }
        
        # Medical keywords for category discovery
        self.medical_keywords = [
            'medical', 'medicine', 'health', 'healthcare', 'disease', 'diseases',
            'drug', 'medication', 'pharmaceutical', 'clinical', 'hospital',
            'therapy', 'treatment', 'diagnosis', 'diagnostic', 'patient',
            'symptom', 'syndrome', 'pathology', 'anatomy', 'physiology',
            'surgery', 'surgical', 'procedure', 'test', 'screening',
            'gene', 'genetic', 'protein', 'enzyme', 'hormone',
            'bacteria', 'bacterial', 'virus', 'viral', 'infection', 'infectious',
            'cancer', 'tumor', 'carcinoma', 'disorder', 'condition'
        ]
        
        # Japanese name mapping for display
        self.category_japanese_names = {
            'disease': '病気',
            'medication': '医薬品',
            'symptom': '症状',
            'surgery': '外科手術',
            'medical test': '医学検査',
            'protein': 'タンパク質',
            'gene': '遺伝子',
            'anatomical structure': '解剖学的構造',
            'infectious disease': '感染症',
            'chemical compound': '化学化合物',
            'medical procedure': '医療処置',
            'bacteria': '細菌',
            'virus': 'ウイルス',
            'therapeutic agent': '治療薬',
            'medical device': '医療機器',
            'rare disease': '希少疾患',
            'mental disorder': '精神疾患',
            'neurological disorder': '神経疾患',
            'organ': '臓器',
            'tissue': '組織',
            'cell type': '細胞型',
            'antibiotic': '抗生物質',
            'vaccine': 'ワクチン',
            'medical sign': '医学的徴候',
            'enzyme': '酵素',
            'hormone': 'ホルモン',
            'medical imaging': '画像診断',
            'biomarker': 'バイオマーカー',
            'fungus': '真菌',
            'parasite': '寄生虫',
        }
    
    def setup_logging(self, log_file):
        """Setup logging functionality"""
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            self.logger = logging.getLogger('WikidataExtractor')
            self.logger.setLevel(logging.DEBUG)
            
            fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            
            ch = logging.StreamHandler()
            ch.setLevel(logging.ERROR)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)
            
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
            
            self.logger.info("="*60)
            self.logger.info("Wikidata Medical Terms Extractor - Log Started")
            self.logger.info("="*60)
            self.logger.info("Log file: " + log_file)
            self.logger.info("Batch size: " + str(self.batch_size))
            self.logger.info("Max retries: " + str(self.max_retries))
        else:
            self.logger = logging.getLogger('WikidataExtractor')
            self.logger.addHandler(logging.NullHandler())
    
    def discover_medical_categories(self, limit=100):
        """
        Discover medical-related categories from Wikimedia categories (Q4167836)
        Returns a dictionary of QID -> English label for medical categories
        """
        print("\n" + "="*60)
        print("Discovering Medical Categories from Wikidata")
        print("="*60)
        
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("MEDICAL CATEGORY DISCOVERY")
        self.logger.info("="*60)
        
        discovered = {}
        
        # Build keyword filter for SPARQL
        keyword_filters = []
        for keyword in self.medical_keywords:
            keyword_filters.append('CONTAINS(LCASE(?enLabel), "' + keyword + '")')
        
        filter_clause = " || ".join(keyword_filters)
        
        query = """
        SELECT DISTINCT ?category ?enLabel ?jaLabel WHERE {
          ?category wdt:P31 wd:Q4167836 .  # instance of Wikimedia category
          ?category rdfs:label ?enLabel FILTER(LANG(?enLabel) = "en") .
          OPTIONAL { ?category rdfs:label ?jaLabel FILTER(LANG(?jaLabel) = "ja") }
          FILTER(""" + filter_clause + """)
        }
        LIMIT """ + str(limit)
        
        self.logger.info("Discovery query:")
        self.logger.info(query)
        
        print("\nSearching for medical categories...")
        print("Keywords: " + ", ".join(self.medical_keywords[:10]) + "...")
        
        try:
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            bindings = results["results"]["bindings"]
            
            print("Found " + str(len(bindings)) + " potential medical categories")
            self.logger.info("Found " + str(len(bindings)) + " categories")
            
            for binding in bindings:
                qid = binding['category']['value'].split('/')[-1]
                en_label = binding.get('enLabel', {}).get('value', '')
                ja_label = binding.get('jaLabel', {}).get('value', '')
                
                # Normalize category name (remove "Category:" prefix if present)
                if en_label.startswith('Category:'):
                    en_label = en_label[9:].strip()
                
                discovered[qid] = en_label
                
                if ja_label:
                    self.category_japanese_names[en_label] = ja_label
                
                self.logger.info("  " + qid + ": " + en_label + 
                               (" (" + ja_label + ")" if ja_label else ""))
            
            print("\nDiscovered categories summary:")
            print("-" * 60)
            for qid, name in list(discovered.items())[:20]:
                ja_name = self.category_japanese_names.get(name, "")
                display = "  " + qid + ": " + name
                if ja_name:
                    display += " (" + ja_name + ")"
                print(display)
            
            if len(discovered) > 20:
                print("  ... and " + str(len(discovered) - 20) + " more")
            
            print("-" * 60)
            
        except Exception as e:
            print("Error during discovery: " + str(e))
            self.logger.error("Discovery error: " + str(e))
            self.logger.error(traceback.format_exc())
        
        return discovered
    
    def save_discovered_categories(self, discovered, filename="discovered_categories.csv"):
        """Save discovered categories to CSV file"""
        if not discovered:
            print("No categories to save")
            return
        
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = output_dir + "/" + filename
        
        rows = []
        for qid, en_name in discovered.items():
            ja_name = self.category_japanese_names.get(en_name, "")
            rows.append({
                'qid': qid,
                'category_en': en_name,
                'category_ja': ja_name
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print("\nDiscovered categories saved to: " + filepath)
        self.logger.info("Saved discovered categories to: " + filepath)
    
    def log_query(self, query, category_name, offset, batch_size):
        """Log query execution"""
        self.logger.info("")
        self.logger.info("-" * 60)
        self.logger.info("SPARQL Query Execution")
        self.logger.info("-" * 60)
        self.logger.info("Category: " + category_name)
        self.logger.info("Offset: " + str(offset))
        self.logger.info("Batch Size: " + str(batch_size))
        self.logger.info("Query Number: " + str(self.stats['total_queries'] + 1))
        self.logger.info("")
        self.logger.info("Query:")
        self.logger.info(query)
        self.logger.info("-" * 60)
    
    def log_response(self, bindings, elapsed_time):
        """Log response"""
        self.logger.info("")
        self.logger.info("Response:")
        self.logger.info("  Results: " + str(len(bindings)) + " items")
        self.logger.info("  Elapsed Time: " + str(round(elapsed_time, 2)) + " seconds")
        
        if len(bindings) > 0:
            self.logger.info("  Sample (first 3 items):")
            for i, binding in enumerate(bindings[:3]):
                item_id = binding.get('item', {}).get('value', '').split('/')[-1]
                en_label = binding.get('enLabel', {}).get('value', '')
                ja_label = binding.get('jaLabel', {}).get('value', '')
                self.logger.info("    [" + str(i+1) + "] " + item_id + " | EN: " + en_label + " | JA: " + ja_label)
        
        self.logger.info("-" * 60)
    
    def log_error(self, error, retry_count, category_name, offset):
        """Log error"""
        self.logger.error("")
        self.logger.error("!" * 60)
        self.logger.error("ERROR OCCURRED")
        self.logger.error("!" * 60)
        self.logger.error("Category: " + category_name)
        self.logger.error("Offset: " + str(offset))
        self.logger.error("Retry Attempt: " + str(retry_count))
        self.logger.error("Error Type: " + type(error).__name__)
        self.logger.error("Error Message: " + str(error))
        self.logger.error("")
        self.logger.error("Traceback:")
        self.logger.error(traceback.format_exc())
        self.logger.error("!" * 60)
    
    def execute_sparql_with_retry(self, query, category_name, offset, batch_size, retry_count=0):
        """Execute SPARQL query with retry mechanism, optimized for 504 Gateway Timeout"""
        self.stats['total_queries'] += 1
        
        self.log_query(query, category_name, offset, batch_size)
        
        start_time = time.time()
        
        try:
            self.sparql.setQuery(query)
            
            self.logger.info("Sending HTTP Request to: https://query.wikidata.org/sparql")
            
            results = self.sparql.query().convert()
            
            elapsed_time = time.time() - start_time
            bindings = results["results"]["bindings"]
            
            self.log_response(bindings, elapsed_time)
            
            self.stats['successful_queries'] += 1
            self.stats['total_items'] += len(bindings)
            
            return results
        
        except HTTPError as e:
            elapsed_time = time.time() - start_time
            self.stats['failed_queries'] += 1
            
            # Handle 504 Gateway Timeout specifically
            if e.code == 504:
                self.stats['timeout_504_errors'] += 1
                self.log_error(e, retry_count + 1, category_name, offset)
                
                if retry_count < self.max_retries:
                    self.stats['total_retries'] += 1
                    
                    # Longer wait time for 504 errors (query complexity issue)
                    wait_time = min(600, (3 ** retry_count) * 10)  # 10s, 30s, 90s, 270s...
                    
                    error_msg = "504 Gateway Timeout (attempt " + str(retry_count + 1) + "/" + str(self.max_retries) + ")"
                    print(error_msg)
                    print("Query too complex or server overloaded.")
                    print("Consider reducing --batch-size or --limit")
                    wait_msg = "Waiting " + str(wait_time) + " seconds before retry..."
                    print(wait_msg)
                    
                    self.logger.warning("504 Gateway Timeout - Retrying after " + str(wait_time) + " seconds...")
                    self.logger.warning("Suggestion: Reduce batch size or query complexity")
                    
                    time.sleep(wait_time)
                    return self.execute_sparql_with_retry(query, category_name, offset, batch_size, retry_count + 1)
                else:
                    self.logger.error("Max retries reached for 504 error.")
                    self.logger.error("Recommendation: Use smaller batch size or download Wikidata dumps")
                    self.logger.error("Dumps available at: https://dumps.wikimedia.org/wikidatawiki/entities/")
                    print("\n" + "!"*60)
                    print("PERSISTENT 504 TIMEOUT ERROR")
                    print("!"*60)
                    print("The query is too complex for the Wikidata server.")
                    print("\nSuggestions:")
                    print("1. Reduce --batch-size (try 100-300)")
                    print("2. Reduce --limit per category")
                    print("3. Use Wikidata dumps for offline processing:")
                    print("   https://dumps.wikimedia.org/wikidatawiki/entities/")
                    print("4. Check service status: https://status.wikimedia.org/")
                    print("!"*60 + "\n")
                    raise
            else:
                # Other HTTP errors
                self.stats['other_errors'] += 1
                self.log_error(e, retry_count + 1, category_name, offset)
                
                if retry_count < self.max_retries:
                    self.stats['total_retries'] += 1
                    wait_time = (retry_count + 1) * 5
                    
                    error_msg = "HTTP Error " + str(e.code) + " (attempt " + str(retry_count + 1) + "/" + str(self.max_retries) + ")"
                    print(error_msg)
                    wait_msg = "Waiting " + str(wait_time) + " seconds before retry..."
                    print(wait_msg)
                    
                    self.logger.warning("Retrying after " + str(wait_time) + " seconds...")
                    
                    time.sleep(wait_time)
                    return self.execute_sparql_with_retry(query, category_name, offset, batch_size, retry_count + 1)
                else:
                    self.logger.error("Max retries reached.")
                    raise
            
        except (IncompleteRead, URLError, socket.timeout) as e:
            elapsed_time = time.time() - start_time
            self.stats['failed_queries'] += 1
            self.stats['network_errors'] += 1
            
            self.log_error(e, retry_count + 1, category_name, offset)
            
            if retry_count < self.max_retries:
                self.stats['total_retries'] += 1
                
                # Exponential backoff for network errors
                wait_time = min(300, (2 ** retry_count) * 5)
                
                error_msg = "Network error (attempt " + str(retry_count + 1) + "/" + str(self.max_retries) + "): " + type(e).__name__
                print(error_msg)
                wait_msg = "Waiting " + str(wait_time) + " seconds before retry..."
                print(wait_msg)
                
                self.logger.warning("Retrying after " + str(wait_time) + " seconds...")
                
                time.sleep(wait_time)
                return self.execute_sparql_with_retry(query, category_name, offset, batch_size, retry_count + 1)
            else:
                self.logger.error("Max retries reached. Giving up on this batch.")
                raise
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.stats['failed_queries'] += 1
            self.stats['other_errors'] += 1
            
            self.log_error(e, retry_count + 1, category_name, offset)
            
            if retry_count < self.max_retries:
                self.stats['total_retries'] += 1
                
                wait_time = (retry_count + 1) * 5
                
                error_msg = "Error (attempt " + str(retry_count + 1) + "/" + str(self.max_retries) + "): " + str(e)
                print(error_msg)
                wait_msg = "Waiting " + str(wait_time) + " seconds before retry..."
                print(wait_msg)
                
                self.logger.warning("Retrying after " + str(wait_time) + " seconds...")
                
                time.sleep(wait_time)
                return self.execute_sparql_with_retry(query, category_name, offset, batch_size, retry_count + 1)
            else:
                self.logger.error("Max retries reached. Giving up on this batch.")
                raise
    
    def fetch_batch(self, category_qid, category_name, offset, batch_size):
        """Fetch one batch of data from specified offset"""
        query = """
        SELECT DISTINCT ?item ?enLabel ?jaLabel ?enDescription ?jaDescription 
               ?meshId ?icd10 ?icd9 ?snomedId ?umlsId
        WHERE {
          ?item wdt:P31/wdt:P279* wd:""" + category_qid + """ .
          
          ?item rdfs:label ?enLabel .
          FILTER(LANG(?enLabel) = "en")
          
          OPTIONAL {
            ?item rdfs:label ?jaLabel .
            FILTER(LANG(?jaLabel) = "ja")
          }
          
          OPTIONAL {
            ?item schema:description ?enDescription .
            FILTER(LANG(?enDescription) = "en")
          }
          
          OPTIONAL {
            ?item schema:description ?jaDescription .
            FILTER(LANG(?jaDescription) = "ja")
          }
          
          OPTIONAL { ?item wdt:P486 ?meshId }
          OPTIONAL { ?item wdt:P494 ?icd10 }
          OPTIONAL { ?item wdt:P493 ?icd9 }
          OPTIONAL { ?item wdt:P5806 ?snomedId }
          OPTIONAL { ?item wdt:P2892 ?umlsId }
        }
        LIMIT """ + str(batch_size) + """
        OFFSET """ + str(offset)
        
        results = self.execute_sparql_with_retry(query, category_name, offset, batch_size)
        return results["results"]["bindings"]
    
    def fetch_terms_by_category(self, category_qid, category_name_en, limit=None):
        """Fetch medical terms from specified category with pagination"""
        category_name_ja = self.category_japanese_names.get(category_name_en, category_name_en)
        
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("Starting Category: " + category_name_en + " (" + category_qid + ")")
        self.logger.info("Japanese: " + category_name_ja)
        self.logger.info("="*60)
        
        print("\n" + "="*60)
        print("Category: " + category_name_en + " (" + category_name_ja + ")")
        print("="*60)
        
        all_terms = []
        offset = 0
        consecutive_empty = 0
        max_empty_batches = 3
        
        effective_limit = limit if limit is not None else 1000000
        
        self.logger.info("Limit: " + str(effective_limit))
        self.logger.info("Batch Size: " + str(self.batch_size))
        
        while offset < effective_limit:
            try:
                remaining = effective_limit - offset
                current_batch_size = min(self.batch_size, remaining)
                
                progress_msg = "  Fetching... offset=" + str(offset) + " (current: " + str(len(all_terms)) + " items)"
                print(progress_msg, end='\r')
                
                bindings = self.fetch_batch(category_qid, category_name_en, offset, current_batch_size)
                
                if not bindings:
                    consecutive_empty += 1
                    self.logger.warning("Empty batch received. Consecutive empty: " + str(consecutive_empty))
                    if consecutive_empty >= max_empty_batches:
                        empty_msg = "\n  No more results. Category completed."
                        print(empty_msg)
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
                    small_batch_msg = "\n  Last batch received."
                    print(small_batch_msg)
                    self.logger.info("Last batch received (partial batch)")
                    break
                
                offset += current_batch_size
                time.sleep(1)
                
            except Exception as e:
                error_msg = "\n  Batch fetch failed (offset=" + str(offset) + "): " + str(e)
                print(error_msg)
                self.logger.error("Batch fetch failed. Skipping category.")
                print("  Skipping this category and continuing...")
                break
        
        count_msg = "\n  Completed: " + str(len(all_terms)) + " items"
        print(count_msg)
        
        self.logger.info("")
        self.logger.info("Category Completed: " + category_name_en)
        self.logger.info("Total items collected: " + str(len(all_terms)))
        self.logger.info("="*60)
        
        return all_terms
    
    def extract_all(self, categories, limit_per_category=None):
        """Extract medical terms from all categories"""
        all_terms = []
        
        print("\n" + "="*60)
        cat_msg = "Medical Terms Extraction: " + str(len(categories)) + " categories"
        print(cat_msg)
        if limit_per_category is None or limit_per_category == 0:
            print("Per category: Unlimited (practical limit: 1M items)")
            print("Batch size: " + str(self.batch_size) + " items")
        else:
            limit_msg = "Per category max: " + str(limit_per_category) + " items"
            print(limit_msg)
            print("Batch size: " + str(self.batch_size) + " items")
        print("="*60)
        
        self.logger.info("")
        self.logger.info("#"*60)
        self.logger.info("EXTRACTION START")
        self.logger.info("#"*60)
        self.logger.info("Total Categories: " + str(len(categories)))
        self.logger.info("Limit per Category: " + str(limit_per_category if limit_per_category else "Unlimited"))
        
        start_time = time.time()
        
        for idx, (qid, name_en) in enumerate(categories.items(), 1):
            name_ja = self.category_japanese_names.get(name_en, name_en)
            cat_progress = "\n[" + str(idx) + "/" + str(len(categories)) + "] " + name_en + " (" + name_ja + ")"
            print(cat_progress)
            
            terms = self.fetch_terms_by_category(qid, name_en, limit_per_category)
            all_terms.extend(terms)
            
            if idx < len(categories):
                time.sleep(2)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "="*60)
        print("Extraction completed")
        total_msg = "Total items: " + str(len(all_terms))
        print(total_msg)
        time_msg = "Elapsed time: " + str(round(elapsed_time/60, 1)) + " minutes"
        print(time_msg)
        print("="*60 + "\n")
        
        self.logger.info("")
        self.logger.info("#"*60)
        self.logger.info("EXTRACTION COMPLETED")
        self.logger.info("#"*60)
        self.logger.info("Total Items Collected: " + str(len(all_terms)))
        self.logger.info("Elapsed Time: " + str(round(elapsed_time/60, 1)) + " minutes")
        self.logger.info("")
        self.logger.info("Statistics:")
        self.logger.info("  Total Queries: " + str(self.stats['total_queries']))
        self.logger.info("  Successful Queries: " + str(self.stats['successful_queries']))
        self.logger.info("  Failed Queries: " + str(self.stats['failed_queries']))
        self.logger.info("  Total Retries: " + str(self.stats['total_retries']))
        self.logger.info("  Total Items Retrieved: " + str(self.stats['total_items']))
        self.logger.info("")
        self.logger.info("Error Breakdown:")
        self.logger.info("  504 Gateway Timeout: " + str(self.stats['timeout_504_errors']))
        self.logger.info("  Network Errors: " + str(self.stats['network_errors']))
        self.logger.info("  Other Errors: " + str(self.stats['other_errors']))
        if self.stats['total_queries'] > 0:
            success_rate = round(self.stats['successful_queries'] / self.stats['total_queries'] * 100, 1)
            self.logger.info("")
            self.logger.info("  Success Rate: " + str(success_rate) + "%")
        self.logger.info("#"*60)
        
        df = pd.DataFrame(all_terms)
        
        if len(df) == 0:
            print("Warning: No data collected.")
            self.logger.warning("No data collected!")
            return df
        
        original_count = len(df)
        df = df.drop_duplicates(subset=['qid'])
        duplicates_removed = original_count - len(df)
        
        if duplicates_removed > 0:
            dup_msg = "Duplicates removed: " + str(duplicates_removed)
            print(dup_msg)
            unique_msg = "Unique items: " + str(len(df)) + "\n"
            print(unique_msg)
            
            self.logger.info("")
            self.logger.info("Duplicates removed: " + str(duplicates_removed))
            self.logger.info("Unique items: " + str(len(df)))
        
        return df
    
    def analyze_data_quality(self, df):
        """Analyze data quality"""
        if len(df) == 0:
            print("No data available. Skipping analysis.")
            return pd.DataFrame()
        
        print("\n" + "="*60)
        print("Data Quality Analysis")
        print("="*60 + "\n")
        
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("DATA QUALITY ANALYSIS")
        self.logger.info("="*60)
        
        print("1. Basic Statistics:")
        total_msg = "   Total records: " + str(len(df))
        print(total_msg)
        self.logger.info("Total Records: " + str(len(df)))
        
        unique_msg = "   Unique QIDs: " + str(df['qid'].nunique())
        print(unique_msg)
        self.logger.info("Unique QIDs: " + str(df['qid'].nunique()))
        
        print("\n2. Language Coverage:")
        has_en = (df['en_label'].notna() & (df['en_label'] != '')).sum()
        has_ja = (df['ja_label'].notna() & (df['ja_label'] != '')).sum()
        en_msg = "   English labels: " + str(has_en) + " (" + str(round(has_en/len(df)*100, 1)) + "%)"
        print(en_msg)
        self.logger.info("English Labels: " + str(has_en) + " (" + str(round(has_en/len(df)*100, 1)) + "%)")
        
        ja_msg = "   Japanese labels: " + str(has_ja) + " (" + str(round(has_ja/len(df)*100, 1)) + "%)"
        print(ja_msg)
        self.logger.info("Japanese Labels: " + str(has_ja) + " (" + str(round(has_ja/len(df)*100, 1)) + "%)")
        
        print("\n3. Description Coverage:")
        has_en_desc = (df['en_description'].notna() & (df['en_description'] != '')).sum()
        has_ja_desc = (df['ja_description'].notna() & (df['ja_description'] != '')).sum()
        en_desc_msg = "   English descriptions: " + str(has_en_desc) + " (" + str(round(has_en_desc/len(df)*100, 1)) + "%)"
        print(en_desc_msg)
        
        ja_desc_msg = "   Japanese descriptions: " + str(has_ja_desc) + " (" + str(round(has_ja_desc/len(df)*100, 1)) + "%)"
        print(ja_desc_msg)
        
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
            ext_msg = "   " + name + ": " + str(count) + " (" + str(round(count/len(df)*100, 1)) + "%)"
            print(ext_msg)
            self.logger.info(name + ": " + str(count) + " (" + str(round(count/len(df)*100, 1)) + "%)")
        
        print("\n5. Items by Category:")
        self.logger.info("")
        self.logger.info("Category Breakdown:")
        category_counts = df['category_en'].value_counts().sort_values(ascending=False)
        for category, count in category_counts.items():
            cat_ja = self.category_japanese_names.get(category, category)
            cat_msg = "   " + category + " (" + cat_ja + "): " + str(count)
            print(cat_msg)
            self.logger.info("  " + category + ": " + str(count))
        
        print("\n6. English-Japanese Pairs:")
        bilingual = df[(df['en_label'] != '') & (df['ja_label'] != '')]
        bi_msg = "   Bilingual pairs: " + str(len(bilingual)) + " (" + str(round(len(bilingual)/len(df)*100, 1)) + "%)"
        print(bi_msg)
        self.logger.info("")
        self.logger.info("Bilingual Pairs: " + str(len(bilingual)) + " (" + str(round(len(bilingual)/len(df)*100, 1)) + "%)")
        
        print("\n" + "="*60 + "\n")
        self.logger.info("="*60)
        
        return bilingual
    
    def save_results(self, df, prefix="small"):
        """Save results as CSV and JSON"""
        if len(df) == 0:
            print("No data to save. Skipping.")
            self.logger.warning("No data to save")
            return {}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "output"
        
        os.makedirs(output_dir, exist_ok=True)
        
        print("Saving results...\n")
        self.logger.info("")
        self.logger.info("Saving results...")
        
        # Full CSV
        full_csv = output_dir + "/" + prefix + "_medical_terms_full_" + timestamp + ".csv"
        df.to_csv(full_csv, index=False, encoding='utf-8-sig')
        file_size_mb = os.path.getsize(full_csv) / (1024 * 1024)
        full_msg = "   Full CSV: " + full_csv + " (" + str(round(file_size_mb, 2)) + " MB)"
        print(full_msg)
        self.logger.info("Full CSV: " + full_csv + " (" + str(round(file_size_mb, 2)) + " MB)")
        
        # EN-JA pairs CSV
        bilingual_df = df[(df['en_label'] != '') & (df['ja_label'] != '')].copy()
        if len(bilingual_df) > 0:
            bilingual_csv = output_dir + "/" + prefix + "_en_ja_pairs_" + timestamp + ".csv"
            cols_to_save = ['en_label', 'ja_label', 'category_en', 'category_ja', 
                           'en_description', 'ja_description', 'qid']
            bilingual_df[cols_to_save].to_csv(bilingual_csv, index=False, encoding='utf-8-sig')
            file_size_mb = os.path.getsize(bilingual_csv) / (1024 * 1024)
            bi_msg = "   EN-JA pairs CSV: " + bilingual_csv + " (" + str(len(bilingual_df)) + " pairs, " + str(round(file_size_mb, 2)) + " MB)"
            print(bi_msg)
            self.logger.info("EN-JA pairs CSV: " + bilingual_csv + " (" + str(len(bilingual_df)) + " pairs, " + str(round(file_size_mb, 2)) + " MB)")
        
        # Category CSVs
        category_dir = output_dir + "/by_category_" + timestamp
        os.makedirs(category_dir, exist_ok=True)
        for category in df['category_en'].unique():
            cat_df = df[df['category_en'] == category]
            safe_name = category.replace('/', '_').replace('\\', '_').replace(' ', '_')
            cat_file = category_dir + "/" + safe_name + ".csv"
            cat_df.to_csv(cat_file, index=False, encoding='utf-8-sig')
        cat_count = len(df['category_en'].unique())
        cat_msg = "   Category CSVs: " + category_dir + "/ (" + str(cat_count) + " files)"
        print(cat_msg)
        self.logger.info("Category CSVs: " + category_dir + "/ (" + str(cat_count) + " files)")
        
        # JSON
        json_file = output_dir + "/" + prefix + "_medical_terms_" + timestamp + ".json"
        df.to_json(json_file, orient='records', force_ascii=False, indent=2)
        file_size_mb = os.path.getsize(json_file) / (1024 * 1024)
        json_msg = "   JSON: " + json_file + " (" + str(round(file_size_mb, 2)) + " MB)"
        print(json_msg)
        self.logger.info("JSON: " + json_file + " (" + str(round(file_size_mb, 2)) + " MB)")
        
        # Report
        report_file = output_dir + "/" + prefix + "_report_" + timestamp + ".txt"
        bilingual_count = len(bilingual_df) if len(bilingual_df) > 0 else 0
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("Wikidata Medical Terms Extraction Report\n")
            f.write("="*60 + "\n\n")
            f.write("Execution time: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
            f.write("Scale: " + prefix + "\n")
            f.write("Total items: " + str(len(df)) + "\n")
            f.write("EN-JA pairs: " + str(bilingual_count) + "\n")
            if len(df) > 0:
                f.write("Bilingual ratio: " + str(round(bilingual_count/len(df)*100, 1)) + "%\n\n")
            
            f.write("Statistics:\n")
            f.write("  Total queries: " + str(self.stats['total_queries']) + "\n")
            f.write("  Successful: " + str(self.stats['successful_queries']) + "\n")
            f.write("  Failed: " + str(self.stats['failed_queries']) + "\n")
            f.write("  Retries: " + str(self.stats['total_retries']) + "\n\n")
            
            f.write("Error Breakdown:\n")
            f.write("  504 Gateway Timeout: " + str(self.stats['timeout_504_errors']) + "\n")
            f.write("  Network Errors: " + str(self.stats['network_errors']) + "\n")
            f.write("  Other Errors: " + str(self.stats['other_errors']) + "\n\n")
            
            f.write("Items by category:\n")
            for category, count in df['category_en'].value_counts().items():
                cat_ja = self.category_japanese_names.get(category, category)
                f.write("  " + category + " (" + cat_ja + "): " + str(count) + "\n")
            
            f.write("\nLanguage coverage:\n")
            has_ja = (df['ja_label'].notna() & (df['ja_label'] != '')).sum()
            ja_pct = round(has_ja/len(df)*100, 1) if len(df) > 0 else 0
            f.write("  Japanese labels: " + str(has_ja) + " (" + str(ja_pct) + "%)\n")
            
            f.write("\nExternal ID coverage:\n")
            external_ids = [
                ('mesh_id', 'MeSH'),
                ('icd10', 'ICD-10'),
                ('snomed_id', 'SNOMED CT'),
                ('umls_id', 'UMLS')
            ]
            for col, name in external_ids:
                count = (df[col].notna() & (df[col] != '')).sum()
                pct = round(count/len(df)*100, 1) if len(df) > 0 else 0
                f.write("  " + name + ": " + str(count) + " (" + str(pct) + "%)\n")
        
        report_msg = "   Report: " + report_file
        print(report_msg)
        self.logger.info("Report: " + report_file)
        
        print("\nSave completed!\n")
        self.logger.info("")
        self.logger.info("All results saved successfully")
        
        return {
            'full_csv': full_csv,
            'bilingual_csv': bilingual_csv if len(bilingual_df) > 0 else None,
            'category_dir': category_dir,
            'json': json_file,
            'report': report_file
        }


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Wikidata Medical Terms Extractor (English categories with EN-JA pairs)',
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
  
  If encountering 504 Gateway Timeout errors:
    python %(prog)s --small --limit 1000 --batch-size 200 --log logs/timeout.log
    python %(prog)s --medium --limit 500 --batch-size 100 --log logs/safe.log
  
  Note: 504 errors indicate query complexity issues. Solutions:
    1. Reduce --batch-size (try 100-300 instead of default 1000)
    2. Reduce --limit per category
    3. For large-scale extraction, consider Wikidata dumps:
       https://dumps.wikimedia.org/wikidatawiki/entities/
        """
    )
    
    size_group = parser.add_mutually_exclusive_group(required=True)
    size_group.add_argument('--small', action='store_true', help='Small test (5 categories)')
    size_group.add_argument('--medium', action='store_true', help='Medium test (15 categories)')
    size_group.add_argument('--large', action='store_true', help='Large test (30+ categories)')
    
    parser.add_argument('--limit', type=int, default=2000, 
                       help='Max items per category (0 for unlimited, default: 2000)')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Items per query (default: 1000). Reduce to 100-300 if encountering 504 timeouts')
    parser.add_argument('--log', type=str, default=None,
                       help='Log file path (e.g., logs/debug.log)')
    parser.add_argument('--discover', action='store_true',
                       help='Discover medical categories from Wikidata before extraction')
    parser.add_argument('--discover-only', action='store_true',
                       help='Only discover categories, do not extract terms')
    parser.add_argument('--discover-limit', type=int, default=100,
                       help='Maximum categories to discover (default: 100)')
    
    return parser.parse_args()


def main():
    """Main function"""
    print("="*60)
    print("Wikidata Medical Terms Extractor")
    print("(English categories with EN-JA pairs)")
    print("="*60)
    
    args = parse_arguments()
    
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
    
    limit_label = "Unlimited" if args.limit == 0 else str(args.limit) + " items"
    
    print("\nConfiguration:")
    print("  Scale: " + size_label + " (" + str(category_count) + " categories)")
    print("  Per category: " + limit_label)
    print("  Batch size: " + str(args.batch_size) + " items")
    if args.log:
        print("  Log file: " + args.log)
    else:
        print("  Log file: None")
    print("")
    
    if args.small and args.limit <= 2000:
        est_time = "10-20 minutes"
    elif args.medium and args.limit <= 5000:
        est_time = "1-2 hours"
    elif args.large or args.limit == 0:
        est_time = "Several hours or more"
    else:
        est_time = "Varies"
    
    print("Estimated time: " + est_time)
    print("="*60)
    
    extractor = MedicalTermsExtractor(
        batch_size=args.batch_size,
        max_retries=5,
        log_file=args.log
    )
    
    # Category discovery mode
    if args.discover or args.discover_only:
        discovered = extractor.discover_medical_categories(limit=args.discover_limit)
        
        if discovered:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extractor.save_discovered_categories(
                discovered, 
                filename="discovered_medical_categories_" + timestamp + ".csv"
            )
        
        if args.discover_only:
            print("\n" + "="*60)
            print("Discovery completed!")
            print("="*60)
            print("\nTotal discovered: " + str(len(discovered)) + " categories")
            print("Check output/discovered_medical_categories_*.csv")
            return
        
        # Ask user if they want to use discovered categories
        print("\n" + "="*60)
        print("Use discovered categories for extraction?")
        print("="*60)
        print("Options:")
        print("  1. Use only predefined categories (default)")
        print("  2. Use only discovered categories")
        print("  3. Use both predefined and discovered")
        print("")
        
        choice = input("Enter choice (1/2/3) [1]: ").strip() or "1"
        
        if choice == "2":
            categories = discovered
            print("Using discovered categories only")
        elif choice == "3":
            # Merge predefined and discovered
            if args.small:
                base_categories = extractor.small_test_categories
            elif args.medium:
                base_categories = extractor.medium_test_categories
            else:
                base_categories = extractor.large_test_categories
            
            categories = {**base_categories, **discovered}
            print("Using both predefined and discovered categories")
        else:
            if args.small:
                categories = extractor.small_test_categories
            elif args.medium:
                categories = extractor.medium_test_categories
            else:
                categories = extractor.large_test_categories
            print("Using predefined categories only")
    else:
        # Normal mode without discovery
        if args.small:
            categories = extractor.small_test_categories
        elif args.medium:
            categories = extractor.medium_test_categories
        else:
            categories = extractor.large_test_categories
    
    limit = None if args.limit == 0 else args.limit
    
    df = extractor.extract_all(categories, limit_per_category=limit)
    
    bilingual_df = extractor.analyze_data_quality(df)
    
    if len(bilingual_df) > 0:
        print("Sample data (EN-JA pairs, first 5):")
        print("="*80)
        sample = bilingual_df[['en_label', 'ja_label', 'category_en']].head()
        for idx, row in sample.iterrows():
            en_part = row['en_label'][:30].ljust(30)
            ja_part = row['ja_label'][:20].ljust(20)
            cat_part = "[" + row['category_en'] + "]"
            sample_line = "  " + en_part + " <-> " + ja_part + " " + cat_part
            print(sample_line)
        print("="*80 + "\n")
    
    files = extractor.save_results(df, prefix=size_name)
    
    print("="*60)
    print("Extraction completed!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check CSV files in output folder")
    print("2. Review data quality")
    if args.log:
        print("3. Check log file: " + args.log)
    print("")


if __name__ == "__main__":
    main()