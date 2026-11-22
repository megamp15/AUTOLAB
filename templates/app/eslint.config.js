import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  { files: ["**/*.{ts,tsx,mjs}"], languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  // The browser extension: plain scripts Chrome loads as they are.
  { files: ["extension/**/*.js"], languageOptions: { globals: { ...globals.browser, ...globals.webextensions } } },
);
