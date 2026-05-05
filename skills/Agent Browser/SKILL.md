---
name: Agent Browser
version: 0.2.0
name_zh: "浏览器自动化"
name_ja: "ブラウザ自動化"
description: "High-performance browser automation CLI (Rust-based, Node.js fallback). For automating web interactions, scraping structured data, filling forms, and testing web UIs via navigation, click, input, and snapshot commands."
description_zh: "基于 Rust 的高性能浏览器自动化工具。自动化网页交互、抓取结构化数据、填写表单、测试 Web UI。"
description_ja: "Rustベースの高性能ブラウザ自動化CLIツール。Webインタラクション自動化、構造化データ抽出、フォーム入力、Web UIテストに対応。"
read_when:
  - Automating web interactions
  - Extracting structured data from pages
  - Filling forms programmatically
  - Testing web UIs
metadata: {"clawdbot":{"emoji":"🌐","requires":{"bins":["node","npm"]},"npmDeps":["agent-browser"]}}
allowed-tools: Bash(agent-browser:*)
---

# Browser Automation with agent-browser

## 重要行为规范

1. **默认使用有头模式（`--headed`）**：所有 `agent-browser open` 命令必须附加 `--headed` 参数，以便用户可以看到浏览器窗口中的操作过程。
2. **验证码与人工干预**：当遇到验证码（CAPTCHA）、二次验证、滑块验证、短信验证码等需要人工操作的场景时，必须暂停自动化流程，明确提示用户手动完成验证操作，待用户确认完成后再继续执行后续步骤。
3. **自动关闭浏览器**：所有浏览器操作完毕后，必须执行 `agent-browser close` 关闭浏览器，释放资源。不允许在任务结束后遗留打开的浏览器实例。

## Installation

### npm recommended

```bash
npm install -g agent-browser
agent-browser install
agent-browser install --with-deps
```

### From Source

```bash
git clone https://github.com/vercel-labs/agent-browser
cd agent-browser
pnpm install
pnpm build
agent-browser install
```

## Quick start

```bash
agent-browser open <url> --headed  # 以有头模式导航到页面
agent-browser snapshot -i          # 获取可交互元素及其引用
agent-browser click @e1            # 通过引用点击元素
agent-browser fill @e2 "text"      # 通过引用填写输入框
agent-browser close                # 操作完毕，关闭浏览器
```

## Core workflow

1. Navigate: `agent-browser open <url> --headed`（必须使用有头模式）
2. Snapshot: `agent-browser snapshot -i` (returns elements with refs like `@e1`, `@e2`)
3. Interact using refs from the snapshot
4. Re-snapshot after navigation or significant DOM changes
5. 如遇到验证码/人工验证，暂停并提示用户手动完成
6. Close: `agent-browser close`（所有操作完毕后必须关闭浏览器）

## Commands

### Navigation

```bash
agent-browser open <url>      # Navigate to URL
agent-browser back            # Go back
agent-browser forward         # Go forward
agent-browser reload          # Reload page
agent-browser close           # Close browser
```

### Snapshot (page analysis)

```bash
agent-browser snapshot            # Full accessibility tree
agent-browser snapshot -i         # Interactive elements only (recommended)
agent-browser snapshot -c         # Compact output
agent-browser snapshot -d 3       # Limit depth to 3
agent-browser snapshot -s "#main" # Scope to CSS selector
```

### Interactions (use @refs from snapshot)

```bash
agent-browser click @e1           # Click
agent-browser dblclick @e1        # Double-click
agent-browser focus @e1           # Focus element
agent-browser fill @e2 "text"     # Clear and type
agent-browser type @e2 "text"     # Type without clearing
agent-browser press Enter         # Press key
agent-browser press Control+a     # Key combination
agent-browser keydown Shift       # Hold key down
agent-browser keyup Shift         # Release key
agent-browser hover @e1           # Hover
agent-browser check @e1           # Check checkbox
agent-browser uncheck @e1         # Uncheck checkbox
agent-browser select @e1 "value"  # Select dropdown
agent-browser scroll down 500     # Scroll page
agent-browser scrollintoview @e1  # Scroll element into view
agent-browser drag @e1 @e2        # Drag and drop
agent-browser upload @e1 file.pdf # Upload files
```

### Get information

```bash
agent-browser get text @e1        # Get element text
agent-browser get html @e1        # Get innerHTML
agent-browser get value @e1       # Get input value
agent-browser get attr @e1 href   # Get attribute
agent-browser get title           # Get page title
agent-browser get url             # Get current URL
agent-browser get count ".item"   # Count matching elements
agent-browser get box @e1         # Get bounding box
```

### Check state

```bash
agent-browser is visible @e1      # Check if visible
agent-browser is enabled @e1      # Check if enabled
agent-browser is checked @e1      # Check if checked
```

### Screenshots & PDF

```bash
agent-browser screenshot          # Screenshot to stdout
agent-browser screenshot path.png # Save to file
agent-browser screenshot --full   # Full page
agent-browser pdf output.pdf      # Save as PDF
```

### Video recording

```bash
agent-browser record start ./demo.webm    # Start recording (uses current URL + state)
agent-browser click @e1                   # Perform actions
agent-browser record stop                 # Stop and save video
agent-browser record restart ./take2.webm # Stop current + start new recording
```

