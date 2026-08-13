import docx
from typing import Iterator, Tuple
from core.entities import EntityLocation

class DocumentTraverser:
    """
    Traverses a python-docx Document and yields (text, EntityLocation, paragraph_object).
    The paragraph_object is used later by the processor to apply replacements.
    """
    def __init__(self, doc: docx.Document):
        self.doc = doc

    def traverse(self) -> Iterator[Tuple[str, EntityLocation, object]]:
        # 1. Main Document Paragraphs
        for i, paragraph in enumerate(self.doc.paragraphs):
            text = paragraph.text
            if text.strip():
                yield text, EntityLocation(paragraph_index=i), paragraph

        # 2. Tables
        for t_idx, table in enumerate(self.doc.tables):
            # Extract header texts if possible
            headers = []
            if len(table.rows) > 0:
                for cell in table.rows[0].cells:
                    headers.append(cell.text.strip())

            for r_idx, row in enumerate(table.rows):
                is_header = (r_idx == 0) # Simple heuristic: first row is header
                for c_idx, cell in enumerate(row.cells):
                    header_text = headers[c_idx] if c_idx < len(headers) else ""
                    
                    for p_idx, paragraph in enumerate(cell.paragraphs):
                        text = paragraph.text
                        if text.strip():
                            # We can pack the header text into the location object or yield it
                            loc = EntityLocation(
                                table_index=t_idx, 
                                row_index=r_idx, 
                                cell_index=c_idx, 
                                paragraph_index=p_idx,
                                is_header=is_header
                            )
                            # Let's attach the header text to the location object
                            setattr(loc, 'header_text', header_text)
                            yield text, loc, paragraph

        # 3. Headers and Footers (from sections)
        for s_idx, section in enumerate(self.doc.sections):
            for p_idx, paragraph in enumerate(section.header.paragraphs):
                text = paragraph.text
                if text.strip():
                    yield text, EntityLocation(
                        paragraph_index=p_idx,
                        is_header=True
                    ), paragraph
            
            for p_idx, paragraph in enumerate(section.footer.paragraphs):
                text = paragraph.text
                if text.strip():
                    yield text, EntityLocation(
                        paragraph_index=p_idx,
                        is_footer=True
                    ), paragraph
