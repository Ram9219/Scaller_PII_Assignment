import json
import argparse
import sys
import os
from typing import List, Dict, Any

# Add parent to path for imports if run as script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detectors import RegexDetector, NERDetector, ContextDetector
from core.resolver import EntityResolver
from core.entities import EntityLocation
from config import ENABLED_ENTITIES

def evaluate(ground_truth_path: str, output_dir: str = "evaluation"):
    with open(ground_truth_path, 'r') as f:
        data = json.load(f)

    detectors = [RegexDetector(), NERDetector(), ContextDetector()]
    resolver = EntityResolver()

    categories = [
        "PERSON", "EMAIL", "PHONE", "COMPANY", "PHYSICAL_OR_MAILING_ADDRESS",
        "SSN", "CREDIT_CARD", "DATE_OF_BIRTH", "IP_ADDRESS"
    ]
    if "AADHAAR" in ENABLED_ENTITIES:
        categories.append("AADHAAR")
    if "DIN" in ENABLED_ENTITIES:
        categories.append("DIN")

    metrics = {cat: {"tp": 0, "fp": 0, "fn": 0} for cat in categories}
    
    false_positives = []
    false_negatives = []

    for item_idx, item in enumerate(data):
        text = item["text"]
        gt_entities = item.get("entities", [])
        
        # Simple location for evaluation
        location = EntityLocation(paragraph_index=item_idx)
        
        candidates = []
        # Pass empty context for general text, unless it's a table in GT (not supported in simple GT yet)
        for detector in detectors:
            if hasattr(detector, 'refine_entities'):
                candidates = detector.refine_entities(candidates, text)
                candidates.extend(detector.detect_additional_entities_from_context(text, location))
            else:
                candidates.extend(detector.detect(text, location, text))
        
        predictions = resolver.resolve(candidates)
        
        unmatched_gt = list(gt_entities)
        unmatched_pred = list(predictions)
        
        # Match Predictions to Ground Truth
        for pred in predictions:
            matched = False
            for gt in unmatched_gt:
                # Type must match. Span must overlap (we use simple substring check for text)
                if gt["type"] == pred.entity_type and (pred.text in gt["text"] or gt["text"] in pred.text):
                    if gt["type"] in metrics:
                        metrics[gt["type"]]["tp"] += 1
                    unmatched_gt.remove(gt)
                    unmatched_pred.remove(pred)
                    matched = True
                    break
            
            if not matched:
                if pred.entity_type in metrics:
                    metrics[pred.entity_type]["fp"] += 1
                false_positives.append({
                    "predicted_text": pred.text,
                    "predicted_type": pred.entity_type,
                    "detector_source": pred.detector,
                    "confidence": pred.confidence,
                    "location": f"Paragraph {item_idx}",
                    "surrounding_context": text
                })
                
        for gt in unmatched_gt:
            if gt["type"] in metrics:
                metrics[gt["type"]]["fn"] += 1
            false_negatives.append({
                "ground_truth_text": gt["text"],
                "expected_type": gt["type"],
                "location": f"Paragraph {item_idx}",
                "surrounding_context": text
            })

    # Overall metrics
    total_tp = sum(m["tp"] for m in metrics.values())
    total_fp = sum(m["fp"] for m in metrics.values())
    total_fn = sum(m["fn"] for m in metrics.values())

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    print("=" * 60)
    print("EVALUATION RESULTS (per-category and overall)")
    print("=" * 60)
    print(f"Overall TP: {total_tp} | FP: {total_fp} | FN: {total_fn}")
    print(f"Overall Precision: {overall_precision:.4f}")
    print(f"Overall Recall:    {overall_recall:.4f}")
    print(f"Overall F1 Score:  {overall_f1:.4f}")
    print("-" * 60)
    
    for cat in categories:
        m = metrics[cat]
        tp, fp, fn = m["tp"], m["fp"], m["fn"]
        if tp + fn == 0:
            print(f"{cat:<30} TP:{tp:<3} FP:{fp:<3} FN:{fn:<3} | P:N/A    R:N/A    F1:N/A")
        else:
            p = tp / (tp + fp) if (tp + fp) > 0 else 0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0
            f = 2 * (p * r) / (p + r) if (p + r) > 0 else 0
            print(f"{cat:<30} TP:{tp:<3} FP:{fp:<3} FN:{fn:<3} | P:{p:.4f} R:{r:.4f} F1:{f:.4f}")

    # Write JSON logs
    os.makedirs(output_dir, exist_ok=True)
    failure_analysis = {
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }
    with open(os.path.join(output_dir, "failure_analysis.json"), "w") as f:
        json.dump(failure_analysis, f, indent=4)
        
    print("-" * 60)
    print(f"Failure Analysis exported to {os.path.join(output_dir, 'failure_analysis.json')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt", default="ground_truth.example.json", help="Path to ground truth JSON")
    args = parser.parse_args()
    
    gt_path = args.gt if os.path.isabs(args.gt) else os.path.join(os.path.dirname(__file__), args.gt)
    evaluate(gt_path, output_dir=os.path.dirname(__file__))
