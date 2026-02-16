---
name: coderabbit-comment-review
description: Systematically review and respond to CodeRabbit feedback on pull requests. Follows Django best practices with automatic quality gates.
usage: /coderabbit-comment-review <PR-number>
example: /coderabbit-comment-review 123
---

<command-name>coderabbit-comment-review</command-name>

# CodeRabbit Comment Review - PR Response Workflow

Systematically addresses CodeRabbit feedback on pull requests following a two-phase approach: planning and implementation.

## Overview

When CodeRabbit reviews a PR, it leaves inline comments with suggestions. This command helps you:
1. Discover all unresolved CodeRabbit comments
2. Plan responses and implementation strategy
3. Implement agreed-upon changes
4. Respond to comments with proper threading
5. Commit and push improvements

## Usage

```bash
/coderabbit-comment-review <PR-number>
```

Example:
```bash
/coderabbit-comment-review 123
```

## Phase 1: CodeRabbit Status Check & Discovery Planning Phase

### Step 1: Notify User and Check Context

1. **Notify the user the planning phase has started**
   - Indicate which Claude model is being used

2. **Verify Repository Details**
   ```bash
   # Check current repository
   gh repo view --json owner,name

   # Confirm PR exists
   gh pr view <PR-number> --json number,title,state
   ```
   - This ensures correct owner/repo before API calls

### Step 2: Check CodeRabbit Status

1. **Quick check**: If last CodeRabbit comment is >10 minutes old, assume review complete and proceed

2. **Only ask user if**: Comments are <10 minutes old OR status is unclear

3. **Look for indicators**:
   - Check comment timestamps: Comments all from same time period = likely complete
   - Look for "Review completed" message in PR conversation
   - If all comments are >10 minutes old, review is likely complete

4. **User confirmation** (if needed):
   > "CodeRabbit appears to still be actively reviewing this PR. Should I proceed with addressing existing comments, or would you prefer to wait for CodeRabbit to complete its review?"

5. **Proceed only after**: User explicitly confirms to continue OR comments are clearly complete

### Step 3: Initial Assessment

1. **Get PR overview**:
   ```bash
   gh pr view <PR-number> --json comments,reviews
   ```

2. **Get all CodeRabbit review comments**:
   ```bash
   gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<PR-number>/reviews
   ```

3. **Extract inline CodeRabbit comments systematically**:

   a. Get all inline comments:
   ```bash
   gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<PR-number>/comments --paginate
   ```

   b. Filter for CodeRabbit:
   ```bash
   jq '.[] | select(.user.login == "coderabbitai[bot]")'
   ```

   c. Identify top-level comments (not replies):
   ```bash
   jq '.[] | select(.user.login == "coderabbitai[bot]") | select(.in_reply_to_id == null)'
   ```

   d. Extract key details:
   ```bash
   jq '{id: .id, path: .path, line: .line, body: (.body | split("\\n")[0:2] | join(" "))}'
   ```

4. **Check for existing replies**:
   ```bash
   # Get all comments with replies
   gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<PR-number>/comments --paginate | \
     jq '.[] | select(.in_reply_to_id != null) | .in_reply_to_id' | sort -u
   ```
   - Filter out already-addressed comments from the unresolved list

5. **Cross-reference** with conversation thread to identify which comments have been addressed

6. **Create structured list** of unresolved comments organized by priority:
   - Critical Issues
   - Recent Comments
   - Refactor Suggestions

7. **Write unresolved comments** to temporary document:
   ```bash
   /tmp/pr<PR-number>_unresolved_coderabbit_comments.md
   ```
   - If this file already exists, clear it out and add a new list

8. **Print todo list** of unresolved comments with the id and summary for the user to see

### Step 4: Responding to Comments (CRITICAL)

**Guidelines for leaving comments:**

- ✅ **Comments should be left using Claude's GitHub user**
- ❌ **NEVER leave general PR comments** - Always respond to specific inline code comments
- ✅ **Use nested replies**: Respond directly to CodeRabbit's inline comments in files view
- ✅ **Command format for replies**:
  ```bash
  gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<PR-number>/comments \
    -X POST \
    --field body="RESPONSE" \
    --field in_reply_to=<COMMENT_ID>
  ```
- ✅ **Alternative for simple acknowledgment**: Add reaction instead of comment when appropriate
- ✅ **Verify nesting**: Responses should appear under original comment with proper threading

### Step 5: Plan Response for Each Unresolved Comment

1. **Use available model** (note which model is in use - prefer Opus for planning if available)

2. **Start a plan for next steps**

