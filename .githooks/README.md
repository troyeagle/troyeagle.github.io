# 博客本地提交检查

只作用于安装后的 `troyeagle/troyeagle.github.io` 本地检出。需要 Python 3，不依赖额外包。

```sh
python3 .githooks/install.py install
python3 .githooks/install.py status
python3 .githooks/install.py uninstall
```

安装入口只修改本仓库的 `core.hooksPath`，在 Git 私有目录中保存原配置和分发脚本。原钩子保留在原处并先执行；检查器不修改全局配置、工具管理的钩子或其他仓库。

本仓库的 `.trae/traecli.toml` 将工具自动协作者配置为 `Bot <bot@anonymous.com>`，由后续在该项目启动的 TRAE CLI 会话读取。已启动的旧会话如果仍添加默认署名，检查器会拒绝提交；使用项目配置重新启动工具后再提交。当前工具默认的钩子接管已验证仍会委托本地检查器，不会自动跳过检查。

- `pre-commit` 检查实际作者、提交者和暂存区新增/修改的文本文件；工作区未暂存内容不影响结果，符号链接只读取目标文字，不跟随链接。
- `commit-msg` 在原钩子完成后检查提交信息、真实账户路径、已脱敏旧邮箱以及 AI 协作者尾注。
- 本人的提交身份必须为 `troyeagle <troyeagle@qq.com>`。用指纹识别已确认的旧署名，原值不写入规则。
- AI 协作者尾注必须为 `Co-authored-by: Bot <bot@anonymous.com>`，且只能保留一条。
- 禁止写入真实账户绝对路径；使用 `/Users/{youraccountname}/...` 占位符或相对路径。
- 错误只显示规则、文件或提交信息的行号，不回显匹配到的账户和旧邮箱。不自动修改暂存文件或提交信息。

提交信息的私人值检查也覆盖看起来像注释的原始文本，以防 `git commit -m` 将这些行原样写入提交；被拦截时删除相关私人值或注释后重试。

只检查文本，图片、PDF、音视频等不做内容识别。不能仅凭 Git 判断一个缺少 AI 尾注的提交是否由 AI 创建，AI agent 仍须按 `AGENTS.md` 添加规定尾注。

新克隆或移动目录后需重新运行安装命令。GitHub 网页提交不会经过本地钩子。Git 钩子是本地防误操作机制，`git commit --no-verify`、底层 Git 写对象操作或显式覆盖钩子路径都能绕过；它不代替服务器约束。

此目录不接入 GitHub Actions，不改 Pages 发布及产物同步。Git 默认不分发安装后的私有配置，也不会在 GitHub Runner 上自动加载这些钩子。

验证：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .githooks -p 'test_*.py' -v`。测试只使用临时仓库，不修改博客提交历史。
