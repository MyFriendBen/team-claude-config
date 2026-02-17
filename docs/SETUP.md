# Team Claude Code Setup Guide

This guide will help you set up your local development environment to use the shared team Claude Code configurations.

## Prerequisites

- Claude Code CLI installed (`npm install -g @anthropic/claude-code`)
- Git configured with GitHub access
- MyFriendBen workspace directory (e.g., `~/code/mfb/` or your chosen location)

## Quick Setup (Recommended)

The easiest way to get started is using the automated setup script:

```bash
# Clone the team config repo
git clone git@github.com:your-org/team-claude-config.git ~/code/team-claude-config

# Run the setup script
cd ~/code/team-claude-config
./setup.sh <mfb-workspace> <backend-repo> <frontend-repo>

# Example:
./setup.sh ~/code/mfb benefits-be benefits-fe
```

**What it does:**
- ✅ Creates all symlinks (CLAUDE.md, commands/)
- ✅ Sets up hooks.json with your paths
- ✅ Installs git hooks for proper attribution
- ✅ Safe to run multiple times

Done! You're ready to use Claude Code. See the [main README](../README.md) for next steps.

---

## Manual Setup (Alternative)

If you prefer to set things up manually or need more control, follow these detailed steps:

### One-Time Setup

### Step 1: Clone Team Config Repo

```bash
cd ~/code
git clone git@github.com:your-org/team-claude-config.git
```

### Step 2: Backup Existing Configs (if any)

```bash
# Backup existing CLAUDE.md if present
if [ -f <mfb-workspace>/CLAUDE.md ]; then
  mv <mfb-workspace>/CLAUDE.md <mfb-workspace>/CLAUDE.md.backup
  echo "Backed up existing CLAUDE.md"
fi

# Backup existing commands if present
if [ -d <mfb-workspace>/.claude/commands ]; then
  mv <mfb-workspace>/.claude/commands <mfb-workspace>/.claude/commands.backup
  echo "Backed up existing commands"
fi
```

### Step 3: Symlink Shared Configs

```bash
# Symlink CLAUDE.md to your mfb workspace
ln -s <team-config-path>/CLAUDE.md <mfb-workspace>/CLAUDE.md

# Create .claude directory in mfb if it doesn't exist
mkdir -p <mfb-workspace>/.claude

# Symlink shared commands (project-level)
ln -s <team-config-path>/commands <mfb-workspace>/.claude/commands
```

### Step 4: Set Up Hooks (Automated Quality Gates)

Hooks automatically run formatters, linters, and tests when you create or modify files.

1. **Copy and customize hooks template**:
   ```bash
   # Copy template to your workspace
   cp <team-config-path>/hooks.json.template <mfb-workspace>/.claude/hooks.json

   # Replace placeholder with your actual mfb workspace path
   # Example for macOS (replace with your actual path):
   sed -i '' 's|<mfb-workspace>|/Users/yourusername/code/mfb|g' <mfb-workspace>/.claude/hooks.json

   # Example for Linux (replace with your actual path):
   sed -i 's|<mfb-workspace>|/home/yourusername/code/mfb|g' <mfb-workspace>/.claude/hooks.json
   ```

2. **What hooks do**:

   **file_created** - When you create new files:
   - Auto-format Python with ruff
   - Lint Python with ruff --fix
   - Type check Python with mypy
   - Run tests for new test files
   - Auto-format TypeScript with Prettier
   - Lint TypeScript with ESLint --fix
   - Type check TypeScript with tsc

   **file_modified** - When you modify files:
   - Auto-format and lint (same as above)
   - Re-run related tests
   - Type check modified files

   **before_commit** - Before creating commits:
   - Run full test suite (backend)
   - Lint all staged files (backend + frontend)
   - Type check all staged files (backend + frontend)

3. **Customize if needed**:
   - Edit `<mfb-workspace>/.claude/hooks.json`
   - Set `enabled: false` to disable specific hooks
   - Adjust `blocking: true/false` to make hooks non-blocking
   - Modify commands for your specific setup

### Step 5: Verify Setup

```bash
# Check CLAUDE.md is linked
ls -la <mfb-workspace>/CLAUDE.md
# Should show: CLAUDE.md -> <team-config-path>/CLAUDE.md

# Check commands are linked
ls -la <mfb-workspace>/.claude/commands
# Should show: commands -> <team-config-path>/commands

# Test in Claude Code
cd <mfb-workspace>
# Start Claude Code - /add-program should now be available
```

## Personal Customization

You can still customize your own setup without affecting the team:

### Personal Settings

Keep these in `~/.claude/config.json` (not version controlled):
```json
{
  "mcpServers": {
    "your-personal-server": {
      // Your personal MCP configs
    }
  }
}
```

### Personal Keybindings

Keep these in `~/.claude/keybindings.json`:
```json
{
  "your-custom-binding": {
    // Your personal keybindings
  }
}
```

### Personal Commands

Create personal experimental commands outside the team commands:
```bash
mkdir -p <mfb-workspace>/.claude/personal-commands
# Add your experimental commands here
# These won't be shared with the team
```

Or create global commands (available in all projects):
```bash
mkdir -p ~/.claude/skills
# Add global commands here
```

## Staying Updated

### Pull Latest Team Changes

```bash
cd ~/code/team-claude-config
git pull origin main
```

Do this regularly (weekly or when notified by team). Changes apply automatically via symlinks.

### Contributing Your Improvements

When you create a useful command or improve the CLAUDE.md:

```bash
cd ~/code/team-claude-config

# Create a branch
git checkout -b add-my-command

# Make your changes
# ... edit files ...

# Commit and push
git add .
git commit -m "Add new command for X"
git push origin add-my-command

# Open a PR on GitHub
gh pr create --title "Add new command for X" --body "Description of what this does and why it's useful"
```

## Working with Multiple Projects

The symlinked CLAUDE.md will be used by Claude Code when working in:
- `<mfb-workspace>/benefits-api/`
- `<mfb-workspace>/benefits-calculator/`
- Any other repos under `<mfb-workspace>/`

Individual repos can have their own `CLAUDE.md` for project-specific additions.

## Troubleshooting

### CLAUDE.md Not Loading

```bash
# Check if symlink exists
ls -la <mfb-workspace>/CLAUDE.md

# If broken, recreate it
rm <mfb-workspace>/CLAUDE.md
ln -s <team-config-path>/CLAUDE.md <mfb-workspace>/CLAUDE.md
```

### Commands Not Available

```bash
# Check commands symlink
ls -la <mfb-workspace>/.claude/commands

# If broken, recreate it
rm <mfb-workspace>/.claude/commands
ln -s <team-config-path>/commands <mfb-workspace>/.claude/commands
```

### Want to Use Your Own CLAUDE.md

```bash
# Remove symlink
rm <mfb-workspace>/CLAUDE.md

# Copy shared version as starting point
cp <team-config-path>/CLAUDE.md <mfb-workspace>/CLAUDE.md

# Edit as needed (but you won't get automatic updates)
```

### Conflicts Between Team and Personal Config

If you have personal preferences that conflict with team config:
1. Keep the team config as-is
2. Add your preferences to project-specific CLAUDE.md files
3. Or discuss with team if your approach should become the standard

## Questions?

- Team chat: Ask in your dev channel
- Issues: Open an issue in the team-claude-config repo
- Documentation: Check README.md and CONVENTIONS.md
