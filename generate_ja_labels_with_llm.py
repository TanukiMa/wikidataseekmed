#!/usr/bin/env python3
"""
Generate Japanese labels for medical terms using multiple LLM models from HuggingFace.

Uses HuggingFace Inference API to query multiple models in parallel and stores
all suggestions in Supabase for voting/consensus.
"""

import os
import sys
import json
import time
import argparse
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default LLM models to use
DEFAULT_MODELS = [
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "google/gemma-2-9b-it",
]


class HuggingFaceTranslator:
    """Generate Japanese medical term translations using HuggingFace models"""

    def __init__(self, hf_token: str, supabase_url: str, supabase_key: str):
        """
        Initialize translator

        Args:
            hf_token: HuggingFace API token
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        if not hf_token:
            raise ValueError("HuggingFace token required. Set HF_TOKEN environment variable.")

        self.hf_token = hf_token
        self.hf_api_url = "https://api-inference.huggingface.co/models/"
        self.headers = {"Authorization": f"Bearer {hf_token}"}

        self.client: Client = create_client(supabase_url, supabase_key)
        self.job_id: Optional[int] = None

        logger.info("Initialized HuggingFace translator")

    def build_prompt(self, term: Dict[str, Any]) -> str:
        """
        Build prompt for LLM translation

        Args:
            term: Dictionary containing term data

        Returns:
            Formatted prompt string
        """
        # Extract context from external IDs
        context_parts = []

        if term.get('mesh_id'):
            context_parts.append(f"MeSH ID: {term['mesh_id']}")
        if term.get('icd10'):
            context_parts.append(f"ICD-10: {term['icd10']}")
        if term.get('icd11'):
            context_parts.append(f"ICD-11: {term['icd11']}")
        if term.get('snomed_id'):
            context_parts.append(f"SNOMED CT: {term['snomed_id']}")
        if term.get('umls_id'):
            context_parts.append(f"UMLS: {term['umls_id']}")

        context = "\n".join(context_parts) if context_parts else "No external IDs available"

        en_label = term.get('en_label', 'Unknown')
        en_description = term.get('en_description', '')
        category = term.get('category_en', 'medical term')

        prompt = f"""You are a medical terminology expert. Translate the following medical term from English to Japanese.

English Term: {en_label}
Category: {category}
{f'Description: {en_description}' if en_description else ''}

External Medical Codes:
{context}

Provide ONLY the Japanese translation of the term, without any explanation or additional text.
The translation should be:
- Medically accurate
- Commonly used in Japanese medical contexts
- Consistent with the external medical codes provided

