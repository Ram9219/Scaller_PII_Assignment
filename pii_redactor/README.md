# Scaler AI Labs: PII Redactor

A production-ready NLP pipeline for automated detection and deterministic redaction of Personally Identifiable Information (PII) from complex DOCX documents.

## Project Overview & Problem Statement
Organizations handling sensitive documents (like Red Herring Prospectuses, legal contracts, and HR forms) often face the challenge of redacting PII before sharing or archiving these documents. Manual redaction is error-prone and time-consuming. This project provides an automated Python pipeline that detects PII across unstructured paragraphs, complex nested tables, headers, and footers, and redacts them securely without destroying the underlying document structure or styling. 

## Architecture & Pipeline
The engine employs a **State-Aware, Two-Pass Redaction Architecture**:
1. **Pass 1 (Discovery & Memoization)**: Scans the document for high-confidence entities using NLP and Contextual Regular Expressions. Confidently detected `PERSON` and `COMPANY` entities are saved into a global deterministic memoization state.
2. **Pass 2 (Redaction & Structural Preservation)**: Iterates over the document structure recursively. Discovered entities and exact substring matches from the global state are deterministically replaced. 
3. **API Layer**: Wraps the core engine in a scalable FastAPI application.

## Supported PII Categories
The redactor successfully identifies and replaces the following entity types:
- `PERSON`
- `COMPANY`
- `PHONE`
- `EMAIL`
- `PHYSICAL_OR_MAILING_ADDRESS`
- `SSN` / `AADHAAR` / `DIN`
- `DATE_OF_BIRTH`
- `IP_ADDRESS`
- `CREDIT_CARD`

## Detection Strategy
The system uses a highly integrated ensemble approach:
- **`NERDetector`**: Uses `spaCy` (`en_core_web_sm`) for statistical Named Entity Recognition (e.g., PERSON, ORG).
- **`RegexDetector`**: Identifies standardized formats (e.g., Email, Phone, SSN, IP, Aadhaar).
- **`ContextDetector`**: Bridges the gap by using domain-specific contextual keywords to boost confidence (e.g., detecting `DIN: 12345678` or `Address: ...`).

## Entity Resolution & Deterministic Replacement
When multiple detectors flag the same or overlapping text, the `EntityResolver` applies conflict-resolution rules (e.g., preferring Context > NER). 
The `DeterministicReplacer` uses an MD5-based seed derived from the normalized entity text and entity type. This guarantees that "John Doe" is always replaced by the same synthetic name (e.g., "Michael Smith") throughout the entire document, maintaining readability.

## DOCX Structural Preservation
`python-docx` applies text at a "Run" level, meaning single words are often split across multiple styling boundaries. The engine calculates character-level offset boundaries, gracefully applying replacements across fragmented text runs while strictly preserving original fonts, bolding, italics, and table structures.

## Evaluation Methodology & Metrics
The pipeline was validated against two heavily stratified benchmarks:
1. **Synthetic Dataset**: Handcrafted edge cases, heavily fragmented formatting, complex tables.
2. **Real-Document Dataset**: Ground-truth extractions from a 127-page real-world Red Herring Prospectus.

**Verified Evaluation Metrics**:
- **Synthetic Benchmark**: Precision = `1.0000`, Recall = `1.0000`, F1 = `1.0000`
- **Real-Document Benchmark**: Precision = `1.0000`, Recall = `1.0000`, F1 = `1.0000`

**Full-Document Audit Results (127 pages)**:
- **Coverage**: 100%
- **Surviving PII Instances**: 0
- **Unintended Changes**: 0

**Automated Tests**: 17/17 passed (including structural preservation, overlapping span safety, and API tests).

## Repository Structure
```
pii_redactor/
├── api.py                  # FastAPI Application
├── config.py               # Global configuration (Categories, etc.)
├── core/
│   ├── replacement.py      # Deterministic MD5 Replacer
│   └── resolver.py         # Entity conflict resolver
├── detectors/
│   ├── base.py
│   ├── context_detector.py # Keyword-aware context matching
│   ├── ner_detector.py     # spaCy integration
│   └── regex_detector.py   # Pattern matching
├── document/
│   ├── processor.py        # Central redactor pipeline
│   └── traversal.py        # Deep DOCX element traversal
├── evaluation/             # Benchmarks, evaluator, and audit scripts
├── tests/                  # Pytest regression suite
├── Dockerfile              # Render deployment configuration
├── requirements.txt
└── README.md
```

## Local Installation
```bash
git clone <repository_url>
cd pii_redactor
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Usage

### 1. CLI Usage
Run the script directly on a local DOCX file:
```bash
python main.py -i "input.docx" -o "output.docx"
```

### 2. FastAPI Usage
Start the development server:
```bash
uvicorn api:app --reload
```
Test with cURL:
```bash
curl -X POST \
  -F "file=@input.docx" \
  http://localhost:8000/redact \
  --output redacted.docx
```

## Live Deployment
- **API Base URL**: [https://scaller-pii-assignment-1.onrender.com](https://scaller-pii-assignment-1.onrender.com)
- **Swagger Documentation**: [https://scaller-pii-assignment-1.onrender.com/docs](https://scaller-pii-assignment-1.onrender.com/docs)

*(Note: The deployment runs the Dockerfile securely via Render, utilizing in-memory tempfiles without saving user uploads).*

## Docker Usage
To build and run the Docker image locally:
```bash
docker build -t pii-redactor .
docker run --rm -d -p 8000:8000 pii-redactor
```

## Known Limitations & Future Improvements
- **Embedded Images/OCR**: Currently, embedded images and scanned-document PII are outside the implemented text-redaction scope. Future enhancements will integrate Tesseract OCR/Vision models to support image-based redaction natively within the DOCX.
