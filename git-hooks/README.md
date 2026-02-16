# Git Hooks

This directory contains Git hooks that ensure commits are properly attributed to developers, not AI assistants.

## Available Hooks

### `prepare-commit-msg`

Automatically removes Claude co-author lines from commit messages to ensure proper attribution.

**What it removes:**
- `Co-Authored-By: Claude ...` lines
- `🤖 Generated with Claude Code` footers
- `Generated with [Claude Code]` links

**Result:** Commits are attributed only to the developer who made them.

## Setup Instructions

### Per-Repository Setup

For each repository where you want to use these hooks:

```bash
# Navigate to your repository
cd <mfb-workspace>/benefits-api  # or benefits-calculator

# Copy the hook
cp <team-config-path>/git-hooks/prepare-commit-msg .git/hooks/

# Make it executable
chmod +x .git/hooks/prepare-commit-msg
```

### Global Setup (All Repositories)

To use these hooks in all your repositories:

```bash
# Set global git hooks directory
git config --global core.hooksPath <team-config-path>/git-hooks

# Make hooks executable
chmod +x <team-config-path>/git-hooks/*
```

**Note:** Global setup applies to ALL repositories on your machine, not just MyFriendBen projects.

### Automated Setup Script

You can create a script to set up hooks for all MyFriendBen repos:

```bash
#!/bin/bash
# setup-git-hooks.sh

MFB_WORKSPACE="<mfb-workspace>"
HOOKS_DIR="<team-config-path>/git-hooks"

for repo in benefits-api benefits-calculator; do
  if [ -d "$MFB_WORKSPACE/$repo/.git" ]; then
    echo "Setting up hooks for $repo..."
    cp "$HOOKS_DIR/prepare-commit-msg" "$MFB_WORKSPACE/$repo/.git/hooks/"
    chmod +x "$MFB_WORKSPACE/$repo/.git/hooks/prepare-commit-msg"
    echo "✅ $repo hooks configured"
  fi
done
```

## How It Works

When you run `git commit`:

1. You write your commit message (or Claude writes it)
2. Git runs the `prepare-commit-msg` hook
3. The hook removes any Claude co-author lines
4. Git saves the cleaned commit message
5. Commit is attributed only to you

## Testing

To verify the hook is working:

```bash
# Create a test commit with Claude co-author
git commit -m "Test commit

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Check the actual commit message
git log -1 --pretty=%B

# Should NOT include the Co-Authored-By line
```

## Disabling

To temporarily disable the hook:

```bash
# Rename it
mv .git/hooks/prepare-commit-msg .git/hooks/prepare-commit-msg.disabled

# Or use --no-verify flag
git commit --no-verify -m "message"
```

## Why This Matters

- **Proper attribution** - Commits reflect who actually wrote/reviewed the code
- **Git analytics** - Tools like GitHub Insights show accurate contributor stats
- **Code ownership** - Clear responsibility for changes
- **Team transparency** - No confusion about who to ask about changes

## Customization

If you want to keep the Claude footer but remove co-author:

Edit the hook and comment out these lines:
```bash
# sed -i.bak '/🤖 Generated with.*Claude Code/d' "$COMMIT_MSG_FILE"
# sed -i.bak '/Generated with \[Claude Code\]/d' "$COMMIT_MSG_FILE"
```
