import re
from typing import List
from core.entities import PIIEntity, EntityLocation
from config import (
    DOB_CONTEXT_WORDS, 
    ADDRESS_CONTEXT_WORDS, 
    COMPANY_SUFFIXES, 
    PERSON_PREFIXES, 
    PERSON_TITLES,
    CONFIDENCE_THRESHOLDS,
    ENABLED_ENTITIES
)

class ContextDetector:
    def __init__(self):
        # Common false positive words for PERSON NER
        self.person_stopwords = {"aadhaar", "pan", "din", "cin", "gstin", "email", "phone", "date", "no.", "number", "id", "rupees", "lakhs", "crores"}
        
        self.tech_stopwords = {"ip", "log", "ssn", "user", "identifier"}
        
        # Address regex patterns for PIN code and block structure
        self.pin_pattern = re.compile(r'\b\d{6}\b')
        self.street_indicators = ["st", "street", "rd", "road", "marg", "lane", "nagar", "apartment", "apt", "building", "bldg", "floor", "flr", "plot", "phase", "block"]
        self.address_labels = ["address:", "address :", "registered office", "corporate office", "residential", "mailing", "office address", "contact address"]

    def _has_keyword(self, text: str, keywords: List[str]) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _has_word(self, text: str, words: set) -> bool:
        text_lower = text.lower()
        # Fast exact word check
        for w in text_lower.split():
            clean_w = re.sub(r'[^\w\s]', '', w)
            if clean_w in words:
                return True
        return False
        
    def refine_entities(self, entities: List[PIIEntity], context_text: str = "") -> List[PIIEntity]:
        refined = []
        surrounding = context_text.lower()
        
        for ent in entities:
            header_context = ""
            if hasattr(ent.location, 'header_text'):
                header_context = ent.location.header_text.lower()
                
            # Table Header Context
            if "dob" in header_context or "birth" in header_context:
                if ent.entity_type == "DATE":
                    ent.entity_type = "DATE_OF_BIRTH"
                    ent.confidence = CONFIDENCE_THRESHOLDS["TABLE_HEADER_HIGH"]
            elif "name" in header_context and ent.entity_type == "PERSON":
                ent.confidence = CONFIDENCE_THRESHOLDS["TABLE_HEADER_HIGH"]
            elif "address" in header_context and ent.entity_type == "ADDRESS_CANDIDATE":
                ent.entity_type = "PHYSICAL_OR_MAILING_ADDRESS"
                ent.confidence = CONFIDENCE_THRESHOLDS["TABLE_HEADER_HIGH"]
            elif ("company" in header_context or "entity" in header_context) and ent.entity_type == "COMPANY_CANDIDATE":
                ent.entity_type = "COMPANY"
                ent.confidence = CONFIDENCE_THRESHOLDS["TABLE_HEADER_HIGH"]

            # Paragraph/Cell Context Validation
            if ent.entity_type == "DATE":
                if self._has_keyword(surrounding, DOB_CONTEXT_WORDS):
                    ent.entity_type = "DATE_OF_BIRTH"
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]

            elif ent.entity_type == "COMPANY_CANDIDATE":
                # Restrict promotion: requires corporate suffix in the entity itself OR strong adjacent context
                if self._has_keyword(ent.text, COMPANY_SUFFIXES):
                    ent.entity_type = "COMPANY"
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]
                elif self._has_keyword(surrounding, ["company:", "organization:", "manager:", "registrar:"]):
                    ent.entity_type = "COMPANY"
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]
                else:
                    continue # Reject generic ORG without strong evidence
            
            elif ent.entity_type == "ADDRESS_CANDIDATE":
                # Must not promote just because "city" is in the sentence. Need strong labels or PIN.
                has_label = self._has_keyword(surrounding, self.address_labels)
                has_pin = bool(self.pin_pattern.search(surrounding))
                has_street = self._has_word(surrounding, set(self.street_indicators))
                
                # Check for multiple address components (comma separated block)
                is_multi_line = len([x for x in surrounding.split(",") if len(x.strip()) > 3]) > 2
                
                if has_label or (has_pin and has_street) or (is_multi_line and (has_pin or has_street)):
                    ent.entity_type = "PHYSICAL_OR_MAILING_ADDRESS"
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]
                else:
                    continue # Reject standalone city/location
                    
            elif ent.entity_type == "PERSON":
                # Filter out obvious false positives
                if self._has_word(ent.text, self.person_stopwords):
                    continue
                
                # Reject if it's a generic capitalized term or starts with "The "
                if ent.text.lower().startswith("the ") or len(ent.text.split()) == 1:
                    # Single words like "Offer" or phrases like "The Offer" are highly suspicious without context
                    has_strong_context = self._has_keyword(surrounding, PERSON_PREFIXES) or self._has_keyword(surrounding, PERSON_TITLES)
                    if not has_strong_context:
                        continue # Reject generic term

                # Contextual rejection for technical identifiers without person titles
                if self._has_word(surrounding, self.tech_stopwords):
                    if not (self._has_keyword(surrounding, PERSON_PREFIXES) or self._has_keyword(surrounding, PERSON_TITLES)):
                        continue # Reject
                
                # Reject known legal/financial non-PII terms
                domain_terms = ["offer", "issue", "equity", "shares", "anchor", "investor", "building", "process", "sebi", "icdr", "regulations", "companies act", "exchange", "qib", "nii", "rii", "amount", "percentage", "page"]
                if self._has_keyword(ent.text, domain_terms):
                    continue

                if self._has_keyword(surrounding, PERSON_PREFIXES) or self._has_keyword(surrounding, PERSON_TITLES):
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]
                elif len(ent.text.split()) >= 2 and ent.text.istitle():
                    # If it's a multi-word Title Cased entity that survived the filters, it's plausible.
                    pass
                else:
                    continue # Reject low-confidence candidates with no context

            elif ent.entity_type == "PHONE":
                # A 10-12 digit number by itself must NOT automatically be classified as PHONE.
                # Must have phone context, country code, or formatting.
                has_phone_context = self._has_keyword(surrounding, ["phone", "telephone", "tel", "mobile", "contact", "direct line", "reached at"])
                has_country_code = '+' in ent.text
                has_separators = '-' in ent.text or '(' in ent.text
                
                if self._has_word(surrounding, {"aadhaar", "pan", "din", "financial", "rupees"}):
                    continue # Strong Aadhaar or financial context suppresses phone
                
                # If just a plain sequence of digits (e.g. 1234567890) and no context
                if not has_phone_context and not has_country_code and not has_separators:
                    continue # Reject generic 10 digit number

            elif ent.entity_type == "AADHAAR":
                # Aadhaar context strongly increases, Card context suppresses
                if self._has_keyword(surrounding, ["card", "payment", "paid", "credit", "debit"]):
                    continue # Reject Aadhaar
                if self._has_keyword(surrounding, ["aadhaar"]):
                    ent.confidence = CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"]

            refined.append(ent)
            
        final_entities = []
        for ent in refined:
            if ent.entity_type in ENABLED_ENTITIES:
                final_entities.append(ent)
                
        return final_entities

    def detect_address_from_context(self, text: str, location: EntityLocation) -> List[PIIEntity]:
        entities = []
        if "PHYSICAL_OR_MAILING_ADDRESS" not in ENABLED_ENTITIES:
            return entities
            
        text_lower = text.lower()
        
        # 1. Prefix based detection
        if self._has_keyword(text_lower, ["registered office:", "address:", "residential address:", "corporate office:", "contact address:"]):
            parts = re.split(r'(?i)(?:registered office|contact address|address|residential address|corporate office)[:\s]+', text, 1)
            if len(parts) > 1 and len(parts[1].strip()) > 10:
                address_text = parts[1].strip()
                start_idx = text.find(address_text)
                entities.append(PIIEntity(
                    text=address_text,
                    entity_type="PHYSICAL_OR_MAILING_ADDRESS",
                    start=start_idx,
                    end=start_idx + len(address_text),
                    confidence=CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"],
                    detector="context_block",
                    location=location,
                    source_context=text
                ))
                return entities

        # 2. Implicit detection based on PIN codes + Street indicators in a comma-separated block
        if self.pin_pattern.search(text) and self._has_word(text_lower, set(self.street_indicators)) and "," in text:
            entities.append(PIIEntity(
                text=text.strip(),
                entity_type="PHYSICAL_OR_MAILING_ADDRESS",
                start=text.find(text.strip()),
                end=text.find(text.strip()) + len(text.strip()),
                confidence=CONFIDENCE_THRESHOLDS["CONTEXT_HIGH"],
                detector="context_implicit",
                location=location,
                source_context=text
            ))
            
        return entities
