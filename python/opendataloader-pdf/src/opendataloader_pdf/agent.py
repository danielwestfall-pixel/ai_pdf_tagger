import argparse
import base64
import concurrent.futures
import json
import logging
import os
import re
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pikepdf
import requests
from dotenv import load_dotenv

import threading

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pdf_tagger_agent")

load_dotenv()


class AdaptiveRateLimiter:
    """Thread-safe adaptive rate limiter to space requests and prevent 429 errors."""
    def __init__(self):
        self.delay = 1.0  # Safe default: 1.0s delay
        self.lock = threading.Lock()
        self.last_request_time = 0.0
        self.last_429_time = 0.0

    def wait_if_needed(self):
        sleep_time = 0.0
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.delay:
                sleep_time = self.delay - elapsed
                self.last_request_time = now + sleep_time
            else:
                self.last_request_time = now

        if sleep_time > 0.0:
            time.sleep(sleep_time)

    def report_429(self):
        with self.lock:
            now = time.time()
            # Only increase delay at most once every 2 seconds to prevent rapid doubling from concurrent threads
            if now - self.last_429_time > 2.0:
                self.delay = min(5.0, self.delay * 2.0)
                self.last_429_time = now
                logger.warning(f"Rate Limiter: 429 rate limit hit. Spacing requests by {self.delay:.2f}s...")

    def report_success(self):
        with self.lock:
            # Gradually decay delay back to 0.1s minimum on success
            self.delay = max(0.1, self.delay * 0.95)



class GeminiAgentDocument:
    """Document representation matching Docling conversion results."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def export_to_dict(self) -> Dict[str, Any]:
        return self.data


class GeminiAgentConversionResult:
    """Conversion result mimicking Docling's result structure."""

    def __init__(self, document: GeminiAgentDocument, status: str, errors: List[str], page_count: int):
        self.document = document
        self.status = status
        self.errors = errors
        self.input = type("Input", (), {"page_count": page_count})()
        self.timings = {}


