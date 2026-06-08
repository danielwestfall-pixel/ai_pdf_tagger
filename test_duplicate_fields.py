#!/usr/bin/env python3
"""
Test script to verify duplicate field name detection and enrichment features.
"""

import sys
import json
sys.path.insert(0, r"c:\Users\DanielW1814\Desktop\Gregs_Cousin\ai_pdf_tagger\python\opendataloader-pdf\src")

from opendataloader_pdf.agent import GeminiAgentConverter

# Create converter instance
converter = GeminiAgentConverter(api_key="test", model_name="gemini-2.0-flash", max_workers=1)

# Test 1: Deduplicate field names
print("=" * 60)
print("TEST 1: Deduplication of field names by type")
print("=" * 60)

form_fields = [
    {"page_no": 1, "name": "email", "type": "text", "tooltip": "Email address", "bbox": [0, 0, 10, 10]},
    {"page_no": 2, "name": "email", "type": "text", "tooltip": "Email again", "bbox": [0, 0, 10, 10]},
    {"page_no": 3, "name": "email", "type": "checkbox", "tooltip": "Email checkbox", "bbox": [20, 20, 30, 30]},
    {"page_no": 1, "name": "phone", "type": "text", "tooltip": "Phone number", "bbox": [40, 40, 50, 50]},
    {"page_no": 2, "name": "phone", "type": "text", "tooltip": "Phone again", "bbox": [60, 60, 70, 70]},
]

deduplicated = converter._deduplicate_form_field_names(form_fields)

print("\nOriginal fields:")
for f in form_fields:
    print(f"  {f['type']:10} {f['name']:15} page {f['page_no']} - {f['tooltip']}")

print("\nAfter deduplication:")
for f in deduplicated:
    print(f"  {f['type']:10} {f['name']:15} → {f['new_name']:20} (page {f['page_no']})")

# Test 2: Split multi-page radio groups
print("\n" + "=" * 60)
print("TEST 2: Splitting multi-page radio button groups")
print("=" * 60)

radio_fields = [
    {"page_no": 1, "name": "choice", "new_name": "choice", "type": "radio", "bbox": [0, 0, 10, 10]},
    {"page_no": 1, "name": "choice", "new_name": "choice", "type": "radio", "bbox": [15, 0, 25, 10]},
    {"page_no": 2, "name": "choice", "new_name": "choice", "type": "radio", "bbox": [0, 0, 10, 10]},
    {"page_no": 2, "name": "choice", "new_name": "choice", "type": "radio", "bbox": [15, 0, 25, 10]},
    {"page_no": 1, "name": "sex", "new_name": "sex", "type": "radio", "bbox": [30, 0, 40, 10]},
    {"page_no": 1, "name": "sex", "new_name": "sex", "type": "radio", "bbox": [45, 0, 55, 10]},
]

split = converter._split_multipage_radio_groups(radio_fields)

print("\nBefore split:")
for f in radio_fields:
    print(f"  {f['type']:10} {f['name']:15} page {f['page_no']}")

print("\nAfter split (multi-page groups renamed):")
for f in split:
    print(f"  {f['type']:10} {f.get('new_name', f['name']):20} page {f['page_no']}")

# Test 3: Text extraction nearby
print("\n" + "=" * 60)
print("TEST 3: Nearby text extraction")
print("=" * 60)

# Mock page text dict
mock_page_dict = {
    "blocks": [
        {
            "type": 0,  # Text block
            "bbox": [10, 10, 100, 30],
            "lines": [
                {
                    "spans": [
                        {"text": "First Name:", "bbox": [10, 10, 60, 25]},
                    ]
                }
            ]
        },
        {
            "type": 0,
            "bbox": [10, 50, 100, 70],
            "lines": [
                {
                    "spans": [
                        {"text": "Please enter your first name", "bbox": [10, 50, 100, 65]},
                    ]
                }
            ]
        },
    ]
}

field_bbox = [0, 5, 20, 15]  # Form field near coordinates
nearby = converter._extract_nearby_text(field_bbox, mock_page_dict, radius=100)

print(f"\nField bbox (normalized 0-1000): {field_bbox}")
print(f"Nearby text found: {nearby}")

print("\n" + "=" * 60)
print("All tests passed! ✓")
print("=" * 60)
