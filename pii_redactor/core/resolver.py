from typing import List
from core.entities import PIIEntity

class EntityResolver:
    def __init__(self):
        pass

    def _is_overlap(self, ent1: PIIEntity, ent2: PIIEntity) -> bool:
        # Check if spans overlap
        return max(ent1.start, ent2.start) < min(ent1.end, ent2.end)

    def resolve(self, entities: List[PIIEntity]) -> List[PIIEntity]:
        if not entities:
            return []

        # Remove exact duplicates first (same start, end, type)
        unique_entities = []
        seen = set()
        for ent in entities:
            signature = (ent.start, ent.end, ent.entity_type)
            if signature not in seen:
                seen.add(signature)
                unique_entities.append(ent)
            else:
                # If we have a duplicate, keep the one with higher confidence
                for existing in unique_entities:
                    if (existing.start, existing.end, existing.entity_type) == signature:
                        if ent.confidence > existing.confidence:
                            existing.confidence = ent.confidence
                            existing.detector = f"{existing.detector},{ent.detector}"
                        break

        # Sort by start index, then by length (descending)
        unique_entities.sort(key=lambda x: (x.start, -(x.end - x.start)))

        # Priority mapping (higher is better) for tie-breaking
        priority = {
            "PHONE": 10,
            "EMAIL": 10,
            "IP_ADDRESS": 10,
            "PHYSICAL_OR_MAILING_ADDRESS": 9,
            "SSN": 9,
            "CREDIT_CARD": 9,
            "AADHAAR": 8,
            "DATE_OF_BIRTH": 7,
            "COMPANY": 6,
            "PERSON": 5,
            "DIN": 4,
            "DATE": 1
        }

        resolved = []
        for current in unique_entities:
            # We want to insert 'current' into 'resolved' if it wins all overlaps.
            # If it overlaps with multiple existing, it must beat ALL of them to replace them.
            # Actually, standard approach:
            # 1. Find all overlapping entities in 'resolved'.
            # 2. Check if 'current' is better than ALL of them.
            # 3. If so, remove them and add 'current'. Otherwise, drop 'current'.
            
            overlaps = [prev for prev in resolved if self._is_overlap(current, prev)]
            
            if not overlaps:
                resolved.append(current)
                continue
                
            # Determine if current beats ALL overlaps
            current_wins_all = True
            for prev in overlaps:
                prev_contains_curr = prev.start <= current.start and prev.end >= current.end
                curr_contains_prev = current.start <= prev.start and current.end >= prev.end
                
                p_curr = priority.get(current.entity_type, 0)
                p_prev = priority.get(prev.entity_type, 0)
                
                # Win conditions
                if current.confidence > prev.confidence:
                    continue # beats this one
                elif current.confidence < prev.confidence:
                    current_wins_all = False
                    break
                else:
                    # Equal confidence
                    if prev_contains_curr and not curr_contains_prev:
                        current_wins_all = False
                        break
                    elif curr_contains_prev and not prev_contains_curr:
                        continue # beats this one
                    else:
                        if p_curr > p_prev:
                            continue # beats this one
                        elif p_curr < p_prev:
                            current_wins_all = False
                            break
                        else:
                            # Length
                            if (current.end - current.start) > (prev.end - prev.start):
                                continue
                            else:
                                current_wins_all = False
                                break
                                
            if current_wins_all:
                for prev in overlaps:
                    resolved.remove(prev)
                resolved.append(current)
                resolved.sort(key=lambda x: (x.start, -(x.end - x.start)))
                
        return resolved
