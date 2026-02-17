# MyFriendBen Team Conventions

This document outlines team standards for working with Claude Code across MyFriendBen projects.

## Core Workflow

Every feature follows: **Research → Plan → Implement → Validate**

1. **Research** - Understand existing patterns before writing code
2. **Plan** - Propose approach and get alignment
3. **Implement** - Build with tests and error handling
4. **Validate** - Run formatters, linters, and tests

## Django Backend Standards

### Code Organization

- **Fat models, skinny views** - Business logic in models/managers
- **Custom managers** - Abstract database queries into reusable methods
- **Service layer** - Multi-model operations in dedicated service modules
- **Type hints everywhere** - All functions must have type annotations

### Testing Requirements

- All models must have tests
- All views must have tests
- Use Django's TestCase for database tests
- Use pytest for unit tests
- Aim for >80% code coverage

### Database Patterns

```python
# ✅ Good: Query logic in manager
class ProgramManager(models.Manager):
    def active_for_state(self, state_code):
        return self.filter(active=True, states__contains=state_code)

# ❌ Bad: Query logic in view
def get_programs(request):
    programs = Program.objects.filter(active=True, states__contains=request.state)
```

### Settings Organization

- `settings/base.py` - Shared settings
- `settings/development.py` - Local dev settings
- `settings/production.py` - Production settings
- `settings/testing.py` - Test settings

## React Frontend Standards

### Component Structure

- **Functional components only** - No class components
- **TypeScript for everything** - All components, hooks, and utilities
- **Single responsibility** - Each component does one thing well
- **Custom hooks for logic** - Extract reusable stateful logic into hooks
- **Props interfaces** - Every component must define a typed props interface

Example:
```typescript
// ✅ Good: Typed component with single responsibility
interface ProgramCardProps {
  program: Program;
  onSelect: (id: string) => void;
}

export const ProgramCard: React.FC<ProgramCardProps> = ({ program, onSelect }) => {
  return (
    <Card onClick={() => onSelect(program.id)}>
      <Typography variant="h6">{program.name}</Typography>
      <Typography>{program.description}</Typography>
    </Card>
  );
};

// ❌ Bad: Untyped props, doing too much
export const ProgramCard = ({ program }) => {
  const [data, setData] = useState();
  useEffect(() => {
    // Fetching data in a display component - should be in parent
  }, []);
  // ... complex logic that should be extracted
};
```

### TypeScript Patterns

- **Strict mode enabled** - No implicit any
- **Interface for objects** - `interface` for component props and data shapes
- **Type for unions** - `type` for union types and utility combinations
- **Avoid any** - Use `unknown` or proper types
- **Type imports** - Use `import type` for type-only imports

```typescript
// ✅ Good: Proper typing
interface User {
  id: string;
  name: string;
  email: string;
}

type UserRole = 'admin' | 'user' | 'guest';

// ❌ Bad: Using any
function updateUser(user: any) {
  // ...
}
```

### State Management

- **Local state first** - Use `useState` for component-local state
- **Context for shared state** - React Context for app-wide state
- **React Query for API data** - Server state separate from UI state
- **Avoid prop drilling** - Use Context or composition if passing through 3+ levels
- **Immutable updates** - Always create new objects/arrays

```typescript
// ✅ Good: Immutable update
setPrograms(prev => [...prev, newProgram]);

// ❌ Bad: Mutating state
programs.push(newProgram);
setPrograms(programs);
```

### File Organization

```
src/
├── components/          # Reusable components
│   ├── Button/
│   │   ├── Button.tsx
│   │   ├── Button.test.tsx
│   │   └── index.ts
├── pages/               # Page components
├── hooks/               # Custom hooks
│   └── useScreener.ts
├── api/                 # API client functions
│   └── programs.ts
├── types/               # Shared types
│   └── models.ts
└── utils/               # Pure utilities
    └── formatting.ts
```

### Testing Requirements

- **Component tests** - React Testing Library for all components
- **Test behavior** - Query by role/label, not class names or IDs
- **Hook tests** - Test custom hooks in isolation
- **E2E tests** - Playwright for critical user flows
- **Aim for >80% coverage** - Focus on business logic and user interactions

