import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import fitz
import pikepdf
import pytest
from opendataloader_pdf.agent import GeminiAgentConverter


@pytest.fixture
def sample_pdf():
    # Create a simple 1-page PDF using pikepdf
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))  # standard Letter size

    # Create a form field widget
    widget_dict = pikepdf.Dictionary(
        Subtype=pikepdf.Name("/Widget"),
        FT=pikepdf.Name("/Tx"),
        T=pikepdf.String("TextField1"),
        Rect=[50, 100, 150, 120],  # [left, bottom, right, top]
    )
    # Add annotation list
    page.Annots = pdf.make_indirect([widget_dict])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
    pdf.save(pdf_path)
    pdf.close()

    yield pdf_path

    # Clean up
    if os.path.exists(pdf_path):
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


def test_closest_widget_matching():
    widgets = [
        {"index": 0, "bbox": [100.0, 100.0, 120.0, 150.0], "name": "test1", "tooltip": ""},
        {"index": 1, "bbox": [500.0, 500.0, 520.0, 550.0], "name": "test2", "tooltip": ""},
    ]
    converter = GeminiAgentConverter(api_key="mock")

    # Exact match
    match = converter._find_closest_widget([100.0, 100.0, 120.0, 150.0], widgets)
    assert match is not None
    assert match["index"] == 0

    # Close match (within tolerance)
    match_close = converter._find_closest_widget([102.0, 98.0, 118.0, 152.0], widgets)
    assert match_close is not None
    assert match_close["index"] == 0

    # Out of tolerance
    match_far = converter._find_closest_widget([300.0, 300.0, 320.0, 350.0], widgets)
    assert match_far is None


def test_apply_semantic_tags_persists_structure_tree_changes():
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pikepdf.Array([
        pdf.make_stream(b"/H1 BMC\nEMC\n"),
        pdf.make_stream(
        b"/Story <</MCID 0>> BDC\nEMC\n/Caption BMC\nEMC\n"
        b"/H2 <</MCID 1>> BDC\nEMC\n/H#33 /P0 BDC\nEMC\n/H1_Title BMC\nEMC\n"
        ),
    ])

    span_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Caption"),
        )
    )
    story_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Story"),
            K=pikepdf.Array([span_elem]),
        )
    )
    h2_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/H2"),
        )
    )
    h3_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/H3"),
        )
    )
    h1_title_elem = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/H1_Title"),
        )
    )
    pdf.Root.StructTreeRoot = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array([story_elem, h2_elem, h3_elem, h1_title_elem]),
            RoleMap=pikepdf.Dictionary(
                Story=pikepdf.Name("/Div"),
                Caption=pikepdf.Name("/Span"),
                H1_Title=pikepdf.Name("/H1"),
            ),
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as dst:
        dst_path = dst.name

    try:
        pdf.save(src_path)
        pdf.close()

        converter = GeminiAgentConverter(api_key="mock")
        result = converter.apply_semantic_tags(
            src_path,
            {"H1": "P", "Story": "P", "Caption": "Artifact", "H2": "P", "H3": "P"},
            dst_path,
        )

        assert result["rejected_mappings"] == {"Story": "P"}
        assert result["content_tag_count"] == 5
        assert result["artifact_count"] == 1

        updated = pikepdf.Pdf.open(dst_path)
        try:
            struct_root = updated.Root.StructTreeRoot
            updated_story = struct_root.K[0]
            updated_h2 = struct_root.K[1]
            updated_h3 = struct_root.K[2]
            updated_h1_title = struct_root.K[3]
            updated_content = b"".join(
                stream.read_bytes() for stream in updated.pages[0].Contents
            )
            marked_content_tags = [
                str(instruction.operands[0])
                for instruction in pikepdf.parse_content_stream(updated.pages[0])
                if str(instruction.operator) in {"BMC", "BDC"}
            ]

            assert str(updated_story.S) == "/Story"
            assert "/K" not in updated_story
            assert str(updated_h2.S) == "/P"
            assert str(updated_h3.S) == "/P"
            assert str(updated_h1_title.S) == "/P"
            assert str(struct_root.RoleMap.Story) == "/Div"
            assert str(struct_root.RoleMap.H1_Title) == "/P"
            assert "/Caption" not in struct_root.RoleMap
            assert marked_content_tags == ["/P", "/Story", "/Artifact", "/P", "/P", "/P"]
            assert b"/P /P0 BDC" in updated_content
            assert b"/Story" in updated_content
            assert b"/Caption" not in updated_content
            assert b"/H2" not in updated_content
            assert b"/H3" not in updated_content
            assert b"/H1_Title" not in updated_content
            assert b"/H#33" not in updated_content
        finally:
            updated.close()
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        for path in (src_path, dst_path):
            if os.path.exists(path):
                os.unlink(path)


