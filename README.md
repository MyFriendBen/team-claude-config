# Team Claude Code Configuration

This repository contains shared Claude Code configurations, custom commands (skills), and documentation for the MyFriendBen development team.

## Purpose

- **Consistency**: Ensure all developers use the same Claude Code workflows and conventions
- **Version Control**: Track changes to our AI-assisted development patterns
- **Collaboration**: Share useful custom commands across the team
- **Onboarding**: Help new team members get productive quickly

## What's Included

### `CLAUDE.md`
Shared instructions for Claude Code when working with MyFriendBen projects. This file provides:
- Core workflow (Research → Plan → Implement → Validate)
- Django best practices and patterns
- Project architecture overview
- CodeRabbit PR review response process

### `commands/`
Custom Claude Code commands for MyFriendBen projects:
- `/add-program` - Implements new benefit programs from Linear tickets
- `/coderabbit-comment-review` - Systematically respond to CodeRabbit PR feedback
- `/linear-code-review` - Review all PRs in Linear's Code Review column with comprehensive analysis
- Add your own project-specific commands here as the team develops them

### `hooks.json.template`
Automated quality gates that run on file creation, modification, and before commits:
- **Backend**: ruff formatting/linting, mypy type checking, pytest
- **Frontend**: Prettier formatting, ESLint linting, TypeScript checking
- Symlink to your workspace after replacing placeholders with your paths

### `git-hooks/`
Git hooks for proper commit attribution:
- `prepare-commit-msg` - Removes Claude co-author lines from commits
- Ensures commits are attributed only to the developer
- Copy to `.git/hooks/` in each repository or set up globally

### `docs/`
Team documentation:
- `SETUP.md` - Step-by-step setup guide for new team members
- `CONVENTIONS.md` - Team coding standards and practices

## Setup Instructions

### Quick Setup (Recommended)

Use the automated setup script:

```bash
# Clone this repo
git clone git@github.com:your-org/team-claude-config.git <team-config-path>

# Run setup script
cd <team-config-path>
./setup.sh <mfb-workspace> [backend-repo] [frontend-repo]

# Examples:
./setup.sh ~/code/mfb
./setup.sh ~/code/mfb benefits-api benefits-calculator
./setup.sh ~/work/mfb my-backend my-frontend
```

**What the script does:**
- ✅ Creates all necessary symlinks (CLAUDE.md, commands/)
- ✅ Sets up hooks.json with your paths
- ✅ Installs git hooks for proper attribution
- ✅ Idempotent (safe to run multiple times)
- ✅ Interactive confirmation before changes

### Manual Setup

**Note:** Replace placeholders with your actual paths:
- `<team-config-path>` - Where you clone this repo (e.g., `~/projects/team-claude-config` or `~/dev/team-claude-config`)
- `<mfb-workspace>` - Your MyFriendBen workspace directory (e.g., `~/work/mfb`, `~/code/mfb`, or `~/projects/mfb`)

#### One-Time Setup

1. **Clone this repo**
   ```bash
   git clone git@github.com:your-org/team-claude-config.git <team-config-path>
   ```

2. **Set up your mfb workspace directory**
   ```bash
   mkdir -p <mfb-workspace>/.claude
   ```

3. **Symlink shared CLAUDE.md**
   ```bash
   # Backup existing if present
   if [ -f <mfb-workspace>/CLAUDE.md ]; then
     mv <mfb-workspace>/CLAUDE.md <mfb-workspace>/CLAUDE.md.backup
   fi

   # Create symlink
   ln -s <team-config-path>/CLAUDE.md <mfb-workspace>/CLAUDE.md
   ```

4. **Symlink project commands**
   ```bash
   # Backup existing commands if present
   if [ -d <mfb-workspace>/.claude/commands ]; then
     mv <mfb-workspace>/.claude/commands <mfb-workspace>/.claude/commands.backup
   fi

   # Create symlink to shared commands
   ln -s <team-config-path>/commands <mfb-workspace>/.claude/commands
   ```

