```markdown
# hermes-brain Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `hermes-brain` repository. The codebase is written in TypeScript, with no specific framework detected. It emphasizes clear file naming, consistent import/export styles, and conventional commit messages. This guide will help you contribute code, write tests, and follow repository standards efficiently.

## Coding Conventions

### File Naming
- Use **PascalCase** for file names.
  - Example: `MyComponent.ts`, `DataService.ts`

### Import Style
- Use **relative imports** for referencing modules.
  - Example:
    ```typescript
    import { MyHelper } from './MyHelper';
    ```

### Export Style
- Use **named exports** (not default exports).
  - Example:
    ```typescript
    // MyHelper.ts
    export function MyHelper() { /* ... */ }
    ```

### Commit Messages
- Use **conventional commit** format.
- Common prefix: `chore`
- Keep commit messages concise (average ~46 characters).
  - Example:
    ```
    chore: update dependencies to latest versions
    ```

## Workflows

### Commit Code Changes
**Trigger:** When you have made code changes and are ready to commit.
**Command:** `/commit-changes`

1. Stage your changes:
    ```
    git add .
    ```
2. Write a conventional commit message, using the appropriate prefix (e.g., `chore:`).
    ```
    git commit -m "chore: describe your change briefly"
    ```
3. Push your changes:
    ```
    git push
    ```

### Add New Module
**Trigger:** When you need to add a new TypeScript module or component.
**Command:** `/add-module`

1. Create a new file using PascalCase, e.g., `NewModule.ts`.
2. Implement your logic using named exports.
    ```typescript
    // NewModule.ts
    export function NewModule() { /* ... */ }
    ```
3. Import the module using a relative path where needed.
    ```typescript
    import { NewModule } from './NewModule';
    ```
4. Write corresponding tests (see Testing Patterns).

### Write Tests
**Trigger:** When you add or modify functionality.
**Command:** `/write-test`

1. Create a test file with the pattern `*.test.*` (e.g., `MyModule.test.ts`).
2. Write tests for your module or function.
    ```typescript
    // MyModule.test.ts
    import { MyModule } from './MyModule';

    describe('MyModule', () => {
      it('should behave as expected', () => {
        // test implementation
      });
    });
    ```
3. Run your tests using your chosen test runner.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern (e.g., `Feature.test.ts`).
- The specific testing framework is not detected; use your team's standard or clarify before contributing.
- Place test files alongside the modules they test or in a dedicated test directory.

## Commands
| Command           | Purpose                                      |
|-------------------|----------------------------------------------|
| /commit-changes   | Guide for committing code using conventions  |
| /add-module       | Steps to add a new module/component          |
| /write-test       | Instructions for writing and running tests   |
```