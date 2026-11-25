# AI agent 工程规约

本文件适用于本仓库及其所有子目录中的 AI agent 工作，包括 ChatGPT / Codex、Claude、DeepSeek、TRAE，以及其他模型、工具或协作代理。开始工作和创建提交前应读取本文件。用户在当前会话中的明确指示优先；已获得的授权不需重复确认。

## 统一匿名协作者

AI agent 创建或修改的 Git 提交，AI 协作者统一使用以下尾注，且只保留一条：

```text
Co-authored-by: Bot <bot@anonymous.com>
```

- 多个 AI agent 共同参与时仍使用同一条匿名尾注，不分别署名。
- AI 协作者尾注中不得写入模型、工具、厂商或组织名称，也不得使用厂商域名邮箱、员工邮箱或 agent 自带的默认身份。ChatGPT、Claude、DeepSeek、TRAE CLI 等默认协作者署名均须替换为上述匿名身份。
- 此规则适用于普通提交、amend、squash 和由 AI 编辑的 merge 提交信息；创建或编辑 PR 时，预备的最终提交信息也须遵守。
- 本规则只规定 AI 的 `Co-authored-by`。主作者和提交者使用用户指定的仓库身份，不改成 Bot，不擅自修改全局 Git 身份。用户明确指定的人类协作者署名按用户要求保留。

## 提交与推送前核对

1. 检查提交范围和当前工作区，保留用户已有的暂存、未暂存及未跟踪内容。
2. 创建提交时，在信息正文末尾添加一个空行和规定的匿名尾注。
3. 提交后、推送前执行：

   ```sh
   git log -1 --format=%B
   ```

   核对实际提交信息恰好有一条匿名 AI 尾注，没有工具自动追加的其他 AI 身份。不要仅依据提交命令中的 `-m` 参数判断结果。
4. 如果工具或提交钩子自动追加了默认署名，先配置该工具的署名设置，或修正本 agent 刚创建且尚未推送的提交，再核对最终内容；验证通过后才推送。
5. 已发布历史的改写必须在用户明确授权的范围内进行。需要强制更新时，备份旧历史并使用带明确旧 SHA 的 `--force-with-lease`，不得覆盖检查期间新增的提交。改写后同步修正受影响的固定 SHA 引用和发布状态，验证自动化仍可用。

维护入口及静态应用发布流程见 [MAINTENANCE.md](MAINTENANCE.md)。

## 用户提交身份与公开路径

用户指定的人类作者和提交者统一为 `troyeagle <troyeagle@qq.com>`；AI 协作者统一为 `Co-authored-by: Bot <bot@anonymous.com>`，只保留一条。第三方作者及 GitHub 自动提交身份按其实际归属保留。

仅在本仓库设置 Git 身份，不修改全局配置：

```sh
git config --local user.name troyeagle
git config --local user.email troyeagle@qq.com
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

公开资料中的本机账户绝对路径统一写作 `/Users/{youraccountname}/...`。这是说明占位符；执行命令时应替换为本机账户，或使用相对路径重新生成素材清单。不得把真实本机账户路径再次提交到公开仓库。

## 博客本地提交检查

本仓库在当前检出安装本地提交检查；新克隆或移动目录后执行 `python3 .githooks/install.py install`，用 `python3 .githooks/install.py status` 核对。检查实际暂存内容、作者/提交者和提交信息，不自动修改数据。触发拦截时修正问题后重新提交，不用 `--no-verify` 绕过。规则和停用方式见 [.githooks/README.md](.githooks/README.md)。仅加载博客仓库，不修改其他工程、GitHub CI 或发布配置。
