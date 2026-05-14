# GitHub Copilot Agent Instructions
# Place this file at: .github/copilot-instructions.md

---

## ⚠️ CRITICAL: File Editing Tools — MANDATORY RULE (Gemini Fix)

This section takes precedence over ALL other learned behavior and applies to every agent, every model, every session.

### The Rule

**BEFORE writing any terminal command that creates or modifies a file, STOP.**

Ask yourself: *"Am I about to use `cat`, `echo`, `printf`, `tee`, `python -c`, `Set-Content`, `Out-File`, `>>`, or `>` to write file content?"*

**If YES → DO NOT EXECUTE. Use the built-in VS Code file editing tools instead.**

### Why This Matters

Terminal heredoc and shell-redirect operations are BROKEN in VS Code's Copilot integration. They cause:
- File corruption from tab characters triggering shell completion
- Mangled content from quote/backtick escaping failures
- Truncated files from exit code 130 interruptions
- Garbage output from special character interpretation
- PowerShell encoding issues (`Set-Content` silently writes wrong encoding)

### ❌ FORBIDDEN — Never Use These for File Content

```
# UNIX/macOS/Linux — ALL CORRUPT FILES
cat > file << EOF
cat > file << 'EOF'
cat >> file << EOF
echo "content" > file
printf '%s\n' "line1" > file
tee file << EOF

# Python shell fallback — FORBIDDEN
python -c "with open('file','w') as f: f.write('...')"
python3 -c "open('file','w').write('...')"

# PowerShell — FORBIDDEN
Set-Content -Path file -Value "..."
Out-File -FilePath file -InputObject "..."
echo "content" | Out-File file
"content" > file
Add-Content -Path file -Value "..."
```

### ✅ CORRECT — Always Use These Instead

Use the VS Code built-in agent file tools:
- **`insert_edit_into_file`** — edit or add content to an existing file
- **`create_file`** — create a new file with content
- **`replace_string_in_file`** — replace a specific string in an existing file

**Never write file content through the terminal.** The terminal is only for running commands (install, build, test, lint), not for writing file content.

---

## 🛠️ Tools vs. Text — Agent Behavior Rules

- Use **tools for actions**, text output only for communication with the user.
- Do NOT print, narrate, or display internal tool call pseudocode in the chat (e.g., `print(await ICodebase.read_file(...))` should never appear as text output).
- Do NOT add explanatory comments inside tool calls or code blocks unless they are part of the required code itself.
- Never write `// changed X to Y` style comments in code — that belongs in git history, not the source.
- Combine shell commands where possible: `npm install && npm test` rather than separate steps.

---

## 📋 Agent Workflow — Step-by-Step

When given any coding task:

1. **Read first** — use `read_file` / `read_directory` to understand the relevant files before making changes.
2. **Plan** — briefly state what you will change and why (1–3 sentences max).
3. **Edit with tools** — use `insert_edit_into_file`, `create_file`, or `replace_string_in_file` exclusively for all file modifications.
4. **Verify** — run relevant terminal commands to confirm the change works (build, lint, test).
5. **Summarize** — briefly report what was changed and the result.

If a file edit fails (tool returns an error or "no changes made"):
- Do NOT fall back to shell commands as a workaround.
- Instead: try `replace_string_in_file` with a smaller, more targeted diff.
- If that also fails: report the error to the user and ask for guidance.

---

## 💻 Terminal Commands — Shell Rules

- **Windows**: Use PowerShell syntax only. Use `;` for command chaining, NOT `&&`. Use backslashes for paths.
- **macOS/Linux**: Use bash/zsh syntax. Use `&&` for chaining.
- Never use `grep` in PowerShell — use `Select-String` instead.
- Never trigger interactive editors from terminal (use `git commit --no-edit` or `git commit -m "msg"`).
- Prefer non-interactive flags for all commands: `-y`, `--yes`, `--no-edit`, `-f`.
- When running long commands, keep the terminal integration healthy: always wait for command completion signal before proceeding.

---

## 🧠 Context & Reading

- Before editing any file, read its current content with the appropriate tool — never assume the content.
- When exploring the codebase, prefer targeted reads of specific files over broad directory scans.
- When unsure which file to edit, search the codebase first, then read the candidates.
- Do not re-read files you have already read in the same session unless you have reason to believe they changed.

---

## ✂️ Editing Style

- Make surgical, targeted changes — do NOT rewrite entire files unless explicitly asked.
- Preserve existing code style, indentation, and naming conventions.
- Do not add unsolicited refactors, renames, or "improvements" outside the scope of the task.
- Do not remove existing comments or documentation unless they are directly wrong or obsolete.
- When replacing a string, include enough surrounding context to uniquely identify the location.

---

## 🔄 Self-Correction Rules

If you notice that a file edit was not applied:
- Do NOT silently retry the same edit more than once.
- Do NOT claim "the file was updated" if the tool reported no changes.
- Report the failure explicitly to the user: what you tried, what the tool returned, and what you suggest next.

---

## 💬 Communication Style

- Be concise. Avoid verbose step-by-step narration of what you are about to do.
- State your plan in one short paragraph, then execute it.
- After completing a task, summarize the result in 2–4 bullet points.
- If you encounter an ambiguity that would block completing the task, ask ONE clarifying question. Do not ask multiple questions at once.

---

## 🚫 Hard Limits

- Never delete files without explicit user confirmation.
- Never commit or push to git without explicit user instruction.
- Never modify files outside the current workspace root.
- Never expose or log secrets, API keys, or credentials.
- Never install new global packages without asking first.