# AutoQQ — QQ 好友/群成员筛选工具

## 工具用途

本工具专为**市场营销专业同学**设计，用于通过**年龄和性别**从 QQ 好友及群成员中快速筛选精准客户群体，辅助市场调研与客户画像分析。

- **目标用户**：市场营销相关专业学生及从业者
- **使用场景**：课堂实训、市场调研作业、客户群体初筛
- **禁止用途**：不得用于骚扰用户、发送垃圾广告、诈骗、侵犯隐私等任何违法违规行为。使用者需自行遵守《网络安全法》《个人信息保护法》等相关法律法规。

> ⚠️ 本工具仅供合法市场调研之用，请勿用于非法用途。

---

## 前置环境（新电脑必须配置）

### 1. 安装 Python 3（必须）

启动器和筛选工具是 Python 脚本，**必须安装**。

```powershell
# 官网下载：https://www.python.org/downloads/
# 安装时勾选 "Add Python to PATH"

# 验证
python --version
```

### 2. 安装 Node.js（必须）

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

### 步骤 1：双击 `run_rbt.bat` 启动 Bot

Bot 会自动杀旧进程、启动 PMHQ（QQ 会自动重启）、启动 LLBot。等待显示 **API 就绪**：

```
==================================================
  Bot 启动完成！
  API 地址: http://127.0.0.1:8099
  API 就绪! 账号: 华万能
==================================================
```

### 步骤 2：双击 `run_autoqq.bat` 打开筛选工具

在筛选工具中：
- 先点「加载群列表」
- 选择性别、年龄范围
- 勾选数据来源（好友/群）
- 点击「开始筛选」
- 点「导出结果」保存到文件

> 注意：启动 Bot 时 QQ 会被关闭再重启，请等待自动重新登录。筛选时如果偶尔有几条失败属正常，Bot 会自动恢复。

---

## 目录结构

```
AutoQQ/
├── run_rbt.bat                 # ★ 启动 Bot
├── run_autoqq.bat              # ★ 打开筛选工具
├── qq_gui.py                   # 筛选工具 GUI
├── qq_filter.py                # 命令行筛选工具
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
**A**: **需要**。筛选工具是 Python 脚本，必须安装 Python 3。Node.js 也需要安装来运行 Bot。

---

## 推送到 GitHub

```powershell
# 1. 进入项目目录
cd E:\Program\AutoQQ

# 2. 初始化 Git (首次)
git init

# 3. 添加所有文件
git add -A

# 4. 提交
git commit -m "AutoQQ - QQ好友/群成员筛选工具"

# 5. 在 github.com 上创建新仓库 (不要勾选 README)

# 6. 设置远程地址（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/仓库名.git

# 7. 推送
git branch -M main
git push -u origin main

# 后续更新只需：
git add -A
git commit -m "更新说明"
git push
```

---

## 技术架构

```
QQ.exe ←─[DLL 注入]─→ PMHQ (13000) ←→ LLBot (8099) ←→ 筛选工具
                            │                     │
                      pmhq.dll               qq_gui.py
                    (Rust 内存钩子)       (Python tkinter)
```