Japanese translation:"""

        return prompt

    def query_huggingface(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """
        Query HuggingFace Inference API

        Args:
            model_name: Model identifier
            prompt: Prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Response dictionary or None if failed
        """
        api_url = f"{self.hf_api_url}{model_name}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            }
        }

        start_time = time.time()

        try:
            response = requests.post(
                api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )

            generation_time = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                result = response.json()

                # Handle different response formats
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '').strip()
                elif isinstance(result, dict):
                    generated_text = result.get('generated_text', '').strip()
                else:
                    logger.warning(f"Unexpected response format from {model_name}: {result}")
                    return None

                return {
                    'generated_text': generated_text,
                    'generation_time_ms': generation_time,
                    'model_name': model_name
                }

            elif response.status_code == 503:
                # Model is loading
                logger.warning(f"Model {model_name} is loading. Wait time: {response.json().get('estimated_time', 'unknown')}")
                return None

            else:
                logger.error(f"HuggingFace API error for {model_name}: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout querying {model_name}")
            return None
        except Exception as e:
            logger.error(f"Error querying {model_name}: {e}")
            return None

    def clean_translation(self, text: str) -> str:
        """
        Clean up generated translation

        Args:
            text: Raw generated text

        Returns:
            Cleaned Japanese translation
        """
        # Remove common prefixes/suffixes
        text = text.strip()

        # Remove markdown or formatting
        text = text.replace('**', '').replace('*', '')

        # Take only the first line if multiple lines
        if '\n' in text:
            text = text.split('\n')[0].strip()

        # Remove quotes if present
        text = text.strip('"').strip("'").strip('「').strip('」')

        return text

    def generate_translation(
        self,
        term: Dict[str, Any],
        models: List[str],
        max_workers: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate translations using multiple models in parallel

        Args:
            term: Term dictionary
            models: List of model names
            max_workers: Maximum parallel workers

        Returns:
            List of translation results
        """
        qid = term['qid']
        prompt = self.build_prompt(term)

        logger.info(f"Generating translations for {qid} ({term.get('en_label')}) using {len(models)} models")

        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_model = {
                executor.submit(self.query_huggingface, model, prompt): model
                for model in models
            }

            for future in as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    result = future.result()
                    if result and result.get('generated_text'):
                        cleaned = self.clean_translation(result['generated_text'])

                        if cleaned:
                            results.append({
                                'qid': qid,
                                'model_name': model,
                                'suggested_ja_label': cleaned,
                                'generation_time_ms': result.get('generation_time_ms'),
                                'prompt_filled': prompt,
                                'source_fields_used': {
                                    'mesh_id': term.get('mesh_id'),
                                    'icd10': term.get('icd10'),
                                    'icd11': term.get('icd11'),
                                    'snomed_id': term.get('snomed_id'),
                                    'umls_id': term.get('umls_id'),
                                }
                            })

                            logger.info(f"  {model}: {cleaned} ({result.get('generation_time_ms')}ms)")
                        else:
                            logger.warning(f"  {model}: Empty translation after cleaning")
                    else:
                        logger.warning(f"  {model}: No result")

                except Exception as e:
                    logger.error(f"  {model}: Exception - {e}")

        return results

    def save_translations(self, translations: List[Dict[str, Any]]):
        """
        Save translations to Supabase

        Args:
            translations: List of translation dictionaries
        """
        if not translations:
            logger.warning("No translations to save")
            return

        try:
            # Upsert translations (on conflict update)
            response = self.client.table('llm_translations').upsert(
                translations,
                on_conflict='qid,model_name'
            ).execute()

            logger.info(f"Saved {len(translations)} translations to Supabase")

        except Exception as e:
            logger.error(f"Failed to save translations: {e}")

    def create_translation_job(
        self,
        models: List[str],
        filter_criteria: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Create translation job record

        Args:
            models: List of model names
            filter_criteria: Filter criteria for terms

        Returns:
            Job ID or None
        """
        try:
            job_data = {
                'status': 'running',
                'models_used': models,
                'filter_criteria': filter_criteria or {},
                'execution_environment': os.getenv('GITHUB_ACTIONS') == 'true' and 'github_actions' or 'local',
                'github_run_id': os.getenv('GITHUB_RUN_ID'),
                'github_actor': os.getenv('GITHUB_ACTOR'),
            }

            response = self.client.table('translation_jobs').insert(job_data).execute()

            if response.data and len(response.data) > 0:
                job_id = response.data[0]['id']
                self.job_id = job_id
                logger.info(f"Created translation job: ID={job_id}")
                return job_id
            else:
                logger.warning("Failed to create translation job")
                return None

        except Exception as e:
            logger.error(f"Error creating translation job: {e}")
            return None

    def update_translation_job(
        self,
        job_id: int,
        status: str,
        total_terms: int = 0,
        terms_processed: int = 0,
        terms_failed: int = 0,
        translations_generated: int = 0,
        avg_time_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """Update translation job with results"""
        try:
            update_data = {
                'status': status,
                'completed_at': 'now()',
                'total_terms': total_terms,
                'terms_processed': terms_processed,
                'terms_failed': terms_failed,
                'translations_generated': translations_generated,
            }

            if avg_time_ms is not None:
                update_data['average_generation_time_ms'] = avg_time_ms

            if error_message:
                update_data['error_message'] = error_message

            self.client.table('translation_jobs').update(update_data).eq('id', job_id).execute()

            logger.info(f"Updated translation job: ID={job_id}, status={status}")

        except Exception as e:
            logger.error(f"Error updating translation job: {e}")

    def fetch_terms_needing_translation(
        self,
        limit: Optional[int] = None,
        prioritize_external_ids: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch terms that need Japanese translation

        Args:
            limit: Maximum number of terms to fetch
            prioritize_external_ids: Prioritize terms with more external IDs

        Returns:
            List of term dictionaries
        """
        try:
            if prioritize_external_ids:
                # Use the view that ranks by external ID count
                query = self.client.table('translation_candidates_with_context').select('*')
            else:
                query = self.client.table('terms_needing_ja_translation').select('*')

            if limit:
                query = query.limit(limit)

            response = query.execute()

            terms = response.data
            logger.info(f"Fetched {len(terms)} terms needing translation")

            return terms

        except Exception as e:
            logger.error(f"Error fetching terms: {e}")
            return []


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Generate Japanese labels using HuggingFace LLMs'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of terms to translate'
    )
    parser.add_argument(
        '--models',
        nargs='+',
        default=DEFAULT_MODELS,
        help='List of HuggingFace model names to use'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=3,
        help='Maximum parallel workers for model queries (default: 3)'
    )
    parser.add_argument(
        '--skip-save',
        action='store_true',
        help='Generate translations but don\'t save to Supabase (for testing)'
    )
    parser.add_argument(
        '--qid',
        help='Translate a specific QID only'
    )

    args = parser.parse_args()

    # Get credentials from environment
    hf_token = os.getenv('HF_TOKEN')
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not hf_token:
        logger.error(
            "Missing HuggingFace token!\n"
            "Set environment variable:\n"
            "  export HF_TOKEN='hf_xxxxx'\n"
            "\n"
            "Get your token at: https://huggingface.co/settings/tokens"
        )
        sys.exit(1)

    if not supabase_url or not supabase_key:
        logger.error(
            "Missing Supabase credentials!\n"
            "Set environment variables:\n"
            "  export SUPABASE_URL='https://xxxxx.supabase.co'\n"
            "  export SUPABASE_KEY='your-key'"
        )
        sys.exit(1)

    try:
        # Initialize translator
        translator = HuggingFaceTranslator(hf_token, supabase_url, supabase_key)

        # Fetch terms
        if args.qid:
            # Translate specific QID
            response = translator.client.table('medical_terms').select('*').eq('qid', args.qid).execute()
            terms = response.data
            if not terms:
                logger.error(f"QID not found: {args.qid}")
                sys.exit(1)
        else:
            terms = translator.fetch_terms_needing_translation(limit=args.limit)

        if not terms:
            logger.info("No terms need translation")
            sys.exit(0)

        # Create translation job
        job_id = translator.create_translation_job(
            models=args.models,
            filter_criteria={'limit': args.limit, 'qid': args.qid} if args.qid else {'limit': args.limit}
        )

        # Process terms
        total_terms = len(terms)
        all_translations = []
        terms_processed = 0
        terms_failed = 0
        total_generation_time = 0

        logger.info(f"Processing {total_terms} terms with {len(args.models)} models")
        logger.info(f"Models: {', '.join(args.models)}")

        for i, term in enumerate(terms, 1):
            qid = term['qid']
            logger.info(f"\n[{i}/{total_terms}] Processing {qid}: {term.get('en_label')}")

            try:
                translations = translator.generate_translation(
                    term,
                    models=args.models,
                    max_workers=args.max_workers
                )

                if translations:
                    all_translations.extend(translations)
                    terms_processed += 1

                    # Track generation time
                    for t in translations:
                        if t.get('generation_time_ms'):
                            total_generation_time += t['generation_time_ms']
                else:
                    terms_failed += 1

                # Save in batches of 10
                if not args.skip_save and len(all_translations) >= 10:
                    translator.save_translations(all_translations)
                    all_translations = []

                # Be nice to the API
                time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to process {qid}: {e}")
                terms_failed += 1

        # Save remaining translations
        if not args.skip_save and all_translations:
            translator.save_translations(all_translations)

        # Update job
        if job_id:
            avg_time = total_generation_time / max(1, terms_processed * len(args.models))
            translator.update_translation_job(
                job_id=job_id,
                status='completed',
                total_terms=total_terms,
                terms_processed=terms_processed,
                terms_failed=terms_failed,
                translations_generated=terms_processed * len(args.models),
                avg_time_ms=avg_time
            )

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("TRANSLATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total terms: {total_terms}")
        logger.info(f"Successfully processed: {terms_processed}")
        logger.info(f"Failed: {terms_failed}")
        logger.info(f"Translations generated: {terms_processed * len(args.models)}")
        if total_generation_time > 0:
            logger.info(f"Average generation time: {total_generation_time / max(1, terms_processed * len(args.models)):.0f}ms")
        if job_id:
            logger.info(f"Translation job ID: {job_id}")
        logger.info("=" * 60)

        sys.exit(0 if terms_failed == 0 else 1)

    except Exception as e:
        logger.error(f"Translation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