class GeminiAgentConverter:
    """Multimodal layout converter using Gemini API for visual tagging."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        max_workers: int = 3,
        should_cancel: Optional[callable] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.max_workers = max_workers
        self.should_cancel = should_cancel or (lambda: False)
        self.rate_limiter = AdaptiveRateLimiter()
        self.pikepdf_lock = threading.Lock()

        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY environment variable is not set. Visual tagging agent will fail "
                "unless the key is passed explicitly."
            )

    def convert(
        self,
        pdf_path: str,
        page_range: Optional[Tuple[int, int]] = None,
        progress_callback: Optional[Any] = None
    ) -> GeminiAgentConversionResult:
        """Process the PDF, call Gemini for layout analysis, and build layout JSON."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Open with PyMuPDF to get pages
        doc = fitz.open(str(pdf_file))
        total_pages = len(doc)

        start_page = 1
        end_page = total_pages
        if page_range:
            start_page = max(1, page_range[0])
            end_page = min(total_pages, page_range[1])

        logger.info(f"Processing PDF '{pdf_file.name}' (pages {start_page} to {end_page})...")

        # Open with pikepdf for form field updates
        pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))

        # We will process each page, calling Gemini and getting the layout schema
        pages_to_process = list(range(start_page - 1, end_page))

        errors = []
        texts_out = []
        tables_out = []
        pictures_out = []
        form_fields_data = []  # Track form fields for post-processing
        all_page_text_dicts = {}  # Store text dicts for surrounding text extraction

        completed_count = 0
        total_to_process = len(pages_to_process)

        # Process in parallel using a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_page = {
                executor.submit(self._process_single_page, pdf_pikepdf, doc, page_num): page_num
                for page_num in pages_to_process
            }

            for future in concurrent.futures.as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    page_texts, page_tables, page_pictures, page_form_fields, page_text_dict = future.result()
                    texts_out.extend(page_texts)
                    tables_out.extend(page_tables)
                    pictures_out.extend(page_pictures)
                    form_fields_data.extend(page_form_fields)
                    all_page_text_dicts[page_num + 1] = page_text_dict  # Store for text extraction
                    completed_count += 1
                    logger.info(f"Page {page_num + 1} processed successfully.")
                    if progress_callback:
                        try:
                            progress_callback(completed_count, total_to_process)
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {e}")
                    errors.append(f"Page {page_num + 1}: {str(e)}")

        # Save the updated pikepdf document to the same location or to a temp location
        # Since we modified the form fields in pdf_pikepdf, save it back
        # Note: In-place save requires a temp file
        temp_pdf_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                temp_pdf_path = tmp.name
            pdf_pikepdf.save(temp_pdf_path)
            # Reopen to replace content, or we can just copy/overwrite the input path
            # (or return it so CLI can clean it up). Let's keep temp_pdf_path for CLI.
            self.temp_pdf_path = temp_pdf_path
        except Exception as e:
            logger.error(f"Failed to save modified PDF with updated form fields: {e}")
            errors.append(f"PDF Save Error: {str(e)}")
        finally:
            pdf_pikepdf.close()
            doc.close()

        status = "success"
        if errors:
            status = "partial_success" if len(errors) < (end_page - start_page + 1) else "failure"

        # Post-process form fields: deduplicate, split multi-page groups, enrich with text
        if form_fields_data:
            form_fields_data = self._deduplicate_form_field_names(form_fields_data)
            form_fields_data = self._split_multipage_radio_groups(form_fields_data)
            form_fields_data = self._enrich_form_fields_with_text(form_fields_data, all_page_text_dicts)

        # Construct Docling JSON structure
        docling_json = {
            "schema_version": "1.0.0",
            "texts": texts_out,
            "tables": tables_out,
            "pictures": pictures_out,
            "pages": {str(i + 1): {"page_no": i + 1} for i in pages_to_process},
            "form_fields": form_fields_data,  # Include processed form fields
        }

        document = GeminiAgentDocument(docling_json)
        return GeminiAgentConversionResult(document, status, errors, total_pages)

    def _process_single_page(
        self, pdf_pikepdf: pikepdf.Pdf, doc: fitz.Document, page_num: int
    ) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], Dict]:
        """Extract elements for a single page by calling Gemini."""
        if not self.api_key:
            raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY environment variable.")

        # Render page to PNG bytes and extract widgets under the lock
        with self.pikepdf_lock:
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            image_bytes = pix.tobytes("png")
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Extract Widget annotations (form fields)
            widgets, page_width, page_height = self._extract_widget_annotations(pdf_pikepdf, page_num)

        form_fields_context = ""
        if widgets:
            form_fields_context = "Here are the form field bounding boxes on this page [ymin, xmin, ymax, xmax]:\n"
            for w in widgets:
                form_fields_context += f"- Field {w['index']}: {w['bbox']} (current name: '{w['name']}', tooltip: '{w['tooltip']}')\n"

        prompt = f"""You are a professional PDF Accessibility (PDF/UA) tagging expert.
Your task is to analyze the visual layout of this PDF page and output a structured layout plan that complies with the PDF/UA Matterhorn Protocol.

First, examine the page image. Here is the context of the page:
- Page number: {page_num + 1}
- Page width: {page_width} points
- Page height: {page_height} points

{form_fields_context}

Please output a JSON object containing:
1. "elements": A list of layout elements on the page in logical reading order.
2. "form_fields": Association of the provided form fields with descriptive names and screen-reader tooltips.

Each item in "elements" must have:
- "type": "heading", "paragraph", "list_item", "table", "figure", "header", "footer", "formula"
- "bbox": [ymin, xmin, ymax, xmax] (normalized 0-1000 coordinates, where 0,0 is Top-Left and 1000,1000 is Bottom-Right of the page image)
- "text": The textual content of the element as seen on the page.
- "heading_level": 1, 2, 3, 4, 5, or 6 (only if type is "heading")
- "alt_text": A concise, descriptive alternative description (only if type is "figure" and it is informative).
- "is_decorative": true/false (only if type is "figure")
- "table_data": Grid data (only if type is "table") with structure:
  - "rows": List of rows, where each row is a list of cell objects:
    - "text": Cell content text
    - "row_span": Integer (default 1)
    - "col_span": Integer (default 1)
    - "is_header": true/false (whether it's a table header cell)

Rules for Matterhorn Protocol Compliance:
1. Headings Hierarchy: Heading levels must follow a strict descending order (e.g. H1 followed by H2, not H1 followed directly by H3). Visually determine if text is a section title or just styled text.
2. Headers/Footers: Running page headers, footers, page numbers, and decorative rules must be identified as "header" or "footer" or "figure" with "is_decorative": true, so they can be marked as artifacts.
3. Informative vs. Decorative Figures: If a figure conveys information (e.g. a chart, diagram, or illustration), provide a clear, concise alternative text description. If a figure is decorative (e.g. a background shape, a divider line), mark "is_decorative": true.
4. Tables: Identify cell grids, row spans, column spans, and distinguish table header cells (TH) from data cells (TD).
5. Reading Order: List all elements in a logical, single-column reading order.

Each item in "form_fields" must map one of the provided form fields:
- "bbox": [ymin, xmin, ymax, xmax] (must match one of the provided form field bboxes exactly)
- "name": A clean alphanumeric identifier in snake_case (e.g., "first_name", "date_of_birth") based on its visual label.
- "tooltip": A descriptive, helpful alternative description for screen readers (e.g., "Enter your first name", "Select your date of birth").

Response format:
Respond ONLY with a valid JSON object matching the schema. Do not wrap in markdown code blocks like ```json ... ```.
"""

        # Call Gemini API with retries
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        response_data = self._call_gemini_api_with_retry(payload)
        gemini_json_str = response_data["candidates"][0]["content"]["parts"][0]["text"]

        # Clean JSON markdown wrapper if any
        gemini_json_str = re.sub(r"^```json\s*", "", gemini_json_str.strip())
        gemini_json_str = re.sub(r"\s*```$", "", gemini_json_str)

        try:
            parsed_response = json.loads(gemini_json_str)
            if not isinstance(parsed_response, dict):
                parsed_response = {}
        except Exception as e:
            logger.error(f"Failed to parse JSON response from Gemini on page {page_num + 1}: {gemini_json_str}")
            raise e

        # Update the form fields in-place in pikepdf Page under the lock
        with self.pikepdf_lock:
            self._update_pdf_form_fields(pdf_pikepdf, page_num, widgets, parsed_response.get("form_fields", []))

        # Convert to Docling-compatible JSON elements
        page_texts = []
        page_tables = []
        page_pictures = []

        for elem in parsed_response.get("elements", []):
            if not isinstance(elem, dict):
                logger.warning(f"Skipping malformed layout element (not a dict): {elem}")
                continue
            el_type = elem.get("type")
            bbox_norm = elem.get("bbox")
            text = elem.get("text", "")

            if not bbox_norm or len(bbox_norm) != 4:
                continue

            # Convert 0-1000 top-left image coordinates back to absolute PDF bottomleft points
            ymin, xmin, ymax, xmax = bbox_norm
            l = (xmin / 1000.0) * page_width
            r = (xmax / 1000.0) * page_width
            b = (1.0 - ymax / 1000.0) * page_height
            t = (1.0 - ymin / 1000.0) * page_height

            prov = [{"page_no": page_num + 1, "bbox": {"l": l, "t": t, "r": r, "b": b, "coord_origin": "BOTTOMLEFT"}}]

            if el_type == "heading":
                level = elem.get("heading_level", 1)
                page_texts.append({"label": "section_header", "text": text, "prov": prov, "meta": {"level": level}})
            elif el_type == "paragraph":
                page_texts.append({"label": "text", "text": text, "prov": prov})
            elif el_type == "list_item":
                page_texts.append({"label": "list_item", "text": text, "prov": prov})
            elif el_type == "formula":
                latex = elem.get("latex", text)
                page_texts.append({"label": "formula", "text": latex, "prov": prov})
            elif el_type in ("header", "footer"):
                label = "page_header" if el_type == "header" else "page_footer"
                page_texts.append({"label": label, "text": text, "prov": prov})
            elif el_type == "figure":
                is_dec = elem.get("is_decorative", False)
                if is_dec:
                    # Skip decorative figures or mark them
                    continue
                alt = elem.get("alt_text", "")
                page_pictures.append({"prov": prov, "annotations": [{"kind": "description", "text": alt}]})
            elif el_type == "table":
                table_data = elem.get("table_data", {})
                if not isinstance(table_data, dict):
                    table_data = {}
                rows = []
                table_cells = []

                gemini_rows = table_data.get("rows", [])
                if not isinstance(gemini_rows, list):
                    gemini_rows = []
                num_rows = len(gemini_rows)
                num_cols = 0
                if num_rows > 0 and isinstance(gemini_rows[0], list):
                    num_cols = len(gemini_rows[0])

                # Fill grid placeholder
                grid = [[] for _ in range(num_rows)]
                for r_idx, crow in enumerate(gemini_rows):
                    if not isinstance(crow, list):
                        continue
                    for c_idx, cell in enumerate(crow):
                        if not isinstance(cell, dict):
                            continue
                        grid[r_idx].append(0)
                        cell_text = cell.get("text", "")
                        r_span = cell.get("row_span", 1)
                        c_span = cell.get("col_span", 1)
                        table_cells.append(
                            {
                                "start_row_offset_idx": r_idx,
                                "start_col_offset_idx": c_idx,
                                "row_span": r_span,
                                "col_span": c_span,
                                "text": cell_text,
                            }
                        )

                page_tables.append({"prov": prov, "data": {"grid": grid, "table_cells": table_cells}})

        # Extract page text for surrounding text lookup later
        with self.pikepdf_lock:
            page = doc.load_page(page_num)
            page_text_dict = page.get_text("dict")
        
        # Collect form field data with enrichment info for post-processing
        page_form_fields = []
        for field in parsed_response.get("form_fields", []):
            bbox = field.get("bbox")
            name = field.get("name")
            tooltip = field.get("tooltip")
            
            if bbox and name:
                # Find the widget to get field type
                matched_widget = self._find_closest_widget(bbox, widgets)
                field_type = "text"  # default
                if matched_widget:
                    field_type = self._get_field_type(pdf_pikepdf.pages[page_num].Annots[matched_widget["index"]])
                
                page_form_fields.append({
                    "page_no": page_num + 1,
                    "bbox": bbox,
                    "name": name,
                    "tooltip": tooltip,
                    "type": field_type,
                    "original_name": matched_widget.get("name", name) if matched_widget else name,
                })

        return page_texts, page_tables, page_pictures, page_form_fields, page_text_dict

    def _extract_widget_annotations(
        self, pdf_pikepdf: pikepdf.Pdf, page_num: int
    ) -> Tuple[List[Dict], float, float]:
        """Extract bboxes of Widget annotations in normalized scale."""
        widgets = []
        page = pdf_pikepdf.pages[page_num]

        mediabox = page.get("/MediaBox")
        if not mediabox:
            mediabox = page.get("/CropBox")

        if not mediabox:
            return widgets, 612.0, 792.0  # standard Letter default

        page_width = float(mediabox[2]) - float(mediabox[0])
        page_height = float(mediabox[3]) - float(mediabox[1])

        if "/Annots" in page:
            for i, annot in enumerate(page.Annots):
                if annot.get("/Subtype") == "/Widget":
                    rect = annot.get("/Rect")
                    if rect:
                        l, b, r, t = [float(x) for x in rect]

                        # Map to top-left 0-1000 image scale
                        xmin = max(0.0, min(1000.0, (l / page_width) * 1000.0))
                        xmax = max(0.0, min(1000.0, (r / page_width) * 1000.0))
                        ymin = max(0.0, min(1000.0, ((page_height - t) / page_height) * 1000.0))
                        ymax = max(0.0, min(1000.0, ((page_height - b) / page_height) * 1000.0))

                        widgets.append(
                            {
                                "index": i,
                                "bbox": [round(ymin, 1), round(xmin, 1), round(ymax, 1), round(xmax, 1)],
                                "name": str(annot.get("/T") or ""),
                                "tooltip": str(annot.get("/TU") or ""),
                            }
                        )
        return widgets, page_width, page_height

    def _update_pdf_form_fields(
        self, pdf_pikepdf: pikepdf.Pdf, page_num: int, widgets: List[Dict], gemini_fields: List[Dict]
    ):
        """Update form fields in the PDF's COS dictionaries."""
        if not gemini_fields or not widgets:
            return

        page = pdf_pikepdf.pages[page_num]

        for field in gemini_fields:
            bbox = field.get("bbox")
            name = field.get("name")
            tooltip = field.get("tooltip")

            if not bbox or not name or not tooltip:
                continue

            # Find matching widget index
            matched = self._find_closest_widget(bbox, widgets)
            if matched:
                annot = page.Annots[matched["index"]]

                # Set /TU (tooltip) on Widget annotation
                annot["/TU"] = pikepdf.String(tooltip)

                # Set /T (field name)
                if "/T" in annot:
                    annot["/T"] = pikepdf.String(name)
                elif "/Parent" in annot:
                    parent = annot["/Parent"]
                    parent["/T"] = pikepdf.String(name)
                    if "/TU" not in parent:
                        parent["/TU"] = pikepdf.String(tooltip)
                else:
                    annot["/T"] = pikepdf.String(name)

                logger.debug(f"Updated form field: name='{name}', tooltip='{tooltip}'")

    def _find_closest_widget(self, gemini_bbox: List[float], widgets: List[Dict], tolerance: float = 35.0) -> Optional[Dict]:
        """Find the closest widget to the Gemini-reported bbox by Euclidean distance of centers."""
        if not gemini_bbox or len(gemini_bbox) != 4:
            return None

        best_match = None
        min_dist = float("inf")

        y1, x1, y2, x2 = gemini_bbox
        cy1, cx1 = (y1 + y2) / 2.0, (x1 + x2) / 2.0

        for w in widgets:
            wy1, wx1, wy2, wx2 = w["bbox"]
            cy2, cx2 = (wy1 + wy2) / 2.0, (wx1 + wx2) / 2.0

            dist = ((cy1 - cy2) ** 2 + (cx1 - cx2) ** 2) ** 0.5
            if dist < min_dist and dist < tolerance:
                min_dist = dist
                best_match = w

        return best_match

    def _get_field_type(self, annot) -> str:
        """Extract field type from PDF annotation /FT entry."""
        try:
            ft = annot.get("/FT")
            if not ft:
                return "text"
            
            ft_str = str(ft).strip("/")
            if ft_str == "Tx":
                return "text"
            elif ft_str == "Btn":
                # Could be checkbox, radio, or button
                flags = annot.get("/Ff", 0)
                if isinstance(flags, (list, tuple)):
                    flags = flags[0] if flags else 0
                flags = int(flags) if flags else 0
                
                # Bit 15 (value 32768) indicates radio button
                if flags & 32768:
                    return "radio"
                else:
                    return "checkbox"
            elif ft_str == "Ch":
                return "dropdown"
            else:
                return "text"
        except Exception as e:
            logger.debug(f"Could not determine field type: {e}")
            return "text"

    def _extract_nearby_text(self, field_bbox: List[float], page_text_dict: Dict, radius: float = 50.0) -> List[str]:
        """Extract text near a form field from the page text layer."""
        if not field_bbox or len(field_bbox) != 4 or not page_text_dict:
            return []
        
        ymin, xmin, ymax, xmax = field_bbox
        # Scale from 0-1000 to approximate points (assuming ~612 width for letter)
        field_x1 = (xmin / 1000.0) * 612
        field_x2 = (xmax / 1000.0) * 612
        field_y1 = (ymin / 1000.0) * 792
        field_y2 = (ymax / 1000.0) * 792
        
        nearby_text = []
        blocks = page_text_dict.get("blocks", [])
        
        for block in blocks:
            if block.get("type") != 0:  # Skip non-text blocks
                continue
            
            block_bbox = block.get("bbox")
            if not block_bbox or len(block_bbox) < 4:
                continue
            
            b_x0, b_y0, b_x1, b_y1 = block_bbox[:4]
            
            # Check if block is near the field (within radius)
            # Calculate distance from field to block
            dx = max(field_x1 - b_x1, b_x0 - field_x2, 0)
            dy = max(field_y1 - b_y1, b_y0 - field_y2, 0)
            distance = (dx ** 2 + dy ** 2) ** 0.5
            
            if distance <= radius:
                # Extract text from this block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text and text not in nearby_text:
                            nearby_text.append(text)
        
        return nearby_text

    def extract_form_fields_only(self, pdf_path: str) -> Dict[str, Any]:
        """Extract only form fields from PDF without running Gemini tagging."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = None
        pdf_pikepdf = None
        try:
            doc = fitz.open(str(pdf_file))
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))
            
            # Store page count before any operations
            page_count = len(doc)
            
            form_fields_data = []
            all_page_text_dicts = {}
            
            # Extract form fields from all pages
            for page_num in range(page_count):
                widgets, _, _ = self._extract_widget_annotations(pdf_pikepdf, page_num)
                
                # Extract page text for context
                with self.pikepdf_lock:
                    page = doc.load_page(page_num)
                    page_text_dict = page.get_text("dict")
                    all_page_text_dicts[page_num] = page_text_dict
                
                # Collect form field data
                for widget in widgets:
                    field_type = "text"  # default
                    try:
                        if page_num < len(pdf_pikepdf.pages) and "/Annots" in pdf_pikepdf.pages[page_num]:
                            annots = pdf_pikepdf.pages[page_num].Annots
                            if widget["index"] < len(annots):
                                field_type = self._get_field_type(annots[widget["index"]])
                    except Exception as e:
                        logger.warning(f"Could not determine field type for widget {widget['index']}: {e}")
                    
                    form_fields_data.append({
                        "page_no": page_num + 1,
                        "bbox": widget["bbox"],
                        "name": widget["name"],
                        "original_name": widget["name"],
                        "widget_index": widget["index"],
                        "tooltip": widget["tooltip"],
                        "original_tooltip": widget["tooltip"],
                        "type": field_type,
                    })
            
            # Apply post-processing pipeline
            if form_fields_data:
                form_fields_data = self._deduplicate_form_field_names(form_fields_data)
                form_fields_data = self._split_multipage_radio_groups(form_fields_data)
                form_fields_data = self._enrich_form_fields_with_text(form_fields_data, all_page_text_dicts)
            
            return {
                "status": "success",
                "form_fields": form_fields_data,
                "summary": {
                    "total_fields": len(form_fields_data),
                    "page_count": page_count
                }
            }
        except Exception as e:
            logger.error(f"Error extracting form fields: {e}")
            raise
        finally:
            # Ensure documents are closed
            if doc:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Could not close fitz document: {e}")
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")

    def detect_missing_form_fields(
        self,
        pdf_path: str,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        """Visually detect likely missing form fields that are not PDF widgets yet."""
        if not self.api_key or self.api_key == "dummy":
            raise ValueError("Gemini API key is required to visually detect missing form fields.")

        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = None
        pdf_pikepdf = None
        try:
            doc = fitz.open(str(pdf_file))
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))
            page_count = len(doc)
            start_page = 0
            end_page = page_count - 1
            if page_range:
                start_page = max(0, page_range[0])
                end_page = min(page_count - 1, page_range[1])

            detected_fields = []
            for page_num in range(start_page, end_page + 1):
                with self.pikepdf_lock:
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=150)
                    image_bytes = pix.tobytes("png")
                    base64_image = base64.b64encode(image_bytes).decode("utf-8")
                    widgets, page_width, page_height = self._extract_widget_annotations(pdf_pikepdf, page_num)

                existing_context = "Existing PDF widgets to skip:\n"
                if widgets:
                    for widget in widgets:
                        existing_context += (
                            f"- {widget['bbox']} name='{widget['name']}' tooltip='{widget['tooltip']}'\n"
                        )
                else:
                    existing_context += "- None\n"

                prompt = f"""You are detecting missing interactive PDF form fields before accessibility tagging.
