"""MCP server for OpenDataLoader PDF."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import opendataloader_pdf

logger = logging.getLogger("opendataloader_pdf_mcp")

mcp = FastMCP("opendataloader-pdf")


@mcp.tool()
def convert_pdf(
    input_path: str,
    format: str = "markdown",
    password: str | None = None,
    pages: str | None = None,
    keep_line_breaks: bool = False,
    sanitize: bool = False,
    content_safety_off: str | None = None,
    replace_invalid_chars: str | None = None,
    use_struct_tree: bool = False,
    table_method: str | None = None,
    reading_order: str | None = None,
    markdown_page_separator: str | None = None,
    text_page_separator: str | None = None,
    html_page_separator: str | None = None,
    image_output: str | None = None,
    image_format: str | None = None,
    include_header_footer: bool = False,
    detect_strikethrough: bool = False,
    hybrid: str | None = None,
    hybrid_mode: str | None = None,
    hybrid_url: str | None = None,
    hybrid_timeout: str | None = None,
    hybrid_fallback: bool = False,
    image_dir: str | None = None,
) -> str:
    """Convert a PDF file to the specified format.

    Args:
        input_path: Path to the input PDF file.
        format: Output format. Values: json, text, html, markdown,
            markdown-with-html, markdown-with-images. Default: markdown.
        password: Password for encrypted PDF files.
        pages: Pages to extract (e.g., "1,3,5-7"). Default: all pages.
        keep_line_breaks: Preserve original line breaks in extracted text.
        sanitize: Replace emails, phone numbers, IPs, credit cards, URLs with placeholders.
        content_safety_off: Disable content safety filters.
            Values: all, hidden-text, off-page, tiny, hidden-ocg.
        replace_invalid_chars: Replacement character for invalid/unrecognized characters.
        use_struct_tree: Use PDF structure tree for reading order and semantic structure.
        table_method: Table detection method. Values: default, cluster.
        reading_order: Reading order algorithm. Values: off, xycut.
        markdown_page_separator: Separator between pages in Markdown output.
            Use %page-number% for page numbers.
        text_page_separator: Separator between pages in text output.
        html_page_separator: Separator between pages in HTML output.
        image_output: Image output mode. Values: off, embedded, external.
        image_format: Image format. Values: png, jpeg.
        include_header_footer: Include page headers and footers in output.
        detect_strikethrough: Detect strikethrough text (experimental).
        hybrid: Hybrid backend. Values: off, docling-fast.
        hybrid_mode: Hybrid triage mode. Values: auto, full.
        hybrid_url: Hybrid backend server URL.
        hybrid_timeout: Hybrid backend timeout in milliseconds.
        hybrid_fallback: Enable Java fallback on hybrid backend error.
        image_dir: Directory path to save extracted images.

    Returns:
        The converted content as text.
    """
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine output file extension from format
    ext_map = {
        "json": ".json",
        "text": ".txt",
        "html": ".html",
        "markdown": ".md",
        "markdown-with-html": ".md",
        "markdown-with-images": ".md",
    }
    if format not in ext_map:
        raise ValueError(
            f"Unsupported format: {format!r}. "
            f"Supported formats: {', '.join(ext_map)}"
        )
    ext = ext_map[format]

    with tempfile.TemporaryDirectory() as tmp_dir:
        kwargs: dict[str, Any] = {
            "input_path": str(input_file),
            "output_dir": tmp_dir,
            "format": format,
            "quiet": True,
        }

        # Only pass non-default values
        if password is not None:
            kwargs["password"] = password
        if pages is not None:
            kwargs["pages"] = pages
        if keep_line_breaks:
            kwargs["keep_line_breaks"] = True
        if sanitize:
            kwargs["sanitize"] = True
        if content_safety_off is not None:
            kwargs["content_safety_off"] = content_safety_off
        if replace_invalid_chars is not None:
            kwargs["replace_invalid_chars"] = replace_invalid_chars
        if use_struct_tree:
            kwargs["use_struct_tree"] = True
        if table_method is not None:
            kwargs["table_method"] = table_method
        if reading_order is not None:
            kwargs["reading_order"] = reading_order
        if markdown_page_separator is not None:
            kwargs["markdown_page_separator"] = markdown_page_separator
        if text_page_separator is not None:
            kwargs["text_page_separator"] = text_page_separator
        if html_page_separator is not None:
            kwargs["html_page_separator"] = html_page_separator
        if format == "markdown-with-images" and image_output is None:
            # Force embedded images so they survive the temp directory cleanup
            kwargs["image_output"] = "embedded"
        elif image_output is not None:
            kwargs["image_output"] = image_output
        if image_format is not None:
            kwargs["image_format"] = image_format
        if include_header_footer:
            kwargs["include_header_footer"] = True
        if detect_strikethrough:
            kwargs["detect_strikethrough"] = True
        if hybrid is not None:
            kwargs["hybrid"] = hybrid
        if hybrid_mode is not None:
            kwargs["hybrid_mode"] = hybrid_mode
        if hybrid_url is not None:
            kwargs["hybrid_url"] = hybrid_url
        if hybrid_timeout is not None:
            kwargs["hybrid_timeout"] = hybrid_timeout
        if hybrid_fallback:
            kwargs["hybrid_fallback"] = True
        if image_dir is not None:
            kwargs["image_dir"] = image_dir

        opendataloader_pdf.convert(**kwargs)

        # Find and read the output file
        stem = input_file.stem
        output_file = Path(tmp_dir) / f"{stem}{ext}"

        if not output_file.is_file():
            files = [f for f in Path(tmp_dir).iterdir() if f.is_file()]
            if not files:
                raise RuntimeError(
                    "Conversion completed but no output file was generated."
                )
            matching_ext = sorted(f for f in files if f.suffix == ext)
            if not matching_ext:
                raise RuntimeError(
                    f"Conversion completed but no '{ext}' output file was generated."
                )
            output_file = matching_ext[0]

        return output_file.read_text(encoding="utf-8")


@mcp.tool()
def tag_pdf_with_agent(
    input_path: str,
    output_dir: str = ".",
    gemini_key: str | None = None,
    model: str = "gemini-2.5-flash",
    workers: int = 5,
) -> str:
    """Audit and tag a PDF file visually to the PDF/UA Matterhorn Protocol using Gemini.

    This tool renders PDF pages to images, uses a Gemini multimodal agent to visually
    group and classify elements (headings, tables, lists, informative figures, headers/footers),
    names and updates tooltips on form fields, and generates a fully compliant tagged PDF.

    Args:
        input_path: Path to the input PDF file.
        output_dir: Directory where the tagged PDF will be saved. Default: ".".
        gemini_key: Optional Gemini API Key (overrides GEMINI_API_KEY env variable).
        model: Gemini model name. Default: gemini-2.5-flash.
        workers: Number of parallel page auditing threads. Default: 5.

    Returns:
        Status message with the path to the tagged PDF.
    """
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    from opendataloader_pdf.agent import GeminiAgentConverter

    # Resolve API Key
    api_key = gemini_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Gemini API Key is missing. Pass gemini_key or set the GEMINI_API_KEY environment variable."
        )

    # Instantiate the agent converter
    converter = GeminiAgentConverter(api_key=api_key, model_name=model, max_workers=workers)

    # Convert to tagged-pdf using agent workflow
    logger.info(f"Starting Visual PDF Tagger AI Agent on: {input_file}")
    result = converter.convert(str(input_file))

    out_path = Path(output_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    # Run the Java CLI inside the agent via the local mock server flow
    temp_pdf = getattr(converter, "temp_pdf_path", None)
    if not temp_pdf or not os.path.exists(temp_pdf):
        logger.warning("No modified PDF was generated. Falling back to input PDF.")
        temp_pdf = str(input_file)

    import socket
    import threading
    import time
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

    # Find free port
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

    # Call convert to generate tagged PDF
    from opendataloader_pdf.convert_generated import convert as wrapper_convert

    wrapper_convert(
        input_path=temp_pdf,
        output_dir=str(out_path),
        format="tagged-pdf",
        hybrid="docling-fast",
        hybrid_mode="full",
        hybrid_url=f"http://127.0.0.1:{port}",
        quiet=True,
    )

    temp_pdf_stem = Path(temp_pdf).stem
    generated_tagged = out_path / f"{temp_pdf_stem}_tagged.pdf"
    final_tagged = out_path / f"{input_file.stem}_tagged.pdf"

    if generated_tagged.is_file():
        if generated_tagged != final_tagged:
            if final_tagged.exists():
                final_tagged.unlink()
            generated_tagged.rename(final_tagged)
        msg = f"Successfully generated tagged PDF complying with the Matterhorn Protocol at: {final_tagged}"
    else:
        raise RuntimeError(
            f"Failed to generate tagged PDF. Java CLI output was not found at {generated_tagged}."
        )

    # Clean up temp PDF
    try:
        if temp_pdf and temp_pdf != str(input_file) and os.path.exists(temp_pdf):
            os.unlink(temp_pdf)
    except Exception:
        pass

    return msg


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