```typescript
// ✅ Good: Testing user behavior
test('submits form when button clicked', async () => {
  render(<ScreenerForm />);

  await userEvent.type(screen.getByLabelText(/age/i), '25');
  await userEvent.click(screen.getByRole('button', { name: /submit/i }));

  expect(await screen.findByText(/results/i)).toBeInTheDocument();
});

// ❌ Bad: Testing implementation details
test('calls handleSubmit', () => {
  const handleSubmit = jest.fn();
  render(<ScreenerForm onSubmit={handleSubmit} />);

  wrapper.find('.submit-button').simulate('click');
  expect(handleSubmit).toHaveBeenCalled();
});
```

### API Integration

- **Typed responses** - Define interfaces for all API responses
- **React Query patterns** - Use queries for reads, mutations for writes
- **Error handling** - Handle loading, error, and success states
- **Centralized API client** - All API calls in dedicated functions

```typescript
// ✅ Good: Typed API integration
interface ProgramsResponse {
  programs: Program[];
  total: number;
}

export const usePrograms = (screenId: string) => {
  return useQuery<ProgramsResponse>({
    queryKey: ['programs', screenId],
    queryFn: () => api.getPrograms(screenId),
  });
};
```

### Styling

- **Material-UI first** - Use MUI components as base
- **Theme consistency** - All colors, spacing from theme
- **sx prop or styled()** - For component-specific styles
- **Responsive** - Use MUI breakpoints
- **White label support** - Support dynamic theming

```typescript
// ✅ Good: Theme-based styling
<Box sx={{
  p: 2,
  bgcolor: 'primary.main',
  [theme.breakpoints.down('sm')]: { p: 1 }
}}>

// ❌ Bad: Hardcoded values
<Box style={{ padding: '16px', backgroundColor: '#1976d2' }}>
```

## Git Workflow

### Branching

- `main` - Production-ready code
- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code improvements

### Commits

- Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- Write descriptive messages focusing on "why" not "what"
- Include Claude Code attribution footer when using Claude

```bash
git commit -m "feat: add eligibility check for SNAP

Implements PolicyEngine integration for SNAP calculations.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Pull Requests

- Keep PRs focused and reasonably sized
- Include tests with all code changes
- Add description explaining what and why
- Link to Linear ticket if applicable
- Address CodeRabbit feedback systematically

## Claude Code Best Practices

### When to Use Skills

- `/add-program` - For implementing new benefit programs from Linear
- Create new skills when you repeat the same workflow 3+ times

### CLAUDE.md Placement

- **Team config** (`team-claude-config/CLAUDE.md`) - Shared patterns for all MFB projects
- **Workspace** (`<mfb-workspace>/CLAUDE.md`) - Symlinked to team config
- **Project-specific** (`benefits-api/CLAUDE.md`) - Backend-only instructions
- **Project-specific** (`benefits-calculator/CLAUDE.md`) - Frontend-only instructions

### Adding New Patterns

When you discover a useful pattern:
1. Test it in your work first
2. Document why it helps
3. Add to team config via PR
4. Share with team

## Code Review

### As Author

- Self-review before requesting review
- Run tests and linters locally
- Provide context in PR description
- Be responsive to feedback

### As Reviewer

- Review within 24 hours
- Focus on logic, not style (linters handle that)
- Ask questions to understand tradeoffs
- Approve when satisfied, don't nitpick

### Working with CodeRabbit

- CodeRabbit reviews all PRs automatically
- Address feedback systematically
- Reply directly to inline comments (use nested replies)
- Commit changes after addressing feedback
- See CLAUDE.md for detailed CodeRabbit response workflow

## Multi-Tenant Considerations

### White Label Architecture

- Never hard-code state-specific logic
- Use WhiteLabel model for configuration
- Support multiple states in single deployment
- Test with multiple white label configs

### Translation Support

- All user-facing text must use Translation model
- Support English and Spanish minimum
- Use translation keys consistently
- Test with multiple languages

## Security

- Never commit secrets or API keys
- Use environment variables for config
- Validate all user input
- Follow OWASP Top 10 guidelines
- Use parameterized queries (Django ORM does this)

## Performance

- Use select_related() and prefetch_related() for query optimization
- Cache expensive calculations
- Paginate large querysets
- Monitor N+1 query problems

## Questions?

- Check team-claude-config README
- Ask in team chat
- Review existing code for examples
- When in doubt, ask before implementing
