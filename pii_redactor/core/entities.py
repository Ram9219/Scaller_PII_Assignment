from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class EntityLocation:
    """Represents the location of an entity within the DOCX document."""
    paragraph_index: Optional[int] = None
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    cell_index: Optional[int] = None
    is_header: bool = False
    is_footer: bool = False
    
    def __hash__(self):
        return hash((self.paragraph_index, self.table_index, self.row_index, self.cell_index, self.is_header, self.is_footer))

@dataclass
class PIIEntity:
    """Represents a detected PII candidate."""
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    detector: str
    location: EntityLocation
    source_context: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "detector": self.detector,
            "location": {
                "paragraph_index": self.location.paragraph_index,
                "table_index": self.location.table_index,
                "row_index": self.location.row_index,
                "cell_index": self.location.cell_index,
                "is_header": self.location.is_header,
                "is_footer": self.location.is_footer,
            },
            "source_context": self.source_context
        }