Inspect the page image and identify visible blanks, answer lines, light-blue answer boxes, checkboxes, radio choices, word-bank blanks, matching activities, or dropdown-like areas that should be real PDF form fields but are not already listed as existing widgets.

Page number: {page_num + 1}
Page width: {page_width} points
Page height: {page_height} points

{existing_context}

Use these form-field standards:
- Add only fields the learner/user is expected to fill in or choose.
- Skip decorative lines, page headers/footers, labels, instructions, and already-existing widgets.
- Text fields use type "text"; checkboxes use "checkbox"; radio choices use "radio".
- Word-bank questions should use type "combobox" at each blank, with "options" set to every visible word-bank option and "allow_custom_text": true.
- Matching/draw-a-line questions should use type "combobox" as a screen-reader workaround. Put the combobox beside each item in the shorter-named group, and set "options" to the item names from the opposite group. Use "allow_custom_text": true.
- Other select-from-a-list questions should use type "combobox" with visible choices in "options" and "allow_custom_text": true.
- Use clean snake_case names based on nearby visual labels. If a page repeats a generic blank, include the page/row context in the name.
- Tooltips should be short screen-reader instructions, such as "Enter the adjective", "Choose a word from the word bank or type your own", or "Choose the matching item or type your own".
- The bbox must tightly cover the interactive blank/box, normalized as [ymin, xmin, ymax, xmax] from 0 to 1000 with origin at the top-left of the page image.

