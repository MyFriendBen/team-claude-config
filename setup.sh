#!/bin/bash

# Team Claude Code Configuration Setup Script
# Automatically sets up symlinks and configuration for MyFriendBen development

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default repo names
DEFAULT_BACKEND_REPO="benefits-api"
DEFAULT_FRONTEND_REPO="benefits-calculator"

# Print colored output
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Print usage
usage() {
    echo "Usage: $0 <mfb-workspace> [backend-repo] [frontend-repo]"
    echo ""
    echo "Arguments:"
    echo "  mfb-workspace     Path to your MyFriendBen workspace (required)"
    echo "  backend-repo      Name of backend repo (default: benefits-api)"
    echo "  frontend-repo     Name of frontend repo (default: benefits-calculator)"
    echo ""
    echo "Examples:"
    echo "  $0 ~/code/mfb"
    echo "  $0 ~/work/mfb benefits-be benefits-fe"
    echo "  $0 /Users/dev/projects/mfb"
    echo ""
    echo "What this script does:"
    echo "  - Creates symlinks for CLAUDE.md and commands/"
    echo "  - Sets up hooks.json with correct paths"
    echo "  - Installs git hooks for proper commit attribution"
    echo "  - Safe to run multiple times (idempotent)"
    exit 1
}

# Check if symlink exists and points to correct target
check_symlink() {
    local link_path="$1"
    local expected_target="$2"

    if [ -L "$link_path" ]; then
        local current_target=$(readlink "$link_path")
        if [ "$current_target" = "$expected_target" ]; then
            return 0  # Already correct
        else
            return 1  # Exists but wrong target
        fi
    elif [ -e "$link_path" ]; then
        return 2  # Exists but not a symlink
    else
        return 3  # Doesn't exist
    fi
}

# Create or update symlink
create_symlink() {
    local target="$1"
    local link_path="$2"
    local description="$3"

    # Disable exit-on-error temporarily to capture return code
    set +e
    check_symlink "$link_path" "$target"
    local status=$?
    set -e

    case $status in
        0)
            print_success "$description already set up correctly"
            return 0
            ;;
        1)
            print_warning "$description exists but points to wrong location"
            print_info "Updating symlink..."
            ln -sf "$target" "$link_path"
            print_success "$description updated"
            ;;
        2)
            print_warning "$description exists but is not a symlink"
            print_info "Backing up to ${link_path}.backup"
            mv "$link_path" "${link_path}.backup"
            ln -s "$target" "$link_path"
            print_success "$description created (original backed up)"
            ;;
        3)
            ln -s "$target" "$link_path"
            print_success "$description created"
            ;;
    esac
}