Recording creates a fresh context but preserves cookies/storage from your session. If no URL is provided, it automatically returns to your current page. For smooth demos, explore first, then start recording.

### Wait

```bash
agent-browser wait @e1                     # Wait for element
agent-browser wait 2000                    # Wait milliseconds
agent-browser wait --text "Success"        # Wait for text
agent-browser wait --url "/dashboard"    # Wait for URL pattern
agent-browser wait --load networkidle      # Wait for network idle
agent-browser wait --fn "window.ready"     # Wait for JS condition
```

### Mouse control

```bash
agent-browser mouse move 100 200      # Move mouse
agent-browser mouse down left         # Press button
agent-browser mouse up left           # Release button
agent-browser mouse wheel 100         # Scroll wheel
```

### Semantic locators (alternative to refs)

```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

### Browser settings

```bash
agent-browser set viewport 1920 1080      # Set viewport size
agent-browser set device "iPhone 14"      # Emulate device
agent-browser set geo 37.7749 -122.4194   # Set geolocation
agent-browser set offline on              # Toggle offline mode
agent-browser set headers '{"X-Key":"v"}' # Extra HTTP headers
agent-browser set credentials user pass   # HTTP basic auth
agent-browser set media dark              # Emulate color scheme
```

### Cookies & Storage

```bash
agent-browser cookies                     # Get all cookies
agent-browser cookies set name value      # Set cookie
agent-browser cookies clear               # Clear cookies
agent-browser storage local               # Get all localStorage
agent-browser storage local key           # Get specific key
agent-browser storage local set k v       # Set value
agent-browser storage local clear         # Clear all
```

### Network

```bash
agent-browser network route <url>              # Intercept requests
agent-browser network route <url> --abort      # Block requests
agent-browser network route <url> --body '{}'  # Mock response
agent-browser network unroute [url]            # Remove routes
agent-browser network requests                 # View tracked requests
agent-browser network requests --filter api    # Filter requests
```

### Tabs & Windows

```bash
agent-browser tab                 # List tabs
agent-browser tab new [url]       # New tab
agent-browser tab 2               # Switch to tab
agent-browser tab close           # Close tab
agent-browser window new          # New window
```

### Frames

```bash
agent-browser frame "#iframe"     # Switch to iframe
agent-browser frame main          # Back to main frame
```

### Dialogs

```bash
agent-browser dialog accept [text]  # Accept dialog
agent-browser dialog dismiss        # Dismiss dialog
```

### JavaScript

```bash
agent-browser eval "document.title"   # Run JavaScript
```

### State management

```bash
agent-browser state save auth.json    # Save session state
agent-browser state load auth.json    # Load saved state
```

## Example: Form submission

```bash
agent-browser open https://example.com/form --headed
agent-browser snapshot -i
# Output shows: textbox "Email" [ref=e1], textbox "Password" [ref=e2], button "Submit" [ref=e3]

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Check result
agent-browser close        # 操作完毕，关闭浏览器
```

## Example: Authentication with saved state

```bash
# Login once
agent-browser open https://app.example.com/login --headed
agent-browser snapshot -i
agent-browser fill @e1 "username"
agent-browser fill @e2 "password"
agent-browser click @e3
# 如果出现验证码，请手动完成验证后告知继续
agent-browser wait --url "/dashboard"
agent-browser state save auth.json
agent-browser close

# Later sessions: load saved state
agent-browser state load auth.json
agent-browser open https://app.example.com/dashboard --headed
# ... 执行操作 ...
agent-browser close
```

## Sessions (parallel browsers)

```bash
agent-browser --session test1 open site-a.com
agent-browser --session test2 open site-b.com
agent-browser session list
```

## JSON output (for parsing)

Add `--json` for machine-readable output:

```bash
agent-browser snapshot -i --json
agent-browser get text @e1 --json
```

## Debugging

```bash
agent-browser open example.com --headed              # Show browser window
agent-browser console                                # View console messages
agent-browser console --clear                        # Clear console
agent-browser errors                                 # View page errors
agent-browser errors --clear                         # Clear errors
agent-browser highlight @e1                          # Highlight element
agent-browser trace start                            # Start recording trace
agent-browser trace stop trace.zip                   # Stop and save trace
agent-browser record start ./debug.webm              # Record from current page
agent-browser record stop                            # Save recording
agent-browser --cdp 9222 snapshot                    # Connect via CDP
```

## Troubleshooting

- If the command is not found on Linux ARM64, use the full path in the bin folder.
- If an element is not found, use snapshot to find the correct ref.
- If the page is not loaded, add a wait command after navigation.
- Use --headed to see the browser window for debugging.

## Options

- --session <name> uses an isolated session.
- --json provides JSON output.
- --full takes a full page screenshot.
- --headed shows the browser window.
- --timeout sets the command timeout in milliseconds.
- --cdp <port> connects via Chrome DevTools Protocol.

## Notes

- Refs are stable per page load but change on navigation.
- Always snapshot after navigation to get new refs.
- Use fill instead of type for input fields to ensure existing text is cleared.

## Reporting Issues

- Skill issues: Open an issue at https://github.com/TheSethRose/Agent-Browser-CLI
- agent-browser CLI issues: Open an issue at https://github.com/vercel-labs/agent-browser