3. **Decide a plan of action** for each unresolved comment:

   - **Agree**:
     - Update the plan that we will implement suggested changes
     - Leave a comment following guidelines above affirming the change will be implemented
     - Example: "Good catch! I'll refactor this to use a custom manager method as suggested."

   - **Disagree**:
     - Provide clear reasoning with context about why suggestion doesn't fit
     - Example: "This pattern is intentional here because we need to handle X edge case. The standard approach would fail when..."

   - **Partial agreement**:
     - Acknowledge valid points while explaining constraints
     - Example: "You're right about the duplication. I'll extract the common logic, but keeping the validation inline since it's specific to each case."

   - **Be constructive**:
     - Engage in technical dialogue to reach consensus
     - Ask clarifying questions if needed

## Phase 2: Implementation When Agreeing

### Step 1: Switch to Implementation Mode

1. **Notify User** we're on to phase 2

2. **Use available model** (note which model - prefer Sonnet for implementation if available)

3. **Optional**: Use specialized agent if available (e.g., senior-django-engineer)

### Step 2: Work Through Plan and Implement Changes

Implement agreed-upon changes following Django best practices:

- Extract duplicated logic into managers/services
- Add proper error handling and validation
- Implement suggested architectural improvements
- Follow fat models, skinny views pattern
- Add type hints where missing
- Update docstrings

### Step 3: Validation

**After making changes, validate everything:**

1. **Verify comment threading**:
   - Ensure all responses are properly nested under original comments
   - Verify comment URLs follow format: `#discussion_r[NUMBER]`
   - Check that conversation threads are properly linked

2. **Run quality checks**:
   ```bash
   # Run tests
   python manage.py test

   # Run linting
   ruff check .

   # Run type checking
   mypy .

   # Check formatting
   black --check .
   ```

3. **Verify changes work**:
   - All tests passing
   - No new linting errors
   - Type checking clean

### Step 4: Commit and Push Changes

**ALWAYS commit code changes** made during CodeRabbit review process:

1. **Stage changes**:
   ```bash
   git add .
   ```

2. **Create descriptive commit**:
   ```bash
   git commit -m "Address CodeRabbit feedback: [brief description]

   - Change 1: Description
   - Change 2: Description
   - Change 3: Description

   🤖 Generated with Claude Code (https://claude.ai/code)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

3. **Push to update PR**:
   ```bash
   git push
   ```

## Best Practices

### When Agreeing with Feedback

✅ Leave a comment acknowledging and confirming implementation
✅ Implement changes following Django patterns
✅ Run full test suite before committing
✅ Update related tests if needed
✅ Commit with clear description of what changed

### When Disagreeing with Feedback

✅ Provide clear technical reasoning
✅ Reference Django best practices or project constraints
✅ Be respectful and constructive
✅ Offer alternative approaches if applicable
✅ Ask for clarification if suggestion is unclear

### Comment Threading

✅ Always reply to specific inline comments
✅ Never leave general PR-level comments for code feedback
✅ Use reactions (👍) for simple acknowledgments
✅ Verify comments appear in correct thread

## Error Handling

### If PR Not Found

```
❌ Error: Could not find PR #<PR-number>

Please verify:
- PR number is correct
- You have access to the repository
- PR is in the current repository

Usage: /coderabbit-comment-review <PR-number>
```

### If No CodeRabbit Comments

```
ℹ️  No unresolved CodeRabbit comments found on PR #<PR-number>

Either:
- CodeRabbit hasn't reviewed yet (check PR for status)
- All comments have been addressed
- CodeRabbit review is still in progress

Check PR status: gh pr view <PR-number>
```

### If Comment API Fails

```
❌ Error: Failed to post comment to PR

Possible issues:
- GitHub API authentication failed
- Insufficient permissions
- Rate limit exceeded

Try: gh auth status
```

## Quality Gates

All changes must pass:

- ✅ Django tests passing
- ✅ Ruff linting clean
- ✅ MyPy type checking
- ✅ Black formatting
- ✅ No breaking changes to existing functionality

## Success Criteria

- ✅ All CodeRabbit comments reviewed
- ✅ Responses posted with proper threading
- ✅ Agreed-upon changes implemented
- ✅ All tests passing
- ✅ Code quality checks passing
- ✅ Changes committed and pushed
- ✅ PR updated with improvements

## Notes

- This command works with Django projects following MyFriendBen patterns
- Focuses on constructive dialogue with CodeRabbit
- Maintains high code quality standards throughout
- Keeps PR up-to-date with implemented improvements
- Uses proper GitHub comment threading for clarity
