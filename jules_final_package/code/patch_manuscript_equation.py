"""Correct the day-ahead sale sign in Eq. (1) of the revised manuscript copy."""
from pathlib import Path

from docx import Document

paper_dir = Path(__file__).resolve().parents[1] / "paper"
path = next(paper_dir.glob("*_revised.docx"))
document = Document(path)
math_objects = document._element.xpath(".//m:oMath")
if not math_objects:
    raise RuntimeError("No Office Math objects found in the revised manuscript")
math_tag = "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"
math_tokens = list(math_objects[0].iter(math_tag))
operator_index = next(i for i, token in enumerate(math_tokens) if token.text == "+")
if "".join(token.text or "" for token in math_tokens[:operator_index]) != "PtDA":
    raise RuntimeError("The first equation does not match the expected Eq. (1) structure")
math_tokens[operator_index].text = "-"
document.save(path)

check = Document(path)
check_math = check._element.xpath(".//m:oMath")[0]
check_tokens = list(check_math.iter(math_tag))
check_operator = next(i for i, token in enumerate(check_tokens) if token.text in {"+", "-"})
if check_tokens[check_operator].text != "-":
    raise RuntimeError("Eq. (1) sign validation failed")
print(f"Updated and verified Eq. (1) in {path.name}")
