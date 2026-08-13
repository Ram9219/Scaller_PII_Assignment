"""
Configuration for the PII Redaction Pipeline.
"""

# Enabled Entity Types
ENABLED_ENTITIES = {
    "PERSON",
    "EMAIL",
    "PHONE",
    "COMPANY",
    "PHYSICAL_OR_MAILING_ADDRESS",
    "SSN",
    "CREDIT_CARD",
    "DATE_OF_BIRTH",
    "IP_ADDRESS",
    "AADHAAR",
    "DIN"
}

# Confidence Thresholds
CONFIDENCE_THRESHOLDS = {
    "REGEX_HIGH": 0.95,
    "REGEX_MEDIUM": 0.85,
    "NER_HIGH": 0.90,
    "NER_MEDIUM": 0.70,
    "CONTEXT_HIGH": 0.92,
    "TABLE_HEADER_HIGH": 0.95,
}

# Context Keywords for DOB
DOB_CONTEXT_WORDS = [
    "dob", "date of birth", "birth date", "born", "born on"
]

# Context Keywords for Address
ADDRESS_CONTEXT_WORDS = [
    "address", "registered office", "corporate office", "residential", 
    "mailing", "office address", "r/o", "s/o", "d/o", "w/o", "street",
    "road", "village", "taluka", "district", "city", "state", "pin", "pincode",
    "located at", "situated at"
]

# Context Keywords for Company
COMPANY_SUFFIXES = [
    "limited", "ltd", "ltd.", "private", "pvt", "llp", "corporation", 
    "inc", "inc.", "industries", "technologies", "llc", "l.l.c.", "corp", "plc", "pvt ltd", "private limited"
]

# Context Keywords for Person
PERSON_PREFIXES = [
    "mr.", "ms.", "mrs.", "dr.", "shri", "smt"
]
PERSON_TITLES = [
    "director", "promoter", "chairman", "ceo", "cfo", "contact person", "manager"
]

# Debug mode
DEBUG = False

# Replacement settings
FAKER_SEED = 42  # For deterministic replacements

