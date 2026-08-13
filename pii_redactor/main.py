import argparse
import logging
import os
from detectors import RegexDetector, NERDetector, ContextDetector
from core.resolver import EntityResolver
from core.replacement import DeterministicReplacer
from document.processor import DocumentProcessor
from config import DEBUG

def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    parser = argparse.ArgumentParser(description="PII Redactor for DOCX files")
    parser.add_argument("--input", "-i", required=True, help="Input DOCX file path")
    parser.add_argument("--output", "-o", required=True, help="Output redacted DOCX file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-ner", action="store_true", help="Disable NER detector")
    
    args = parser.parse_args()
    setup_logging(args.debug or DEBUG)
    
    if not os.path.exists(args.input):
        logging.error(f"Input file not found: {args.input}")
        return

    logging.info("Initializing detectors...")
    detectors = [RegexDetector(), ContextDetector()]
    
    if not args.no_ner:
        detectors.insert(1, NERDetector())
        
    resolver = EntityResolver()
    replacer = DeterministicReplacer()
    
    processor = DocumentProcessor(detectors, resolver, replacer)
    
    logging.info("Starting document processing...")
    stats = processor.process(args.input, args.output)
    
    logging.info(f"Processing complete. Stats: {stats}")

if __name__ == "__main__":
    main()
