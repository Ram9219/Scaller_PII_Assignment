import re
from typing import List
from core.entities import PIIEntity, EntityLocation
from config import CONFIDENCE_THRESHOLDS, ENABLED_ENTITIES

class RegexDetector:
    def __init__(self):
        # Strict email pattern
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Phone: Supports + 91, 022-23456789, +44 20 7946 0958
        self.phone_pattern = re.compile(r'(?:\+\s?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4,5}\b')
        
        # SSN: XXX-XX-XXXX
        self.ssn_pattern = re.compile(r'\b(?!000|666)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b')
        
        # Credit Card: 13-19 digits, possibly with spaces/hyphens
        self.cc_pattern = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
        
        # IP Address (IPv4)
        self.ip_pattern = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
        
        # Dates (basic formats like DD/MM/YYYY, YYYY-MM-DD, DD Month YYYY, DD.MM.YYYY)
        # Note: Not all dates are DOB. We just detect them here.
        self.date_pattern = re.compile(r'\b(?:\d{1,2}[-/\.\s]\d{1,2}[-/\.\s]\d{2,4}|\d{4}[-/\.\s]\d{1,2}[-/\.\s]\d{1,2}|\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{2,4})\b', re.IGNORECASE)
        
        # Aadhaar: 12 digits, possibly grouped by 4
        self.aadhaar_pattern = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
        
        # DIN: Director Identification Number (8 digits in India)
        self.din_pattern = re.compile(r'\b\d{8}\b')

    def luhn_check(self, card_no: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        n_digits = len(card_no)
        n_sum = 0
        is_second = False
        for i in range(n_digits - 1, -1, -1):
            d = ord(card_no[i]) - ord('0')
            if is_second:
                d = d * 2
            n_sum += d // 10
            n_sum += d % 10
            is_second = not is_second
        return n_sum % 10 == 0

    def detect(self, text: str, location: EntityLocation, context: str = "") -> List[PIIEntity]:
        entities = []
        if not text:
            return entities

        if "EMAIL" in ENABLED_ENTITIES:
            for match in self.email_pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(), entity_type="EMAIL",
                    start=match.start(), end=match.end(),
                    confidence=CONFIDENCE_THRESHOLDS["REGEX_HIGH"],
                    detector="regex", location=location, source_context=context
                ))

        if "PHONE" in ENABLED_ENTITIES:
            for match in self.phone_pattern.finditer(text):
                val = match.group()
                # Basic length validation (at least 10 digits)
                if sum(c.isdigit() for c in val) >= 10:
                    entities.append(PIIEntity(
                        text=val, entity_type="PHONE",
                        start=match.start(), end=match.end(),
                        confidence=CONFIDENCE_THRESHOLDS["REGEX_MEDIUM"], # Context can increase it
                        detector="regex", location=location, source_context=context
                    ))

        if "SSN" in ENABLED_ENTITIES:
            for match in self.ssn_pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(), entity_type="SSN",
                    start=match.start(), end=match.end(),
                    confidence=CONFIDENCE_THRESHOLDS["REGEX_HIGH"],
                    detector="regex", location=location, source_context=context
                ))

        if "CREDIT_CARD" in ENABLED_ENTITIES:
            for match in self.cc_pattern.finditer(text):
                val = match.group()
                clean_val = re.sub(r'[\s-]', '', val)
                if self.luhn_check(clean_val):
                    entities.append(PIIEntity(
                        text=val, entity_type="CREDIT_CARD",
                        start=match.start(), end=match.end(),
                        confidence=CONFIDENCE_THRESHOLDS["REGEX_HIGH"],
                        detector="regex", location=location, source_context=context
                    ))

        if "IP_ADDRESS" in ENABLED_ENTITIES:
            for match in self.ip_pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(), entity_type="IP_ADDRESS",
                    start=match.start(), end=match.end(),
                    confidence=CONFIDENCE_THRESHOLDS["REGEX_HIGH"],
                    detector="regex", location=location, source_context=context
                ))
        
        # Dates - they need context to become DOB, so we detect as DATE candidate
        for match in self.date_pattern.finditer(text):
            entities.append(PIIEntity(
                text=match.group(), entity_type="DATE", # Temporary type
                start=match.start(), end=match.end(),
                confidence=CONFIDENCE_THRESHOLDS["REGEX_MEDIUM"],
                detector="regex", location=location, source_context=context
            ))

        if "AADHAAR" in ENABLED_ENTITIES:
            for match in self.aadhaar_pattern.finditer(text):
                val = match.group()
                clean_val = re.sub(r'[\s-]', '', val)
                # Aadhaar shouldn't be entirely zeroes or simple sequences, but for regex we just output candidate
                if len(clean_val) == 12:
                    entities.append(PIIEntity(
                        text=val, entity_type="AADHAAR",
                        start=match.start(), end=match.end(),
                        confidence=CONFIDENCE_THRESHOLDS["REGEX_MEDIUM"],
                        detector="regex", location=location, source_context=context
                    ))

        if "DIN" in ENABLED_ENTITIES:
            for match in self.din_pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(), entity_type="DIN",
                    start=match.start(), end=match.end(),
                    confidence=CONFIDENCE_THRESHOLDS["REGEX_MEDIUM"],
                    detector="regex", location=location, source_context=context
                ))

        return entities
