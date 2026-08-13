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
from core.entities import PIIEntity
from document.traversal import DocumentTraverser
from core.replacement import DeterministicReplacer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_expected_text(text_orig, resolved_entities, replacer):
    resolved_entities.sort(key=lambda x: x.start)
    expected = ""
    curr = 0
    for ent in resolved_entities:
        expected += text_orig[curr:ent.start]
        expected += replacer.get_replacement(ent.text, ent.entity_type)
        curr = ent.end
    expected += text_orig[curr:]
    return expected

def audit(original_path, redacted_path):
    doc_orig = docx.Document(original_path)
    doc_red = docx.Document(redacted_path)
    
    detectors = [RegexDetector(), NERDetector(), ContextDetector()]
    resolver = EntityResolver()
    replacer = DeterministicReplacer()
    
    trav_orig = DocumentTraverser(doc_orig)
    trav_red = DocumentTraverser(doc_red)
    
    iter_orig = trav_orig.traverse()
    iter_red = trav_red.traverse()
    
    total_candidates = 0
    surviving = []
    unintended_changes = []
    by_category = {}
    
    # Stateful memoization dictionary: {normalized_text: entity_type}
    memoized_entities = {}
    
    domain_terms_lower = [
        "the company", "registered office", "annual report", "board meeting", 
        "statutory auditor", "bankers", "summary", "unless", "there", "while",
        "therefore", "certain", "business", "services", "packaging"
    ]
    
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
                
        # Inject candidates from stateful memoization
        for g_text, g_type in memoized_entities.items():
            for match in re.finditer(r'\b' + re.escape(g_text) + r'\b', text_orig):
                candidates.append(PIIEntity(
                    text=g_text,
                    entity_type=g_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.99,
                    detector="stateful_memo",
                    location=loc_orig,
                    source_context=text_orig
                ))
                
        resolved = resolver.resolve(candidates)
        
        # Update stateful memo
        for ent in resolved:
            if getattr(ent, 'confidence', 1.0) >= 0.95 and ent.entity_type in ["PERSON", "COMPANY"]:
                words = ent.text.split()
                if len(words) >= 2:
                    if ent.text.lower() not in domain_terms_lower:
                        blacklist = ["the company", "registered office", "annual report", "board meeting", "statutory auditor"]
                        if ent.text.lower() not in blacklist:
                            memoized_entities[ent.text] = ent.entity_type
        
        for ent in resolved:
            total_candidates += 1
            cat = ent.entity_type
            by_category[cat] = by_category.get(cat, {'total': 0, 'survived': 0})
            by_category[cat]['total'] += 1
            
        # Span-aware validation
        expected_text = get_expected_text(text_orig, resolved, replacer)
        
        if text_red != expected_text:
            resolved.sort(key=lambda x: x.start)
            curr_orig = 0
            curr_red = 0
            
            for ent in resolved:
                non_pii_orig = text_orig[curr_orig:ent.start]
                non_pii_red = text_red[curr_red:curr_red + len(non_pii_orig)]
                
                if non_pii_orig != non_pii_red:
                    unintended_changes.append({
                        "location": str(loc_orig),
                        "expected": non_pii_orig,
                        "actual": non_pii_red
                    })
                    
                curr_red += len(non_pii_orig)
                
                replacement = replacer.get_replacement(ent.text, ent.entity_type)
                actual_red_span = text_red[curr_red:curr_red + len(replacement)]
                
                if actual_red_span != replacement:
                    surviving.append({
                        "original_text": ent.text,
                        "type": ent.entity_type,
                        "location": str(loc_orig),
                        "expected_replacement": replacement,
                        "actual_text": actual_red_span,
                        "detector_source": getattr(ent, 'detector', 'unknown'),
                        "confidence": getattr(ent, 'confidence', 1.0)
                    })
                    by_category[ent.entity_type]['survived'] += 1
                    
                curr_orig = ent.end
                curr_red += len(replacement)
                
            non_pii_orig = text_orig[curr_orig:]
            non_pii_red = text_red[curr_red:]
            if non_pii_orig != non_pii_red:
                unintended_changes.append({
                    "location": str(loc_orig),
                    "expected": non_pii_orig,
                    "actual": non_pii_red
                })
                
    redacted_count = total_candidates - len(surviving)
    coverage = (redacted_count / total_candidates) if total_candidates > 0 else 1.0
    
    report = {
        "total_original_pii_candidates": total_candidates,
        "redacted_candidates": redacted_count,
        "coverage": coverage,
        "surviving_pii": surviving,
        "unintended_changes": unintended_changes,
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
    logging.info(f"Unintended non-PII changes: {len(report['unintended_changes'])}")
    
    if report['surviving_pii'] or report['unintended_changes']:
        logging.warning("WARNING: ISSUES DETECTED!")
    
if __name__ == "__main__":
    main()
