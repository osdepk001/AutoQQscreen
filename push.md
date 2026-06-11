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