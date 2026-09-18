"""Read the manual, write the step list.

In:  one rendered PNG per manual page.
Out: a sop.json-shaped dict, plus `step_pages` (which page shows each step's drawing).

Each page is read on its own ("which numbered steps are drawn here?"), then the pages are
merged by printed step number. `step_pages` falls out for free: the page that produced a
step is the page that shows it.

The output is a DRAFT. The website pauses here so a person can correct it before any video
is analysed, because the notebook's clearest finding is that the video model leans heavily
on this wording.

Uses the hosted authoring model when AUTHOR_API_KEY is set. Without one it falls back to
the local Cosmos NIM, which is a video model and writes noticeably weaker steps; the result
says which model wrote it so the UI can warn.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from . import config, cosmos

MAX_PAGES = 40

PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "visual_cues": {"type": "array", "items": {"type": "string"}},
                    "completion_state": {"type": "string"},
                    "state_is_monotone": {"type": "boolean"},
                },
                "required": ["step_number", "name", "description", "visual_cues",
                             "completion_state", "state_is_monotone"],
            },
        }
    },
    "required": ["steps"],
}

# One worked example, in the phrasing the video model responds to: parts named by how they
# look, motions a camera would see, and a completion state judgeable from one still frame.
EXAMPLE = """{"steps": [
  {"step_number": 5,
   "name": "Insert 6 metal rack tubes",
   "description": "Slide 6 hollow metal tubes vertically into the pre-drilled holes in the bottom rails.",
   "visual_cues": ["Operator holding slender silver hollow poles",
                   "Inserting poles vertically one by one into round holes along the bottom rails",
                   "Six vertical metal tubes standing upright between the wooden posts"],
   "completion_state": "Several slender metal tubes stand upright in a row inside the frame.",
   "state_is_monotone": true},
  {"step_number": 7,
   "name": "Position cardboard alignment template",
   "description": "Lower the folded cardboard template over the top ends of the 6 metal tubes to hold them aligned.",
   "visual_cues": ["Sliding a cardboard sheet downward over the open top ends of the tubes",
                   "The sheet resting horizontally across all tubes near the top"],
   "completion_state": "A cardboard sheet rests horizontally across the tops of the upright metal tubes.",
   "state_is_monotone": false}
]}"""


def _page_prompt(page_number: int, page_text: str, product: str) -> str:
    text_hint = f'\nText printed on this page: "{page_text[:600]}"' if page_text.strip() else ""
    return f"""This is page {page_number} of the assembly manual for {product}.{text_hint}

List every NUMBERED assembly step drawn on this page. Use the bold printed step number.
If the page has no numbered steps (cover, parts list, warnings, tools), return {{"steps": []}}.

For each step write:
- name: a short imperative title.
- description: what is done, naming parts by how they LOOK (colour, shape, material) and their
  part numbers if printed.
- visual_cues: 2-4 things a video camera would see while the step is performed - hand motions,
  the parts being held, how the assembly changes.
- completion_state: ONE sentence describing how the object looks once this step is done,
  judgeable from a single still photo without seeing any motion.
- state_is_monotone: true if that state stays true for the rest of the assembly; false if a
  later step undoes it (a temporary jig is removed, the assembly is flipped back, etc.).

Example of the expected style and format:
{EXAMPLE}

Reply with JSON only."""


def _page_text(pdf_path, page_number: int) -> str:
    doc = pymupdf.open(pdf_path)
    try:
        return re.sub(r"\s+", " ", doc[page_number - 1].get_text())
    finally:
        doc.close()


def author(pdf_path, page_images: list[Path], product: str, *, progress=None) -> dict:
    """Draft a SOP from a manual. Returns {"sop", "step_pages", "author_model", "warnings"}."""
    hosted = config.HAVE_AUTHOR_KEY
    client = cosmos.author_client() if hosted else cosmos.video_client()
    model = config.AUTHOR_MODEL if hosted else config.NIM_MODEL
    warnings = []
    if not hosted:
        warnings.append("No AUTHOR_API_KEY set: steps were drafted by the local video model, "
                        "which writes weaker descriptions. Review them carefully.")

    pages = list(enumerate(page_images[:MAX_PAGES], start=1))
    if len(page_images) > MAX_PAGES:
        warnings.append(f"Manual has {len(page_images)} pages; only the first {MAX_PAGES} were read.")

    def read_page(item):
        number, image = item
        try:
            ans = cosmos.ask(
                _page_prompt(number, _page_text(pdf_path, number), product),
                images=[image], schema=PAGE_SCHEMA, model=model, client=client,
                max_tokens=2000, guided=not hosted)
            return number, ans.get("steps", []), None
        except Exception as exc:
            return number, [], f"page {number}: {exc}"

    found = {}  # step_number -> (page, step)
    done = 0
    with ThreadPoolExecutor(4) as pool:
        for number, steps, error in pool.map(read_page, pages):
            done += 1
            if progress:
                progress(done, len(pages))
            if error:
                warnings.append(f"Could not read {error}")
            for step in steps:
                n = step.get("step_number")
                # A step drawn across two pages is kept from the first page it appears on.
                if isinstance(n, int) and n > 0 and n not in found and step.get("name"):
                    found[n] = (number, step)

    if not found:
        warnings.append("No numbered steps were found in the manual. Add them by hand.")

    expected, step_pages = [], {}
    for n in sorted(found):
        page, step = found[n]
        step_pages[str(n)] = page
        expected.append({
            "step_id": n,
            "manual_reference": f"Step {n} (p. {page})",
            "name": step["name"].strip(),
            "description": step.get("description", "").strip(),
            "visual_cues": [c.strip() for c in step.get("visual_cues", []) if c.strip()],
            "completion_state": step.get("completion_state", "").strip(),
            "state_is_monotone": bool(step.get("state_is_monotone", True)),
        })

    numbers = sorted(found)
    if numbers and numbers != list(range(numbers[0], numbers[-1] + 1)):
        missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        warnings.append(f"Step numbers are not continuous; missing {missing}. "
                        "A page may have been misread.")

    return {
        "sop": {"task_name": product, "total_manual_steps": len(expected),
                "expected_steps": expected},
        "step_pages": step_pages,
        "author_model": model,
        "warnings": warnings,
    }
