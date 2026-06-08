import * as path from 'path';
import { fileURLToPath } from 'url';

export function getIntegrationPaths(importMetaUrl: string, suiteName: string) {
  const filename = fileURLToPath(importMetaUrl);
  const dirname = path.dirname(filename);

  const rootDir = path.resolve(dirname, '..', '..', '..');
  const inputPdf = path.join(rootDir, 'samples', 'pdf', '1901.03003.pdf');
  const tempDir = path.join(dirname, 'temp', suiteName);

  return { rootDir, inputPdf, tempDir };
}
