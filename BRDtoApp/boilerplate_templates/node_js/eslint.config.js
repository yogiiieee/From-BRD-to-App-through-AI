import globals from "globals";
import js from "@eslint/js";
import ts from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

export default [
  {
    files: ["**/*.{js,ts}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module"
      }
    },
    globals: {
      ...globals.node,
    },
    extends: [
      js.configs.recommended,
      ts.configs.recommended
    ],
    rules: {
      "no-unused-vars": "warn",
      "prefer-const": "warn"
    },
    ignores: [
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "*.log"
    ]
  }
];
