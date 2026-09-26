from pathlib import Path

from docx import Document


doc = Document(Path(__file__).resolve().parents[1] / "完整论文.docx")
capturing = False
for block in doc.element.body:
    tag = block.tag.rsplit("}", 1)[-1]
    if tag == "p":
        text_value = "".join(block.itertext()).strip()
        if text_value.startswith("7  问题三"):
            capturing = True
        if text_value.startswith("9  模型检验"):
            capturing = False
        if capturing and text_value:
            print(f"P\t{text_value}")
    elif tag == "tbl" and capturing:
        rows = []
        for tr in block.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
            cells = []
            for tc in tr.findall("./{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                cells.append("".join(tc.itertext()).strip())
            rows.append(" | ".join(cells))
        print("T\t" + " || ".join(rows))
