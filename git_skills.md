# paper_database_agentops：Git 操作参考

## 仓库信息

- GitHub：https://github.com/Mo1s-only/paper_database_agentops
- SSH 地址：`git@github.com:Mo1s-only/paper_database_agentops.git`
- 主分支：`main`
- 内容：AgentOps 论文 PDF、精读笔记、选题调研和实验代码。
- 以下命令适用于 PowerShell；路径中含空格或中文时使用引号。

## 首次 clone

```powershell
git clone git@github.com:Mo1s-only/paper_database_agentops.git
cd paper_database_agentops
git remote -v
git status --short --branch
```

如果出现 `Permission denied (publickey)`，先执行 `ssh -T git@github.com` 检查当前 GitHub SSH 身份，将本机 SSH 公钥添加到有仓库权限的 GitHub 账户；不要上传私钥。GitHub 认证成功时 SSH 测试也可能返回退出码 1，按返回消息判断。

## 每次开始工作

```powershell
git status --short --branch
git remote -v
git pull --ff-only origin main
```

从仓库根目录执行，并确认当前分支是 `main`、`origin` 是上述目标地址。工作区存在未提交修改时，先提交或用 `git stash push -u` 临时保存，再拉取；恢复时运行 `git stash pop` 并处理可能的冲突。不要覆盖尚未保存的修改。

## 每次提交和 push

```powershell
git status --short
git diff
git add --all
git diff --cached --stat
git diff --cached
git commit -m "docs: update AgentOps paper notes"
git pull --rebase origin main
git push -u origin main
git fetch origin
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

提交前确认暂存区只包含本次要上传的内容；`git add --all` 也会暂存删除。提交信息应描述实际改动。没有改动时不必创建空提交。首次提交到空远程时跳过 `git pull --rebase`，直接推送。最后两个提交 ID 应一致，且工作区应无待提交内容。

`git_skills.md` 是操作参考；Git 不会在 clone 或 push 时自动执行它。操作本仓库的人员和 AI 助手应先阅读本文件。

## 上传范围和敏感信息

`agentsight/` 以普通源码快照上传，不是本仓库的 Git 子模块。上游为 https://github.com/eunomia-bpf/agentsight ，快照基于提交 `bb99b66f8f98e4b9f8b1769a3da0a8fbbe26b6c3`，附带本地新增的 `test/` 测试文件。本机原有 `agentsight/.git` 仅保留在本地，不上传；在本机该目录内运行 Git 命令会操作上游仓库，因此本仓库的提交和推送务必在根目录执行。

原始检出的 `libbpf/`、`bpftool/` 和 `.agents/sources/agent-skills/` 依赖目录为空，未包含于此快照。需要构建完整上游项目时，在本仓库外另行执行 `git clone --recurse-submodules https://github.com/eunomia-bpf/agentsight.git`，并按上游文档准备依赖。本仓库内的 `agentsight/.gitmodules` 仅作为上游信息保留，不能通过在本仓库根目录运行 `git submodule update` 恢复这些依赖。

- 保留论文 PDF、Markdown、论文提取文本和实验源代码。
- `.gitignore` 排除 `.env`、私钥、本机助手配置、依赖、缓存和实验运行输出。
- `.env.example` 可以提交，但只能包含占位符，不能含真实 API key。
- 即使文件已经在 `.gitignore` 中，之前被 Git 跟踪的版本仍会被提交；用 `git ls-files` 检查，必要时仅使用 `git rm --cached -- <文件>` 取消跟踪，保留本地文件。
- 不使用 `git push --force`、`git reset --hard` 或 `git clean -fd` 解决日常同步问题。
- 大型新增数据先检查大小；超大文件应使用 Git LFS 或外部存储，并同步更新此说明。

## 冲突和常见问题

- 推送提示 `non-fast-forward`：运行 `git fetch origin`，检查差异后 `git rebase origin/main`，解决冲突再推送，不强制覆盖远程。
- rebase 冲突：编辑冲突文件，`git add -- <文件>`，然后 `git rebase --continue`；需要撤回本次 rebase 时用 `git rebase --abort`。
- PDF 冲突不能逐行合并：保留需要的版本，或分别命名存放两个版本后再提交。
- 推送连接中断：先用 `git ls-remote origin refs/heads/main` 核对远程提交，再决定是否重试。
- 新机器身份未配置：在仓库内设置 `git config user.name "你的名字"` 和 `git config user.email "你的 GitHub 提交邮箱"`。

## 给 AI 助手的约定

先检查工作区、分支和远程，再暂存、检查、提交、推送。不要输出密钥，不要提交本地日志或数据库，不要擅自覆盖远程历史。推送完成后报告目标分支、提交 ID 和未上传的内容；失败时如实说明失败阶段。
