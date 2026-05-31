# -*- coding: utf-8 -*-
"""Web UI resources for the PDF Tagger Agent web interface."""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Matterhorn AI Tagger</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #080c16;
            --panel-bg: rgba(13, 20, 38, 0.6);
            --panel-border: rgba(255, 255, 255, 0.07);
            --primary-glow: rgba(99, 102, 241, 0.12);
            --secondary-glow: rgba(168, 85, 247, 0.12);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-primary: #6366f1;
            --accent-primary-glow: rgba(99, 102, 241, 0.4);
            --accent-secondary: #a855f7;
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.2);
            --warning: #f59e0b;
            --danger: #ef4444;
            --font-main: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'Fira Code', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: var(--font-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow-x: hidden;
            padding: 2rem 1.5rem;
        }

        /* Ambient Glow backgrounds */
        body::before {
            content: "";
            position: absolute;
            top: -10%;
            left: -10%;
            width: 50%;
            height: 50%;
            background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%);
            z-index: -1;
            filter: blur(80px);
            pointer-events: none;
        }

        body::after {
            content: "";
            position: absolute;
            bottom: -10%;
            right: -10%;
            width: 50%;
            height: 50%;
            background: radial-gradient(circle, var(--secondary-glow) 0%, transparent 70%);
            z-index: -1;
            filter: blur(80px);
            pointer-events: none;
        }

        .container {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 2rem;
            flex-grow: 1;
        }

        /* Header styling */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--panel-border);
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
        }

        .logo-icon svg {
            width: 24px;
            height: 24px;
            fill: white;
        }

        .logo-title h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(to right, #ffffff, #c7d2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.025em;
        }

        .logo-title p {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .system-status {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .badge {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--panel-border);
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .badge-pulse {
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; box-shadow: 0 0 12px var(--success); }
            100% { transform: scale(0.9); opacity: 0.7; }
        }

        /* Glassmorphic Cards */
        .grid-layout {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }

        @media (min-width: 900px) {
            .grid-layout {
                grid-template-columns: 1.2fr 1fr;
            }
        }

        .card {
            background-color: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 1.75rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease, border-color 0.3s ease;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.12);
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #ffffff;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.75rem;
        }

        .card-title svg {
            width: 20px;
            height: 20px;
            stroke: var(--accent-primary);
        }

        /* Dropzone Styling */
        .dropzone {
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 2.5rem 1.5rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            background: rgba(255, 255, 255, 0.01);
        }

        .dropzone:hover, .dropzone.dragover {
            border-color: var(--accent-primary);
            background: rgba(99, 102, 241, 0.05);
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.1) inset;
        }

        .dropzone-icon {
            width: 60px;
            height: 60px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.3s ease;
        }

        .dropzone:hover .dropzone-icon {
            transform: translateY(-5px);
            background: rgba(99, 102, 241, 0.1);
        }

        .dropzone-icon svg {
            width: 32px;
            height: 32px;
            stroke: var(--text-secondary);
            transition: stroke 0.3s ease;
        }

        .dropzone:hover .dropzone-icon svg {
            stroke: var(--accent-primary);
        }

        .dropzone-text h3 {
            font-size: 1rem;
            font-weight: 500;
            margin-bottom: 0.25rem;
        }

        .dropzone-text p {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        /* Configuration options */
        .config-form {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        label {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-secondary);
        }

        select, input[type="text"], input[type="password"] {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.65rem 0.85rem;
            color: white;
            font-family: var(--font-main);
            font-size: 0.9rem;
            transition: all 0.3s ease;
            width: 100%;
        }

        select:focus, input[type="text"]:focus, input[type="password"]:focus {
            outline: none;
            border-color: var(--accent-primary);
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 0 10px rgba(99, 102, 241, 0.25);
        }

        /* Toggle switches */
        .toggle-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0;
        }

        .toggle-label {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }

        .toggle-label span:first-child {
            font-size: 0.9rem;
            font-weight: 500;
        }

        .toggle-label span:last-child {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(255, 255, 255, 0.1);
            transition: .3s;
            border-radius: 24px;
            border: 1px solid var(--panel-border);
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 16px;
            width: 16px;
            left: 3px;
            bottom: 3px;
            background-color: var(--text-secondary);
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--accent-primary);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
            background-color: white;
        }

        /* Action Buttons */
        .btn {
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.8rem 1.5rem;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
            filter: brightness(1.1);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn:disabled {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-muted);
            border: 1px solid var(--panel-border);
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
            filter: none;
        }

        /* Status & Progress styling */
        .status-container {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            justify-content: center;
            flex-grow: 1;
            min-height: 250px;
        }

        .progress-radial-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            gap: 1rem;
            color: var(--text-muted);
            border: 1px dashed rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 3rem 1.5rem;
        }

        .progress-radial-placeholder svg {
            width: 48px;
            height: 48px;
            stroke: rgba(255, 255, 255, 0.1);
        }

        /* Active Tagging UI */
        .active-tagging-ui {
            display: none;
            flex-direction: column;
            gap: 1.5rem;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .progress-percent {
            font-size: 2.25rem;
            font-weight: 700;
            background: linear-gradient(to right, white, var(--text-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .progress-bar-container {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.02);
        }

        .progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            box-shadow: 0 0 10px rgba(168, 85, 247, 0.5);
            border-radius: 10px;
            transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* Pipeline Steps checklist */
        .pipeline-steps {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .step-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            transition: all 0.3s ease;
        }

        .step-item.active {
            color: white;
            font-weight: 500;
        }

        .step-item.completed {
            color: var(--success);
        }

        .step-item.failed {
            color: var(--danger);
        }

        .step-icon {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 2px solid rgba(255, 255, 255, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: all 0.3s ease;
        }

        .step-item.active .step-icon {
            border-color: var(--accent-primary);
            box-shadow: 0 0 8px rgba(99, 102, 241, 0.4);
            animation: spin-pulse 1.5s linear infinite;
        }

        @keyframes spin-pulse {
            0% { transform: rotate(0deg); opacity: 0.8; }
            50% { opacity: 1; }
            100% { transform: rotate(360deg); opacity: 0.8; }
        }

        .step-item.completed .step-icon {
            border-color: var(--success);
            background-color: var(--success-glow);
        }

        .step-item.failed .step-icon {
            border-color: var(--danger);
            background-color: rgba(239, 68, 68, 0.1);
        }

        .step-icon svg {
            width: 10px;
            height: 10px;
            fill: none;
            display: none;
        }

        .step-item.completed .step-icon svg {
            display: block;
            stroke: var(--success);
            stroke-width: 3px;
        }

        .step-item.failed .step-icon svg {
            display: block;
            stroke: var(--danger);
            stroke-width: 3px;
        }

        /* Success & Download Panel */
        .download-panel {
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            gap: 1.25rem;
            padding: 1.5rem;
            background: rgba(16, 185, 129, 0.05);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 12px;
            animation: slideUp 0.4s ease-out;
        }

        @keyframes slideUp {
            from { transform: translateY(15px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .download-panel svg {
            width: 48px;
            height: 48px;
            stroke: var(--success);
        }

        .download-panel h3 {
            font-size: 1.1rem;
            color: #ffffff;
        }

        .download-panel p {
            font-size: 0.8rem;
            color: var(--text-secondary);
            max-width: 300px;
        }

        .btn-download {
            background: linear-gradient(135deg, var(--success), #059669);
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
            width: 100%;
        }

        .btn-download:hover {
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);
        }

        /* Terminal Console */
        .terminal {
            background-color: #05070e;
            border: 1px solid var(--panel-border);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            display: flex;
            flex-direction: column;
            min-height: 250px;
            max-height: 400px;
        }

        .terminal-header {
            background: rgba(255, 255, 255, 0.02);
            border-bottom: 1px solid var(--panel-border);
            padding: 0.75rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal-controls {
            display: flex;
            gap: 0.4rem;
        }

        .terminal-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .terminal-dot.red { background-color: #ff5f56; }
        .terminal-dot.yellow { background-color: #ffbd2e; }
        .terminal-dot.green { background-color: #27c93f; }

        .terminal-title {
            font-family: var(--font-mono);
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        .terminal-actions {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .terminal-action-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.25rem;
            transition: color 0.3s ease;
        }

        .terminal-action-btn:hover {
            color: var(--text-primary);
        }

        .terminal-action-btn svg {
            width: 12px;
            height: 12px;
            fill: currentColor;
        }

        .terminal-body {
            padding: 1rem;
            overflow-y: auto;
            flex-grow: 1;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            line-height: 1.5;
            color: #d1d5db;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .terminal-line {
            white-space: pre-wrap;
            word-break: break-all;
        }

        .terminal-line.info { color: #60a5fa; }
        .terminal-line.success { color: #34d399; }
        .terminal-line.warning { color: #fbbf24; }
        .terminal-line.error { color: #f87171; }
        .terminal-line.system { color: #9ca3af; }

        /* Footer */
        footer {
            margin-top: 3rem;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.03);
            padding-top: 1.5rem;
        }

        .filename-display {
            background: rgba(99, 102, 241, 0.08);
            border: 1px solid rgba(99, 102, 241, 0.2);
            padding: 0.6rem 1rem;
            border-radius: 8px;
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
        }

        .filename-text {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 80%;
            font-weight: 500;
        }

        .filename-clear {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 0.2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: background 0.3s ease;
        }

        .filename-clear:hover {
            color: var(--danger);
            background: rgba(239, 68, 68, 0.1);
        }

        .filename-clear svg {
            width: 16px;
            height: 16px;
            stroke: currentColor;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <div class="logo-icon">
                    <svg viewBox="0 0 24 24">
                        <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                    </svg>
                </div>
                <div class="logo-title">
                    <h1>Matterhorn AI</h1>
                    <p>PDF/UA Accessibility Tagger</p>
                </div>
            </div>
            <div class="system-status">
                <div class="badge">
                    <div class="badge-pulse"></div>
                    Server Online
                </div>
            </div>
        </header>

        <div class="grid-layout">
            <!-- Left Panel: Input & Config -->
            <div class="card">
                <div class="card-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    Source Document & Engine Settings
                </div>

                <!-- File Dropzone -->
                <div id="dropzone" class="dropzone">
                    <div class="dropzone-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                        </svg>
                    </div>
                    <div class="dropzone-text">
                        <h3>Drag & drop your PDF here</h3>
                        <p>Supports files up to 100+ pages</p>
                    </div>
                    <input type="file" id="fileInput" accept="application/pdf" style="display: none;">
                </div>

                <!-- Filename Display (hidden by default) -->
                <div id="filenameDisplay" class="filename-display" style="display: none;">
                    <span id="filenameText" class="filename-text">document.pdf</span>
                    <button id="filenameClearBtn" class="filename-clear" title="Remove file">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <!-- Config Parameters -->
                <div class="config-form">
                    <div class="form-group">
                        <label for="taggingEngine">Tagging Engine Mode</label>
                        <select id="taggingEngine">
                            <option value="gemini">Gemini Visual AI Agent (Recommended)</option>
                            <option value="docling">Docling Fast Layout Engine</option>
                        </select>
                    </div>

                    <!-- Gemini Specific Settings -->
                    <div id="geminiSettings" class="config-form" style="display: flex;">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="geminiModel">Model Selection</label>
                                <select id="geminiModel">
                                    <option value="gemini-2.5-flash">gemini-2.5-flash (Fast & Accurate)</option>
                                    <option value="gemini-2.0-flash">gemini-2.0-flash (Newer Model)</option>
                                    <option value="gemini-flash-latest">gemini-1.5-flash (Recommended Fallback)</option>
                                    <option value="gemini-2.5-pro">gemini-2.5-pro (Ultimate Quality)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="pageRanges">Page Range (Optional)</label>
                                <input type="text" id="pageRanges" placeholder="e.g., 1-10 or empty for all">
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="customApiKey">Custom API Key (Overrides server key)</label>
                            <input type="password" id="customApiKey" placeholder="AIzaSy...">
                        </div>
                    </div>

                    <!-- Docling Specific Settings -->
                    <div id="doclingSettings" class="config-form" style="display: none;">
                        <div class="form-group" style="flex-direction: row; align-items: center; justify-content: flex-start; gap: 10px; margin-top: 5px;">
                            <input type="checkbox" id="enrichPictureDescription" style="width: auto;">
                            <label for="enrichPictureDescription" style="margin: 0; cursor: pointer;">Enable Picture Descriptions (Generates Alt Text via Gemini)</label>
                        </div>
                    </div>

                    <!-- Common Document Settings -->
                    <div class="form-row" style="margin-top: 15px;">
                        <div class="form-group">
                                <label for="docTitle">Document Title (for PDF/UA metadata)</label>
                                <input type="text" id="docTitle" placeholder="Leave blank to auto-detect from PDF">
                            </div>
                            <div class="form-group">
                                <label for="docLanguage">Document Language (BCP 47)</label>
                                <select id="docLanguage">
                                    <option value="en">English (en)</option>
                                    <option value="fr">French (fr)</option>
                                    <option value="de">German (de)</option>
                                    <option value="es">Spanish (es)</option>
                                    <option value="it">Italian (it)</option>
                                    <option value="nl">Dutch (nl)</option>
                                    <option value="pt">Portuguese (pt)</option>
                                    <option value="ja">Japanese (ja)</option>
                                    <option value="zh">Chinese (zh)</option>
                                    <option value="ko">Korean (ko)</option>
                                    <option value="ar">Arabic (ar)</option>
                                    <option value="ru">Russian (ru)</option>
                                    <option value="pl">Polish (pl)</option>
                                    <option value="sv">Swedish (sv)</option>
                                    <option value="da">Danish (da)</option>
                                    <option value="fi">Finnish (fi)</option>
                                    <option value="nb">Norwegian (nb)</option>
                                    <option value="tr">Turkish (tr)</option>
                                    <option value="cs">Czech (cs)</option>
                                    <option value="hu">Hungarian (hu)</option>
                                    <option value="ro">Romanian (ro)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <button id="startBtn" class="btn" disabled>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:0.25rem;">
                        <path d="M5 3l14 9-14 9V3z"/>
                    </svg>
                    Tag PDF Structure
                </button>
            </div>

            <!-- Right Panel: Processing, Checklist & Download -->
            <div class="card" id="statusCard">
                <div class="card-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    Tagging Progress Status
                </div>

                <div class="status-container">
                    <!-- Idle State Placeholder -->
                    <div id="idleState" class="progress-radial-placeholder">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <polyline points="22 4 12 14.01 9 11.01"/>
                        </svg>
                        <p>Upload a document and select settings to start the automated Matterhorn tagging process.</p>
                    </div>

                    <!-- Active Tagging UI (hidden initially) -->
                    <div id="activeState" class="active-tagging-ui">
                        <div class="progress-header">
                            <div>
                                <h4 id="taggingStatusText" style="color: white; font-weight: 500;">Initializing...</h4>
                                <p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.15rem;" id="activeFileLabel">file.pdf</p>
                            </div>
                            <div class="progress-percent" id="progressPercent">0%</div>
                        </div>

                        <div class="progress-bar-container">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>

                        <!-- Checklist steps -->
                        <div class="pipeline-steps">
                            <div class="step-item" id="stepUpload">
                                <div class="step-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                </div>
                                <span>Upload and verify PDF structure</span>
                            </div>
                            <div class="step-item" id="stepLayout">
                                <div class="step-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                </div>
                                <span>Visual layout & structure analysis</span>
                            </div>
                            <div class="step-item" id="stepWidgets">
                                <div class="step-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                </div>
                                <span>Tag form fields (/T) and tooltips (/TU)</span>
                            </div>
                            <div class="step-item" id="stepCompile">
                                <div class="step-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                </div>
                                <span>Compile PDF/UA structure trees (Java)</span>
                            </div>
                        </div>
                    </div>

                    <!-- Download Panel (hidden initially) -->
                    <div id="downloadPanel" class="download-panel">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <polyline points="22 4 12 14.01 9 11.01"/>
                        </svg>
                        <div>
                            <h3>PDF Tagged Successfully!</h3>
                            <p id="downloadFilenameText">document_tagged.pdf</p>
                        </div>
                        <a id="downloadBtn" href="#" class="btn btn-download">
                            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:0.25rem;">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 3v12"/>
                            </svg>
                            Download Tagged PDF
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Terminal Logs Panel -->
        <div class="terminal">
            <div class="terminal-header">
                <div class="terminal-controls">
                    <div class="terminal-dot red"></div>
                    <div class="terminal-dot yellow"></div>
                    <div class="terminal-dot green"></div>
                </div>
                <div class="terminal-title">mhorn-tagger@agent: ~</div>
                <div class="terminal-actions">
                    <button class="terminal-action-btn" id="copyLogsBtn" title="Copy console logs">
                        <svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
                        Copy
                    </button>
                    <button class="terminal-action-btn" id="clearLogsBtn" title="Clear console">
                        Clear
                    </button>
                </div>
            </div>
            <div class="terminal-body" id="terminalBody">
                <div class="terminal-line system">Matterhorn Tagging Engine Console initialized. Waiting for task...</div>
            </div>
        </div>

        <footer>
            <p>PDF Tagger AI Agent — Powered by Hancom & Google Gemini Multimodal APIs</p>
        </footer>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const dropzone = document.getElementById('dropzone');
            const fileInput = document.getElementById('fileInput');
            const filenameDisplay = document.getElementById('filenameDisplay');
            const filenameText = document.getElementById('filenameText');
            const filenameClearBtn = document.getElementById('filenameClearBtn');
            
            const taggingEngine = document.getElementById('taggingEngine');
            const geminiSettings = document.getElementById('geminiSettings');
            const geminiModel = document.getElementById('geminiModel');
            const pageRanges = document.getElementById('pageRanges');
            const customApiKey = document.getElementById('customApiKey');
            const docTitle = document.getElementById('docTitle');
            const docLanguage = document.getElementById('docLanguage');
            
            const startBtn = document.getElementById('startBtn');
            const idleState = document.getElementById('idleState');
            const activeState = document.getElementById('activeState');
            const progressPercent = document.getElementById('progressPercent');
            const progressBar = document.getElementById('progressBar');
            const taggingStatusText = document.getElementById('taggingStatusText');
            const activeFileLabel = document.getElementById('activeFileLabel');
            
            const stepUpload = document.getElementById('stepUpload');
            const stepLayout = document.getElementById('stepLayout');
            const stepWidgets = document.getElementById('stepWidgets');
            const stepCompile = document.getElementById('stepCompile');
            
            const downloadPanel = document.getElementById('downloadPanel');
            const downloadBtn = document.getElementById('downloadBtn');
            const downloadFilenameText = document.getElementById('downloadFilenameText');
            
            const terminalBody = document.getElementById('terminalBody');
            const clearLogsBtn = document.getElementById('clearLogsBtn');
            const copyLogsBtn = document.getElementById('copyLogsBtn');

            let selectedFile = null;
            let currentTaskId = null;
            let pollingInterval = null;
            let lastLogIndex = 0;

            // Fetch server configuration on load
            fetch('/v1/agent/config')
                .then(res => res.json())
                .then(config => {
                    logLine(`[SYSTEM] Connected to FastAPI backend (Default Model: ${config.default_model || 'gemini-2.5-flash'})`, 'system');
                    if (config.has_key) {
                        logLine('[SYSTEM] Server-side Gemini API key detected.', 'success');
                    } else {
                        logLine('[WARNING] Server-side Gemini API key is missing. You will need to provide one in settings.', 'warning');
                    }
                    if (config.current_mode_agent) {
                        taggingEngine.value = 'gemini';
                    } else {
                        taggingEngine.value = 'docling';
                    }
                    toggleEngineSettings();
                })
                .catch(err => {
                    logLine(`[ERROR] Failed to check server status: ${err.message}`, 'error');
                });

            // Toggle visibility of engine settings
            const doclingSettings = document.getElementById('doclingSettings');
            taggingEngine.addEventListener('change', toggleEngineSettings);

            function toggleEngineSettings() {
                if (taggingEngine.value === 'gemini') {
                    geminiSettings.style.display = 'flex';
                    doclingSettings.style.display = 'none';
                    logLine('[SYSTEM] Engine set to Gemini Visual AI Agent.', 'info');
                } else {
                    geminiSettings.style.display = 'none';
                    doclingSettings.style.display = 'flex';
                    logLine('[SYSTEM] Engine set to Docling Fast Layout Engine.', 'info');
                }
            }

            // Drag and drop handlers
            dropzone.addEventListener('click', () => fileInput.click());
            
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                }
            });

            dropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropzone.classList.add('dragover');
            });

            dropzone.addEventListener('dragleave', () => {
                dropzone.classList.remove('dragover');
            });

            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    handleFileSelect(e.dataTransfer.files[0]);
                }
            });

            function handleFileSelect(file) {
                if (file.type !== 'application/pdf') {
                    logLine(`[ERROR] Selected file "${file.name}" is not a PDF document.`, 'error');
                    alert('Only PDF documents are supported!');
                    return;
                }
                selectedFile = file;
                filenameText.textContent = `${file.name} (${formatBytes(file.size)})`;
                dropzone.style.display = 'none';
                filenameDisplay.style.display = 'flex';
                startBtn.disabled = false;
                logLine(`[SYSTEM] Loaded PDF file: "${file.name}"`, 'success');
            }

            filenameClearBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                resetFileSelect();
            });

            function resetFileSelect() {
                selectedFile = null;
                fileInput.value = '';
                dropzone.style.display = 'flex';
                filenameDisplay.style.display = 'none';
                startBtn.disabled = true;
                logLine('[SYSTEM] Cleared selected file.', 'system');
            }

            // Start processing button handler
            startBtn.addEventListener('click', () => {
                if (!selectedFile) return;
                const docTitle = document.getElementById('docTitle').value;
                const docLanguage = document.getElementById('docLanguage').value;
                const enrichPictureDescription = document.getElementById('enrichPictureDescription').checked;
                
                const formData = new FormData();
                formData.append('file', selectedFile);
                formData.append('engine', taggingEngine.value);
                
                if (taggingEngine.value === 'gemini') {
                    formData.append('model', document.getElementById('geminiModel').value);
                    const pages = document.getElementById('pageRanges').value;
                    if (pages) formData.append('page_ranges', pages);
                    
                    const apiKey = document.getElementById('customApiKey').value;
                    if (apiKey) formData.append('custom_api_key', apiKey);
                } else {
                    if (enrichPictureDescription) {
                        formData.append('enrich_picture_description', 'true');
                    }
                }
                
                if (docLanguage) formData.append('language', docLanguage);
                if (docTitle) formData.append('title', docTitle);

                // Disable UI inputs
                startBtn.disabled = true;
                taggingEngine.disabled = true;
                geminiModel.disabled = true;
                pageRanges.disabled = true;
                customApiKey.disabled = true;
                docTitle.disabled = true;
                docLanguage.disabled = true;
                filenameClearBtn.disabled = true;

                // Show active UI
                idleState.style.display = 'none';
                downloadPanel.style.display = 'none';
                activeState.style.display = 'flex';
                activeFileLabel.textContent = selectedFile.name;
                updateProgress(5, 'Uploading PDF...');

                resetStepIndicators();
                stepUpload.classList.add('active');

                // Clear log terminal for new run
                terminalBody.innerHTML = '';
                logLine(`[SYSTEM] Initiating tagging pipeline for ${selectedFile.name}...`, 'system');

                fetch('/v1/agent/tag', {
                    method: 'POST',
                    body: formData
                })
                .then(res => {
                    if (!res.ok) {
                        return res.json().then(data => {
                            throw new Error(data.detail || 'Failed to start tagging task');
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    currentTaskId = data.task_id;
                    logLine(`[SYSTEM] Task started successfully. ID: ${currentTaskId}`, 'success');
                    
                    lastLogIndex = 0;
                    // Start polling
                    if (pollingInterval) clearInterval(pollingInterval);
                    pollingInterval = setInterval(pollTaskStatus, 1000);
                })
                .catch(err => {
                    logLine(`[ERROR] Failed to start task: ${err.message}`, 'error');
                    resetUIForNextRun();
                    taggingStatusText.textContent = 'Failed to start';
                    stepUpload.classList.remove('active');
                    stepUpload.classList.add('failed');
                });
            });

            // Poll task status
            function pollTaskStatus() {
                if (!currentTaskId) return;

                fetch(`/v1/agent/tasks/${currentTaskId}/status?since=${lastLogIndex}`)
                    .then(res => {
                        if (!res.ok) throw new Error('Polling status failed');
                        return res.json();
                    })
                    .then(data => {
                        // Append new logs
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(log => {
                                // Strip timestamp prefixes if any, colorize based on contents
                                let lineClass = 'system';
                                if (log.includes('INFO')) lineClass = 'info';
                                if (log.includes('WARNING')) lineClass = 'warning';
                                if (log.includes('ERROR') || log.includes('Exception')) lineClass = 'error';
                                if (log.includes('SUCCESS') || log.includes('Successfully')) lineClass = 'success';
                                logLine(log, lineClass);
                            });
                            lastLogIndex += data.logs.length;
                        }

                        // Update progress bar
                        updateProgress(data.progress, data.current_action || 'Processing...');

                        // Update steps based on progress and logs
                        updateStepProgress(data.progress, data.logs || []);

                        if (data.status === 'completed') {
                            clearInterval(pollingInterval);
                            handleTaskSuccess(data.output_url);
                        } else if (data.status === 'failed') {
                            clearInterval(pollingInterval);
                            handleTaskFailure(data.error || 'Unknown server error');
                        }
                    })
                    .catch(err => {
                        logLine(`[ERROR] Connection error during status poll: ${err.message}`, 'error');
                    });
            }

            function updateStepProgress(progress, logs) {
                // Determine step states based on progress and log messages
                if (progress >= 10) {
                    stepUpload.classList.remove('active');
                    stepUpload.classList.add('completed');
                }
                
                if (progress >= 20 && progress < 70) {
                    stepLayout.classList.add('active');
                } else if (progress >= 70) {
                    stepLayout.classList.remove('active');
                    stepLayout.classList.add('completed');
                }

                if (progress >= 40 && progress < 75) {
                    stepWidgets.classList.add('active');
                } else if (progress >= 75) {
                    stepWidgets.classList.remove('active');
                    stepWidgets.classList.add('completed');
                }

                if (progress >= 75 && progress < 100) {
                    stepCompile.classList.add('active');
                } else if (progress >= 100) {
                    stepCompile.classList.remove('active');
                    stepCompile.classList.add('completed');
                }
            }

            function handleTaskSuccess(outputUrl) {
                logLine('[SUCCESS] Tagging process finished successfully!', 'success');
                taggingStatusText.textContent = 'Tagging Complete!';
                updateProgress(100);

                // Set download link
                downloadBtn.href = outputUrl;
                downloadFilenameText.textContent = `${selectedFile.name.replace('.pdf', '')}_tagged.pdf`;
                
                // Show download panel
                activeState.style.display = 'none';
                downloadPanel.style.display = 'flex';

                resetUIForNextRun();
            }

            function handleTaskFailure(errorMsg) {
                logLine(`[ERROR] PDF Tagging failed: ${errorMsg}`, 'error');
                taggingStatusText.textContent = 'Tagging Failed';
                
                // Mark active step as failed
                const activeStep = document.querySelector('.step-item.active');
                if (activeStep) {
                    activeStep.classList.remove('active');
                    activeStep.classList.add('failed');
                }

                resetUIForNextRun();
            }

            function resetUIForNextRun() {
                startBtn.disabled = false;
                taggingEngine.disabled = false;
                geminiModel.disabled = false;
                pageRanges.disabled = false;
                customApiKey.disabled = false;
                docTitle.disabled = false;
                docLanguage.disabled = false;
                filenameClearBtn.disabled = false;
            }

            function resetStepIndicators() {
                [stepUpload, stepLayout, stepWidgets, stepCompile].forEach(step => {
                    step.className = 'step-item';
                });
            }

            function updateProgress(percent, statusText) {
                progressBar.style.width = `${percent}%`;
                progressPercent.textContent = `${percent}%`;
                if (statusText) {
                    taggingStatusText.textContent = statusText;
                }
            }

            // Log Console Utilities
            function logLine(text, className = '') {
                const line = document.createElement('div');
                line.className = `terminal-line ${className}`;
                line.textContent = text;
                terminalBody.appendChild(line);
                terminalBody.scrollTop = terminalBody.scrollHeight;
            }

            clearLogsBtn.addEventListener('click', () => {
                terminalBody.innerHTML = '';
                logLine('[SYSTEM] Terminal logs cleared.', 'system');
            });

            copyLogsBtn.addEventListener('click', () => {
                const text = terminalBody.innerText;
                navigator.clipboard.writeText(text)
                    .then(() => alert('Logs copied to clipboard!'))
                    .catch(err => alert('Failed to copy logs: ' + err));
            });

            // Helper to format file sizes
            function formatBytes(bytes, decimals = 2) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const dm = decimals < 0 ? 0 : decimals;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
            }
        });
    </script>
</body>
</html>
"""