def test_extract_semantic_tags_reports_structure_safe_targets():
    pdf = pikepdf.Pdf.new()
    story_child = pdf.make_indirect(
        pikepdf.Dictionary(Type=pikepdf.Name("/StructElem"), S=pikepdf.Name("/P"))
    )
    story = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Story"),
            K=pikepdf.Array([story_child]),
        )
    )
    heading = pdf.make_indirect(
        pikepdf.Dictionary(Type=pikepdf.Name("/StructElem"), S=pikepdf.Name("/H1"))
    )
    styled_table = pdf.make_indirect(
        pikepdf.Dictionary(Type=pikepdf.Name("/StructElem"), S=pikepdf.Name("/Table"))
    )
    styled_para = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Styled_Subheader"),
            K=pikepdf.Array([styled_table]),
        )
    )
    pdf.add_blank_page(page_size=(612, 792))
    pdf.Root.StructTreeRoot = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array([story, heading, styled_para]),
            RoleMap=pikepdf.Dictionary(Styled_Subheader=pikepdf.Name("/P")),
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name

    try:
        pdf.save(src_path)
        pdf.close()
        tags = GeminiAgentConverter(api_key="mock").extract_tags_from_pdf(src_path)["tags"]
        story_info = next(tag for tag in tags if tag["tag_name"] == "Story")
        heading_info = next(tag for tag in tags if tag["tag_name"] == "H1")

        assert story_info["has_struct_children"] is True
        assert "P" not in story_info["allowed_targets"]
        assert "Div" in story_info["allowed_targets"]
        assert "Artifact" in story_info["allowed_targets"]
        assert heading_info["has_struct_children"] is False
        assert "P" in heading_info["allowed_targets"]
        styled_info = next(tag for tag in tags if tag["tag_name"] == "Styled_Subheader")
        assert styled_info["screen_reader_tag"] == "P"
        assert styled_info["screen_reader_kind"] == "container/paragraph tag"
        assert "H2" in styled_info["allowed_targets"]
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        if os.path.exists(src_path):
            os.unlink(src_path)


def test_update_pdf_with_enriched_fields_updates_duplicate_names_individually():
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Annots = pdf.make_indirect([
        pikepdf.Dictionary(
            Subtype=pikepdf.Name("/Widget"),
            FT=pikepdf.Name("/Tx"),
            T=pikepdf.String("Duplicate#Field"),
            TU=pikepdf.String("Existing first"),
            Rect=[50, 100, 150, 120],
        ),
        pikepdf.Dictionary(
            Subtype=pikepdf.Name("/Widget"),
            FT=pikepdf.Name("/Tx"),
            T=pikepdf.String("Duplicate#Field"),
            TU=pikepdf.String("Existing second"),
            Rect=[200, 100, 300, 120],
        ),
    ])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as dst:
        dst_path = dst.name

    try:
        pdf.save(src_path)
        pdf.close()

        converter = GeminiAgentConverter(api_key="mock")
        fields = converter.extract_form_fields_only(src_path)["form_fields"]

        assert fields[0]["original_tooltip"] == "Existing first"
        assert fields[1]["original_tooltip"] == "Existing second"
        assert fields[0]["widget_index"] == 0
        assert fields[1]["widget_index"] == 1

        fields[0]["new_name"] = "duplicate_first"
        fields[0]["tooltip"] = "Updated first"
        fields[1]["new_name"] = "duplicate_second"
        fields[1]["tooltip"] = "Updated second"

        result = converter.update_pdf_with_enriched_fields(src_path, fields, dst_path)
        assert result["fields_updated"] == 2

        updated = pikepdf.Pdf.open(dst_path)
        try:
            assert str(updated.pages[0].Annots[0].T) == "duplicate_first"
            assert str(updated.pages[0].Annots[0].TU) == "Updated first"
            assert str(updated.pages[0].Annots[1].T) == "duplicate_second"
            assert str(updated.pages[0].Annots[1].TU) == "Updated second"
        finally:
            updated.close()
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        for path in (src_path, dst_path):
            if os.path.exists(path):
                os.unlink(path)


