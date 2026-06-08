/**
 * Integration tests that actually run the JAR (slow)
 */

import { describe, it, expect } from 'vitest';
import { convert } from '../src/index';
import * as fs from 'fs';
import * as path from 'path';
import { getIntegrationPaths } from './helpers/integrationPaths';
import { useTempDirLifecycle } from './helpers/tempDirLifecycle';

const { inputPdf, tempDir } = getIntegrationPaths(import.meta.url, 'convert');

useTempDirLifecycle(tempDir);

describe('convert() integration', () => {
  it('should generate output file', async () => {
    await convert(inputPdf, {
      outputDir: tempDir,
      format: 'json',
      quiet: true,
    });

    const outputFile = path.join(tempDir, '1901.03003.json');
    expect(fs.existsSync(outputFile)).toBe(true);
    expect(fs.statSync(outputFile).size).toBeGreaterThan(0);
  }, 30000);
});
