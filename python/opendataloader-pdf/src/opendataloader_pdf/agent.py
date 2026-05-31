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
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.max_workers = max_workers
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
                    page_texts, page_tables, page_pictures = future.result()
                    texts_out.extend(page_texts)
                    tables_out.extend(page_tables)
                    pictures_out.extend(page_pictures)
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

        # Construct Docling JSON structure
        docling_json = {
            "schema_version": "1.0.0",
            "texts": texts_out,
            "tables": tables_out,
            "pictures": pictures_out,
            "pages": {str(i + 1): {"page_no": i + 1} for i in pages_to_process},
        }

        document = GeminiAgentDocument(docling_json)
        return GeminiAgentConversionResult(document, status, errors, total_pages)

    def _process_single_page(
        self, pdf_pikepdf: pikepdf.Pdf, doc: fitz.Document, page_num: int
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
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

        return page_texts, page_tables, page_pictures

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

    def _call_gemini_api_with_retry(self, payload: Dict, max_retries: int = 15) -> Dict:
        """Call Gemini API with robust retries, exponential backoff, and model fallback."""
        headers = {"Content-Type": "application/json"}

        backoff = 2.0
        for attempt in range(max_retries):
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

                    sleep_time = backoff + (time.time() % 1.0)
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