def test_deduplicate_form_field_names_renames_everything_pdf_safe():
    converter = GeminiAgentConverter(api_key="mock")
    fields = [
        {"page_no": 1, "name": "Student Name #1!", "type": "text", "tooltip": "Name"},
        {"page_no": 1, "name": "Student Name 1", "type": "text", "tooltip": "Name again"},
        {"page_no": 2, "name": "123 Choice/Answer?", "type": "combobox", "tooltip": "Choice"},
        {"page_no": 2, "name": "x" * 100, "type": "text", "tooltip": "Long"},
    ]

    result = converter._deduplicate_form_field_names(fields)

    assert [field["new_name"] for field in result] == [
        "student_name_1",
        "student_name_1_2",
        "field_123_choice_answer",
        "x" * 64,
    ]
    assert [field["original_name"] for field in result] == [
        "Student Name #1!",
        "Student Name 1",
        "123 Choice/Answer?",
        "x" * 100,
    ]
    assert all(len(field["new_name"]) <= 64 for field in result)
    assert all("#" not in field["new_name"] and "/" not in field["new_name"] for field in result)


def test_multipage_radio_split_counts_logical_groups_only():
    converter = GeminiAgentConverter(api_key="mock")
    fields = [
        {"page_no": 1, "name": "Name Page 1", "type": "text"},
        {"page_no": 2, "name": "Name Page 2", "type": "text"},
        {"page_no": 1, "name": "ChoiceGroup", "type": "radio"},
        {"page_no": 1, "name": "ChoiceGroup", "type": "radio"},
        {"page_no": 2, "name": "ChoiceGroup", "type": "radio"},
        {"page_no": 2, "name": "ChoiceGroup", "type": "radio"},
    ]

    renamed = converter._deduplicate_form_field_names(fields)
    split = converter._split_multipage_radio_groups(renamed)

    assert converter._count_multipage_radio_split_groups(split) == 1
    text_fields = [field for field in split if field["type"] == "text"]
    radio_fields = [field for field in split if field["type"] == "radio"]

    assert all(not field.get("multipage_radio_split") for field in text_fields)
    assert {field["new_name"] for field in radio_fields} == {
        "choicegroup_page_1",
        "choicegroup_page_2",
    }


def test_multipage_radio_split_count_ignores_page_named_text_fields():
    converter = GeminiAgentConverter(api_key="mock")
    fields = [
        {"page_no": 1, "name": "field_page_1", "type": "text"},
        {"page_no": 2, "name": "field_page_2", "type": "text"},
    ]

    renamed = converter._deduplicate_form_field_names(fields)
    split = converter._split_multipage_radio_groups(renamed)

    assert converter._count_multipage_radio_split_groups(split) == 0
    assert all("_page_" in field["new_name"] for field in split)