Return ONLY JSON:
{{
  "form_fields": [
    {{
      "bbox": [ymin, xmin, ymax, xmax],
      "name": "snake_case_name",
      "tooltip": "screen reader instruction",
      "type": "text",
      "options": [],
      "allow_custom_text": false,
      "required": false
    }}
  ]
}}
"""

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64_image,
                                    }
                                },
                            ]
                        }
                    ],
                    "generationConfig": {"responseMimeType": "application/json"},
                }
                response_data = self._call_gemini_api_with_retry(payload)
                gemini_json_str = response_data["candidates"][0]["content"]["parts"][0]["text"]
                gemini_json_str = re.sub(r"^```json\s*", "", gemini_json_str.strip())
                gemini_json_str = re.sub(r"\s*```$", "", gemini_json_str)
                try:
                    parsed = json.loads(gemini_json_str)
                except Exception as e:
                    logger.warning(f"Could not parse missing-field detection on page {page_num + 1}: {e}")
                    parsed = {}

                for field in parsed.get("form_fields", []):
                    normalized = self._normalize_detected_form_field(field, page_num + 1)
                    if not normalized:
                        continue
                    if self._overlaps_existing_widget(normalized["bbox"], widgets):
                        continue
                    detected_fields.append(normalized)

            return {
                "status": "success",
                "form_fields": detected_fields,
                "summary": {
                    "detected_fields": len(detected_fields),
                    "page_count": page_count,
                    "pages_scanned": end_page - start_page + 1,
                },
            }
        finally:
            if doc:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Could not close fitz document: {e}")
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")

    def add_form_fields_to_pdf(self, pdf_path: str, form_fields: List[Dict], output_path: str) -> Dict[str, Any]:
        """Add detected form fields to a PDF as real widget annotations."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        pdf_pikepdf = None
        try:
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))
            self._ensure_acroform(pdf_pikepdf)

            added = 0
            skipped = 0
            for index, field in enumerate(form_fields):
                page_no = int(field.get("page_no", 1))
                if page_no < 1 or page_no > len(pdf_pikepdf.pages):
                    skipped += 1
                    continue
                page = pdf_pikepdf.pages[page_no - 1]
                _, page_width, page_height = self._extract_widget_annotations(pdf_pikepdf, page_no - 1)
                bbox = field.get("bbox")
                if not bbox or len(bbox) != 4:
                    skipped += 1
                    continue
                rect = self._normalized_bbox_to_pdf_rect(bbox, page_width, page_height)
                field_name = self._standardize_field_name(
                    field.get("new_name") or field.get("name") or f"field_{index + 1}"
                )
                if not field_name:
                    field_name = f"field_{index + 1}"
                tooltip = str(field.get("tooltip") or field_name.replace("_", " "))
                field_type = str(field.get("type") or "text").lower()

                annot = self._make_widget_annotation(pdf_pikepdf, field_type, rect, field_name, tooltip, field)
                if annot is None:
                    skipped += 1
                    continue
                indirect_annot = pdf_pikepdf.make_indirect(annot)
                if page.get("/Annots") is None:
                    page["/Annots"] = pikepdf.Array([])
                page.Annots.append(indirect_annot)
                pdf_pikepdf.Root.AcroForm.Fields.append(indirect_annot)
                added += 1

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            pdf_pikepdf.save(str(output_file))
            return {
                "status": "success",
                "output_path": str(output_file),
                "fields_added": added,
                "fields_skipped": skipped,
                "total_fields": len(form_fields),
            }
        finally:
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")

    def update_pdf_with_enriched_fields(self, pdf_path: str, enriched_fields: List[Dict], output_path: str) -> Dict[str, Any]:
        """Apply enriched form field names and tooltips to a PDF and save as new file."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = None
        pdf_pikepdf = None
        try:
            doc = fitz.open(str(pdf_file))
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))

            # Prefer widget identity when available. Duplicate PDF fields often share
            # page/name/type, so a flat key by name silently drops later duplicates.
            field_mapping = {}
            fallback_mapping = {}
            for field in enriched_fields:
                page_no = field.get("page_no", 1)
                orig_name = field.get("original_name") or field.get("name", "")
                field_type = field.get("type", "text")
                new_name = field.get("new_name", orig_name)
                tooltip = field.get("tooltip", field.get("original_tooltip", ""))
                widget_index = field.get("widget_index")
                bbox_key = self._normalized_bbox_key(field.get("bbox"))
                
                mapping = {
                    "new_name": new_name,
                    "tooltip": tooltip,
                    "original_name": orig_name
                }
                if widget_index is not None:
                    field_mapping[(page_no, int(widget_index), field_type)] = mapping
                if bbox_key is not None:
                    field_mapping[(page_no, bbox_key, field_type)] = mapping

                fallback_key = (page_no, orig_name, field_type)
                fallback_mapping.setdefault(fallback_key, []).append(mapping)

            # Process each page and update form fields
            updated_count = 0
            for page_num in range(len(doc)):
                widgets, _, _ = self._extract_widget_annotations(pdf_pikepdf, page_num)
                
                # Match widgets to enriched fields and update
                for widget in widgets:
                    widget_name = widget.get("name", "")
                    
                    # Determine field type from annotation
                    field_type = "text"
                    try:
                        if page_num < len(pdf_pikepdf.pages) and "/Annots" in pdf_pikepdf.pages[page_num]:
                            annots = pdf_pikepdf.pages[page_num].Annots
                            if widget["index"] < len(annots):
                                field_type = self._get_field_type(annots[widget["index"]])
                    except Exception as e:
                        logger.warning(f"Could not determine field type: {e}")
                    
                    # Look up in enriched fields
                    page_no = page_num + 1
                    widget_bbox_key = self._normalized_bbox_key(widget.get("bbox"))
                    mapping = field_mapping.get((page_no, widget.get("index"), field_type))
                    if mapping is None and widget_bbox_key is not None:
                        mapping = field_mapping.get((page_no, widget_bbox_key, field_type))
                    if mapping is None:
                        candidates = fallback_mapping.get((page_no, widget_name, field_type), [])
                        mapping = candidates.pop(0) if candidates else None

                    if mapping is not None:
                        new_name = mapping["new_name"]
                        tooltip = mapping["tooltip"]
                        
                        # Update the PDF annotation
                        try:
                            with self.pikepdf_lock:
                                page = pdf_pikepdf.pages[page_num]
                                if "/Annots" in page:
                                    annots = page.Annots
                                    if widget["index"] < len(annots):
                                        annot = annots[widget["index"]]
                                        
                                        # Update field name
                                        if "/T" in annot:
                                            annot["/T"] = pikepdf.String(new_name)
                                        elif "/Parent" in annot:
                                            parent = annot["/Parent"]
                                            parent["/T"] = pikepdf.String(new_name)
                                        else:
                                            annot["/T"] = pikepdf.String(new_name)
                                        
                                        # Update tooltip
                                        annot["/TU"] = pikepdf.String(tooltip)
                                        updated_count += 1
                        except Exception as e:
                            logger.warning(f"Could not update field {widget_name}: {e}")
            
            # Save modified PDF
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            pdf_pikepdf.save(str(output_file))
            
            logger.info(f"Updated {updated_count} form fields in PDF, saved to {output_file}")
            
            return {
                "status": "success",
                "output_path": str(output_file),
                "fields_updated": updated_count,
                "total_fields": len(enriched_fields)
            }
        except Exception as e:
            logger.error(f"Error updating PDF form fields: {e}")
            raise
        finally:
            if doc:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Could not close fitz document: {e}")
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")

    def _normalized_bbox_key(self, bbox: Any) -> Optional[Tuple[float, float, float, float]]:
        """Create a stable key for matching form widgets by extracted bbox."""
        if not bbox or len(bbox) != 4:
            return None
        try:
            return tuple(round(float(value), 1) for value in bbox)
        except (TypeError, ValueError):
            return None

    def _normalize_detected_form_field(self, field: Dict, page_no: int) -> Optional[Dict]:
        """Validate and normalize a visual form-field detection."""
        if not isinstance(field, dict):
            return None
        bbox = field.get("bbox")
        if not bbox or len(bbox) != 4:
            return None
        try:
            normalized_bbox = [max(0.0, min(1000.0, round(float(value), 1))) for value in bbox]
        except (TypeError, ValueError):
            return None
        if normalized_bbox[2] <= normalized_bbox[0] or normalized_bbox[3] <= normalized_bbox[1]:
            return None
        field_type = str(field.get("type") or "text").lower()
        if field_type == "dropdown":
            field_type = "combobox"
        if field_type not in {"text", "checkbox", "radio", "combobox"}:
            field_type = "text"
        name = self._standardize_field_name(field.get("name") or f"page_{page_no}_field")
        tooltip = str(field.get("tooltip") or name.replace("_", " ")).strip()
        return {
            "page_no": page_no,
            "bbox": normalized_bbox,
            "name": name,
            "new_name": name,
            "original_name": "",
            "tooltip": tooltip,
            "original_tooltip": "",
            "type": field_type,
            "options": [str(option) for option in field.get("options", [])] if isinstance(field.get("options"), list) else [],
            "allow_custom_text": bool(field.get("allow_custom_text", field_type == "combobox")),
            "required": bool(field.get("required", False)),
        }

    def _overlaps_existing_widget(self, bbox: List[float], widgets: List[Dict], threshold: float = 0.35) -> bool:
        """Return True when a detected bbox overlaps an existing widget enough to skip it."""
        for widget in widgets:
            existing = widget.get("bbox")
            if existing and self._bbox_iou(bbox, existing) >= threshold:
                return True
        return False

    def _bbox_iou(self, a: List[float], b: List[float]) -> float:
        """Intersection-over-union for normalized [ymin, xmin, ymax, xmax] boxes."""
        ay1, ax1, ay2, ax2 = [float(v) for v in a]
        by1, bx1, by2, bx2 = [float(v) for v in b]
        inter_y1 = max(ay1, by1)
        inter_x1 = max(ax1, bx1)
        inter_y2 = min(ay2, by2)
        inter_x2 = min(ax2, bx2)
        inter_area = max(0.0, inter_y2 - inter_y1) * max(0.0, inter_x2 - inter_x1)
        if inter_area <= 0:
            return 0.0
        area_a = max(0.0, ay2 - ay1) * max(0.0, ax2 - ax1)
        area_b = max(0.0, by2 - by1) * max(0.0, bx2 - bx1)
        union = area_a + area_b - inter_area
        return inter_area / union if union > 0 else 0.0

    def _normalized_bbox_to_pdf_rect(self, bbox: List[float], page_width: float, page_height: float) -> pikepdf.Array:
        """Convert normalized top-left bbox to PDF bottom-left rect."""
        ymin, xmin, ymax, xmax = [float(value) for value in bbox]
        left = (xmin / 1000.0) * page_width
        right = (xmax / 1000.0) * page_width
        top = (1.0 - ymin / 1000.0) * page_height
        bottom = (1.0 - ymax / 1000.0) * page_height
        return pikepdf.Array([left, bottom, right, top])

    def _ensure_acroform(self, pdf_pikepdf: pikepdf.Pdf) -> None:
        """Ensure the PDF catalog has an AcroForm fields array."""
        if pdf_pikepdf.Root.get("/AcroForm") is None:
            pdf_pikepdf.Root["/AcroForm"] = pdf_pikepdf.make_indirect(
                pikepdf.Dictionary(Fields=pikepdf.Array([]))
            )
        acroform = pdf_pikepdf.Root.AcroForm
        if acroform.get("/Fields") is None:
            acroform["/Fields"] = pikepdf.Array([])
        if acroform.get("/DA") is None:
            acroform["/DA"] = pikepdf.String("/Helv 10 Tf 0 g")
        acroform["/NeedAppearances"] = True

    def _make_widget_annotation(
        self,
        pdf_pikepdf: pikepdf.Pdf,
        field_type: str,
        rect: pikepdf.Array,
        field_name: str,
        tooltip: str,
        field: Dict,
    ) -> Optional[pikepdf.Dictionary]:
        """Create a basic widget annotation for supported field types."""
        annot = pikepdf.Dictionary(
            Type=pikepdf.Name("/Annot"),
            Subtype=pikepdf.Name("/Widget"),
            Rect=rect,
            T=pikepdf.String(field_name),
            TU=pikepdf.String(tooltip),
            F=4,
            DA=pikepdf.String("/Helv 10 Tf 0 g"),
            MK=pikepdf.Dictionary(BC=pikepdf.Array([0, 0, 0]), BG=pikepdf.Array([1, 1, 1])),
            BS=pikepdf.Dictionary(W=1, S=pikepdf.Name("/S")),
        )
        if bool(field.get("required", False)):
            annot["/Ff"] = 2

        if field_type == "text":
            annot["/FT"] = pikepdf.Name("/Tx")
            annot["/V"] = pikepdf.String("")
            return annot
        if field_type == "checkbox":
            annot["/FT"] = pikepdf.Name("/Btn")
            annot["/V"] = pikepdf.Name("/Off")
            annot["/AS"] = pikepdf.Name("/Off")
            return annot
        if field_type == "radio":
            annot["/FT"] = pikepdf.Name("/Btn")
            annot["/Ff"] = int(annot.get("/Ff", 0)) | 32768
            annot["/V"] = pikepdf.Name("/Off")
            annot["/AS"] = pikepdf.Name("/Off")
            return annot
        if field_type in {"dropdown", "combobox"}:
            annot["/FT"] = pikepdf.Name("/Ch")
            options = field.get("options") if isinstance(field.get("options"), list) else []
            annot["/Opt"] = pikepdf.Array([pikepdf.String(str(option)) for option in options])
            flags = int(annot.get("/Ff", 0)) | 131072
            if bool(field.get("allow_custom_text", True)):
                flags |= 262144
            annot["/Ff"] = flags
            return annot
        return None

    def _standardize_field_name(self, value: Any) -> str:
        """Apply the app's form-field naming convention: lowercase snake_case."""
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        if text and text[0].isdigit():
            text = f"field_{text}"
        return text[:64].strip("_")

    def _deduplicate_form_field_names(self, form_fields_data: List[Dict]) -> List[Dict]:
        """Rename every field to a PDF-safe unique name."""
        name_counts = {}  # Track occurrences by sanitized base name
        deduplicated = []
        
        for field in form_fields_data:
            name = field.get("name", "field")
            page_no = field.get("page_no", 1)
            field.setdefault("original_name", name)
            field.setdefault("original_tooltip", field.get("tooltip", ""))
            
            base_name = self._standardize_field_name(field.get("new_name") or name) or f"field_page_{page_no}"
            count = name_counts.get(base_name, 0) + 1
            name_counts[base_name] = count
            new_name = base_name if count == 1 else self._append_field_name_suffix(base_name, count)
            
            field["new_name"] = new_name
            deduplicated.append(field)
            logger.debug(f"Field '{name}' on page {page_no} -> '{new_name}'")
        
        return deduplicated

    def _append_field_name_suffix(self, base_name: str, count: int) -> str:
        """Append a numeric suffix while preserving the field-name length cap."""
        suffix = f"_{count}"
        return f"{base_name[:64 - len(suffix)].rstrip('_')}{suffix}"

    def _split_multipage_radio_groups(self, form_fields_data: List[Dict]) -> List[Dict]:
        """Split radio button groups that span multiple pages."""
        # Radio buttons with the same name on different pages should be separated
        split_fields = []
        radio_groups = {}  # Track radio groups by name
        
        for field in form_fields_data:
            if field.get("type") != "radio":
                split_fields.append(field)
                continue
            
            name = self._radio_group_key(field)
            page_no = field.get("page_no", 1)
            
            if name not in radio_groups:
                radio_groups[name] = {}
            
            if page_no not in radio_groups[name]:
                radio_groups[name][page_no] = []
            
            radio_groups[name][page_no].append(field)
        
        # Now process radio buttons, splitting multi-page groups
        for field in form_fields_data:
            if field.get("type") != "radio":
                continue
            
            name = self._radio_group_key(field)
            page_no = field.get("page_no", 1)
            pages_for_group = list(radio_groups[name].keys())
            
            if len(pages_for_group) > 1:
                # This radio button group spans multiple pages - rename it
                base_name = self._standardize_field_name(name) or "radio"
                new_name = self._append_field_name_suffix(f"{base_name}_page", page_no)
                field["new_name"] = new_name
                field["multipage_radio_split"] = True
                field["multipage_radio_group"] = base_name
                logger.debug(f"Radio group '{name}' split across pages. Page {page_no} variant: '{new_name}'")
            
            split_fields.append(field)
        
        return split_fields

    def _radio_group_key(self, field: Dict) -> str:
        """Return the logical radio group name before per-widget renaming."""
        return str(field.get("original_name") or field.get("name") or field.get("new_name") or "radio")

    def _count_multipage_radio_split_groups(self, form_fields_data: List[Dict]) -> int:
        """Count logical radio groups split across pages, not individual widgets."""
        groups = {
            field.get("multipage_radio_group")
            for field in form_fields_data
            if field.get("multipage_radio_split") and field.get("multipage_radio_group")
        }
        return len(groups)

    def _enrich_form_fields_with_text(self, form_fields_data: List[Dict], all_page_text_dicts: Dict) -> List[Dict]:
        """Enrich form fields with surrounding text for tooltips and radio button options."""
        for field in form_fields_data:
            field.setdefault("original_tooltip", field.get("tooltip", ""))
            page_no = field.get("page_no", 1)
            page_text_dict = all_page_text_dicts.get(page_no)
            
            if not page_text_dict:
                continue
            
            bbox = field.get("bbox")
            nearby_text = self._extract_nearby_text(bbox, page_text_dict, radius=60.0)
            
            # Store nearby text in field
            field["nearby_text"] = nearby_text
            
            # If tooltip is generic, try to enhance it with nearby text
            tooltip = field.get("tooltip", "")
            field_type = field.get("type", "text")
            
            # For radio buttons, nearby text could be the options
            if field_type == "radio" and nearby_text:
                field["inferred_options"] = nearby_text
                if not tooltip or tooltip == "Select an option":
                    field["tooltip"] = f"Radio button group. Options: {', '.join(nearby_text[:3])}"
            
            # For checkboxes and dropdowns, enhance tooltip if weak
            elif field_type in ("checkbox", "dropdown") and nearby_text and (not tooltip or len(tooltip) < 10):
                field["tooltip"] = f"{tooltip}. Label: {nearby_text[0]}" if tooltip else nearby_text[0]
            
            # For text fields, use nearby label as hint
            elif field_type == "text" and nearby_text and (not tooltip or len(tooltip) < 10):
                field["tooltip"] = f"{tooltip}. Associated text: {nearby_text[0]}" if tooltip else nearby_text[0]
        
        return form_fields_data

    def extract_tags_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Extract all tags from PDF structure tree with content context."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = None
        pdf_pikepdf = None
        try:
            doc = fitz.open(str(pdf_file))
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))
            
            page_count = len(doc)
            all_tags = []
            tag_frequency = {}
            
            # Extract structure tree tags
            if pdf_pikepdf.Root.get("/StructTreeRoot"):
                struct_root = pdf_pikepdf.Root["/StructTreeRoot"]
                role_map_targets = self._get_role_map_targets(struct_root)
                self._extract_struct_tree_tags(
                    struct_root, all_tags, tag_frequency, role_map_targets
                )
                self._extract_role_map_tags(struct_root, all_tags, tag_frequency)
            
            # If no structure tree, extract text content for analysis
            if not all_tags:
                for page_num in range(page_count):
                    page = doc.load_page(page_num)
                    text_dict = page.get_text("dict")
                    self._extract_tags_from_content(text_dict, page_num, all_tags, tag_frequency)
            
            return {
                "status": "success",
                "tags": all_tags,
                "tag_frequency": tag_frequency,
                "available_pdf_ua_tags": self._available_pdf_ua_tags(),
                "summary": {
                    "total_tags": len(all_tags),
                    "unique_tag_types": len(tag_frequency),
                    "page_count": page_count
                }
            }
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            raise
        finally:
            if doc:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Could not close fitz document: {e}")
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")

    def suggest_semantic_tags(self, tags_with_content: List[Dict]) -> Dict[str, Any]:
        """Analyze tags and suggest semantic mappings based on content."""
        pdf_ua_tags = self._available_pdf_ua_tags()
        
        suggestions = {}
        for tag_info in tags_with_content:
            old_tag = tag_info.get("tag_name", "")
            content = tag_info.get("content", "").strip()[:100]  # First 100 chars
            
            if not old_tag or old_tag in pdf_ua_tags:
                continue  # Already semantic
            
            # Simple content-based heuristics
            suggested_tag = "P"  # Default to paragraph
            
            if content:
                content_lower = content.lower()
                
                # Detect headings
                if any(word in content_lower for word in ["chapter", "section", "title"]):
                    suggested_tag = "H1"
                # Detect lists
                elif content_lower.startswith(("•", "-", "◦", "▪", "·")) or content.startswith(("1.", "2.", "•")):
                    suggested_tag = "LI"
                # Detect tables
                elif "\t" in content or "|" in content:
                    suggested_tag = "Table"
                # Detect images/figures
                elif any(word in content_lower for word in ["figure", "image", "photo", "picture", "graphic"]):
                    suggested_tag = "Figure"
                # Detect formulas
                elif any(char in content for char in ["∑", "∫", "∂", "√", "×", "÷", "≤", "≥"]):
                    suggested_tag = "Formula"
                # Detect form fields
                elif any(word in content_lower for word in ["enter", "input", "select", "check", "yes", "no"]):
                    suggested_tag = "P"  # Could be text field indicator
            
            suggestions[old_tag] = {
                "suggested_tag": suggested_tag,
                "confidence": 0.7,  # Could be enhanced with Gemini
                "content_sample": content,
                "pdf_ua_semantic_tags": pdf_ua_tags
            }
        
        return {
            "status": "success",
            "suggestions": suggestions,
            "available_pdf_ua_tags": pdf_ua_tags,
            "total_old_tags": len(suggestions)
        }

    def apply_semantic_tags(
        self,
        pdf_path: str,
        tag_mappings: Dict[str, str],
        output_path: str,
        restructure_document: bool = False,
        tag_untagged_form_fields: bool = True,
    ) -> Dict[str, Any]:
        """Apply semantic tag mappings to PDF and save as new file."""
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        pdf_pikepdf = None
        self._pruned_artifact_objgens = set()
        try:
            pdf_pikepdf = pikepdf.Pdf.open(str(pdf_file))
            
            applied_count = 0
            normalized_mappings = self._normalize_tag_mappings(tag_mappings)
            rejected_mappings = {}
            
            # Apply tag mappings to structure tree
            if pdf_pikepdf.Root.get("/StructTreeRoot"):
                struct_root = pdf_pikepdf.Root["/StructTreeRoot"]
                normalized_mappings = self._expand_tag_mappings_with_role_map(
                    struct_root, normalized_mappings
                )
                normalized_mappings, rejected_mappings = self._filter_semantic_tag_mappings_for_structure(
                    struct_root, normalized_mappings
                )
                applied_count = self._apply_tag_mappings(struct_root, normalized_mappings)
                applied_count += self._apply_role_map_mappings(struct_root, normalized_mappings)
                self._remove_pruned_artifacts_from_parent_tree(
                    struct_root, self._pruned_artifact_objgens
                )

            # Acrobat's Content panel reads marked-content tags from page streams.
            content_tag_count = self._apply_marked_content_tag_mappings(
                pdf_pikepdf, normalized_mappings
            )
            applied_count += content_tag_count

            structure_result = {
                "document_structured": False,
                "page_containers": 0,
                "form_fields_tagged": 0,
            }
            if restructure_document:
                structure_result = self._structure_document_tags(
                    pdf_pikepdf,
                    tag_untagged_form_fields=tag_untagged_form_fields,
                )
            
            # Save the modified PDF
            output_file = Path(output_path).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)
            pdf_pikepdf.save(str(output_file))
            
            logger.info(f"Applied {applied_count} tag mappings. Saved to: {output_file}")
            
            return {
                "status": "success",
                "applied_count": applied_count,
                "content_tag_count": content_tag_count,
                "artifact_count": self._count_mapped_values(tag_mappings, "Artifact"),
                "rejected_mappings": rejected_mappings,
                **structure_result,
                "output_path": str(output_file)
            }
        except Exception as e:
            logger.error(f"Error applying semantic tags: {e}")
            raise
        finally:
            if pdf_pikepdf:
                try:
                    pdf_pikepdf.close()
                except Exception as e:
                    logger.warning(f"Could not close pikepdf document: {e}")
            self._pruned_artifact_objgens = set()

    def _extract_struct_tree_tags(
        self,
        struct_elem,
        tags_list: List[Dict],
        tag_freq: Dict,
        role_map_targets: Optional[Dict[str, str]] = None,
    ) -> None:
        """Recursively extract tags from PDF structure tree."""
        try:
            if not hasattr(struct_elem, "get"):
                return

            tag_name = struct_elem.get("/S")
            if tag_name:
                tag_name_str = self._normalize_tag_name(tag_name)
                content = self._extract_struct_tag_content(struct_elem)
                
                # Track frequency
                if tag_name_str not in tag_freq:
                    tag_freq[tag_name_str] = 0
                tag_freq[tag_name_str] += 1
                
                # Add to list
                screen_reader_tag = self._screen_reader_tag_for_tag(
                    tag_name_str, role_map_targets or {}
                )
                tags_list.append({
                    "tag_name": tag_name_str,
                    "content": content[:100],  # Limit to 100 chars
                    "has_struct_children": bool(self._iter_struct_children(struct_elem)),
                    "child_tags": [
                        self._normalize_tag_name(child.get("/S"))
                        for child in self._iter_struct_children(struct_elem)
                        if hasattr(child, "get") and child.get("/S") is not None
                    ],
                    "screen_reader_tag": screen_reader_tag,
                    "screen_reader_description": self._available_pdf_ua_tags().get(
                        screen_reader_tag, "Custom structure type"
                    ),
                    "screen_reader_kind": self._screen_reader_kind(screen_reader_tag),
                    "allowed_targets": self._allowed_semantic_targets_for_struct_elem(
                        struct_elem, role_map_targets or {}
                    ),
                    "page_no": 1  # Would need to map from struct tree to pages
                })

            for child in self._iter_struct_children(struct_elem):
                self._extract_struct_tree_tags(child, tags_list, tag_freq, role_map_targets)
        except Exception as e:
            logger.debug(f"Could not extract struct tree tag: {e}")

    def _extract_struct_tag_content(self, struct_elem: Any) -> str:
        """Extract a small title/sample from a structure element for the editor preview."""
        if not hasattr(struct_elem, "get"):
            return ""

        title = struct_elem.get("/T")
        if title:
            return str(title)[:100]

        child_titles = []
        for child in self._iter_struct_children(struct_elem)[:3]:
            child_title = child.get("/T") if hasattr(child, "get") else None
            if child_title:
                child_titles.append(str(child_title))
        return " ".join(child_titles)[:100]

    def _extract_tags_from_content(self, text_dict: Dict, page_num: int, tags_list: List[Dict], tag_freq: Dict) -> None:
        """Extract pseudo-tags from page content (blocks/lines)."""
        if "blocks" not in text_dict:
            return
        
        for block in text_dict["blocks"]:
            block_type = block.get("type", "unknown")
            content = ""
            
            if block_type == 1:  # Image
                content = "(Image)"
                tag_name = "Image"
            elif "lines" in block:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        content += span.get("text", "") + " "
                
                content = content[:100].strip()
                
                # Heuristic: detect heading by font size
                if block["lines"]:
                    first_span = block["lines"][0]["spans"][0]
                    font_size = first_span.get("size", 12)
                    if font_size > 14:
                        tag_name = "H1"
                    elif font_size > 12:
                        tag_name = "H2"
                    else:
                        tag_name = "P"
                else:
                    tag_name = "P"
            else:
                continue
            
            if tag_name not in tag_freq:
                tag_freq[tag_name] = 0
            tag_freq[tag_name] += 1
            
            tags_list.append({
                "tag_name": tag_name,
                "content": content,
                "page_no": page_num + 1
            })

    def _extract_role_map_tags(self, struct_root, tags_list: List[Dict], tag_freq: Dict) -> None:
        """Extract custom tag names from StructTreeRoot RoleMap."""
        try:
            role_map = struct_root.get("/RoleMap") if hasattr(struct_root, "get") else None
            if role_map is None or not hasattr(role_map, "items"):
                return

            for raw_key, raw_value in role_map.items():
                tag_name = self._normalize_tag_name(raw_key)
                mapped_to = self._normalize_tag_name(raw_value)
                if not tag_name:
                    continue

                tag_freq[tag_name] = tag_freq.get(tag_name, 0) + 1
                tags_list.append({
                    "tag_name": tag_name,
                    "content": f"RoleMap -> {mapped_to}" if mapped_to else "RoleMap",
                    "has_struct_children": False,
                    "child_tags": [],
                    "screen_reader_tag": mapped_to or tag_name,
                    "screen_reader_description": self._available_pdf_ua_tags().get(
                        mapped_to or tag_name, "Custom structure type"
                    ),
                    "screen_reader_kind": self._screen_reader_kind(mapped_to or tag_name),
                    "allowed_targets": self._allowed_semantic_targets_for_profile(
                        {
                            "tag_name": tag_name,
                            "has_struct_children": False,
                            "child_tags": [],
                            "screen_reader_tag": mapped_to or tag_name,
                        }
                    ),
                    "page_no": 1,
                })
        except Exception as e:
            logger.debug(f"Could not extract role map tags: {e}")

    def _apply_tag_mappings(self, struct_elem, mappings: Dict[str, str]) -> int:
        """Recursively apply tag mappings to structure tree."""
        applied = 0
        try:
            tag_value = struct_elem.get("/S") if hasattr(struct_elem, "get") else None
            if tag_value is not None:
                old_tag = self._normalize_tag_name(tag_value)
                if old_tag in mappings:
                    new_tag = mappings[old_tag]
                    if new_tag != "Artifact":
                        struct_elem["/S"] = self._to_pdf_name(new_tag)
                    applied += 1
                    logger.debug(f"Applied mapping: {old_tag} -> {new_tag}")
            
            applied += self._apply_child_tag_mappings(struct_elem, mappings)
        except Exception as e:
            logger.debug(f"Could not apply tag mapping: {e}")
        
        return applied

    def _apply_child_tag_mappings(self, struct_elem: Any, mappings: Dict[str, str]) -> int:
        """Apply mappings below an element and prune children mapped to artifacts."""
        if not hasattr(struct_elem, "get") or struct_elem.get("/K") is None:
            return 0

        k_value = struct_elem.get("/K")
        if self._is_struct_element_like(k_value):
            old_tag = self._normalize_tag_name(k_value.get("/S"))
            if mappings.get(old_tag) == "Artifact":
                self._remember_pruned_artifact(k_value)
                del struct_elem["/K"]
                return 1
            return self._apply_tag_mappings(k_value, mappings)

        if not self._is_struct_children_collection(k_value):
            return 0

        applied = 0
        kept_children = []
        changed = False
        try:
            for child in k_value:
                if not hasattr(child, "get"):
                    kept_children.append(child)
                    continue
                old_tag = self._normalize_tag_name(child.get("/S"))
                if mappings.get(old_tag) == "Artifact":
                    self._remember_pruned_artifact(child)
                    applied += 1
                    changed = True
                    continue
                applied += self._apply_tag_mappings(child, mappings)
                kept_children.append(child)
        except TypeError:
            return applied

        if changed and kept_children:
            struct_elem["/K"] = pikepdf.Array(kept_children)
        elif changed:
            del struct_elem["/K"]
        return applied

    def _remember_pruned_artifact(self, struct_elem: Any) -> None:
        """Track removed structure elements so ParentTree references can be nulled."""
        objgen = getattr(struct_elem, "objgen", None)
        if objgen is not None:
            self._pruned_artifact_objgens.add(objgen)

    def _remove_pruned_artifacts_from_parent_tree(
        self, struct_root: Any, pruned_objgens: set
    ) -> int:
        """Null ParentTree entries that point to pruned artifact structure elements."""
        if not pruned_objgens or not hasattr(struct_root, "get"):
            return 0
        parent_tree = struct_root.get("/ParentTree")
        return self._clean_parent_tree_node(parent_tree, pruned_objgens)

    def _clean_parent_tree_node(self, node: Any, pruned_objgens: set) -> int:
        if not hasattr(node, "get"):
            return 0
        cleaned = 0
        nums = node.get("/Nums")
        if self._is_struct_children_collection(nums):
            try:
                for idx in range(1, len(nums), 2):
                    cleaned += self._clean_parent_tree_value(nums, idx, pruned_objgens)
            except TypeError:
                pass
        kids = node.get("/Kids")
        if self._is_struct_children_collection(kids):
            try:
                for kid in kids:
                    cleaned += self._clean_parent_tree_node(kid, pruned_objgens)
            except TypeError:
                pass
        return cleaned

    def _clean_parent_tree_value(self, nums: Any, idx: int, pruned_objgens: set) -> int:
        value = nums[idx]
        if self._is_pruned_struct_ref(value, pruned_objgens):
            nums[idx] = None
            return 1
        if self._is_struct_children_collection(value):
            cleaned = 0
            try:
                for child_idx, child in enumerate(value):
                    if self._is_pruned_struct_ref(child, pruned_objgens):
                        value[child_idx] = None
                        cleaned += 1
            except TypeError:
                pass
            return cleaned
        return 0

    def _is_pruned_struct_ref(self, value: Any, pruned_objgens: set) -> bool:
        objgen = getattr(value, "objgen", None)
        return objgen is not None and objgen in pruned_objgens

    def _apply_role_map_mappings(self, struct_root, mappings: Dict[str, str]) -> int:
        """Apply tag mappings into StructTreeRoot RoleMap entries."""
        applied = 0
        try:
            role_map = struct_root.get("/RoleMap") if hasattr(struct_root, "get") else None
            if role_map is None or not hasattr(role_map, "keys"):
                return 0

            for raw_key in list(role_map.keys()):
                old_tag = self._normalize_tag_name(raw_key)
                mapped_tag = self._normalize_tag_name(role_map[raw_key])
                if old_tag in mappings:
                    if mappings[old_tag] == "Artifact":
                        del role_map[raw_key]
                    else:
                        role_map[raw_key] = self._to_pdf_name(mappings[old_tag])
                    applied += 1
                    logger.debug(f"Updated RoleMap: {old_tag} -> {mappings[old_tag]}")
                elif mapped_tag in mappings:
                    role_map[raw_key] = self._to_pdf_name(mappings[mapped_tag])
                    applied += 1
                    logger.debug(
                        f"Updated RoleMap value: {old_tag} -> {mappings[mapped_tag]}"
                    )
        except Exception as e:
            logger.debug(f"Could not apply role map mappings: {e}")

        return applied

    def _expand_tag_mappings_with_role_map(
        self, struct_root: Any, mappings: Dict[str, str]
    ) -> Dict[str, str]:
        """Map custom RoleMap keys when their resolved standard tag is mapped."""
        expanded = dict(mappings)
        try:
            role_map = struct_root.get("/RoleMap") if hasattr(struct_root, "get") else None
            if role_map is None or not hasattr(role_map, "items"):
                return expanded
            for raw_key, raw_value in role_map.items():
                custom_tag = self._normalize_tag_name(raw_key)
                resolved_tag = self._normalize_tag_name(raw_value)
                if custom_tag and resolved_tag in mappings and custom_tag not in expanded:
                    expanded[custom_tag] = mappings[resolved_tag]
        except Exception as e:
            logger.debug(f"Could not expand tag mappings from role map: {e}")
        return expanded

    def _apply_marked_content_tag_mappings(
        self, pdf_pikepdf: pikepdf.Pdf, mappings: Dict[str, str]
    ) -> int:
        """Apply tag mappings to page marked-content tags used by BMC/BDC operators."""
        applied = 0
        for page in pdf_pikepdf.pages:
            applied += self._apply_marked_content_tag_mappings_to_container(
                page.get("/Contents"), mappings
            )
            resources = page.get("/Resources")
            applied += self._apply_xobject_marked_content_tag_mappings(resources, mappings)
        return applied

    def _structure_document_tags(
        self,
        pdf_pikepdf: pikepdf.Pdf,
        tag_untagged_form_fields: bool = True,
    ) -> Dict[str, Any]:
        """Wrap existing tags in /Document and page-level /Part containers."""
        struct_root = pdf_pikepdf.Root.get("/StructTreeRoot")
        if struct_root is None:
            struct_root = pdf_pikepdf.make_indirect(
                pikepdf.Dictionary(Type=pikepdf.Name("/StructTreeRoot"))
            )
            pdf_pikepdf.Root["/StructTreeRoot"] = struct_root

        page_refs = [page.obj for page in pdf_pikepdf.pages]
        page_index = {
            getattr(page_ref, "objgen", None): idx
            for idx, page_ref in enumerate(page_refs)
        }
        existing_kids = self._as_struct_kids(struct_root.get("/K"))
        if len(existing_kids) == 1 and self._normalize_tag_name(existing_kids[0].get("/S")) == "Document":
            existing_kids = self._as_struct_kids(existing_kids[0].get("/K"))
        existing_kids = self._flatten_document_grouping_kids(existing_kids, page_index)

        document_elem = pdf_pikepdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name("/StructElem"),
                S=pikepdf.Name("/Document"),
                P=struct_root,
            )
        )
        page_parts = []
        for idx, page_ref in enumerate(page_refs):
            part = pdf_pikepdf.make_indirect(
                pikepdf.Dictionary(
                    Type=pikepdf.Name("/StructElem"),
                    S=pikepdf.Name("/Part"),
                    T=pikepdf.String(f"Page {idx + 1}"),
                    Pg=page_ref,
                    P=document_elem,
                    K=pikepdf.Array([]),
                )
            )
            page_parts.append(part)

        for child in existing_kids:
            if not hasattr(child, "get"):
                continue
            idx = self._infer_struct_elem_page_index(child, page_index)
            if idx is None or idx < 0 or idx >= len(page_parts):
                idx = 0
            child["/P"] = page_parts[idx]
            page_parts[idx].K.append(child)

        tagged_forms = 0
        if tag_untagged_form_fields:
            tagged_forms = self._tag_untagged_form_fields(pdf_pikepdf, page_parts)

        document_elem["/K"] = pikepdf.Array(page_parts)
        struct_root["/K"] = document_elem
        return {
            "document_structured": True,
            "page_containers": len(page_parts),
            "form_fields_tagged": tagged_forms,
        }

    def _tag_untagged_form_fields(self, pdf_pikepdf: pikepdf.Pdf, page_parts: List[Any]) -> int:
        """Add /Form OBJR structure elements for widget annotations not already in the tree."""
        tagged_annots = self._collect_tagged_annotation_objgens(pdf_pikepdf.Root.get("/StructTreeRoot"))
        added = 0
        for page_idx, page in enumerate(pdf_pikepdf.pages):
            annots = page.get("/Annots")
            if annots is None or page_idx >= len(page_parts):
                continue
            for annot in annots:
                if not hasattr(annot, "get") or annot.get("/Subtype") != "/Widget":
                    continue
                objgen = getattr(annot, "objgen", None)
                if objgen is not None and objgen in tagged_annots:
                    continue
                form_elem = pdf_pikepdf.make_indirect(
                    pikepdf.Dictionary(
                        Type=pikepdf.Name("/StructElem"),
                        S=pikepdf.Name("/Form"),
                        Pg=page.obj,
                        P=page_parts[page_idx],
                        K=pikepdf.Dictionary(
                            Type=pikepdf.Name("/OBJR"),
                            Obj=annot,
                            Pg=page.obj,
                        ),
                    )
                )
                page_parts[page_idx].K.append(form_elem)
                added += 1
        return added

    def _collect_tagged_annotation_objgens(self, obj: Any) -> set:
        """Collect annotation object ids already referenced by OBJR structure entries."""
        tagged = set()
        if obj is None:
            return tagged
        if hasattr(obj, "get"):
            if obj.get("/Type") == "/OBJR" and obj.get("/Obj") is not None:
                objgen = getattr(obj.get("/Obj"), "objgen", None)
                if objgen is not None:
                    tagged.add(objgen)
            for key in ("/K",):
                tagged.update(self._collect_tagged_annotation_objgens(obj.get(key)))
            return tagged
        if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
            try:
                for item in obj:
                    tagged.update(self._collect_tagged_annotation_objgens(item))
            except TypeError:
                pass
        return tagged

    def _as_struct_kids(self, value: Any) -> List[Any]:
        """Normalize a StructTreeRoot/StructElem /K value to child structure elements."""
        if value is None:
            return []
        if self._is_struct_element_like(value):
            return [value]
        if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict)):
            kids = []
            try:
                for item in value:
                    if self._is_struct_element_like(item):
                        kids.append(item)
            except TypeError:
                return []
            return kids
        return []

    def _flatten_document_grouping_kids(
        self, kids: List[Any], page_index: Dict[Any, int]
    ) -> List[Any]:
        """Unwrap broad document grouping containers before assigning content to pages."""
        flattened = []
        unwrap_tags = {"Document", "Part", "Art", "Article", "Sect", "Div", "NonStruct"}
        for child in kids:
            tag = self._normalize_tag_name(child.get("/S")) if hasattr(child, "get") else ""
            child_kids = self._as_struct_kids(child.get("/K")) if hasattr(child, "get") else []
            has_direct_page = self._direct_struct_elem_page_index(child, page_index) is not None
            if tag in unwrap_tags and child_kids and not has_direct_page:
                flattened.extend(self._flatten_document_grouping_kids(child_kids, page_index))
            else:
                flattened.append(child)
        return flattened

    def _infer_struct_elem_page_index(self, elem: Any, page_index: Dict[Any, int]) -> Optional[int]:
        """Infer the first page touched by a structure subtree."""
        if not hasattr(elem, "get"):
            return None
        idx = self._direct_struct_elem_page_index(elem, page_index)
        if idx is not None:
            return idx
        k_value = elem.get("/K")
        if hasattr(k_value, "get"):
            idx = page_index.get(getattr(k_value.get("/Pg"), "objgen", None))
            if idx is not None:
                return idx
            return self._infer_struct_elem_page_index(k_value, page_index)
        if hasattr(k_value, "__iter__") and not isinstance(k_value, (str, bytes, dict)):
            try:
                for child in k_value:
                    if hasattr(child, "get"):
                        idx = page_index.get(getattr(child.get("/Pg"), "objgen", None))
                        if idx is not None:
                            return idx
                        idx = self._infer_struct_elem_page_index(child, page_index)
                        if idx is not None:
                            return idx
            except TypeError:
                return None
        return None

    def _direct_struct_elem_page_index(self, elem: Any, page_index: Dict[Any, int]) -> Optional[int]:
        """Infer a page only from an element's own /Pg entry."""
        if not hasattr(elem, "get"):
            return None
        pg = elem.get("/Pg")
        return page_index.get(getattr(pg, "objgen", None))

    def _apply_xobject_marked_content_tag_mappings(
        self, resources: Any, mappings: Dict[str, str]
    ) -> int:
        """Apply marked-content mappings inside form XObject content streams."""
        if not hasattr(resources, "get"):
            return 0

        xobjects = resources.get("/XObject")
        if not hasattr(xobjects, "items"):
            return 0

        applied = 0
        for _, xobject in xobjects.items():
            if not hasattr(xobject, "get") or xobject.get("/Subtype") != "/Form":
                continue
            applied += self._apply_marked_content_tag_mappings_to_stream(xobject, mappings)
            applied += self._apply_xobject_marked_content_tag_mappings(
                xobject.get("/Resources"), mappings
            )
        return applied

    def _apply_marked_content_tag_mappings_to_container(
        self, contents: Any, mappings: Dict[str, str]
    ) -> int:
        """Apply marked-content mappings to a page /Contents stream or stream array."""
        if contents is None:
            return 0

        if self._is_content_stream_collection(contents):
            applied = 0
            for stream in contents:
                if hasattr(stream, "read_bytes"):
                    applied += self._apply_marked_content_tag_mappings_to_stream(
                        stream, mappings
                    )
            return applied

        if hasattr(contents, "read_bytes"):
            return self._apply_marked_content_tag_mappings_to_stream(contents, mappings)

        return 0

    def _apply_marked_content_tag_mappings_to_stream(
        self, stream: Any, mappings: Dict[str, str]
    ) -> int:
        """Rewrite marked-content tag operands on BMC/BDC operators."""
        try:
            with warnings.catch_warnings(record=True) as parse_warnings:
                warnings.simplefilter("always")
                instructions = pikepdf.parse_content_stream(stream)
            if parse_warnings:
                logger.debug(
                    "Skipping marked-content rewrite for stream with parser warnings: %s",
                    "; ".join(str(warning.message) for warning in parse_warnings),
                )
                return 0
        except Exception as e:
            logger.debug(f"Could not parse content stream for marked-content update: {e}")
            return 0

        updated_instructions = []
        applied = 0

        for instruction in instructions:
            operator = str(getattr(instruction, "operator", ""))
            operands = list(getattr(instruction, "operands", []))
            if operator in {"BMC", "BDC"} and operands:
                old_tag = self._normalize_tag_name(operands[0])
                if old_tag in mappings:
                    operands[0] = self._to_pdf_name(mappings[old_tag])
                    instruction = pikepdf.ContentStreamInstruction(
                        operands, pikepdf.Operator(operator)
                    )
                    applied += 1
            updated_instructions.append(instruction)

        if applied:
            try:
                stream.write(pikepdf.unparse_content_stream(updated_instructions))
            except Exception as e:
                logger.debug(f"Could not write updated content stream: {e}")
                return 0

        return applied

    def _is_content_stream_collection(self, value: Any) -> bool:
        """Return True when /Contents is an array-like list of content streams."""
        if isinstance(value, (str, bytes, dict)) or not hasattr(value, "__iter__"):
            return False
        try:
            items = list(value)
        except TypeError:
            return False
        return bool(items) and all(hasattr(item, "read_bytes") for item in items)

    def _normalize_tag_mappings(self, mappings: Dict[str, str]) -> Dict[str, str]:
        """Normalize mapping keys/values to plain tag names."""
        normalized_mappings: Dict[str, str] = {}
        for key, value in mappings.items():
            normalized_key = self._normalize_tag_name(key)
            normalized_value = self._normalize_tag_name(value)
            if normalized_key and normalized_value:
                normalized_mappings[normalized_key] = normalized_value
        return normalized_mappings

    def _filter_semantic_tag_mappings_for_structure(
        self, struct_root: Any, mappings: Dict[str, str]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Reject mappings whose target tag would be incompatible with existing children."""
        role_map_targets = self._get_role_map_targets(struct_root)
        profiles = self._collect_struct_tag_profiles(struct_root, role_map_targets)
        accepted = {}
        rejected = {}
        for source_tag, target_tag in mappings.items():
            profile = profiles.get(source_tag)
            if profile is None:
                accepted[source_tag] = target_tag
                continue
            allowed = set(self._allowed_semantic_targets_for_profile(profile))
            if target_tag in allowed:
                accepted[source_tag] = target_tag
            else:
                rejected[source_tag] = target_tag
                logger.warning(
                    "Rejected unsafe semantic mapping %s -> %s for existing structure",
                    source_tag,
                    target_tag,
                )
        return accepted, rejected

    def _collect_struct_tag_profiles(
        self, struct_elem: Any, role_map_targets: Optional[Dict[str, str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Collect aggregate structural facts by tag name."""
        profiles: Dict[str, Dict[str, Any]] = {}
        self._collect_struct_tag_profiles_from_elem(
            struct_elem, profiles, role_map_targets or {}
        )
        for profile in profiles.values():
            profile["child_tags"] = sorted(profile["child_tags"])
            profile["allowed_targets"] = self._allowed_semantic_targets_for_profile(profile)
        return profiles

    def _collect_struct_tag_profiles_from_elem(
        self,
        struct_elem: Any,
        profiles: Dict[str, Dict[str, Any]],
        role_map_targets: Dict[str, str],
    ) -> None:
        if not hasattr(struct_elem, "get"):
            return
        tag_name = self._normalize_tag_name(struct_elem.get("/S"))
        children = self._iter_struct_children(struct_elem)
        if tag_name:
            profile = profiles.setdefault(
                tag_name,
                {
                    "tag_name": tag_name,
                    "count": 0,
                    "has_struct_children": False,
                    "child_tags": set(),
                    "screen_reader_tag": self._screen_reader_tag_for_tag(
                        tag_name, role_map_targets
                    ),
                },
            )
            profile["count"] += 1
            if children:
                profile["has_struct_children"] = True
                profile["child_tags"].update(
                    self._normalize_tag_name(child.get("/S"))
                    for child in children
                    if hasattr(child, "get") and child.get("/S") is not None
                )
        for child in children:
            self._collect_struct_tag_profiles_from_elem(child, profiles, role_map_targets)

    def _allowed_semantic_targets_for_struct_elem(
        self, struct_elem: Any, role_map_targets: Optional[Dict[str, str]] = None
    ) -> List[str]:
        tag_name = (
            self._normalize_tag_name(struct_elem.get("/S"))
            if hasattr(struct_elem, "get")
            else ""
        )
        profile = {
            "tag_name": tag_name,
            "has_struct_children": bool(self._iter_struct_children(struct_elem)),
            "child_tags": [
                self._normalize_tag_name(child.get("/S"))
                for child in self._iter_struct_children(struct_elem)
                if hasattr(child, "get") and child.get("/S") is not None
            ],
            "screen_reader_tag": self._screen_reader_tag_for_tag(
                tag_name, role_map_targets or {}
            ),
        }
        return self._allowed_semantic_targets_for_profile(profile)

    def _allowed_semantic_targets_for_profile(self, profile: Dict[str, Any]) -> List[str]:
        """Return PDF/UA tags that preserve the source element's structural role."""
        all_tags = set(self._available_pdf_ua_tags())
        source_tag = self._normalize_tag_name(profile.get("tag_name"))
        screen_reader_tag = self._normalize_tag_name(profile.get("screen_reader_tag"))
        child_tags = {
            self._normalize_tag_name(tag)
            for tag in profile.get("child_tags", [])
            if self._normalize_tag_name(tag)
        }
        has_struct_children = bool(profile.get("has_struct_children"))

        artifact = {"Artifact"}
        grouping = {
            "Document",
            "Part",
            "Art",
            "Sect",
            "Div",
            "BlockQuote",
            "TOC",
            "TOCI",
            "Index",
            "NonStruct",
            "Private",
        }
        list_tags = {"L", "LI", "Lbl", "LBody"}
        table_tags = {"Table", "THead", "TBody", "TFoot", "TR", "TH", "TD"}
        ruby_tags = {"Ruby", "RB", "RT", "RP"}
        warichu_tags = {"Warichu", "WT", "WP"}
        leaf_tags = {
            "P",
            "H",
            "H1",
            "H2",
            "H3",
            "H4",
            "H5",
            "H6",
            "Caption",
            "Lbl",
            "Span",
            "Quote",
            "Note",
            "Reference",
            "BibEntry",
            "Code",
            "Link",
            "Annot",
            "RB",
            "RT",
            "RP",
            "WT",
            "WP",
            "Figure",
            "Formula",
            "Form",
        }
        is_custom_role_mapped_leaf = (
            source_tag not in all_tags and screen_reader_tag in leaf_tags
        )

        if is_custom_role_mapped_leaf:
            allowed = leaf_tags | artifact
        elif source_tag in table_tags or child_tags.intersection(table_tags):
            allowed = table_tags | artifact
        elif source_tag in list_tags or child_tags.intersection(list_tags):
            allowed = list_tags | artifact
        elif source_tag in ruby_tags or child_tags.intersection(ruby_tags):
            allowed = ruby_tags | artifact
        elif source_tag in warichu_tags or child_tags.intersection(warichu_tags):
            allowed = warichu_tags | artifact
        elif has_struct_children:
            allowed = grouping | list_tags | table_tags | {"Ruby", "Warichu"} | artifact
        elif source_tag in grouping:
            allowed = grouping | artifact
        else:
            allowed = leaf_tags | artifact

        return sorted(tag for tag in allowed if tag in all_tags)

    def _get_role_map_targets(self, struct_root: Any) -> Dict[str, str]:
        targets = {}
        try:
            role_map = struct_root.get("/RoleMap") if hasattr(struct_root, "get") else None
            if role_map is None or not hasattr(role_map, "items"):
                return targets
            for raw_key, raw_value in role_map.items():
                tag_name = self._normalize_tag_name(raw_key)
                mapped_to = self._normalize_tag_name(raw_value)
                if tag_name and mapped_to:
                    targets[tag_name] = mapped_to
        except Exception as e:
            logger.debug(f"Could not read role map targets: {e}")
        return targets

    def _screen_reader_tag_for_tag(self, tag_name: str, role_map_targets: Dict[str, str]) -> str:
        return role_map_targets.get(tag_name, tag_name)

    def _screen_reader_kind(self, tag_name: str) -> str:
        tag_name = self._normalize_tag_name(tag_name)
        if tag_name == "P":
            return "container/paragraph tag"
        if tag_name in {"H", "H1", "H2", "H3", "H4", "H5", "H6"}:
            return "container/heading tag"
        if tag_name in {"Document", "Part", "Art", "Sect", "Div", "BlockQuote", "TOC", "TOCI", "Index", "NonStruct", "Private"}:
            return "container/grouping tag"
        if tag_name in {"L", "LI", "Lbl", "LBody"}:
            return "container/list tag"
        if tag_name in {"Table", "THead", "TBody", "TFoot", "TR", "TH", "TD"}:
            return "container/table tag"
        if tag_name in {"Span", "Quote", "Note", "Reference", "BibEntry", "Code", "Link", "Annot", "Ruby", "RB", "RT", "RP", "Warichu", "WT", "WP"}:
            return "inline/text tag"
        if tag_name == "Figure":
            return "figure tag"
        if tag_name == "Formula":
            return "formula tag"
        if tag_name == "Form":
            return "form field tag"
        if tag_name == "Artifact":
            return "artifact"
        return "custom structure tag"

    def _is_struct_children_collection(self, value: Any) -> bool:
        """Return True when /K is an array-like container of child elements."""
        if isinstance(value, (str, bytes, dict)):
            return False
        if self._is_struct_element_like(value):
            return False
        return isinstance(value, (list, tuple)) or hasattr(value, "__iter__")

    def _iter_struct_children(self, struct_elem) -> List[Any]:
        """Return child structure elements from a StructElem or StructTreeRoot /K entry."""
        if not hasattr(struct_elem, "get"):
            return []

        k_value = struct_elem.get("/K")
        if k_value is None:
            return []

        if self._is_struct_element_like(k_value):
            return [k_value]

        if not self._is_struct_children_collection(k_value):
            return []

        children = []
        try:
            for child in k_value:
                if hasattr(child, "get"):
                    children.append(child)
        except TypeError:
            return []
        return children

    def _is_struct_element_like(self, value: Any) -> bool:
        """Return True when a pikepdf object looks like a structure element/root."""
        if not hasattr(value, "get"):
            return False
        return (
            value.get("/S") is not None
            or value.get("/K") is not None
            or self._normalize_tag_name(value.get("/Type")) in {"StructElem", "StructTreeRoot"}
        )

    def _available_pdf_ua_tags(self) -> Dict[str, str]:
        """PDF/UA target tags exposed to the semantic tag editor."""
        return {
            "Document": "Complete document",
            "Part": "Large-scale document division",
            "Art": "Article or self-contained body of content",
            "Sect": "Section of related content",
            "Div": "Generic block-level division",
            "BlockQuote": "Block quotation",
            "Caption": "Caption for a figure, table, or other item",
            "TOC": "Table of contents",
            "TOCI": "Table of contents item",
            "Index": "Index",
            "NonStruct": "Non-structural grouping element",
            "Private": "Private/application-specific structure element",
            "P": "Paragraph text content",
            "H": "Heading with inferred level",
            "H1": "Heading level 1",
            "H2": "Heading level 2",
            "H3": "Heading level 3",
            "H4": "Heading level 4",
            "H5": "Heading level 5",
            "H6": "Heading level 6",
            "L": "List container",
            "LI": "List item",
            "Lbl": "Label for a list item or form field",
            "LBody": "List item body",
            "Table": "Table",
            "THead": "Table header row group",
            "TBody": "Table body row group",
            "TFoot": "Table footer row group",
            "TR": "Table row",
            "TH": "Table header cell",
            "TD": "Table data cell",
            "Span": "Generic inline text span",
            "Quote": "Inline quotation",
            "Note": "Note or footnote",
            "Reference": "Reference to content elsewhere",
            "BibEntry": "Bibliography entry",
            "Code": "Computer code",
            "Link": "Link",
            "Annot": "Annotation",
            "Ruby": "Ruby annotation wrapper",
            "RB": "Ruby base text",
            "RT": "Ruby annotation text",
            "RP": "Ruby punctuation",
            "Warichu": "Warichu annotation wrapper",
            "WT": "Warichu text",
            "WP": "Warichu punctuation",
            "Figure": "Image or graphic",
            "Formula": "Mathematical formula",
            "Form": "Interactive form element",
            "Artifact": "Page artifact/decorative content",
        }

    def _count_mapped_values(self, mappings: Dict[str, str], target_value: str) -> int:
        """Count normalized mapping values matching a target tag."""
        return sum(
            1
            for value in mappings.values()
            if self._normalize_tag_name(value) == target_value
        )

    def _normalize_tag_name(self, tag_value: Any) -> str:
        """Normalize a PDF tag name to plain form (e.g. '/P' -> 'P')."""
        if tag_value is None:
            return ""

        text = str(tag_value).strip()
        if not text:
            return ""

        if text.startswith("/"):
            text = text[1:]

        if text.startswith("<") and text.endswith(">") and len(text) > 2:
            text = text[1:-1]

        return text.strip()

    def _to_pdf_name(self, tag_value: str):
        """Convert a normalized tag value to a pikepdf Name object."""
        normalized = self._normalize_tag_name(tag_value)
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        return pikepdf.Name(f"/{normalized}")

    def _call_gemini_api_with_retry(self, payload: Dict, max_retries: int = 15) -> Dict:
        """Call Gemini API with robust retries, exponential backoff, and model fallback."""
        # Check for cancellation before starting
        if self.should_cancel():
            raise RuntimeError("User cancelled the task")
        
        headers = {"Content-Type": "application/json"}

        backoff = 2.0
        for attempt in range(max_retries):
            # Check for cancellation on each retry
            if self.should_cancel():
                raise RuntimeError("User cancelled the task")
            
            # Block/wait to respect the current adaptive rate limit delay
            self.rate_limiter.wait_if_needed()

            # Construct URL using the current model_name (which might have changed due to fallback)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                if response.status_code == 200:
                    self.rate_limiter.report_success()
                    return response.json()
                elif response.status_code == 429:
                    self.rate_limiter.report_429()

                    try:
                        err_json = response.json()
                        err_msg = ""
                        status_str = ""
                        if isinstance(err_json, dict) and "error" in err_json:
                            err_detail = err_json["error"]
                            if isinstance(err_detail, dict):
                                err_msg = err_detail.get("message", "")
                                status_str = err_detail.get("status", "")
                            else:
                                err_msg = str(err_detail)
                        
                        logger.info(f"Gemini API 429 details - status: '{status_str}', message: '{err_msg}'")
                        
                        if "RESOURCE_EXHAUSTED" in status_str or "Quota exceeded" in err_msg or "quota" in err_msg.lower():
                            fallback_chain = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
                            
                            curr_model = self.model_name
                            current_idx = -1
                            for idx, m in enumerate(fallback_chain):
                                if m == curr_model:
                                    current_idx = idx
                                    break
                            
                            if current_idx != -1 and current_idx < len(fallback_chain) - 1:
                                next_model = fallback_chain[current_idx + 1]
                                logger.warning(
                                    f"Quota exceeded for model {curr_model}. "
                                    f"Attempting fallback to {next_model}..."
                                )
                                self.model_name = next_model
                                # Reset retry state and try again immediately with the new model
                                backoff = 2.0
                                continue
                            else:
                                logger.info(f"No further fallback available in chain for {curr_model} (idx={current_idx})")
                    except Exception as fe:
                        logger.error(f"Error checking fallback: {fe}", exc_info=True)

                    # Respect the retry delay Gemini tells us, e.g. "Please retry in 41.001s"
                    suggested_wait = None
                    try:
                        import re as _re
                        m = _re.search(r'retry in (\d+(?:\.\d+)?)s', err_msg, _re.IGNORECASE)
                        if m:
                            suggested_wait = float(m.group(1)) + 1.0  # +1s buffer
                    except Exception:
                        pass
                    sleep_time = suggested_wait if suggested_wait else (backoff + (time.time() % 1.0))
                    logger.warning(f"Gemini API rate limited (429). Retrying in {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    backoff *= 2.0
                else:
                    logger.error(f"Gemini API returned status {response.status_code}: {response.text}")
                    response.raise_for_status()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                # Network exceptions also trigger a minor backoff
                sleep_time = backoff + (time.time() % 1.0)
                logger.warning(f"Gemini API request failed: {e}. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                backoff *= 2.0

        raise RuntimeError("Failed to call Gemini API after maximum retries.")


def main():
    """CLI entry point for running the Visual Tagger AI Agent."""
    parser = argparse.ArgumentParser(description="Visual PDF Tagger AI Agent (Matterhorn Protocol)")
    parser.add_argument("input_path", help="Path to the input PDF file.")
    parser.add_argument(
        "--format",
        default="tagged-pdf",
        choices=["tagged-pdf", "json"],
        help="Output format. Default: tagged-pdf",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory where tagged PDF or JSON will be saved.",
    )
    parser.add_argument(
        "--gemini-key",
        help="Gemini API Key (overrides GEMINI_API_KEY environment variable).",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model name to use. Default: gemini-2.5-flash",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of parallel visual auditing workers. Default: 5",
    )

    args = parser.parse_args()

    api_key = args.gemini_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "Error: Gemini API Key is missing. Set GEMINI_API_KEY environment variable or pass via --gemini-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    converter = GeminiAgentConverter(api_key=api_key, model_name=args.model, max_workers=args.workers)

    try:
        # Run visual conversion
        result = converter.convert(args.input_path)

        out_path = Path(args.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        input_file = Path(args.input_path)

        if args.format == "json":
            out_file = out_path / f"{input_file.stem}_layout.json"
            out_file.write_text(json.dumps(result.document.export_to_dict(), indent=2), encoding="utf-8")
            logger.info(f"Saved layout JSON to: {out_file}")
        else:
            # For tagged-pdf, we now run the Java CLI using the modified PDF file
            temp_pdf = getattr(converter, "temp_pdf_path", None)
            if not temp_pdf or not os.path.exists(temp_pdf):
                logger.error("No modified PDF was generated. Falling back to input PDF.")
                temp_pdf = args.input_path

            # Export the layout JSON to a temp file that the hybrid server configuration can use,
            # or just invoke opendataloader-pdf command directly.
            # Wait, we can invoke the Java CLI directly:
            # opendataloader-pdf --hybrid docling-fast --hybrid-mode full --hybrid-url http://localhost:PORT
            # But wait! It is much easier to just run convert() from python wrapper using the modified PDF,
            # but bypassing docling backend by starting our own local FastAPI server instance just for this command!
            # Or we can just import opendataloader_pdf wrapper and call convert with our layout JSON pre-injected!
            # Let's see: how can we inject the layout JSON into the Java CLI without a running server?
            # Ah! If we just write the layout JSON to a temporary file, can the Java CLI load it?
            # No, Java CLI gets layout from the hybrid URL.
            # So, we can spin up a quick, lightweight FastAPI mock server in a background thread,
            # point --hybrid-url to it, run the java CLI, and then stop the server!
            # This is extremely simple and clean!

            import uvicorn
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse

            app = FastAPI()

            @app.post("/v1/convert/file")
            def convert_mock():
                return JSONResponse(
                    {
                        "status": result.status,
                        "document": {"json_content": result.document.export_to_dict()},
                        "errors": result.errors,
                        "failed_pages": [],
                    }
                )

            @app.get("/health")
            def health_mock():
                return {"status": "ok"}

            # Start server on a free port in a background thread
            import socket
            import threading

            # Find a free port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.close()

            server_thread = threading.Thread(
                target=uvicorn.run,
                args=(app,),
                kwargs={"host": "127.0.0.1", "port": port, "log_level": "error"},
                daemon=True,
            )
            server_thread.start()

            # Wait a moment for server to start
            time.sleep(1.0)

            # Import the convert method from opendataloader_pdf wrapper
            from opendataloader_pdf.convert_generated import convert as wrapper_convert

            # Call convert to generate tagged PDF
            logger.info("Invoking Java tagging engine to compile accessibility tags into PDF...")
            wrapper_convert(
                input_path=temp_pdf,
                output_dir=str(out_path),
                format="tagged-pdf",
                hybrid="docling-fast",
                hybrid_mode="full",
                hybrid_url=f"http://127.0.0.1:{port}",
                quiet=False,
            )

            # Locate the output file and rename it if needed
            # The Java output file will be named like: {temp_pdf_stem}_tagged.pdf
            # Let's rename it to {input_file_stem}_tagged.pdf in output_dir
            temp_pdf_stem = Path(temp_pdf).stem
            generated_tagged = out_path / f"{temp_pdf_stem}_tagged.pdf"
            final_tagged = out_path / f"{input_file.stem}_tagged.pdf"

            if generated_tagged.is_file():
                if generated_tagged != final_tagged:
                    if final_tagged.exists():
                        final_tagged.unlink()
                    generated_tagged.rename(final_tagged)
                logger.info(f"Successfully generated tagged PDF: {final_tagged}")
            else:
                logger.error(
                    f"Expected tagged PDF at {generated_tagged} was not found. "
                    f"Check Java CLI execution output."
                )

            # Clean up temp PDF
            try:
                if temp_pdf and temp_pdf != args.input_path and os.path.exists(temp_pdf):
                    os.unlink(temp_pdf)
            except Exception:
                pass

        sys.exit(0)

    except Exception as e:
        logger.error(f"Visual Tagging Agent failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
