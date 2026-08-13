import sys
import os
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.entities import PIIEntity, EntityLocation
from detectors.ner_detector import NERDetector
from detectors.context_detector import ContextDetector
from detectors.regex_detector import RegexDetector
from core.resolver import EntityResolver
from config import ENABLED_ENTITIES

@pytest.fixture
def ner():
    return NERDetector()

@pytest.fixture
def context_detector():
    return ContextDetector()

@pytest.fixture
def regex():
    return RegexDetector()

@pytest.fixture
def resolver():
    return EntityResolver()

# --- 1. PHONE vs AADHAAR vs FINANCIAL NUMBERS ---
def test_phone_context(regex, context_detector, resolver):
    text = "Her DIN is 11223344 and Aadhaar is 111122223333."
    loc = EntityLocation(paragraph_index=0)
    candidates = regex.detect(text, loc, text)
    refined = context_detector.refine_entities(candidates, text)
    resolved = resolver.resolve(refined)
    
    # 111122223333 should be AADHAAR, not PHONE
    for ent in resolved:
        if ent.text == "111122223333":
            assert ent.entity_type == "AADHAAR"

    text2 = "NEGATIVE EXAMPLES: Financial numbers like 1,200,000 or 1234567890 should not be phones."
    candidates2 = regex.detect(text2, loc, text2)
    refined2 = context_detector.refine_entities(candidates2, text2)
    resolved2 = resolver.resolve(refined2)
    
    assert len([e for e in resolved2 if e.entity_type == "PHONE"]) == 0

# --- 2. ADDRESS FP ---
def test_address_fp(ner, context_detector, resolver):
    loc = EntityLocation(paragraph_index=0)
    
    text1 = "City names like Mumbai, Pune, Delhi without address context."
    cand1 = ner.detect(text1, loc, text1)
    ref1 = context_detector.refine_entities(cand1, text1)
    assert len([e for e in ref1 if e.entity_type == "PHYSICAL_OR_MAILING_ADDRESS"]) == 0
    
    text2 = "Random words like Apple, Orange, Banana."
    cand2 = ner.detect(text2, loc, text2)
    ref2 = context_detector.refine_entities(cand2, text2)
    assert len([e for e in ref2 if e.entity_type == "PHYSICAL_OR_MAILING_ADDRESS"]) == 0
    
    text3 = "Contact Address: B-201, Sunshine Apartments, MG Road, Bengaluru, 560001"
    # Will be caught by context block
    ref3 = context_detector.detect_address_from_context(text3, loc)
    assert len([e for e in ref3 if e.entity_type == "PHYSICAL_OR_MAILING_ADDRESS"]) == 1

# --- 3. DIN / PHONE OVERLAP ---
def test_din_phone_overlap(regex, resolver):
    text = "Mr. Anil Sharma, our Executive Director, can be reached at anil.sharma@domain.in or 022-23456789."
    loc = EntityLocation(paragraph_index=0)
    candidates = regex.detect(text, loc, text)
    resolved = resolver.resolve(candidates)
    
    phones = [e for e in resolved if e.entity_type == "PHONE"]
    dins = [e for e in resolved if e.entity_type == "DIN"]
    assert len(phones) == 1
    assert "022-23456789" in phones[0].text
    # DIN substring should be dropped because PHONE priority > DIN and length is bigger
    assert len(dins) == 0

# --- 4. PERSON FP (Log IP) ---
def test_person_log_ip(ner, context_detector, resolver):
    text = "Log IP: 127.0.0.1, User SSN: 555-66-7777."
    loc = EntityLocation(paragraph_index=0)
    candidates = ner.detect(text, loc, text)
    refined = context_detector.refine_entities(candidates, text)
    
    # "Log IP" might be NER'd as PERSON but context should drop it
    assert len([e for e in refined if e.entity_type == "PERSON"]) == 0

# --- 5. COMPANY FN ---
def test_company_llc(ner, context_detector):
    text = "NextGen Solutions LLC is based in India."
    loc = EntityLocation(paragraph_index=0)
    # Mocking NER since LLC might not be picked up by small model, we test context promotion if it was ORG
    ent = PIIEntity(text="NextGen Solutions LLC", entity_type="COMPANY_CANDIDATE", start=0, end=21, confidence=0.7, detector="spacy_ner", location=loc, source_context=text)
    refined = context_detector.refine_entities([ent], text)
    assert len(refined) == 1
    assert refined[0].entity_type == "COMPANY"

# --- 6. DOB FN ---
def test_dob_dot_format(regex, context_detector):
    loc = EntityLocation(paragraph_index=0)
    
    text1 = "DOB 12.11.1992."
    cand1 = regex.detect(text1, loc, text1)
    ref1 = context_detector.refine_entities(cand1, text1)
    assert len([e for e in ref1 if e.entity_type == "DATE_OF_BIRTH"]) == 1
    
    text2 = "Annual Report Date 12.11.1992"
    cand2 = regex.detect(text2, loc, text2)
    ref2 = context_detector.refine_entities(cand2, text2)
    assert len([e for e in ref2 if e.entity_type == "DATE_OF_BIRTH"]) == 0

# --- 7. SSN FN ---
def test_ssn_overlap(regex, resolver):
    text = "Connect to 10.0.0.1. SSN: 987-65-4321."
    loc = EntityLocation(paragraph_index=0)
    cand = regex.detect(text, loc, text)
    res = resolver.resolve(cand)
    
    ssns = [e for e in res if e.entity_type == "SSN"]
    assert len(ssns) == 1
    assert ssns[0].text == "987-65-4321"

# --- 8. AADHAAR CONTEXT ---
def test_aadhaar_context(regex, context_detector):
    loc = EntityLocation(paragraph_index=0)
    
    text1 = "Paid with card 4532 1234 1234 1234."
    cand1 = regex.detect(text1, loc, text1)
    ref1 = context_detector.refine_entities(cand1, text1)
    assert len([e for e in ref1 if e.entity_type == "AADHAAR"]) == 0
    
    text2 = "Another invalid card 1234 5678 1234 5678."
    cand2 = regex.detect(text2, loc, text2)
    ref2 = context_detector.refine_entities(cand2, text2)
    assert len([e for e in ref2 if e.entity_type == "AADHAAR"]) == 0
