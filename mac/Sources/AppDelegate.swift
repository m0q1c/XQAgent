import Cocoa
import WebKit

let APP_PORT = 18777

class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKUIDelegate {
    let appPort = APP_PORT
    var window: NSWindow!
    var webView: WKWebView!
    var pythonProcess: Process?
    var hasLoadedApp = false
    var statusLabel: NSTextField!

    func applicationDidFinishLaunching(_ notification: Notification) {
        // 程序目录：.app/Contents/Resources/
        let resourceDir = Bundle.main.resourcePath ?? (Bundle.main.bundlePath as NSString).deletingLastPathComponent

        // ── 窗口 ──
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1100, height: 720),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false
        )
        window.title = "XQAgent"
        window.center()
        window.minSize = NSSize(width: 680, height: 480)
        window.setFrameAutosaveName("XQAgentWindow")
        window.delegate = self

        // ── 启动状态标签 ──
        statusLabel = NSTextField(labelWithString: "正在启动 XQAgent…")
        statusLabel.font = NSFont.systemFont(ofSize: 18, weight: .medium)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.alignment = .center
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        window.contentView?.addSubview(statusLabel)
        NSLayoutConstraint.activate([
            statusLabel.centerXAnchor.constraint(equalTo: window.contentView!.centerXAnchor),
            statusLabel.centerYAnchor.constraint(equalTo: window.contentView!.centerYAnchor),
        ])

        // ── WebView（一开始隐藏，Python 就绪后显示）──
        let config = WKWebViewConfiguration()
        if #available(macOS 12.3, *) {
            config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        }
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        webView.allowsBackForwardNavigationGestures = true
        webView.isHidden = true  // 初始隐藏，等待后端就绪
        window.contentView?.addSubview(webView)

        // 菜单
        setupMenu()

        // 启动 Python 后端
        launchPython(in: resourceDir)

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        // ── 超时检测：30 秒后端未就绪则报错 ──
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { [weak self] in
            guard let self = self, !self.hasLoadedApp else { return }
            self.statusLabel.stringValue = "⚠️ 后端启动超时"
            self.statusLabel.textColor = .systemRed
            // 尝试直接加载 localhost（万一后端实际已在运行但检测遗漏）
            self.loadWebApp()
        }
    }

    // MARK: - Python 后端

    /// 记录 Python 输出的日志文件路径（在 ~/Library/Logs/XQAgent/ 下）
    lazy var logDir: String = {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let dir = "\(home)/Library/Logs/XQAgent"
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        return dir
    }()

    func launchPython(in dir: String) {
        // 先清理端口残留
        shell("lsof -ti :\(appPort) 2>/dev/null | xargs kill -9 2>/dev/null")
        usleep(200_000)

        // 优先使用内置 Python（开箱即用）
        let bundledPython = "\(dir)/python/bin/python3"
        let useBundled = FileManager.default.isExecutableFile(atPath: bundledPython)

        let python3 = useBundled ? bundledPython : findPython3()
        guard let python3 = python3 else {
            showError("未找到 Python3", detail: "内置 Python 不可用，且系统中未找到 Python3。")
            return
        }

        pythonProcess = Process()
        guard let proc = pythonProcess else { return }
        let pythonPath = "\(dir)/app.py"
        proc.executableURL = URL(fileURLWithPath: python3)
        proc.arguments = ["-u", pythonPath, "--port", "\(appPort)"]
        proc.currentDirectoryURL = URL(fileURLWithPath: dir)
        // 内置 Python 已通过 @executable_path 链接，无需 DYLD_LIBRARY_PATH
        // 但保留纯净环境避免 brew 路径污染
        var env = ProcessInfo.processInfo.environment
        env["PYTHONHOME"] = dir + "/python"
        proc.environment = env

        // ── Python 日志输出 ──
        let logPath = "\(logDir)/python-\(Int(Date().timeIntervalSince1970)).log"
        let outHandle = FileHandle(forWritingAtPath: logPath) ?? {
            FileManager.default.createFile(atPath: logPath, contents: nil)
            return FileHandle(forWritingAtPath: logPath)!
        }()

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        // 从 Python 输出检测启动完成 + 写入日志文件
        let logPathCopy = logPath
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self = self, !data.isEmpty else { return }

            // 写入日志文件
            if let fh = FileHandle(forWritingAtPath: logPathCopy) {
                fh.seekToEndOfFile()
                fh.write(data)
                try? fh.close()
            }

            if let line = String(data: data, encoding: .utf8) {
                print("[XQ] \(line.trimmingCharacters(in: .whitespacesAndNewlines))")
                if line.contains("已启动") || line.contains("http://localhost") {
                    usleep(500_000)
                    DispatchQueue.main.async { self.loadWebApp() }
                }
            }
        }

        do {
            try proc.run()
            // 轮询端口作为保底
            DispatchQueue.global().async { [weak self] in self?.pollPort() }
        } catch {
            print("[XQ] 启动 Python 失败: \(error)")
            showError("无法启动 Python 后端", detail: error.localizedDescription)
        }
    }

    func pollPort() {
        while !hasLoadedApp {
            let result = shell("lsof -ti :\(appPort) 2>/dev/null")
            if !result.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                usleep(500_000)
                DispatchQueue.main.async { self.loadWebApp() }
                return
            }
            Thread.sleep(forTimeInterval: 0.5)
        }
    }

    func loadWebApp() {
        guard !hasLoadedApp else { return }
        hasLoadedApp = true
        statusLabel.isHidden = true
        webView.isHidden = false
        let url = URL(string: "http://localhost:\(appPort)")!
        webView?.load(URLRequest(url: url))
    }

    func showError(_ title: String, detail: String) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.statusLabel.stringValue = "❌ \(title)"
            self.statusLabel.textColor = .systemRed
            let alert = NSAlert()
            alert.messageText = title
            alert.informativeText = detail + "\n\n日志路径: \(self.logDir)"
            alert.runModal()
        }
    }

    @discardableResult
    func shell(_ command: String) -> String {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/sh")
        task.arguments = ["-c", command]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        try? task.run()
        task.waitUntilExit()
        let raw = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: raw, encoding: .utf8) ?? ""
    }

    func findPython3() -> String? {
        let candidates = [
            "/opt/homebrew/bin/python3.11",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        for p in candidates {
            if FileManager.default.isExecutableFile(atPath: p) {
                return p
            }
        }
        // fallback: which python3
        let whichResult = shell("which python3 2>/dev/null").trimmingCharacters(in: .whitespacesAndNewlines)
        if !whichResult.isEmpty, FileManager.default.isExecutableFile(atPath: whichResult) {
            return whichResult
        }
        return nil
    }

    // MARK: - 菜单

    func setupMenu() {
        let menubar = NSMenu()
        NSApp.mainMenu = menubar

        let appItem = NSMenuItem()
        menubar.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(NSMenuItem(title: "关于 XQAgent", action: #selector(NSApp.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(title: "退出 XQAgent", action: #selector(NSApp.terminate(_:)), keyEquivalent: "q"))

        let editItem = NSMenuItem()
        menubar.addItem(editItem)
        let editMenu = NSMenu(title: "编辑")
        editItem.submenu = editMenu
        editMenu.addItem(NSMenuItem(title: "撤销", action: Selector(("undo:")), keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "重做", action: Selector(("redo:")), keyEquivalent: "Z"))
        editMenu.addItem(.separator())
        editMenu.addItem(NSMenuItem(title: "剪切", action: Selector(("cut:")), keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "复制", action: Selector(("copy:")), keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "粘贴", action: Selector(("paste:")), keyEquivalent: "v"))
        editMenu.addItem(NSMenuItem(title: "全选", action: Selector(("selectAll:")), keyEquivalent: "a"))

        let viewItem = NSMenuItem()
        menubar.addItem(viewItem)
        let viewMenu = NSMenu(title: "视图")
        viewItem.submenu = viewMenu
        viewMenu.addItem(NSMenuItem(title: "重新加载", action: #selector(reloadPage), keyEquivalent: "r"))
        viewMenu.addItem(.separator())
        viewMenu.addItem(NSMenuItem(title: "在浏览器中打开", action: #selector(openInBrowser), keyEquivalent: "b"))
    }

    @objc func reloadPage() { webView?.reloadFromOrigin() }

    @objc func openInBrowser() {
        let url = webView?.url ?? URL(string: "http://localhost:\(appPort)")!
        NSWorkspace.shared.open(url)
    }

    // MARK: - WKUIDelegate: 文件上传（备用方案，前端的 /api/select-file 更优先）

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.allowedFileTypes = nil
        panel.title = "选择文件"
        panel.message = "上传到 XQAgent"
        panel.beginSheetModal(for: window) { response in
            if response == .OK {
                completionHandler(panel.urls)
            } else {
                completionHandler(nil)
            }
        }
    }

    // MARK: - 退出

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        pythonProcess?.terminate()
        pythonProcess?.waitUntilExit()
        shell("lsof -ti :\(appPort) 2>/dev/null | xargs kill -9 2>/dev/null")
    }
}
