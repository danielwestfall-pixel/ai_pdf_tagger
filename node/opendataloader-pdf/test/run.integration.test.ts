import { describe, it, expect } from 'vitest';
import { run, convert } from '../src/index';
import * as path from 'path';
import * as fs from 'fs';
import { getIntegrationPaths } from './helpers/integrationPaths';
import { useTempDirLifecycle } from './helpers/tempDirLifecycle';

const { inputPdf, tempDir } = getIntegrationPaths(import.meta.url, 'run');

useTempDirLifecycle(tempDir);

describe('opendataloader-pdf', () => {
  it('should process PDF and generate markdown output', async () => {
    console.log(`[TEST] Running opendataloader-pdf test...`);
    console.log(`[TEST] Input PDF: ${inputPdf}`);
    console.log(`[TEST] Output directory: ${tempDir}`);

    await run(inputPdf, {
      outputFolder: tempDir,
      generateMarkdown: true,
      generateHtml: true,
      generateAnnotatedPdf: true,
      debug: true,
    });

    expect(fs.existsSync(path.join(tempDir, '1901.03003.json'))).toBe(true);
    expect(fs.existsSync(path.join(tempDir, '1901.03003.md'))).toBe(true);
    expect(fs.existsSync(path.join(tempDir, '1901.03003.html'))).toBe(true);
    expect(fs.existsSync(path.join(tempDir, '1901.03003_annotated.pdf'))).toBe(true);
  }, 30000); // 30 second timeout for this test

  it('should convert PDF with explicit formats using quiet mode', async () => {
    const convertDir = path.join(tempDir, 'convert');
    if (fs.existsSync(convertDir)) {
      fs.rmSync(convertDir, { recursive: true, force: true });
    }
    fs.mkdirSync(convertDir);

    await convert([inputPdf], {
      outputDir: convertDir,
      format: ['json', 'text', 'html', 'pdf', 'markdown'],
    });

    expect(fs.existsSync(path.join(convertDir, '1901.03003.json'))).toBe(true);
    expect(fs.existsSync(path.join(convertDir, '1901.03003.txt'))).toBe(true);
    expect(fs.existsSync(path.join(convertDir, '1901.03003.html'))).toBe(true);
    expect(fs.existsSync(path.join(convertDir, '1901.03003.md'))).toBe(true);
    expect(fs.existsSync(path.join(convertDir, '1901.03003_annotated.pdf'))).toBe(true);
  }, 30000);
});
