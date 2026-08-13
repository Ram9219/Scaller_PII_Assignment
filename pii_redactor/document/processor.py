import docx
from typing import List, Dict, Tuple
from core.entities import PIIEntity
from document.traversal import DocumentTraverser
import logging

class DocumentProcessor:
    def __init__(self, detectors: List, resolver, replacer):
        self.detectors = detectors
        self.resolver = resolver
        self.replacer = replacer
        self.stats = {
            "processed_paragraphs": 0, 
            "entities_replaced": 0,
            "total_candidates": 0,
            "rejected_by_resolver": 0,
            "replacements_in_tables": 0,
            "replacements_in_headers_footers": 0,
            "low_confidence_suspicious": 0
        }
        self.replaced_entities_log = []

    def _get_run_mapping(self, paragraph) -> Tuple[str, List[Tuple[int, int, int]]]:
        """
        Returns full text of the paragraph and a mapping of character index to (run_index, char_index_in_run).
        """
        full_text = ""
        mapping = []
        for r_idx, run in enumerate(paragraph.runs):
            for c_idx, char in enumerate(run.text):
                mapping.append((r_idx, c_idx, len(full_text)))
                full_text += char
        return full_text, mapping

    def _apply_replacements(self, paragraph, entities: List[PIIEntity]):
        """
        Replaces text within runs preserving formatting.
        Applies all entity replacements to the paragraph robustly by building
        an edit list per run and applying them from right-to-left.
        """
        full_text, mapping = self._get_run_mapping(paragraph)
        
        # Structure: run_index -> list of (start_char, end_char, replacement_str)
        run_edits = {i: [] for i in range(len(paragraph.runs))}

        for ent in entities:
            if ent.start >= len(mapping) or ent.end > len(mapping) or ent.start >= ent.end:
                continue

            replacement = self.replacer.get_replacement(ent.text, ent.entity_type)
            self.stats["entities_replaced"] += 1
            
            if hasattr(ent.location, 'table_index') and ent.location.table_index is not None:
                self.stats["replacements_in_tables"] += 1
            if getattr(ent.location, 'is_header', False) or getattr(ent.location, 'is_footer', False):
                self.stats["replacements_in_headers_footers"] += 1
                
            self.replaced_entities_log.append({
                "type": ent.entity_type,
                "original": ent.text,
                "replacement": replacement
            })

            start_map = mapping[ent.start]
            end_map = mapping[ent.end - 1]

            start_run_idx = start_map[0]
            end_run_idx = end_map[0]
            start_char_idx = start_map[1]
            end_char_idx = end_map[1]

            if start_run_idx == end_run_idx:
                run_edits[start_run_idx].append((start_char_idx, end_char_idx + 1, replacement))
            else:
                # Spans multiple runs
                run_edits[start_run_idx].append((start_char_idx, len(paragraph.runs[start_run_idx].text), replacement))
                for i in range(start_run_idx + 1, end_run_idx):
                    run_edits[i].append((0, len(paragraph.runs[i].text), ""))
                run_edits[end_run_idx].append((0, end_char_idx + 1, ""))

        # Apply edits per run, right-to-left
        for r_idx, edits in run_edits.items():
            if not edits:
                continue
            # Sort descending by start_char
            edits.sort(key=lambda x: x[0], reverse=True)
            run = paragraph.runs[r_idx]
            run_text = run.text
            for start_char, end_char, repl in edits:
                run_text = run_text[:start_char] + repl + run_text[end_char:]
            run.text = run_text

    def process(self, input_path: str, output_path: str):
        logging.info(f"Loading document from {input_path}")
        doc = docx.Document(input_path)
        traverser = DocumentTraverser(doc)
        
        for text, location, paragraph in traverser.traverse():
            self.stats["processed_paragraphs"] += 1
            
            candidates = []
            
            # Combine paragraph context with table header context if available
            context = text
            if hasattr(location, 'header_text') and location.header_text:
                context = location.header_text + " | " + context

            for detector in self.detectors:
                if hasattr(detector, 'refine_entities'):
                    candidates = detector.refine_entities(candidates, context)
                    candidates.extend(detector.detect_additional_entities_from_context(text, location))
                else:
                    candidates.extend(detector.detect(text, location, context))
            
            self.stats["total_candidates"] += len(candidates)
            for c in candidates:
                if getattr(c, 'confidence', 1.0) < 0.7:
                    self.stats["low_confidence_suspicious"] += 1
                    
            resolved_entities = self.resolver.resolve(candidates)
            self.stats["rejected_by_resolver"] += (len(candidates) - len(resolved_entities))
            
            if resolved_entities:
                self._apply_replacements(paragraph, resolved_entities)

        logging.info(f"Saving redacted document to {output_path}")
        doc.save(output_path)
        return self.stats