def test_artifact_pruning_nulls_parent_tree_references():
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    page.StructParents = 0
    page.Contents = pdf.make_stream(b"/Caption <</MCID 0>> BDC\nEMC\n")

    caption = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Caption"),
            Pg=page.obj,
        )
    )
    parent_tree = pdf.make_indirect(
        pikepdf.Dictionary(Nums=pikepdf.Array([0, pikepdf.Array([caption])]))
    )
    pdf.Root.StructTreeRoot = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array([caption]),
            ParentTree=parent_tree,
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as dst:
        dst_path = dst.name

    try:
        pdf.save(src_path)
        pdf.close()

        converter = GeminiAgentConverter(api_key="mock")
        converter.apply_semantic_tags(src_path, {"Caption": "Artifact"}, dst_path)

        updated = pikepdf.Pdf.open(dst_path)
        try:
            struct_root = updated.Root.StructTreeRoot
            assert "/K" not in struct_root
            assert struct_root.ParentTree.Nums[1][0] is None
        finally:
            updated.close()
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        for path in (src_path, dst_path):
            if os.path.exists(path):
                os.unlink(path)


def test_add_form_fields_to_pdf_creates_widgets_and_acroform():
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as dst:
        dst_path = dst.name

    try:
        pdf.save(src_path)
        pdf.close()

        converter = GeminiAgentConverter(api_key="mock")
        result = converter.add_form_fields_to_pdf(
            src_path,
            [
                {
                    "page_no": 1,
                    "bbox": [100, 100, 130, 400],
                    "name": "Student Name!",
                    "tooltip": "Enter the student name",
                    "type": "text",
                },
                {
                    "page_no": 1,
                    "bbox": [200, 100, 230, 130],
                    "name": "Agree?",
                    "tooltip": "Check if you agree",
                    "type": "checkbox",
                },
                {
                    "page_no": 1,
                    "bbox": [300, 100, 330, 400],
                    "name": "Word Bank Blank",
                    "tooltip": "Choose a word from the word bank or type your own",
                    "type": "combobox",
                    "options": ["apple", "banana", "cherry"],
                    "allow_custom_text": True,
                },
            ],
            dst_path,
        )

        assert result["fields_added"] == 3
        assert result["fields_skipped"] == 0

        updated = pikepdf.Pdf.open(dst_path)
        try:
            assert len(updated.Root.AcroForm.Fields) == 3
            assert len(updated.pages[0].Annots) == 3
            text_field = updated.pages[0].Annots[0]
            checkbox = updated.pages[0].Annots[1]
            combobox = updated.pages[0].Annots[2]

            assert str(text_field.FT) == "/Tx"
            assert str(text_field.T) == "student_name"
            assert str(text_field.TU) == "Enter the student name"
            assert str(checkbox.FT) == "/Btn"
            assert str(checkbox.T) == "agree"
            assert str(checkbox.AS) == "/Off"
            assert str(combobox.FT) == "/Ch"
            assert str(combobox.T) == "word_bank_blank"
            assert int(combobox.Ff) & 131072
            assert int(combobox.Ff) & 262144
            assert [str(option) for option in combobox.Opt] == ["apple", "banana", "cherry"]
        finally:
            updated.close()
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        for path in (src_path, dst_path):
            if os.path.exists(path):
                os.unlink(path)


