# -*- coding: utf-8 -*-
"""Web UI resources for the PDF Tagger Agent web interface."""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Matterhorn PDF Tools</title>
  <style>
    :root {
      --bg: #0b1020;
      --panel: #121a31;
      --panel-2: #0f172c;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --accent-2: #06b6d4;
      --ok: #22c55e;
      --err: #ef4444;
      --line: #233253;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Segoe UI, Arial, sans-serif;
      color: var(--text);
      background: radial-gradient(1200px 600px at 10% -20%, #1d2a4a 0%, transparent 70%),
                  radial-gradient(1200px 600px at 90% -20%, #11394c 0%, transparent 70%),
                  var(--bg);
      min-height: 100vh;
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: grid;
      grid-template-columns: 220px 1fr 160px;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(11, 16, 32, 0.9);
      backdrop-filter: blur(8px);
    }

    .brand { font-weight: 700; }

    .file-pill {
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 8px 10px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
    }

    .file-pill button {
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
      border: 0;
      color: white;
      border-radius: 8px;
      padding: 6px 10px;
      cursor: pointer;
      font-weight: 600;
    }

    .file-pill span {
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .status { justify-self: end; color: #86efac; font-size: 13px; }

    .tabs {
      display: flex;
      gap: 8px;
      padding: 10px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(15, 23, 44, 0.75);
      position: sticky;
      top: 67px;
      z-index: 10;
    }

    .tab {
      background: transparent;
      border: 1px solid var(--line);
      color: var(--muted);
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
    }

    .tab.active {
      color: white;
      border-color: #36558a;
      background: #182746;
    }

    .view { display: none; padding: 16px; }
    .view.active { display: block; }

    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    .card {
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 16px;
    }

    .title { margin: 0 0 10px 0; font-size: 16px; }
    .muted { color: var(--muted); font-size: 13px; }

    label { display: block; margin: 8px 0 6px; color: var(--muted); font-size: 13px; }

    input[type=text], input[type=password], select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0b1428;
      color: var(--text);
      padding: 8px 10px;
    }

    textarea { min-height: 200px; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

    .btn {
      background: #1f3b67;
      border: 1px solid #2d4f86;
      color: white;
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      margin-top: 10px;
    }

    .btn.primary { background: linear-gradient(90deg, var(--accent), var(--accent-2)); border: 0; }
    .btn.ok { background: #1c4b2c; border-color: #2f6a43; }
    .btn.err { background: #4f1f2a; border-color: #7f3142; }

    .summary {
      font-size: 13px;
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #0c152a;
      margin-top: 10px;
      white-space: pre-wrap;
    }

    .preview-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      background: #0d162c;
    }

    .preview-item.approved { border-color: #2f6a43; background: #0f2017; }
    .preview-item.rejected { border-color: #7f3142; background: #241018; opacity: 0.75; }
    .preview-controls { display: flex; gap: 8px; margin-top: 8px; }

    .terminal {
      border-top: 1px solid var(--line);
      background: #060a15;
      padding: 10px 16px;
      min-height: 100px;
      max-height: 240px;
      overflow: auto;
      font-family: Consolas, monospace;
      font-size: 12px;
      color: #cbd5e1;
      white-space: pre-wrap;
    }

    @media (max-width: 1000px) {
      .topbar { grid-template-columns: 1fr; }
      .status { justify-self: start; }
      .tabs { top: 126px; }
      .grid { grid-template-columns: 1fr; }
      .row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand">Matterhorn PDF Tools</div>
    <div class="file-pill">
      <input id="globalFileInput" type="file" accept="application/pdf" style="display:none" />
      <button onclick="document.getElementById('globalFileInput').click()">Select PDF</button>
      <span id="globalFileLabel">No file selected</span>
    </div>
    <div class="status">Server Online</div>
  </div>

  <div class="tabs">
    <button class="tab active" data-tab="tagger">PDF Tagger</button>
    <button class="tab" data-tab="fields">Form Fields</button>
    <button class="tab" data-tab="semantic">Semantic Tags</button>
  </div>

  <div id="view-tagger" class="view active">
    <div class="grid">
      <div class="card">
        <h3 class="title">Tagging Settings</h3>
        <label for="taggingEngine">Tagging Engine</label>
        <select id="taggingEngine">
          <option value="gemini">Gemini Visual AI</option>
          <option value="docling">Docling</option>
        </select>

        <div id="geminiSettings">
          <label for="geminiQualityPreset">Quality Preset</label>
          <select id="geminiQualityPreset">
            <option value="free_tier">Free Tier</option>
            <option value="balanced">Balanced</option>
            <option value="fast">Fast</option>
            <option value="high">High Accuracy</option>
          </select>
          <div class="row">
            <div>
              <label for="geminiModel">Model</label>
              <select id="geminiModel">
                <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                <option value="gemini-2.0-flash">gemini-2.0-flash</option>
              </select>
            </div>
            <div>
              <label for="geminiWorkers">Workers</label>
              <input id="geminiWorkers" type="text" value="1" />
            </div>
          </div>
          <label for="pageRanges">Page Ranges (optional)</label>
          <input id="pageRanges" type="text" placeholder="e.g. 1-5" />
          <label for="customApiKey">Custom API Key (optional)</label>
          <input id="customApiKey" type="password" placeholder="AIza..." />
        </div>

        <div id="doclingSettings" style="display:none">
          <label><input id="enrichPictureDescription" type="checkbox" /> Enrich picture descriptions</label>
        </div>

        <div class="row">
          <div>
            <label for="docTitle">Document Title</label>
            <input id="docTitle" type="text" />
          </div>
          <div>
            <label for="docLanguage">Document Language</label>
            <select id="docLanguage">
              <option value="en">English (en)</option>
              <option value="fr">French (fr)</option>
              <option value="de">German (de)</option>
              <option value="es">Spanish (es)</option>
            </select>
          </div>
        </div>

        <button id="startBtn" class="btn primary" disabled>Start Tagging</button>
        <button id="cancelBtn" class="btn err" style="display:none">Cancel</button>
      </div>

      <div class="card" id="statusCard">
        <h3 class="title">Tagging Progress</h3>
        <div id="idleState" class="muted">Select a PDF and start tagging.</div>
        <div id="activeState" style="display:none">
          <div id="taggingStatusText" style="margin-bottom:8px">Initializing...</div>
          <div class="muted" id="activeFileLabel">file.pdf</div>
          <div style="margin-top:10px;background:#0b1428;border:1px solid var(--line);border-radius:8px;height:12px">
            <div id="progressBar" style="height:100%;width:0%;background:linear-gradient(90deg,var(--accent),var(--accent-2));border-radius:8px"></div>
          </div>
          <div id="progressPercent" class="muted" style="margin-top:8px">0%</div>
          <div style="display:none"><span id="stepUpload"></span><span id="stepLayout"></span><span id="stepWidgets"></span><span id="stepCompile"></span></div>
        </div>
        <div id="downloadPanel" style="display:none;margin-top:12px">
          <div class="summary">Tagging complete.</div>
          <div id="downloadFilenameText" class="muted" style="margin-top:6px">output.pdf</div>
          <a id="downloadBtn" class="btn ok" href="#" style="display:inline-block;text-decoration:none">Download Tagged PDF</a>
        </div>
      </div>
    </div>
  </div>

  <div id="view-fields" class="view">
    <div class="card">
      <h3 class="title">Extract Form Fields</h3>
      <div class="row">
        <div>
          <button class="btn primary" onclick="extractFormFieldsFromPdf()">Extract Form Fields</button>
          <button class="btn" onclick="detectMissingFormFields()">Detect Missing Fields</button>
          <div id="extractSummary" class="summary" style="display:none"></div>
        </div>
        <div>
          <label for="dedupInput">Input JSON</label>
          <textarea id="dedupInput" placeholder="Extracted fields will be placed here"></textarea>
        </div>
      </div>
      <div style="margin-top:10px">
        <button class="btn" onclick="processDedupFields()">Deduplicate and Enrich</button>
        <button id="addDetectedFieldsBtn" class="btn primary" onclick="addDetectedFormFields()" style="display:none">Add Detected Fields</button>
        <button id="extractCopyBtn" class="btn" style="display:none" onclick="copyExtractedFields()">Copy Extracted</button>
        <button id="extractToEditorBtn" class="btn" style="display:none" onclick="useExtractedForDedup()">Use in Input</button>
      </div>
      <div id="extractOutput" style="display:none"></div>
      <div id="extractPlaceholder" class="muted" style="margin-top:8px">No extracted fields yet.</div>
      <div style="display:none"><span id="extractFieldTypes"></span><span id="extractFileName"></span><span id="extractPageCount"></span><span id="extractTotalFields"></span><input id="extractPdfFile" type="file" /></div>
    </div>

    <div class="card">
      <h3 class="title">Processed Output</h3>
      <div id="dedupSummary" class="summary" style="display:none"></div>
      <div id="dedupOutput" class="summary" style="display:none"></div>
      <div id="dedupPlaceholder" class="muted">No processing run yet.</div>
      <div style="margin-top:10px">
        <button id="dedupCopyBtn" class="btn" onclick="copyDedupOutput()" style="display:none">Copy Output</button>
        <button id="dedupPreviewBtn" class="btn" onclick="showPreviewMode()" style="display:none">Preview Changes</button>
      </div>
      <div style="display:none"><span id="summaryTotal"></span><span id="summaryDedup"></span><span id="summarySplits"></span></div>
    </div>

    <div id="previewSection" class="card" style="display:none">
      <h3 class="title">Preview and Approval</h3>
      <div class="summary">Approved: <span id="approvedCount">0</span> | Rejected: <span id="rejectedCount">0</span> | Pending: <span id="pendingCount">0</span></div>
      <div style="margin-top:10px"><button class="btn ok" onclick="approveAllChanges()">Approve All</button><button class="btn err" onclick="rejectAllChanges()">Reject All</button></div>
      <div id="previewList" style="margin-top:10px"></div>
      <button id="applyApprovedBtn" class="btn primary" onclick="applyApprovedChanges()">Apply Approved Changes</button>
    </div>
  </div>

  <div id="view-semantic" class="view">
    <div class="card">
      <h3 class="title">Semantic Tag Converter</h3>
      <p class="muted">Extract current tags, suggest semantic mappings, review, and apply to a new PDF.</p>
      <div style="margin-top:8px"><button class="btn primary" onclick="extractSemanticTags()">Extract Tags</button><button class="btn" onclick="suggestSemanticTags()">Suggest Mappings</button></div>
      <div id="tagsExtractSummary" class="muted" style="margin-top:8px"></div>
      <label style="margin-top:8px"><input id="showAllSemanticTagTypes" type="checkbox" checked /> View all tag types</label>
      <label style="margin-top:8px"><input id="structureDocumentMode" type="checkbox" /> Document structuring mode</label>
      <div id="tagMappingReview" style="display:none;margin-top:10px">
        <div class="summary">
          <div class="row">
            <div>
              <label>Mapping profile</label>
              <select id="tagProfileSelect"></select>
            </div>
            <div>
              <label>Profile name</label>
              <input id="tagProfileName" type="text" placeholder="worksheet_type_a" />
            </div>
          </div>
          <button class="btn" onclick="loadTagMappingProfile()">Load Profile</button>
          <button class="btn" onclick="saveTagMappingProfile()">Save Profile</button>
          <button class="btn err" onclick="deleteTagMappingProfile()">Delete Profile</button>
        </div>
        <div class="summary" id="tagPreviewPanel" style="display:none">
          <div><strong id="tagPreviewTitle">Tag preview</strong></div>
          <div id="tagPreviewMeta" class="muted" style="margin-top:4px"></div>
          <div id="tagPreviewSample" style="margin-top:8px"></div>
          <iframe id="tagPreviewFrame" title="PDF tag preview" style="width:100%;height:420px;border:1px solid var(--line);border-radius:8px;margin-top:10px;background:#111827"></iframe>
        </div>
        <div class="summary">
          <div class="row">
            <div>
              <label>Source tag type</label>
              <select id="bulkSourceTag"></select>
            </div>
            <div>
              <label>Convert to</label>
              <select id="bulkTargetTag"></select>
            </div>
          </div>
          <button class="btn" onclick="addBulkTagMapping()">Add Bulk Mapping</button>
        </div>
        <div id="tagMappingList"></div>
        <div style="margin-top:8px"><button class="btn" onclick="approveAllTagMappings()">Accept All</button><button class="btn primary" onclick="applyTagMappings()">Apply and Download</button></div>
      </div>
    </div>
  </div>

  <div id="terminalBody" class="terminal">[SYSTEM] Console ready.</div>

  <script>
    var selectedFile = null;
    var currentTaskId = null;
    var pollingInterval = null;
    var lastLogIndex = 0;
    var extractedPdfFile = null;
    var currentExtractedFields = null;
    var currentDetectedMissingFields = null;
    var currentProcessedFields = null;
    var approvalStatus = {};
    var editedValues = {};
    var semanticTagPdfFile = null;
    var semanticPreviewUrl = null;
    var extractedTags = null;
    var tagSuggestions = null;
    var approvedTagMappings = {};
    var initialTagMappings = {};
    var tagProfileStorageKey = 'opendataloader.semanticTagProfiles.v1';
    var availableSemanticTags = {
      Document: 'Complete document',
      Part: 'Large-scale document division',
      Art: 'Article or self-contained body of content',
      Sect: 'Section of related content',
      Div: 'Generic block-level division',
      BlockQuote: 'Block quotation',
      Caption: 'Caption for a figure, table, or other item',
      TOC: 'Table of contents',
      TOCI: 'Table of contents item',
      Index: 'Index',
      NonStruct: 'Non-structural grouping element',
      Private: 'Private/application-specific structure element',
      P: 'Paragraph text content',
      H: 'Heading with inferred level',
      H1: 'Heading level 1',
      H2: 'Heading level 2',
      H3: 'Heading level 3',
      H4: 'Heading level 4',
      H5: 'Heading level 5',
      H6: 'Heading level 6',
      L: 'List container',
      LI: 'List item',
      Lbl: 'Label for a list item or form field',
      LBody: 'List item body',
      Table: 'Table',
      THead: 'Table header row group',
      TBody: 'Table body row group',
      TFoot: 'Table footer row group',
      TR: 'Table row',
      TH: 'Table header cell',
      TD: 'Table data cell',
      Span: 'Generic inline text span',
      Quote: 'Inline quotation',
      Note: 'Note or footnote',
      Reference: 'Reference to content elsewhere',
      BibEntry: 'Bibliography entry',
      Code: 'Computer code',
      Link: 'Link',
      Annot: 'Annotation',
      Ruby: 'Ruby annotation wrapper',
      RB: 'Ruby base text',
      RT: 'Ruby annotation text',
      RP: 'Ruby punctuation',
      Warichu: 'Warichu annotation wrapper',
      WT: 'Warichu text',
      WP: 'Warichu punctuation',
      Figure: 'Image or graphic',
      Formula: 'Mathematical formula',
      Form: 'Interactive form element',
      Artifact: 'Page artifact/decorative content'
    };

    function logLine(msg) {
      var el = document.getElementById('terminalBody');
      el.textContent += "\\n" + msg;
      el.scrollTop = el.scrollHeight;
    }

    function safeSummaryValue(summary, key, fallback) {
      if (summary && typeof summary[key] !== 'undefined' && summary[key] !== null) return summary[key];
      return fallback;
    }

    function escapeHtml(value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function shouldShowAllSemanticTagTypes() {
      var input = document.getElementById('showAllSemanticTagTypes');
      return !input || input.checked;
    }

    function getUniqueExtractedTagNames() {
      var seen = {};
      var tagNames = [];
      (extractedTags || []).forEach(function (tagInfo) {
        var tagName = tagInfo.tag_name || '';
        if (!tagName || seen[tagName]) return;
        seen[tagName] = true;
        tagNames.push(tagName);
      });
      return tagNames.sort();
    }

    function getKnownSourceTagNames() {
      var seen = {};
      var tagNames = [];
      getUniqueExtractedTagNames().concat(Object.keys(availableSemanticTags)).forEach(function (tagName) {
        if (!tagName || seen[tagName]) return;
        seen[tagName] = true;
        tagNames.push(tagName);
      });
      return tagNames.sort();
    }

    function fillSelectOptions(select, values, labels, selectedValue) {
      select.innerHTML = '';
      values.forEach(function (value) {
        var option = document.createElement('option');
        option.value = value;
        option.textContent = labels && labels[value] ? value + ' - ' + labels[value] : value;
        select.appendChild(option);
      });
      if (values.indexOf(selectedValue) >= 0) {
        select.value = selectedValue;
      }
    }

    function intersectValues(left, right) {
      var rightSet = {};
      right.forEach(function (value) { rightSet[value] = true; });
      return left.filter(function (value) { return rightSet[value]; });
    }

    function getAllowedSemanticTargets(sourceTag) {
      var structuralMatches = [];
      var roleMapMatches = [];
      var allTargets = Object.keys(availableSemanticTags);
      (extractedTags || []).forEach(function (tagInfo) {
        var content = tagInfo.content || '';
        if (tagInfo.tag_name !== sourceTag || !Array.isArray(tagInfo.allowed_targets)) return;
        if (content.indexOf('RoleMap -> ') === 0) {
          roleMapMatches.push(tagInfo.allowed_targets);
        } else {
          structuralMatches.push(tagInfo.allowed_targets);
        }
      });

      var matches = structuralMatches.length ? structuralMatches : roleMapMatches;
      if (!matches.length) return allTargets;
      return matches.reduce(function (allowed, next) {
        return intersectValues(allowed, next);
      }, matches[0].slice()).filter(function (tagName) {
        return availableSemanticTags[tagName];
      });
    }

    function getScreenReaderInfo(sourceTag) {
      var roleMapInfo = null;
      var structuralInfo = null;
      (extractedTags || []).forEach(function (tagInfo) {
        var content = tagInfo.content || '';
        if (tagInfo.tag_name !== sourceTag) return;
        if (content.indexOf('RoleMap -> ') === 0 && !roleMapInfo) {
          roleMapInfo = tagInfo;
        } else if (!structuralInfo) {
          structuralInfo = tagInfo;
        }
      });
      var info = roleMapInfo || structuralInfo || {};
      var screenReaderTag = info.screen_reader_tag || getRoleMapTarget(sourceTag) || sourceTag;
      var description = info.screen_reader_description || availableSemanticTags[screenReaderTag] || 'Custom structure type';
      var kind = info.screen_reader_kind || 'custom structure tag';
      return {
        tag: screenReaderTag,
        description: description,
        kind: kind
      };
    }

    function isAllowedSemanticMapping(sourceTag, targetTag) {
      if (!targetTag || !availableSemanticTags[targetTag]) return false;
      return getAllowedSemanticTargets(sourceTag).indexOf(targetTag) >= 0;
    }

    function populateBulkTargetOptions() {
      var sourceSelect = document.getElementById('bulkSourceTag');
      var targetSelect = document.getElementById('bulkTargetTag');
      var sourceTag = sourceSelect ? sourceSelect.value : '';
      var allowedTargets = sourceTag ? getAllowedSemanticTargets(sourceTag) : Object.keys(availableSemanticTags);
      var selected = allowedTargets.indexOf('P') >= 0 ? 'P' : allowedTargets[0];
      if (!targetSelect) return;
      fillSelectOptions(targetSelect, allowedTargets, availableSemanticTags, selected);
    }

    function populateBulkMappingControls() {
      var sourceSelect = document.getElementById('bulkSourceTag');
      if (!sourceSelect) return;
      fillSelectOptions(sourceSelect, getKnownSourceTagNames(), availableSemanticTags, 'H1');
      populateBulkTargetOptions();
      sourceSelect.onchange = populateBulkTargetOptions;
    }

    function getTagProfiles() {
      try {
        return JSON.parse(localStorage.getItem(tagProfileStorageKey) || '{}');
      } catch (e) {
        return {};
      }
    }

    function setTagProfiles(profiles) {
      localStorage.setItem(tagProfileStorageKey, JSON.stringify(profiles));
    }

    function populateTagProfileSelect() {
      var select = document.getElementById('tagProfileSelect');
      var profiles = getTagProfiles();
      var names = Object.keys(profiles).sort();
      if (!select) return;
      select.innerHTML = '';
      if (!names.length) {
        var empty = document.createElement('option');
        empty.value = '';
        empty.textContent = 'No saved profiles';
        select.appendChild(empty);
        return;
      }
      names.forEach(function (name) {
        var option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        select.appendChild(option);
      });
    }

    function applyProfileMappings(profileMappings) {
      var knownSources = {};
      getKnownSourceTagNames().forEach(function (tagName) { knownSources[tagName] = true; });
      Object.keys(profileMappings || {}).forEach(function (sourceTag) {
        var targetTag = profileMappings[sourceTag];
        if (knownSources[sourceTag] && isAllowedSemanticMapping(sourceTag, targetTag)) {
          approvedTagMappings[sourceTag] = targetTag;
        }
      });
      renderTagMappingReview();
      populateBulkMappingControls();
    }

    function ensureSemanticPreviewUrl() {
      if (!semanticTagPdfFile) return '';
      if (!semanticPreviewUrl) {
        semanticPreviewUrl = URL.createObjectURL(semanticTagPdfFile);
      }
      return semanticPreviewUrl;
    }

    function getTagPreviewInfo(tagName) {
      var matches = (extractedTags || []).filter(function (tagInfo) {
        return tagInfo.tag_name === tagName;
      });
      var sample = matches.filter(function (tagInfo) {
        return (tagInfo.content || '').trim();
      })[0] || matches[0] || { tag_name: tagName, page_no: 1, content: '' };
      return {
        count: matches.length,
        pageNo: sample.page_no || 1,
        content: sample.content || '(No text sample available for this tag type.)'
      };
    }

    function rebuildTagMappingsFromCurrentState() {
      var nextMappings = {};
      var showAll = shouldShowAllSemanticTagTypes();
      var suggestionKeys = Object.keys(tagSuggestions || {});

      if (showAll) {
        getUniqueExtractedTagNames().forEach(function (tagName) {
          if (tagSuggestions && tagSuggestions[tagName]) {
            nextMappings[tagName] = tagSuggestions[tagName].suggested_tag;
          } else if (approvedTagMappings[tagName]) {
            nextMappings[tagName] = approvedTagMappings[tagName];
          } else {
            nextMappings[tagName] = getDefaultSemanticMapping(tagName);
          }
        });
      } else {
        suggestionKeys.forEach(function (oldTag) {
          nextMappings[oldTag] = tagSuggestions[oldTag].suggested_tag;
        });
      }

      approvedTagMappings = nextMappings;
      renderTagMappingReview();
      populateBulkMappingControls();
    }

    function getDefaultSemanticMapping(tagName) {
      var roleTarget = getRoleMapTarget(tagName);
      if (roleTarget && isAllowedSemanticMapping(tagName, roleTarget)) return roleTarget;
      if (isAllowedSemanticMapping(tagName, tagName)) return tagName;
      return '';
    }

    function getRoleMapTarget(tagName) {
      var found = '';
      (extractedTags || []).forEach(function (tagInfo) {
        var content = tagInfo.content || '';
        var target;
        if (found || tagInfo.tag_name !== tagName || content.indexOf('RoleMap -> ') !== 0) return;
        target = content.replace('RoleMap -> ', '').trim();
        if (target) found = target;
      });
      return found;
    }

    function getMappingsToApply() {
      var mappings = {};
      Object.keys(approvedTagMappings).forEach(function (sourceTag) {
        var targetTag = approvedTagMappings[sourceTag];
        if (!isAllowedSemanticMapping(sourceTag, targetTag)) return;
        if (initialTagMappings[sourceTag] === targetTag) return;
        mappings[sourceTag] = targetTag;
      });
      return mappings;
    }

    function getRequiredFile() {
      if (!selectedFile) {
        alert('Select a PDF from the top bar first.');
        return null;
      }
      return selectedFile;
    }

    function switchView(name) {
      var views = document.querySelectorAll('.view');
      var tabs = document.querySelectorAll('.tab');
      var i;
      for (i = 0; i < views.length; i++) views[i].classList.remove('active');
      for (i = 0; i < tabs.length; i++) tabs[i].classList.remove('active');
      document.getElementById('view-' + name).classList.add('active');
      document.querySelector('.tab[data-tab="' + name + '"]').classList.add('active');
    }

    (function () {
      var tabs = document.querySelectorAll('.tab');
      var i;
      for (i = 0; i < tabs.length; i++) {
        (function (tab) {
          tab.addEventListener('click', function () { switchView(tab.getAttribute('data-tab')); });
        })(tabs[i]);
      }
    })();

    document.getElementById('globalFileInput').addEventListener('change', function (e) {
      var file = e.target.files[0];
      if (!file) return;
      if (file.type !== 'application/pdf') {
        alert('Only PDF files are supported.');
        return;
      }
      selectedFile = file;
      extractedPdfFile = file;
      semanticTagPdfFile = file;
      if (semanticPreviewUrl) {
        URL.revokeObjectURL(semanticPreviewUrl);
        semanticPreviewUrl = null;
      }
      document.getElementById('globalFileLabel').textContent = file.name;
      document.getElementById('startBtn').disabled = false;
      logLine('[SYSTEM] Selected file: ' + file.name);
    });

    document.getElementById('taggingEngine').addEventListener('change', function (e) {
      var isGemini = e.target.value === 'gemini';
      document.getElementById('geminiSettings').style.display = isGemini ? 'block' : 'none';
      document.getElementById('doclingSettings').style.display = isGemini ? 'none' : 'block';
    });

    document.getElementById('showAllSemanticTagTypes').addEventListener('change', function () {
      rebuildTagMappingsFromCurrentState();
    });
    populateTagProfileSelect();

    document.getElementById('startBtn').addEventListener('click', function () {
      var file = getRequiredFile();
      var formData, pageRanges, customApiKey, docTitle, docLanguage;
      if (!file) return;

      formData = new FormData();
      formData.append('file', file);
      formData.append('engine', document.getElementById('taggingEngine').value);
      formData.append('model', document.getElementById('geminiModel').value);
      formData.append('workers', document.getElementById('geminiWorkers').value || '1');

      pageRanges = document.getElementById('pageRanges').value.trim();
      if (pageRanges) formData.append('page_ranges', pageRanges);

      customApiKey = document.getElementById('customApiKey').value.trim();
      if (customApiKey) formData.append('custom_api_key', customApiKey);

      docTitle = document.getElementById('docTitle').value.trim();
      docLanguage = document.getElementById('docLanguage').value;
      if (docTitle) formData.append('title', docTitle);
      if (docLanguage) formData.append('language', docLanguage);

      document.getElementById('idleState').style.display = 'none';
      document.getElementById('activeState').style.display = 'block';
      document.getElementById('cancelBtn').style.display = 'inline-block';
      document.getElementById('taggingStatusText').textContent = 'Starting task...';
      document.getElementById('activeFileLabel').textContent = file.name;

      fetch('/v1/agent/tag', { method: 'POST', body: formData })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok) throw new Error(result.data.detail || 'Failed to start task');
          currentTaskId = result.data.task_id;
          logLine('[SYSTEM] Task started: ' + currentTaskId);
          if (pollingInterval) clearInterval(pollingInterval);
          pollingInterval = setInterval(pollTaskStatus, 1000);
        })
        .catch(function (err) {
          alert(err.message);
          logLine('[ERROR] ' + err.message);
        });
    });

    document.getElementById('cancelBtn').addEventListener('click', function () {
      if (!currentTaskId) return;
      fetch('/v1/agent/tasks/' + currentTaskId + '/cancel', { method: 'POST' });
      logLine('[SYSTEM] Cancel requested.');
    });

    function pollTaskStatus() {
      if (!currentTaskId) return;
      fetch('/v1/agent/tasks/' + currentTaskId + '/status?since=' + lastLogIndex)
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          var progress, name;
          if (!result.ok) throw new Error(data.detail || 'Polling failed');

          (data.logs || []).forEach(function (line) { logLine(line); });
          lastLogIndex += (data.logs || []).length;

          progress = data.progress || 0;
          document.getElementById('progressBar').style.width = progress + '%';
          document.getElementById('progressPercent').textContent = progress + '%';
          document.getElementById('taggingStatusText').textContent = data.current_action || data.status || 'Processing';

          if (data.status === 'completed') {
            clearInterval(pollingInterval);
            pollingInterval = null;
            document.getElementById('activeState').style.display = 'none';
            document.getElementById('downloadPanel').style.display = 'block';
            document.getElementById('downloadBtn').href = data.output_url || '#';
            name = (selectedFile && selectedFile.name ? selectedFile.name : 'output').replace('.pdf', '_tagged.pdf');
            document.getElementById('downloadFilenameText').textContent = name;
            logLine('[SYSTEM] Tagging completed.');
          }

          if (data.status === 'failed' || data.status === 'cancelled') {
            clearInterval(pollingInterval);
            pollingInterval = null;
            document.getElementById('taggingStatusText').textContent = data.status;
            logLine('[SYSTEM] Task ended with status: ' + data.status);
          }
        })
        .catch(function (err) { logLine('[ERROR] ' + err.message); });
    }

    window.extractFormFieldsFromPdf = function () {
      var file = getRequiredFile();
      var formData;
      if (!file) return;
      formData = new FormData();
      formData.append('file', file);

      fetch('/v1/agent/extract-form-fields', { method: 'POST', body: formData })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          if (!result.ok) throw new Error(data.detail || 'Extraction failed');

          currentExtractedFields = data.form_fields || [];
          document.getElementById('dedupInput').value = JSON.stringify({ form_fields: currentExtractedFields }, null, 2);
          document.getElementById('extractSummary').style.display = 'block';
          document.getElementById('extractSummary').textContent =
            'Total fields: ' + safeSummaryValue(data.summary, 'total_fields', currentExtractedFields.length) +
            '\\nPage count: ' + safeSummaryValue(data.summary, 'page_count', '-');
          document.getElementById('extractCopyBtn').style.display = 'inline-block';
          document.getElementById('extractToEditorBtn').style.display = 'inline-block';
          document.getElementById('extractPlaceholder').style.display = 'none';
        })
        .catch(function (err) { alert(err.message); });
    };

    window.copyExtractedFields = function () {
      if (!currentExtractedFields) return;
      navigator.clipboard.writeText(JSON.stringify({ form_fields: currentExtractedFields }, null, 2));
      alert('Copied.');
    };

    window.detectMissingFormFields = function () {
      var file = getRequiredFile();
      var formData;
      var customApiKey;
      if (!file) return;
      customApiKey = document.getElementById('apiKey').value.trim();
      formData = new FormData();
      formData.append('file', file);
      if (customApiKey) formData.append('api_key', customApiKey);

      fetch('/v1/agent/detect-missing-form-fields', { method: 'POST', body: formData })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          if (!result.ok) throw new Error(data.detail || 'Detection failed');

          currentDetectedMissingFields = data.form_fields || [];
          document.getElementById('dedupInput').value = JSON.stringify({ form_fields: currentDetectedMissingFields }, null, 2);
          document.getElementById('extractSummary').style.display = 'block';
          document.getElementById('extractSummary').textContent =
            'Detected missing fields: ' + safeSummaryValue(data.summary, 'detected_fields', currentDetectedMissingFields.length) +
            '\\nPages scanned: ' + safeSummaryValue(data.summary, 'pages_scanned', '-');
          document.getElementById('addDetectedFieldsBtn').style.display = currentDetectedMissingFields.length ? 'inline-block' : 'none';
          document.getElementById('extractPlaceholder').style.display = 'none';
        })
        .catch(function (err) { alert(err.message); });
    };

    window.addDetectedFormFields = function () {
      var file = getRequiredFile();
      var payload;
      var formFields;
      var formData;
      var addResult = { added: 0, skipped: 0 };
      if (!file) return;
      try {
        payload = JSON.parse(document.getElementById('dedupInput').value || '{}');
      } catch (e) {
        alert('Input JSON is invalid.');
        return;
      }
      formFields = Array.isArray(payload) ? payload : (payload.form_fields || []);
      if (!formFields.length) {
        alert('No detected fields to add.');
        return;
      }

      formData = new FormData();
      formData.append('file', file);
      formData.append('fields_json', JSON.stringify({ form_fields: formFields }));

      fetch('/v1/agent/add-form-fields', { method: 'POST', body: formData })
        .then(function (res) {
          addResult.added = parseInt(res.headers.get('X-Fields-Added') || '0', 10);
          addResult.skipped = parseInt(res.headers.get('X-Fields-Skipped') || '0', 10);
          if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Failed to add fields'); });
          return res.blob();
        })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = file.name.replace('.pdf', '_with_fields.pdf');
          a.click();
          URL.revokeObjectURL(url);
          alert('Added ' + addResult.added + ' field(s).' + (addResult.skipped ? '\\nSkipped ' + addResult.skipped + ' field(s).' : ''));
        })
        .catch(function (err) { alert(err.message); });
    };

    window.useExtractedForDedup = function () {
      if (!currentExtractedFields) return;
      document.getElementById('dedupInput').value = JSON.stringify({ form_fields: currentExtractedFields }, null, 2);
    };

    window.processDedupFields = function () {
      var payload, formFields;
      try {
        payload = JSON.parse(document.getElementById('dedupInput').value || '{}');
      } catch (e) {
        alert('Input JSON is invalid.');
        return;
      }

      formFields = Array.isArray(payload) ? payload : (payload.form_fields || []);
      fetch('/v1/agent/deduplicate-fields', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ form_fields: formFields })
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          if (!result.ok) throw new Error(data.detail || 'Processing failed');

          currentProcessedFields = data.form_fields || [];
          document.getElementById('dedupSummary').style.display = 'block';
          document.getElementById('dedupSummary').textContent =
            'Total fields: ' + safeSummaryValue(data.summary, 'total_fields', currentProcessedFields.length) +
            '\\nDedup applied: ' + (data.summary && data.summary.deduplication_applied ? 'Yes' : 'No') +
            '\\nMulti-page radio splits: ' + safeSummaryValue(data.summary, 'multipage_splits', 0);
          document.getElementById('dedupOutput').style.display = 'block';
          document.getElementById('dedupOutput').textContent = JSON.stringify({ form_fields: currentProcessedFields }, null, 2);
          document.getElementById('dedupPlaceholder').style.display = 'none';
          document.getElementById('dedupCopyBtn').style.display = 'inline-block';
          document.getElementById('dedupPreviewBtn').style.display = 'inline-block';
        })
        .catch(function (err) { alert(err.message); });
    };

    window.copyDedupOutput = function () {
      var out = document.getElementById('dedupOutput').textContent;
      if (!out) return;
      navigator.clipboard.writeText(out);
      alert('Copied.');
    };

    window.showPreviewMode = function () {
      if (!currentProcessedFields || !currentProcessedFields.length) {
        alert('No processed fields to preview.');
        return;
      }
      approvalStatus = {};
      editedValues = {};
      currentProcessedFields.forEach(function (f, i) {
        approvalStatus[i] = null;
        editedValues[i] = { tooltip: f.tooltip || '' };
      });

      document.getElementById('previewList').innerHTML = currentProcessedFields.map(function (field, idx) {
        var previousName = field.original_name || field.name || '';
        var nextName = field.new_name || field.name || '';
        var previous = typeof field.original_tooltip === 'string' ? field.original_tooltip : (field.tooltip || '');
        var next = field.tooltip || '';
        var nameLine = escapeHtml(previousName);
        if (nextName && nextName !== previousName) {
          nameLine += ' -> ' + escapeHtml(nextName);
        }
        return '<div class="preview-item" id="preview-' + idx + '">' +
               '<div><strong>' + escapeHtml(field.type || 'field') + '</strong> | Page ' + escapeHtml(field.page_no || '?') + ' | ' + nameLine + '</div>' +
               '<div class="muted">Existing tooltip: ' + escapeHtml(previous || '(No tooltip)') + '</div>' +
               '<div>Proposed tooltip: <span id="tooltip-display-' + idx + '">' + escapeHtml(next || '(No tooltip change)') + '</span></div>' +
               '<textarea id="tooltip-edit-' + idx + '" style="display:none;margin-top:6px">' + escapeHtml(next) + '</textarea>' +
               '<div class="preview-controls">' +
               '<button class="btn ok" onclick="approveField(' + idx + ')">Approve</button>' +
               '<button class="btn" onclick="editField(' + idx + ', this)">Edit</button>' +
               '<button class="btn err" onclick="rejectField(' + idx + ')">Reject</button>' +
               '</div></div>';
      }).join('');

      document.getElementById('previewSection').style.display = 'block';
      updateChangeCount();
    };

    window.approveField = function (idx) { approvalStatus[idx] = 'approved'; updateFieldPreview(idx); updateChangeCount(); };
    window.rejectField = function (idx) { approvalStatus[idx] = 'rejected'; updateFieldPreview(idx); updateChangeCount(); };

    window.editField = function (idx, btn) {
      var display = document.getElementById('tooltip-display-' + idx);
      var edit = document.getElementById('tooltip-edit-' + idx);
      var v;
      if (edit.style.display === 'none') {
        edit.style.display = 'block';
        display.style.display = 'none';
        btn.textContent = 'Save';
      } else {
        v = edit.value.trim();
        if (!v) return;
        editedValues[idx].tooltip = v;
        display.textContent = v;
        display.style.display = 'inline';
        edit.style.display = 'none';
        btn.textContent = 'Edit';
        approvalStatus[idx] = 'approved';
        updateFieldPreview(idx);
        updateChangeCount();
      }
    };

    window.updateFieldPreview = function (idx) {
      var el = document.getElementById('preview-' + idx);
      if (!el) return;
      el.classList.remove('approved');
      el.classList.remove('rejected');
      if (approvalStatus[idx] === 'approved') el.classList.add('approved');
      if (approvalStatus[idx] === 'rejected') el.classList.add('rejected');
    };

    window.updateChangeCount = function () {
      var approved = 0, rejected = 0, pending = 0;
      Object.keys(approvalStatus).forEach(function (k) {
        if (approvalStatus[k] === 'approved') approved += 1;
        else if (approvalStatus[k] === 'rejected') rejected += 1;
        else pending += 1;
      });
      document.getElementById('approvedCount').textContent = approved;
      document.getElementById('rejectedCount').textContent = rejected;
      document.getElementById('pendingCount').textContent = pending;
    };

    window.approveAllChanges = function () {
      Object.keys(approvalStatus).forEach(function (k) { approvalStatus[k] = 'approved'; updateFieldPreview(k); });
      updateChangeCount();
    };

    window.rejectAllChanges = function () {
      Object.keys(approvalStatus).forEach(function (k) { approvalStatus[k] = 'rejected'; updateFieldPreview(k); });
      updateChangeCount();
    };

    window.applyApprovedChanges = function () {
      var file = extractedPdfFile;
      var approvedFields;
      var formData;
      if (!file) {
        alert('No selected PDF.');
        return;
      }
      approvedFields = currentProcessedFields.filter(function (f, idx) {
        if (approvalStatus[idx] === 'approved') {
          f.tooltip = editedValues[idx].tooltip;
          return true;
        }
        return false;
      });
      if (!approvedFields.length) {
        alert('No approved changes to apply.');
        return;
      }

      formData = new FormData();
      formData.append('file', file);
      formData.append('enriched_json', JSON.stringify({ form_fields: approvedFields }));

      fetch('/v1/agent/apply-and-save-fields', { method: 'POST', body: formData })
        .then(function (res) {
          if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Failed to apply changes'); });
          return res.blob();
        })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = file.name.replace('.pdf', '_updated.pdf');
          a.click();
          URL.revokeObjectURL(url);
        })
        .catch(function (err) { alert(err.message); });
    };

    window.extractSemanticTags = function () {
      var file = getRequiredFile();
      var formData;
      if (!file) return;
      semanticTagPdfFile = file;

      formData = new FormData();
      formData.append('file', file);

      fetch('/v1/agent/extract-tags', { method: 'POST', body: formData })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          if (!result.ok) throw new Error(data.detail || 'Failed to extract tags');
          extractedTags = data.tags || [];
          availableSemanticTags = data.available_pdf_ua_tags || availableSemanticTags;
          document.getElementById('tagsExtractSummary').textContent =
            'Total tags: ' + safeSummaryValue(data.summary, 'total_tags', extractedTags.length) +
            ' | Unique types: ' + safeSummaryValue(data.summary, 'unique_tag_types', '-');
          initializeTagMappingsFromExtractedTags();
          populateBulkMappingControls();
          document.getElementById('tagMappingReview').style.display = 'block';
        })
        .catch(function (err) { alert(err.message); });
    };

    window.suggestSemanticTags = function () {
      if (!extractedTags || !extractedTags.length) {
        alert('Extract tags first.');
        return;
      }
      fetch('/v1/agent/suggest-tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: extractedTags })
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          var data = result.data;
          if (!result.ok) throw new Error(data.detail || 'Failed to suggest tags');

          tagSuggestions = data.suggestions || {};
          availableSemanticTags = data.available_pdf_ua_tags || availableSemanticTags;
          approvedTagMappings = {};
          Object.keys(tagSuggestions).forEach(function (oldTag) {
            approvedTagMappings[oldTag] = tagSuggestions[oldTag].suggested_tag;
          });
          if (shouldShowAllSemanticTagTypes()) {
            getUniqueExtractedTagNames().forEach(function (tagName) {
              if (!approvedTagMappings[tagName]) {
                approvedTagMappings[tagName] = getDefaultSemanticMapping(tagName);
              }
            });
          }
          initialTagMappings = Object.assign({}, approvedTagMappings);

          renderTagMappingReview();
          populateBulkMappingControls();
          document.getElementById('tagMappingReview').style.display = 'block';
        })
        .catch(function (err) { alert(err.message); });
    };

    window.initializeTagMappingsFromExtractedTags = function () {
      approvedTagMappings = {};
      getUniqueExtractedTagNames().forEach(function (tagName) {
        approvedTagMappings[tagName] = getDefaultSemanticMapping(tagName);
      });
      initialTagMappings = Object.assign({}, approvedTagMappings);
      renderTagMappingReview();
      populateBulkMappingControls();
      populateTagProfileSelect();
    };

    window.saveTagMappingProfile = function () {
      var nameInput = document.getElementById('tagProfileName');
      var profileName = (nameInput.value || '').trim();
      var profiles;
      var mappingsToSave = getMappingsToApply();
      if (!profileName) {
        alert('Enter a profile name.');
        return;
      }
      if (!Object.keys(mappingsToSave).length) {
        alert('No mappings to save.');
        return;
      }
      profiles = getTagProfiles();
      profiles[profileName] = {
        mappings: mappingsToSave,
        saved_at: new Date().toISOString()
      };
      setTagProfiles(profiles);
      populateTagProfileSelect();
      document.getElementById('tagProfileSelect').value = profileName;
      alert('Saved mapping profile: ' + profileName);
    };

    window.loadTagMappingProfile = function () {
      var select = document.getElementById('tagProfileSelect');
      var profileName = select ? select.value : '';
      var profile = getTagProfiles()[profileName];
      if (!profileName || !profile) {
        alert('Choose a saved profile.');
        return;
      }
      applyProfileMappings(profile.mappings || {});
      document.getElementById('tagProfileName').value = profileName;
    };

    window.deleteTagMappingProfile = function () {
      var select = document.getElementById('tagProfileSelect');
      var profileName = select ? select.value : '';
      var profiles = getTagProfiles();
      if (!profileName || !profiles[profileName]) {
        alert('Choose a saved profile.');
        return;
      }
      delete profiles[profileName];
      setTagProfiles(profiles);
      populateTagProfileSelect();
      document.getElementById('tagProfileName').value = '';
    };

    window.renderTagMappingReview = function () {
      var container = document.getElementById('tagMappingList');
      container.innerHTML = '';

      Object.keys(approvedTagMappings).forEach(function (oldTag) {
        var row = document.createElement('div');
        var select = document.createElement('select');
        var previewBtn = document.createElement('button');
        var removeBtn = document.createElement('button');
        var title = document.createElement('div');
        var optionKeys = getAllowedSemanticTargets(oldTag);
        var screenReaderInfo = getScreenReaderInfo(oldTag);

        row.className = 'summary';
        row.style.marginBottom = '8px';
        title.innerHTML = '<strong>' + escapeHtml(oldTag) + '</strong>' +
          '<div class="muted">Screen reader: ' + escapeHtml(screenReaderInfo.tag) +
          ' - ' + escapeHtml(screenReaderInfo.description) +
          ' (' + escapeHtml(screenReaderInfo.kind) + ')</div>';

        select.style.width = '260px';
        select.style.marginRight = '8px';
        var noChangeOption = document.createElement('option');
        noChangeOption.value = '';
        noChangeOption.textContent = 'No conversion';
        select.appendChild(noChangeOption);
        optionKeys.forEach(function (tagName) {
          var option = document.createElement('option');
          option.value = tagName;
          option.textContent = tagName + ' - ' + availableSemanticTags[tagName];
          select.appendChild(option);
        });
        select.value = isAllowedSemanticMapping(oldTag, approvedTagMappings[oldTag]) ? approvedTagMappings[oldTag] : '';
        approvedTagMappings[oldTag] = select.value;
        select.addEventListener('change', function () { approvedTagMappings[oldTag] = select.value; });

        removeBtn.className = 'btn err';
        removeBtn.textContent = 'Remove';
        removeBtn.addEventListener('click', function () { deleteTagMapping(oldTag); });

        row.appendChild(title);
        row.appendChild(select);
        previewBtn.className = 'btn';
        previewBtn.textContent = 'Preview';
        previewBtn.addEventListener('click', function () { previewTagType(oldTag); });
        row.appendChild(previewBtn);
        row.appendChild(removeBtn);
        container.appendChild(row);
      });

      if (!Object.keys(approvedTagMappings).length) {
        container.innerHTML = '<div class="muted">No mappings.</div>';
      }
    };

    window.previewTagType = function (tagName) {
      var panel = document.getElementById('tagPreviewPanel');
      var title = document.getElementById('tagPreviewTitle');
      var meta = document.getElementById('tagPreviewMeta');
      var sample = document.getElementById('tagPreviewSample');
      var frame = document.getElementById('tagPreviewFrame');
      var preview = getTagPreviewInfo(tagName);
      var pdfUrl = ensureSemanticPreviewUrl();

      panel.style.display = 'block';
      title.textContent = tagName + ' preview';
      meta.textContent = 'Count: ' + preview.count + ' | Sample page: ' + preview.pageNo;
      sample.textContent = preview.content;
      if (pdfUrl) {
        frame.src = pdfUrl + '#page=' + preview.pageNo;
      }
    };

    window.addBulkTagMapping = function () {
      var sourceSelect = document.getElementById('bulkSourceTag');
      var targetSelect = document.getElementById('bulkTargetTag');
      var sourceTag = sourceSelect ? sourceSelect.value : '';
      var targetTag = targetSelect ? targetSelect.value : 'P';
      if (!sourceTag || !targetTag) {
        alert('Choose a source and target tag type.');
        return;
      }
      if (!isAllowedSemanticMapping(sourceTag, targetTag)) {
        alert('That target tag is not compatible with the selected source tag structure.');
        return;
      }
      approvedTagMappings[sourceTag] = targetTag;
      renderTagMappingReview();
    };

    window.deleteTagMapping = function (oldTag) {
      delete approvedTagMappings[oldTag];
      renderTagMappingReview();
    };

    window.approveAllTagMappings = function () {
      alert('All current mappings are ready to apply.');
    };

    window.applyTagMappings = function () {
      var formData;
      var mappingsToApply;
      var applyResult = { applied: 0, requested: 0, structured: false, pageContainers: 0, formFieldsTagged: 0 };
      if (!semanticTagPdfFile) {
        alert('No selected PDF.');
        return;
      }
      mappingsToApply = getMappingsToApply();
      if (!Object.keys(mappingsToApply).length) {
        alert('No changed mappings to apply. Choose a source tag conversion or load a profile first.');
        return;
      }

      formData = new FormData();
      formData.append('file', semanticTagPdfFile);
      formData.append('tag_mappings', JSON.stringify(mappingsToApply));
      formData.append('restructure_document', document.getElementById('structureDocumentMode').checked ? 'true' : 'false');

      fetch('/v1/agent/apply-tags', { method: 'POST', body: formData })
        .then(function (res) {
          applyResult.applied = parseInt(res.headers.get('X-Applied-Count') || '0', 10);
          applyResult.requested = parseInt(res.headers.get('X-Mapping-Count') || '0', 10);
          applyResult.structured = res.headers.get('X-Document-Structured') === 'true';
          applyResult.pageContainers = parseInt(res.headers.get('X-Page-Containers') || '0', 10);
          applyResult.formFieldsTagged = parseInt(res.headers.get('X-Form-Fields-Tagged') || '0', 10);
          applyResult.rejected = parseInt(res.headers.get('X-Rejected-Mapping-Count') || '0', 10);
          if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Failed to apply tags'); });
          return res.blob();
        })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = semanticTagPdfFile.name.replace('.pdf', '_tagged.pdf');
          a.click();
          URL.revokeObjectURL(url);

          if (applyResult.requested > 0 && applyResult.applied === 0) {
            alert('No structure tags were updated. Try mapping custom tags (e.g. Story, Span, Figure) to semantic PDF/UA tags and re-apply.');
          } else {
            alert(
              'Applied ' + applyResult.applied + ' tag update(s).' +
              (applyResult.rejected ? '\\nSkipped ' + applyResult.rejected + ' unsafe mapping(s).' : '') +
              (applyResult.structured ? '\\nDocument structure: ' + applyResult.pageContainers + ' page container(s), ' + applyResult.formFieldsTagged + ' form field(s) tagged.' : '')
            );
          }
        })
        .catch(function (err) { alert(err.message); });
    };
  </script>
</body>
</html>
"""
