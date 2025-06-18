import globals from "globals";
import pluginJs from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginReactConfig from "eslint-plugin-react/configs/recommended.js";
import pluginReactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  {
    // Apply to JavaScript, JSX, TypeScript, TSX files
    files: ["**/*.{js,mjs,cjs,ts,jsx,tsx}"],
    languageOptions: {
      parser: tseslint.parser, // Use the TypeScript parser
      parserOptions: {
        ecmaFeatures: {
          jsx: true, // Enable JSX parsing
        },
        ecmaVersion: "latest", // Allow latest ECMAScript features
        sourceType: "module", // Use ES Modules
      },
      globals: {
        ...globals.browser, // Add browser global variables (e.g., window, document)
        // Add specific globals if needed for Vite, e.g., 'import.meta': 'readonly'
      },
    },
    // Define plugins
    plugins: {
      "react-hooks": pluginReactHooks,
      "react-refresh": reactRefresh,
    },
    // Define rules
    rules: {
      ...pluginJs.configs.recommended.rules, // Core ESLint recommended rules
      ...pluginReactConfig.rules, // React recommended rules (from eslint-plugin-react)
      ...tseslint.configs.recommended.rules, // TypeScript recommended rules
      "react-hooks/rules-of-hooks": "error", // Ensures React Hooks rules are followed
      "react-hooks/exhaustive-deps": "warn",  // Warns about missing dependencies in useEffect, useCallback etc.
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }], // For Vite's Fast Refresh
      
      // You can add or override specific rules here, for example:
      // "no-unused-vars": "off", // Disable default JS unused vars
      // "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }], // Use TS specific one
    },
    settings: {
      react: {
        version: "detect", // Automatically detect the installed React version
      },
    },
  },
  {
    // Ignore files/directories (similar to .eslintignore)
    ignores: ["dist", "node_modules", "coverage", ".eslintrc.cjs", "*.config.js"],
  }
);