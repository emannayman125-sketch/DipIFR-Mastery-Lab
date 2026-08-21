import { FlatCompat } from "@eslint/eslintrc";

// eslint-config-next only ships a legacy (.eslintrc-style) "extends" config,
// not a native ESLint 9 flat-config export — FlatCompat is Next.js's own
// documented bridge for using it under eslint.config.mjs. (An earlier
// version of this file imported "eslint-config-next/core-web-vitals"
// directly and destructured it as a flat-config array, which doesn't work:
// that file's export is `{ extends: [...] }`, not an array of flat configs.)
const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const config = [
  ...compat.extends("next/core-web-vitals"),
  { ignores: ["node_modules/**", ".next/**", "out/**", "build/**", "next-env.d.ts"] },
];

export default config;