# Main setup function
main() {
    # Parse arguments
    if [ $# -lt 1 ]; then
        usage
    fi

    MFB_WORKSPACE="$1"
    BACKEND_REPO="${2:-$DEFAULT_BACKEND_REPO}"
    FRONTEND_REPO="${3:-$DEFAULT_FRONTEND_REPO}"

    # Validate repo arguments aren't full paths
    if [[ "$BACKEND_REPO" == *"/"* ]]; then
        print_error "Backend repo should be a name, not a full path!"
        print_info "You provided: $BACKEND_REPO"

        # Try to extract just the repo name
        SUGGESTED_BACKEND=$(basename "$BACKEND_REPO")
        print_info "Did you mean: $SUGGESTED_BACKEND?"
        echo ""
        print_warning "Please run the script with just the repo name:"
        echo "  $0 $MFB_WORKSPACE $SUGGESTED_BACKEND $(basename "$FRONTEND_REPO")"
        echo ""
        exit 1
    fi

    if [[ "$FRONTEND_REPO" == *"/"* ]]; then
        print_error "Frontend repo should be a name, not a full path!"
        print_info "You provided: $FRONTEND_REPO"

        # Try to extract just the repo name
        SUGGESTED_FRONTEND=$(basename "$FRONTEND_REPO")
        print_info "Did you mean: $SUGGESTED_FRONTEND?"
        echo ""
        print_warning "Please run the script with just the repo name:"
        echo "  $0 $MFB_WORKSPACE $(basename "$BACKEND_REPO") $SUGGESTED_FRONTEND"
        echo ""
        exit 1
    fi

    # Get absolute path to this script's directory (team-claude-config)
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

    # Expand ~ in workspace path
    MFB_WORKSPACE="${MFB_WORKSPACE/#\~/$HOME}"

    # Convert to absolute path
    MFB_WORKSPACE="$(cd "$MFB_WORKSPACE" 2>/dev/null && pwd)" || {
        print_error "Workspace directory does not exist: $1"
        print_info "Please create it first: mkdir -p $1"
        exit 1
    }

    echo ""
    echo "======================================"
    echo "  Team Claude Code Setup"
    echo "======================================"
    echo ""
    print_info "Configuration:"
    echo "  Workspace:     $MFB_WORKSPACE"
    echo "  Team Config:   $SCRIPT_DIR"
    echo "  Backend Repo:  $BACKEND_REPO"
    echo "  Frontend Repo: $FRONTEND_REPO"
    echo ""

    # Confirm with user
    read -p "Proceed with setup? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Setup cancelled"
        exit 0
    fi
    echo ""

    # Step 1: Create .claude directory if needed
    print_info "Step 1: Creating .claude directory..."
    mkdir -p "$MFB_WORKSPACE/.claude"
    print_success ".claude directory ready"
    echo ""

    # Step 2: Symlink CLAUDE.md
    print_info "Step 2: Setting up CLAUDE.md..."
    create_symlink \
        "$SCRIPT_DIR/CLAUDE.md" \
        "$MFB_WORKSPACE/CLAUDE.md" \
        "CLAUDE.md symlink"
    echo ""

    # Step 3: Symlink commands directory
    print_info "Step 3: Setting up commands..."
    create_symlink \
        "$SCRIPT_DIR/commands" \
        "$MFB_WORKSPACE/.claude/commands" \
        "Commands directory symlink"
    echo ""

    # Step 4: Set up hooks.json
    print_info "Step 4: Setting up hooks.json..."
    HOOKS_FILE="$MFB_WORKSPACE/.claude/hooks.json"

    if [ -f "$HOOKS_FILE" ]; then
        # Check if it's already customized
        if grep -q "<mfb-workspace>" "$HOOKS_FILE"; then
            print_warning "hooks.json exists but has placeholders, updating..."
        else
            print_success "hooks.json already exists and is customized"
            echo ""
            print_info "Step 5: Setting up git hooks..."
            # Skip to git hooks
        fi
    fi

    # Copy and customize hooks template
    if [ ! -f "$HOOKS_FILE" ] || grep -q "<mfb-workspace>" "$HOOKS_FILE" 2>/dev/null; then
        cp "$SCRIPT_DIR/hooks.json.template" "$HOOKS_FILE"

        # Replace placeholders based on OS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|<mfb-workspace>|$MFB_WORKSPACE|g" "$HOOKS_FILE"
            sed -i '' "s|benefits-api|$BACKEND_REPO|g" "$HOOKS_FILE"
            sed -i '' "s|benefits-calculator|$FRONTEND_REPO|g" "$HOOKS_FILE"
        else
            # Linux
            sed -i "s|<mfb-workspace>|$MFB_WORKSPACE|g" "$HOOKS_FILE"
            sed -i "s|benefits-api|$BACKEND_REPO|g" "$HOOKS_FILE"
            sed -i "s|benefits-calculator|$FRONTEND_REPO|g" "$HOOKS_FILE"
        fi

        print_success "hooks.json created and customized"
    fi
    echo ""

    # Step 5: Set up git hooks
    print_info "Step 5: Setting up git hooks..."

    # Backend repo
    if [ -d "$MFB_WORKSPACE/$BACKEND_REPO/.git" ]; then
        BACKEND_HOOK="$MFB_WORKSPACE/$BACKEND_REPO/.git/hooks/prepare-commit-msg"
        cp "$SCRIPT_DIR/git-hooks/prepare-commit-msg" "$BACKEND_HOOK"
        chmod +x "$BACKEND_HOOK"
        print_success "Git hook installed in $BACKEND_REPO"
    else
        print_warning "$BACKEND_REPO not found or not a git repo, skipping git hook"
    fi

    # Frontend repo
    if [ -d "$MFB_WORKSPACE/$FRONTEND_REPO/.git" ]; then
        FRONTEND_HOOK="$MFB_WORKSPACE/$FRONTEND_REPO/.git/hooks/prepare-commit-msg"
        cp "$SCRIPT_DIR/git-hooks/prepare-commit-msg" "$FRONTEND_HOOK"
        chmod +x "$FRONTEND_HOOK"
        print_success "Git hook installed in $FRONTEND_REPO"
    else
        print_warning "$FRONTEND_REPO not found or not a git repo, skipping git hook"
    fi
    echo ""

    # Final verification
    print_info "Verifying setup..."
    echo ""

    errors=0

    # Check CLAUDE.md
    if [ -L "$MFB_WORKSPACE/CLAUDE.md" ]; then
        print_success "CLAUDE.md: $(readlink "$MFB_WORKSPACE/CLAUDE.md")"
    else
        print_error "CLAUDE.md symlink not found"
        errors=$((errors + 1))
    fi

    # Check commands
    if [ -L "$MFB_WORKSPACE/.claude/commands" ]; then
        print_success "Commands: $(readlink "$MFB_WORKSPACE/.claude/commands")"
    else
        print_error "Commands symlink not found"
        errors=$((errors + 1))
    fi

    # Check hooks.json
    if [ -f "$MFB_WORKSPACE/.claude/hooks.json" ]; then
        if grep -q "<mfb-workspace>" "$MFB_WORKSPACE/.claude/hooks.json"; then
            print_error "hooks.json still contains placeholders"
            errors=$((errors + 1))
        else
            print_success "hooks.json configured"
        fi
    else
        print_error "hooks.json not found"
        errors=$((errors + 1))
    fi

    # Check git hooks
    hook_count=0
    if [ -x "$MFB_WORKSPACE/$BACKEND_REPO/.git/hooks/prepare-commit-msg" ]; then
        hook_count=$((hook_count + 1))
    fi
    if [ -x "$MFB_WORKSPACE/$FRONTEND_REPO/.git/hooks/prepare-commit-msg" ]; then
        hook_count=$((hook_count + 1))
    fi

    if [ $hook_count -gt 0 ]; then
        print_success "Git hooks installed in $hook_count repo(s)"
    else
        print_warning "No git hooks installed (repos may not exist yet)"
    fi

    echo ""
    echo "======================================"

    if [ $errors -eq 0 ]; then
        print_success "Setup completed successfully!"
        echo ""
        print_info "Next steps:"
        echo "  1. cd $MFB_WORKSPACE"
        echo "  2. Start Claude Code"
        echo "  3. Try: /add-program or /coderabbit-comment-review"
    else
        print_error "Setup completed with $errors error(s)"
        echo ""
        print_info "Please check the errors above and try again"
        exit 1
    fi

    echo "======================================"
    echo ""
}

# Run main function
main "$@"