5. **Set up hooks (automated quality gates)**
   ```bash
   # Copy hooks template and replace placeholders
   cp <team-config-path>/hooks.json.template <mfb-workspace>/.claude/hooks.json

   # Replace <mfb-workspace> with your actual path
   # On macOS:
   sed -i '' 's|<mfb-workspace>|/your/actual/path/to/mfb|g' <mfb-workspace>/.claude/hooks.json

   # On Linux:
   sed -i 's|<mfb-workspace>|/your/actual/path/to/mfb|g' <mfb-workspace>/.claude/hooks.json
   ```

6. **Set up git hooks (proper commit attribution)**
   ```bash
   # For each repository, copy the prepare-commit-msg hook
   # This removes Claude co-author lines from commits

   # Backend repo
   cp <team-config-path>/git-hooks/prepare-commit-msg <mfb-workspace>/benefits-api/.git/hooks/
   chmod +x <mfb-workspace>/benefits-api/.git/hooks/prepare-commit-msg

   # Frontend repo
   cp <team-config-path>/git-hooks/prepare-commit-msg <mfb-workspace>/benefits-calculator/.git/hooks/
   chmod +x <mfb-workspace>/benefits-calculator/.git/hooks/prepare-commit-msg

   # OR set up globally for all repos (optional)
   git config --global core.hooksPath <team-config-path>/git-hooks
   chmod +x <team-config-path>/git-hooks/*
   ```

7. **Verify setup**
   ```bash
   # Check CLAUDE.md is linked
   ls -la <mfb-workspace>/CLAUDE.md
   # Should show: CLAUDE.md -> <team-config-path>/CLAUDE.md

   # Check commands are linked
   ls -la <mfb-workspace>/.claude/commands
   # Should show: commands -> <team-config-path>/commands

   # Check git hooks
   ls -la <mfb-workspace>/benefits-api/.git/hooks/prepare-commit-msg
   # Should be executable

   # Test in Claude Code
   cd <mfb-workspace>
   # Start Claude Code - /add-program should now be available
   ```

### Staying Updated

When the team adds new commands or updates configurations:

```bash
cd <team-config-path>
git pull origin main

# If new commands were added, re-run setup (safe, idempotent)
./setup.sh <mfb-workspace>
```

Changes automatically apply via symlinks. Re-running setup ensures:
- New git hooks are installed
- Hooks.json includes new patterns
- All symlinks are correct

## Contributing

### Adding New Commands

1. Create your command file in `commands/your-command-name.md`
2. Test it locally in your mfb workspace
3. Submit a PR with documentation

Example:
```bash
cd ~/code/team-claude-config
git checkout -b add-my-command

# Create your command file
# Edit commands/my-command.md

git add commands/my-command.md
git commit -m "Add my-command for X purpose"
git push origin add-my-command

# Open PR
gh pr create --title "Add my-command" --body "Description..."
```

### Updating Instructions

1. Edit `CLAUDE.md` with improvements
2. Document why the change helps the team
3. Get team review before merging

### Keep It Current

When you discover a useful pattern or command:
- Add it here so the whole team benefits
- Keep documentation up to date
- Remove outdated patterns

## Structure

```
team-claude-config/
├── setup.sh                           # 🚀 Automated setup script (run this!)
├── CLAUDE.md                          # Shared base instructions
├── hooks.json.template                # Automated quality gates (format, lint, test)
├── git-hooks/                         # Git hooks for proper attribution
│   ├── README.md                     # Git hooks documentation
│   └── prepare-commit-msg            # Removes Claude co-author from commits
├── commands/                          # Project-level custom commands
│   ├── README.md                     # Commands documentation
│   ├── add-program.md                # Benefit program implementation
│   └── coderabbit-comment-review.md  # PR review response workflow
├── docs/                              # Team documentation
│   ├── SETUP.md                      # Manual setup guide
│   └── CONVENTIONS.md                # Team standards
└── README.md                          # This file
```

## Philosophy

- **Share what works**: If a workflow helps you, share it
- **Document decisions**: Help future team members understand why
- **Stay pragmatic**: Don't over-engineer - keep it simple
- **Iterate**: This repo should evolve with the team

## Questions?

- Check [SETUP.md](docs/SETUP.md) for setup issues
- Check [CONVENTIONS.md](docs/CONVENTIONS.md) for coding standards
- Ask the team in Slack/Discord/your communication channel
- Open an issue in this repo for improvements
