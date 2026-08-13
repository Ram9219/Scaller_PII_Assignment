# PII Redactor for Scaler AI Labs

## Problem Statement
The goal of this project is to build a production-quality, modular Python application that detects and redacts Personally Identifiable Information (PII) from a Red Herring Prospectus DOCX document. It must replace detected PII with deterministic synthetic values while preserving the original document structure and formatting.

## Approach & Architecture
We implemented a **Hybrid Detection Pipeline**:
1. **Document Traversal Engine**: Iterates over paragraphs, tables (including headers and cells), and section headers/footers to extract text alongside structured `EntityLocation` data.
2. **Hybrid Detectors**:
    - **Regex Detector**: Extracts highly structured candidates like Email, Phone, SSN, Credit Card, IP Address, Dates, Aadhaar, and DIN.
    - **NER Detector**: Uses `spaCy` (`en_core_web_sm`) to extract candidates like PERSON, ORG, and GPE.
    - **Context Detector**: Uses contextual keywords (e.g., surrounding text, table headers) to validate ambiguous entities (promoting `DATE` to `DATE_OF_BIRTH`, validating `COMPANY` and `PHYSICAL_OR_MAILING_ADDRESS`).
3. **Entity Resolver**: Handles overlap and deduplication by assigning confidence scores and prioritizing specific matches over generic ones.
4. **Deterministic Replacer**: Uses `Faker` with a fixed seed to map every original PII instance to a consistent, realistic synthetic value.
5. **DOCX Processor**: Carefully replaces text within individual runs. If a PII entity spans multiple runs, it modifies the runs sequentially. This is a run-aware replacement designed to preserve document structure and formatting.

## Evaluation Methodology & Results
An evaluation script (`evaluation/evaluator.py`) is provided that calculates Precision, Recall, and F1 score against a manually annotated `ground_truth.example.json`. 

**Results on Synthetic Ground Truth:**
- **Precision:** 1.0000
- **Recall:** 1.0000
- **F1 Score:** 1.0000

*Note: These perfect scores are on a controlled synthetic evaluation set representing the required PII taxonomy. Real-world performance on complex unstructured text will vary. Address extraction utilizes a fallback block detection to mitigate limitations of pure NER.*

## Installation

```bash
# Set up a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Usage

To redact a document:
```bash
python main.py -i "Red Herring Prospectus.docx" -o "Redacted_Prospectus.docx"
```

To run the evaluation:
```bash
python evaluation/evaluator.py
```

## Known Limitations
- The `python-docx` run-level replacement approach correctly preserves styles, but it assumes the string index offsets match exactly when entities overlap across multiple small runs. The algorithm implements a robust per-run edit list applied right-to-left to mitigate offset shifts.
- Multi-line addresses without explicit prefixes (like "Address:" or "Registered Office:") might be partially missed by NER since spaCy doesn't natively tag entire blocks as addresses.

## Deployment Strategy
The redaction engine is built using standard Python and `python-docx`. It can easily be wrapped in a FastAPI or Flask service and deployed to any cloud provider (e.g., Render, Railway, AWS Lambda). The current implementation focuses on local pipeline stability as per instructions.
