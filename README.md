# AutoQQ — QQ 好友/群成员筛选工具

## 工具用途

本工具专为**市场营销专业同学**设计，用于通过**年龄和性别**从 QQ 好友及群成员中快速筛选精准客户群体，辅助市场调研与客户画像分析。

- **目标用户**：市场营销相关专业学生及从业者
- **使用场景**：课堂实训、市场调研作业、客户群体初筛
- **禁止用途**：不得用于骚扰用户、发送垃圾广告、诈骗、侵犯隐私等任何违法违规行为。使用者需自行遵守《网络安全法》《个人信息保护法》等相关法律法规。

> ⚠️ 本工具仅供合法市场调研之用，请勿用于非法用途。

---

## 前置环境（新电脑必须配置）

### 1. 安装 Node.js（必须）

LLBot 机器人框架依赖 Node.js 运行，**必须安装**。

```powershell
# 方式一：官网下载（推荐，选 LTS 版本）
# https://nodejs.org/

# 方式二：winget 一键安装
winget install OpenJS.NodeJS.LTS
```

**安装后验证**（关掉 PowerShell 重新打开再执行）：
```powershell
node --version
# 应该输出: v20.x.x 或 v22.x.x
```

> ⚠️ 安装完需要**重启电脑**或重新打开命令行窗口，否则可能提示找不到 node。

---

### 2. 安装 QQ NT 客户端（必须）

必须是 **QQ NT 架构版**（版本号 9.x），不是旧版 QQ。

```
下载地址：https://im.qq.com/pcqq
```

安装完成后，找到 QQ.exe 的安装路径。常见位置：
- `C:\Program Files\Tencent\QQNT\QQ.exe`
- `D:\Program Files\Tencent\QQ\QQ.exe`
- `D:\ProgramFiles\QQ\QQ.exe`

---

### 3. 配置 QQ 路径（必须）

打开 `rbt/bin/pmhq/pmhq_config.json`，把路径改成你电脑上 QQ.exe 的实际位置：

```json
{
  "qq_path": "D:\\ProgramFiles\\QQ\\QQ.exe"
}
```

> 注意：路径分隔符用双反斜杠 `\\`，或单正斜杠 `/`。

---

### 4. 登录 QQ（必须）

手动打开 QQ 并**登录你的账号**，勾选"记住密码"和"自动登录"。之后 PMHQ 重启 QQ 时就能自动登录了。

---

## 运行工具

### 双击 `启动AutoQQ.bat`

会打开图形化启动器界面（已打包为 exe，无需安装 Python）。

```
┌──────────────────────────────────────┐
│         AutoQQ 启动器                 │
│                                      │
│  [环境检测]                           │
│   Node.js: 已安装 ✓                  │
│   QQ 客户端: 已运行 ✓                 │
│   Bot 框架文件: 正常 ✓                │
│   PMHQ 桥接文件: 正常 ✓               │
│                                      │
│  [服务控制]                           │
│   QQ 通信桥接: ● 运行中               │
│   Bot 服务:    ● 运行中               │
│   API 接口:    ● 就绪                 │
│                                      │
│  [▶ 启动Bot服务] [■ 停止] [📋 筛选]  │
│                                      │
│  [运行日志]                           │
└──────────────────────────────────────┘
```

### 操作步骤

1. 双击 **`启动AutoQQ.bat`**
2. 点击 **「▶ 启动 Bot 服务」**
   - 程序会自动关闭 QQ 并重新启动（冷注入，确保稳定）
   - 等待日志显示「所有服务启动完成」
3. 三个指示灯都变绿后，点击 **「📋 打开筛选工具」**
4. 在筛选工具中：
   - 先点「加载群列表」
   - 选择性别、年龄范围
   - 勾选数据来源（好友/群）
   - 点击「开始筛选」
   - 点「导出结果」保存到文件

> 注意：启动 Bot 时 QQ 会被关闭再重启，请等待自动重新登录。

---

## 目录结构

```
AutoQQ/
├── 启动AutoQQ.bat              # ★ 双击启动
├── autoqq_launcher.exe         # 启动器（打包好的 exe，无需 Python）
├── autoqq_launcher.py          # 启动器源码（可选，需要 Python）
├── qq_gui.exe                  # 筛选工具（打包好的 exe，无需 Python）
├── qq_gui.py                   # 筛选工具源码（可选）
├── qq_filter.py                # 命令行筛选工具（可选，需要 Python）
│
├── rbt/                        # ★ Bot 框架
│   └── bin/
│       ├── llbot/              # LLBot Node.js 框架
│       │   ├── llbot.js            # 主程序
│       │   ├── default_config.json # 默认配置模板
│       │   ├── webui/              # Web 管理界面
│       │   └── data/               # [运行时] 配置、数据库、日志
│       └── pmhq/               # PMHQ QQ 桥接
│           ├── pmhq-win-x64.exe    # 注入器
│           ├── pmhq.dll            # 注入 DLL
│           └── pmhq_config.json    # ★ QQ 路径配置（需修改）
│
└── napcat/                     # QQ 客户端数据（QQ 自动生成）
    └── QQ/                     # 账号数据、数据库、缓存
```

> `[运行时]` 标记的目录是程序运行自动生成的，可以删除。

---

## 端口说明

| 端口 | 服务 | 用途 |
|------|------|------|
| 13000 | PMHQ 桥接 | QQ 进程内通信 |
| 8099 | OneBot HTTP API | 筛选工具获取数据 |

---

## 常见问题

### Q: Node.js 已安装但提示找不到 node
**A**: 安装后需**重启电脑**或重新打开命令行。或手动检查 `C:\Program Files\nodejs\` 是否在系统 PATH 中。

### Q: 点击启动后 PMHQ 超时
**A**: 
1. 检查 `pmhq_config.json` 中 QQ 路径是否正确
2. 确认 QQ 已安装且为 NT 版本（9.x）
3. 确认杀毒软件没有拦截 `pmhq-win-x64.exe`

### Q: 筛选时提示 "timed out"
**A**: PMHQ 桥接已断开。点击「停止」→ 重新「启动」，然后立即打开筛选工具。

### Q: 启动后 QQ 没有自动登录
**A**: 
1. 检查 `pmhq_config.json` 中 QQ 路径是否正确
2. 确保以前在这台电脑上登录过 QQ 并勾选了"记住密码"

### Q: 换到新电脑怎么用
**A**: 
1. 安装 Node.js
2. 安装 QQ NT
3. 复制整个 AutoQQ 文件夹到新电脑
4. 修改 `rbt/bin/pmhq/pmhq_config.json` 中的 QQ 路径
5. 登录 QQ（勾选记住密码）
6. 双击 `启动AutoQQ.bat`

### Q: 界面显示"QQ 未检测到运行"
**A**: 启动器每 5 秒自动刷新状态，等几秒即可。或者手动打开 QQ 后再观察。

### Q: 需要安装 Python 吗
**A**: **不需要**。工具已打包为 `autoqq_launcher.exe` 和 `qq_gui.exe`，直接双击运行。只有在需要修改源码时才需要 Python。

---

## 技术架构

```
QQ.exe ←─[DLL 注入]─→ PMHQ (13000) ←→ LLBot (8099) ←→ 筛选工具
                            │                     │
                      pmhq.dll               qq_gui.exe
                    (Rust 内存钩子)       (PyInstaller 打包)
```
