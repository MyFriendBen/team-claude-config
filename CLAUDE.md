# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Workflow: Research → Plan → Implement → Validate

**Start every feature with:** "Let me research the codebase and create a plan before implementing."

1. **Research** - Understand existing patterns and architecture
2. **Plan** - Propose approach and verify with you
3. **Implement** - Build with tests and error handling
4. **Validate** - ALWAYS run formatters, linters, and tests after implementation

## Architecture & Patterns

### Core Philosophy

This codebase follows **Django best practices** emphasizing:

- **App-based modularity** - Each Django app is a self-contained module with clear boundaries
- **Domain-driven design** - Business logic separated from framework code
- **Explicit is better than implicit** - Following Python's zen principles
- **12-factor app principles** - Environment-based configuration, stateless processes

### Enforced Standards

The Django project enforces these standards:

- **Fat models, skinny views** - Business logic belongs in models and managers, not views
- **Custom managers and querysets** - Database queries abstracted into reusable manager methods
- **Class-based views where appropriate** - Use CBVs for standard CRUD, FBVs for custom logic
- **Service layer for complex operations** - Multi-model operations in dedicated service modules
- **Comprehensive testing** - All models, views, and business logic must have tests. Use Django's TestCase for database tests, pytest for unit tests
- **Type hints everywhere** - All functions and methods should have type annotations
- **Settings organization** - Split settings by environment (base, development, production, testing)

This codebase prioritizes maintainability through clear separation of concerns and Django-idiomatic patterns.

### Frontend Standards (React + TypeScript)

The React frontend follows modern best practices emphasizing type safety and component reusability:

#### Component Architecture

- **Functional components with hooks** - Use function components, avoid class components
- **Custom hooks for shared logic** - Extract reusable stateful logic into custom hooks
- **Component composition** - Build complex UIs from small, focused components
- **Props typing** - All component props must have TypeScript interfaces/types
- **Single responsibility** - Each component should do one thing well

#### TypeScript Best Practices

- **Strict mode enabled** - Use `strict: true` in tsconfig.json
- **Explicit types** - Avoid `any`, use proper types or `unknown` when type is truly unknown
- **Interface over type** - Prefer `interface` for object shapes, `type` for unions/intersections
- **Type imports** - Use `import type` for type-only imports to improve tree-shaking
- **Utility types** - Leverage TypeScript utility types (Partial, Pick, Omit, etc.)

#### State Management

- **Local state first** - Use `useState` for component-local state
- **Context for shared state** - Use React Context for state shared across component tree
- **React Query for server state** - Use React Query (or similar) for API data fetching and caching
- **Avoid prop drilling** - If passing props through 3+ levels, consider Context or component composition
- **Immutable updates** - Always create new objects/arrays when updating state

#### File Organization

```
benefits-fe/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   └── index.ts
│   ├── pages/              # Page-level components
│   ├── hooks/              # Custom React hooks
│   ├── utils/              # Pure utility functions
│   ├── types/              # Shared TypeScript types
│   ├── api/                # API client functions
│   └── styles/             # Global styles and theme
```

#### Styling Patterns

- **Material-UI components** - Use MUI components as base, customize with theme
- **Styled components** - Use `styled()` or `sx` prop for component-specific styles
- **Theme consistency** - All colors, spacing, typography from theme
- **Responsive design** - Use MUI breakpoints for responsive layouts
- **White label theming** - Support dynamic theming via WhiteLabel configuration

#### Testing Requirements

- **Component tests** - Use React Testing Library for component behavior tests
- **Hook tests** - Test custom hooks with `@testing-library/react-hooks`
- **E2E tests** - Use Playwright for critical user flows (screening wizard, results)
- **Test user behavior, not implementation** - Query by role/label, not class names
- **Aim for >80% coverage** - Focus on critical paths and business logic

#### API Integration

- **Typed API responses** - Define TypeScript interfaces for all API responses
- **Error handling** - Always handle loading, error, and success states
- **React Query patterns** - Use queries for GET, mutations for POST/PUT/DELETE
- **Optimistic updates** - Update UI optimistically for better UX
- **API client layer** - Centralize API calls in dedicated functions

#### Common Patterns

**Form handling:**
```typescript
// Use controlled components with TypeScript
interface FormData {
  age: number;
  income: string;
}

const [formData, setFormData] = useState<FormData>({
  age: 0,
  income: ''
});
```

**API calls:**
```typescript
// Type API responses
interface Program {
  id: string;
  name: string;
  eligible: boolean;
}

const { data, isLoading, error } = useQuery<Program[]>(
  ['programs', screenId],
  () => fetchPrograms(screenId)
);
```

**Error boundaries:**
```typescript
// Wrap components that may error
<ErrorBoundary fallback={<ErrorMessage />}>
  <ProgramResults />
</ErrorBoundary>
```

#### Performance

- **Lazy loading** - Use `React.lazy()` for code splitting
- **Memoization** - Use `useMemo` and `useCallback` for expensive computations
- **Virtualization** - Use virtualized lists for large data sets
- **Image optimization** - Lazy load images, use appropriate formats
- **Bundle analysis** - Monitor bundle size, keep under budget

#### Accessibility

- **Semantic HTML** - Use proper HTML elements (button, nav, main, etc.)
- **ARIA labels** - Add aria-label when text content isn't sufficient
- **Keyboard navigation** - Ensure all interactive elements are keyboard accessible
- **Focus management** - Manage focus for modals, page transitions
- **Screen reader testing** - Test with screen readers (NVDA, JAWS, VoiceOver)

## CodeRabbit PR Review Response

When CodeRabbit reviews your PR and leaves feedback, use the dedicated command to systematically address comments:

```bash
/coderabbit-comment-review <PR-number>
```

This command will:
1. Discover all unresolved CodeRabbit comments
2. Help you plan responses and implementation strategy
3. Guide you through implementing agreed-upon changes
4. Ensure proper comment threading and PR updates
5. Commit and push improvements with appropriate messages

See `commands/coderabbit-comment-review.md` for full documentation on the two-phase process (planning and implementation).

## Project Overview

MyFriendBen is a multi-tenant benefits screening platform that helps individuals and families identify eligible government benefits, nonprofit programs, and tax credits. The system consists of a Django REST API backend and React TypeScript frontend, with support for multiple white label configurations across different states.

## Architecture

### Backend (benefits-be/)

- **Django REST Framework** with PostgreSQL
- **Multi-tenant architecture** - Each state/organization has its own white label configuration
- **Dual eligibility calculation** - Combines PolicyEngine API with custom state-specific calculators
- **Multi-language support** - All content stored in Translation model for i18n
- **Core apps**: screener (household data), programs (benefit definitions), authentication, configuration, integrations, translations, validations

### Frontend (benefits-fe/)

- **React 18 with TypeScript**
- **Multi-step form wizard** for household data collection
- **Material-UI components** with custom styling
- **White label theming** system
- **Playwright** for end-to-end testing

### Key Data Models

- **Screen** - Central household container with demographic and benefit status data
- **HouseholdMember** - Individual family members with age, relationship, income, expenses
- **Program** - Benefit program definitions with eligibility logic and translations
- **WhiteLabel** - Multi-tenant configuration for different states/organizations
