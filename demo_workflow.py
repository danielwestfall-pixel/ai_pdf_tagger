#!/usr/bin/env python3
"""
Demo: Complete Form Field Processing Workflow
1. Extract form fields from PDF
2. Deduplicate and enrich them
"""

import sys
import json
sys.path.insert(0, r"c:\Users\DanielW1814\Desktop\Gregs_Cousin\ai_pdf_tagger\python\opendataloader-pdf\src")

from opendataloader_pdf.agent import GeminiAgentConverter

def demo_complete_workflow():
    """Demonstrate the complete form field extraction and deduplication workflow"""
    
    print("\n" + "=" * 80)
    print("FORM FIELD EXTRACTION & DEDUPLICATION WORKFLOW DEMO")
    print("=" * 80)
    
    # Create converter
    converter = GeminiAgentConverter(api_key="test", model_name="gemini-2.0-flash", max_workers=1)
    
    # Simulate extracted form fields (as if from extract_form_fields_only)
    extracted_fields = [
        {"page_no": 1, "name": "email", "type": "text", "bbox": [10, 10, 100, 50], "tooltip": "Your email address"},
        {"page_no": 2, "name": "email", "type": "text", "bbox": [10, 10, 100, 50], "tooltip": "Confirm email"},
        {"page_no": 1, "name": "email", "type": "checkbox", "bbox": [10, 60, 100, 100], "tooltip": "Subscribe to newsletter"},
        {"page_no": 1, "name": "phone", "type": "text", "bbox": [10, 110, 100, 150], "tooltip": "Phone number"},
        {"page_no": 2, "name": "phone", "type": "text", "bbox": [10, 110, 100, 150], "tooltip": "Alternate phone"},
        {"page_no": 1, "name": "feedback", "type": "radio", "bbox": [50, 10, 150, 50], "tooltip": "Very satisfied"},
        {"page_no": 1, "name": "feedback", "type": "radio", "bbox": [50, 60, 150, 100], "tooltip": "Satisfied"},
        {"page_no": 2, "name": "feedback", "type": "radio", "bbox": [50, 10, 150, 50], "tooltip": "Neutral"},
        {"page_no": 2, "name": "feedback", "type": "radio", "bbox": [50, 60, 150, 100], "tooltip": "Dissatisfied"},
    ]
    
    print("\n📥 STEP 1: EXTRACTED FORM FIELDS FROM PDF")
    print("-" * 80)
    print(f"Total fields: {len(extracted_fields)}")
    for i, field in enumerate(extracted_fields, 1):
        print(f"  {i:2}. {field['type']:10} {field['name']:15} page {field['page_no']} - {field['tooltip']}")
    
    # Apply deduplication
    print("\n🔧 STEP 2: DEDUPLICATION BY TYPE")
    print("-" * 80)
    deduplicated = converter._deduplicate_form_field_names(extracted_fields)
    
    rename_count = 0
    for field in deduplicated:
        if field.get('new_name') != field.get('name'):
            print(f"  ✓ {field['type']:10} {field['name']:15} → {field['new_name']:20} (page {field['page_no']})")
            rename_count += 1
    print(f"  Total renamed: {rename_count} fields")
    
    # Apply multi-page splitting
    print("\n✂️  STEP 3: MULTI-PAGE RADIO GROUP SPLITTING")
    print("-" * 80)
    split_groups = converter._split_multipage_radio_groups(deduplicated)
    
    split_count = 0
    for field in split_groups:
        if "_page_" in field.get('new_name', ''):
            print(f"  ✓ {field['name']:15} → {field['new_name']:30} (page {field['page_no']})")
            split_count += 1
    
    if split_count > 0:
        print(f"  Total splits applied: {split_count}")
    else:
        print(f"  Radio groups properly isolated by page (deduplication handled it)")
    
    # Apply text enrichment
    print("\n📝 STEP 4: TEXT ENRICHMENT")
    print("-" * 80)
    enriched = converter._enrich_form_fields_with_text(split_groups, {})
    
    enriched_count = 0
    for field in enriched:
        if field.get('nearby_text'):
            enriched_count += 1
            nearby = ', '.join(field['nearby_text'][:2])  # Show first 2 nearby texts
            if len(field['nearby_text']) > 2:
                nearby += f", ... (+{len(field['nearby_text'])-2} more)"
            print(f"  ✓ {field['name']:15} - nearby text: {nearby}")
    
    if enriched_count == 0:
        print(f"  (No surrounding text available in demo)")
    
    print(f"  Total enriched: {enriched_count} fields")
    
    # Show final result
    print("\n✅ FINAL RESULT: Processing Complete")
    print("-" * 80)
    
    # Count field types
    type_counts = {}
    for field in enriched:
        field_type = field.get('type', 'text')
        type_counts[field_type] = type_counts.get(field_type, 0) + 1
    
    print(f"Total fields: {len(enriched)}")
    print(f"Field types: {', '.join(f'{k}({v})' for k, v in sorted(type_counts.items()))}")
    
    dedup_applied = any(f.get('new_name') != f.get('name') for f in enriched)
    splits_applied = sum(1 for f in enriched if '_page_' in f.get('new_name', ''))
    
    print(f"Deduplication applied: {'Yes' if dedup_applied else 'No'}")
    print(f"Multi-page splits: {splits_applied}")
    
    # Show a sample field with all enrichment
    print("\n📋 SAMPLE ENRICHED FIELD")
    print("-" * 80)
    sample = enriched[0]
    print(f"Original name: {sample.get('name')}")
    print(f"New name: {sample.get('new_name', sample.get('name'))}")
    print(f"Type: {sample.get('type')}")
    print(f"Page: {sample.get('page_no')}")
    print(f"Tooltip: {sample.get('tooltip')}")
    
    if sample.get('nearby_text'):
        print(f"Nearby text: {sample['nearby_text'][:3]}")
    
    if sample.get('inferred_options'):
        print(f"Inferred options: {sample['inferred_options'][:3]}")
    
    # Show API response format
    print("\n🌐 API RESPONSE FORMAT")
    print("-" * 80)
    api_response = {
        "status": "success",
        "form_fields": enriched,
        "summary": {
            "total_fields": len(enriched),
            "deduplication_applied": dedup_applied,
            "multipage_splits": splits_applied
        }
    }
    print(json.dumps(api_response, indent=2)[:800] + "\n... (truncated)")
    
    print("\n" + "=" * 80)
    print("🎉 WORKFLOW COMPLETE!")
    print("=" * 80)
    print("\nThe complete workflow is now available via the web interface:")
    print("  1. Upload PDF → Extract form fields (POST /v1/agent/extract-form-fields)")
    print("  2. Review extracted JSON in the UI")
    print("  3. Click 'Use in Deduplication Tool' to auto-populate")
    print("  4. Run deduplication & enrichment (POST /v1/agent/deduplicate-fields)")
    print("  5. Download or copy the enriched form fields")
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    demo_complete_workflow()
