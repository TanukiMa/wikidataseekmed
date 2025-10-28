#!/bin/bash
# Demo script for Wikidata Category Finder

echo "================================================================"
echo "Wikidata Category Finder - Demo Script"
echo "================================================================"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python3 -c "import SPARQLWrapper" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  SPARQLWrapper not installed"
    echo "   Install with: pip install SPARQLWrapper"
    echo ""
fi

python3 -c "import pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  pandas not installed"
    echo "   Install with: pip install pandas"
    echo ""
fi

python3 -c "import yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  PyYAML not installed"
    echo "   Install with: pip install pyyaml"
    echo ""
fi

echo ""
echo "================================================================"
echo "📚 Example Commands"
echo "================================================================"
echo ""

echo "1️⃣  Find exact Japanese category and get English + Q number:"
echo "   python3 wikidata_category_finder.py --exact \"病気\""
echo ""

echo "2️⃣  Batch process multiple categories from file:"
echo "   python3 wikidata_category_finder.py --batch sample_japanese_categories.txt --export-csv"
echo ""

echo "3️⃣  Search with Japanese keyword (partial match):"
echo "   python3 wikidata_category_finder.py --search \"医学\" --limit 5"
echo ""

echo "4️⃣  Explore disease category (Q12136) and its subcategories:"
echo "   python3 wikidata_category_finder.py --qid Q12136 --show-subcategories"
echo ""

echo "5️⃣  Deep exploration with 2 levels of subcategories:"
echo "   python3 wikidata_category_finder.py --qid Q12136 --show-subcategories --depth 2"
echo ""

echo "================================================================"
echo "📊 Common Medical Categories (QIDs)"
echo "================================================================"
echo ""
echo "  Q12136    - disease (病気)"
echo "  Q12140    - medication (医薬品)"
echo "  Q169872   - symptom (症状)"
echo "  Q18123741 - infectious disease (感染症)"
echo "  Q12124    - cancer (がん)"
echo "  Q8054     - protein (タンパク質)"
echo "  Q7187     - gene (遺伝子)"
echo ""

echo "================================================================"
echo "💡 Tips"
echo "================================================================"
echo ""
echo "- Start with --depth 1 for subcategories (faster)"
echo "- Use --export-csv to save results for Excel"
echo "- Use --export-json for further processing"
echo "- Combine --search with --show-subcategories for comprehensive exploration"
echo ""

echo "================================================================"
echo "🚀 Ready to start!"
echo "================================================================"
echo ""
echo "Install dependencies first:"
echo "  pip install -r requirements.txt"
echo ""
echo "Then run any example command above!"
echo ""
