import os
import sys
import docx
import json
import logging
import argparse
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detectors import RegexDetector, NERDetector, ContextDetector
from core.resolver import EntityResolver
from document.traversal import DocumentTraverser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def audit(original_path, redacted_path):
    doc_orig = docx.Document(original_path)
    doc_red = docx.Document(redacted_path)
    
    trav_orig = DocumentTraverser(doc_orig)
    trav_red = DocumentTraverser(doc_red)
    
    detectors = [RegexDetector(), NERDetector(), ContextDetector()]
    resolver = EntityResolver()
    
    iter_orig = trav_orig.traverse()
    iter_red = trav_red.traverse()
    
    total_candidates = 0
    surviving = []
    by_category = {}
    
    for (text_orig, loc_orig, para_orig), (text_red, loc_red, para_red) in zip(iter_orig, iter_red):
        if not text_orig.strip():
            continue
            
        candidates = []
        context = text_orig
        if hasattr(loc_orig, 'header_text') and loc_orig.header_text:
            context = loc_orig.header_text + " | " + context
            
        for detector in detectors:
            if hasattr(detector, 'refine_entities'):
                candidates = detector.refine_entities(candidates, context)
                candidates.extend(detector.detect_additional_entities_from_context(text_orig, loc_orig))
            else:
                candidates.extend(detector.detect(text_orig, loc_orig, context))
                
        resolved = resolver.resolve(candidates)
        
        for ent in resolved:
            total_candidates += 1
            cat = ent.entity_type
            by_category[cat] = by_category.get(cat, {'total': 0, 'survived': 0})
            by_category[cat]['total'] += 1
            
            # Simple containment check to see if the EXACT original string survived in the redacted text
            # This is conservative. If it's partially redacted or changed, it's not a pure survival,
            # but usually redaction replaces it completely (e.g. "[PERSON]").
            if re.search(r'\b' + re.escape(ent.text) + r'\b', text_red):
                surviving.append({
                    "original_text": ent.text,
                    "type": ent.entity_type,
                    "location": str(loc_orig),
                    "redacted_text_at_same_location": text_red,
                    "detector_source": ent.detector,
                    "confidence": ent.confidence
                })
                by_category[cat]['survived'] += 1
                
    redacted_count = total_candidates - len(surviving)
    coverage = (redacted_count / total_candidates) if total_candidates > 0 else 1.0
    
    report = {
        "total_original_pii_candidates": total_candidates,
        "redacted_candidates": redacted_count,
        "coverage": coverage,
        "surviving_pii": surviving,
        "by_category": by_category
    }
    
    return report

def main():
    parser = argparse.ArgumentParser(description="Audit a redacted DOCX against the original.")
    parser.add_argument("--original", type=str, required=True, help="Path to original DOCX")
    parser.add_argument("--redacted", type=str, required=True, help="Path to redacted DOCX")
    args = parser.parse_args()
    
    logging.info(f"Auditing {args.redacted} against {args.original}")
    report = audit(args.original, args.redacted)
    
    out_path = os.path.join(os.path.dirname(__file__), "redaction_audit.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=4)
        
    logging.info(f"Audit complete. Coverage: {report['coverage']:.2%} ({report['redacted_candidates']}/{report['total_original_pii_candidates']} redacted)")
    logging.info(f"Surviving PII instances: {len(report['surviving_pii'])}")
    if report['surviving_pii']:
        logging.warning("WARNING: SURVIVING PII DETECTED!")
    
if __name__ == "__main__":
    main()
