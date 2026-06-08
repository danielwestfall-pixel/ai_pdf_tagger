import * as fs from 'fs';
import { beforeAll, afterAll } from 'vitest';

export function useTempDirLifecycle(tempDir: string) {
  beforeAll(() => {
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
    fs.mkdirSync(tempDir, { recursive: true });
  });

  afterAll(() => {
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
}
