import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Do not discover build-output copies of tests under .next/standalone.
  test: { include: ['lib/**/*.test.ts'] },
});
