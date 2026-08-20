import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', '.runtime']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ['playwright.config.ts', 'e2e/**/*.ts'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/features/consultation/repositories/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                '**/inquiry-queue/**',
                '**/inquiry-detail/**',
                '**/consultantWorkspaceMock',
                '**/legacy/styles.css',
              ],
              message:
                '폐기 예정 또는 Mock 원천을 직접 Import하지 말고 공식 Repository 경계를 사용하세요.',
            },
          ],
        },
      ],
    },
  },
])
