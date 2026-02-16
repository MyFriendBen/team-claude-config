# Team Commands Directory

This directory contains custom Claude Code commands for MyFriendBen projects. These are **project-level commands** that get symlinked to `~/code/mfb/.claude/commands/` and are available when working in the mfb workspace.

## Available Commands

### `/add-program`
Implements a new benefit program from Linear ticket created by program-researcher.

**Usage:** `/add-program <ticket-id>`
**Example:** `/add-program LIN-1234`
**Details:** See [add-program.md](add-program.md)

### `/coderabbit-comment-review`
Systematically review and respond to CodeRabbit feedback on pull requests.

**Usage:** `/coderabbit-comment-review <PR-number>`
**Example:** `/coderabbit-comment-review 123`
**Details:** See [coderabbit-comment-review.md](coderabbit-comment-review.md)

## How Project Commands Work

Claude Code looks for custom commands in `.claude/commands/` within your project directory. When you symlink this directory to `~/code/mfb/.claude/commands/`, these commands become available when working in any MyFriendBen repo under the mfb workspace.

## Command File Format

Commands are defined as markdown files with YAML frontmatter:

```markdown
---
name: command-name
description: Brief description of what this command does
usage: /command-name <arguments>
example: /command-name arg1 arg2
---

<command-name>command-name</command-name>

# Full Command Instructions

Detailed step-by-step instructions for Claude Code on how to execute this command...
```

## Adding New Commands

When you create a useful command for MyFriendBen projects:

1. **Create command file**
   ```bash
   cd ~/code/team-claude-config
   touch commands/your-command-name.md
   ```

2. **Define the command** (use format above)
   - Add YAML frontmatter with name, description, usage, example
   - Add `<command-name>` tag
   - Write detailed instructions for Claude
   - Include error handling and quality gates

3. **Test locally**
   ```bash
   # Commands are automatically available via symlink
   cd ~/code/mfb
   # Test by running: /your-command-name
   ```

4. **Submit PR**
   ```bash
   cd ~/code/team-claude-config
   git checkout -b add-your-command
   git add commands/your-command-name.md
   git commit -m "Add your-command-name command"
   git push origin add-your-command
   gh pr create
   ```

## Command Ideas

Consider creating commands for MyFriendBen-specific workflows:
- **Program implementation**: Add new benefit programs (already have `/add-program`)
- **Test generation**: Generate test cases for specific patterns
- **Migration helpers**: Create Django migrations with standard patterns
- **Translation updates**: Add/update translations for new features
- **PR workflows**: Create PRs with standard templates
- **Deployment checks**: Pre-deployment validation
- **Data fixtures**: Generate test data for programs

## Best Practices

- **Project-specific**: Commands should be relevant to MyFriendBen development
- **Clear instructions**: Write step-by-step instructions for Claude
- **Error handling**: Include what to do when things go wrong
- **Quality gates**: Specify validation steps (tests, linting, hooks)
- **Examples**: Show concrete examples of input/output
- **Integration**: Explain how the command fits into the workflow
- **Use existing patterns**: Reference CLAUDE.md conventions

## Project-Level vs Global

- **Project-level** (this directory): Commands specific to MyFriendBen, symlinked to `~/code/mfb/.claude/commands/`
- **Global**: Commands for any project, stored in `~/.claude/skills/`

Since `/add-program` is specific to MyFriendBen's Django architecture, it belongs here as a project-level command.