def test_document_structuring_mode_wraps_tags_and_forms():
    pdf = pikepdf.Pdf.new()
    page1 = pdf.add_blank_page(page_size=(612, 792))
    page2 = pdf.add_blank_page(page_size=(612, 792))

    widget = pikepdf.Dictionary(
        Subtype=pikepdf.Name("/Widget"),
        FT=pikepdf.Name("/Tx"),
        T=pikepdf.String("NameField"),
        Rect=[50, 100, 150, 120],
    )
    page2.Annots = pdf.make_indirect([widget])

    page1_para = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/P"),
            Pg=page1.obj,
        )
    )
    page2_para = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/P"),
            Pg=page2.obj,
        )
    )
    article = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructElem"),
            S=pikepdf.Name("/Article"),
            K=pikepdf.Array([page1_para, page2_para]),
        )
    )
    pdf.Root.StructTreeRoot = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/StructTreeRoot"),
            K=pikepdf.Array([article]),
        )
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as src:
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as dst:
        dst_path = dst.name

    try:
        pdf.save(src_path)
        pdf.close()

        converter = GeminiAgentConverter(api_key="mock")
        result = converter.apply_semantic_tags(
            src_path,
            {},
            dst_path,
            restructure_document=True,
        )

        assert result["document_structured"] is True
        assert result["page_containers"] == 2
        assert result["form_fields_tagged"] == 1

        updated = pikepdf.Pdf.open(dst_path)
        try:
            struct_root = updated.Root.StructTreeRoot
            document = struct_root.K
            page_parts = document.K

            assert str(document.S) == "/Document"
            assert [str(part.S) for part in page_parts] == ["/Part", "/Part"]
            assert str(page_parts[0].K[0].S) == "/P"
            assert str(page_parts[1].K[0].S) == "/P"
            assert str(page_parts[1].K[1].S) == "/Form"
            assert str(page_parts[1].K[1].K.Type) == "/OBJR"
        finally:
            updated.close()
    finally:
        try:
            pdf.close()
        except Exception:
            pass
        for path in (src_path, dst_path):
            if os.path.exists(path):
                os.unlink(path)


@patch("requests.post")
def test_gemini_agent_converter(mock_post, sample_pdf):
    # Mock the response from Gemini API
    mock_response = MagicMock()
    mock_response.status_code = 200

    gemini_output = {
        "elements": [
            {"type": "heading", "bbox": [50, 50, 80, 200], "text": "Introduction", "heading_level": 1},
            {
                "type": "paragraph",
                "bbox": [100, 50, 150, 500],
                "text": "This is a sample document for testing the PDF Tagger Agent.",
            },
            {
                "type": "figure",
                "bbox": [200, 50, 400, 400],
                "text": "Chart showing layout metrics",
                "alt_text": "Alt text generated by visual tagger",
                "is_decorative": False,
            },
        ],
        "form_fields": [
            {
                # Page height is 792.
                # PDF box: [50, 100, 150, 120] -> l=50, b=100, r=150, t=120
                # Normalized:
                # ymin = (792 - 120)/792 * 1000 = 848.48
                # ymax = (792 - 100)/792 * 1000 = 873.73
                # xmin = 50/612 * 1000 = 81.69
                # xmax = 150/612 * 1000 = 245.09
                # We round to [848.5, 81.7, 873.7, 245.1]
                "bbox": [848.5, 81.7, 873.7, 245.1],
                "name": "user_first_name",
                "tooltip": "Enter your first name",
            }
        ],
    }

    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(gemini_output)}]}}]
    }
    mock_post.return_value = mock_response

    converter = GeminiAgentConverter(api_key="mock_key")
    result = converter.convert(sample_pdf)

    # Assertions
    assert result.status == "success"
    assert result.input.page_count == 1

    # Verify JSON output structure matches Docling structure
    data = result.document.export_to_dict()
    assert "texts" in data
    assert "pictures" in data

    # Verify headings mapping
    headings = [t for t in data["texts"] if t["label"] == "section_header"]
    assert len(headings) == 1
    assert headings[0]["text"] == "Introduction"
    assert headings[0]["meta"]["level"] == 1

    # Verify paragraphs mapping
    paras = [t for t in data["texts"] if t["label"] == "text"]
    assert len(paras) == 1
    assert paras[0]["text"] == "This is a sample document for testing the PDF Tagger Agent."

    # Verify picture mapping
    assert len(data["pictures"]) == 1
    assert data["pictures"][0]["annotations"][0]["text"] == "Alt text generated by visual tagger"

    # Verify pikepdf modified fields
    modified_pdf = pikepdf.Pdf.open(converter.temp_pdf_path)
    annot = modified_pdf.pages[0].Annots[0]

    # Assert updated name and tooltip
    assert str(annot.get("/T")) == "user_first_name"
    assert str(annot.get("/TU")) == "Enter your first name"

    modified_pdf.close()

    # Clean up temp modified PDF
    if os.path.exists(converter.temp_pdf_path):
        os.unlink(converter.temp_pdf_path)
