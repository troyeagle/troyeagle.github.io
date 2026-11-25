# 维护说明

## AI 协作者匿名规约

所有在本仓库工作的 AI agent（ChatGPT / Codex、Claude、DeepSeek、TRAE 等）统一遵守根目录 [AGENTS.md](AGENTS.md)。AI 参与的提交只使用一条以下尾注，多 agent 协作也不分别署名：

```text
Co-authored-by: Bot <bot@anonymous.com>
```

主作者和提交者仍使用用户指定的仓库身份。推送前核对实际提交信息，修正工具或钩子自动追加的默认 AI 身份。Claude 的 [CLAUDE.md](CLAUDE.md) 引用同一份规则；不自动读取这些文件的工具，应把 `AGENTS.md` 作为项目指令加载。

这些维护规则文件在 Jekyll 构建中排除，作为 Git 仓库操作规约维护。

## 发布方式与迁移记录

公开源码项目由各自仓库独立部署项目 Pages；私有源码继续使用博客的验证、收集和发布流程。四个公开项目均保留默认停用的博客回退工作流，未来转为私有时按源码规约切换。

### 公开项目站

| 源码仓库 | 项目站 | 博客原目录说明 | 源码发布规约 |
| --- | --- | --- | --- |
| [larp-clues-presentation](https://github.com/troyeagle/larp-clues-presentation) | [/larp-clues-presentation/](https://troyeagle.github.io/larp-clues-presentation/) | [clue/remark.md](clue/remark.md) | [规约](https://github.com/troyeagle/larp-clues-presentation/blob/main/.github/STATIC_PUBLISH.md) |
| [larp-countdown](https://github.com/troyeagle/larp-countdown) | [/larp-countdown/](https://troyeagle.github.io/larp-countdown/) | [countdown/remark.md](countdown/remark.md) | [规约](https://github.com/troyeagle/larp-countdown/blob/main/.github/STATIC_PUBLISH.md) |
| [ai-video-reverse](https://github.com/troyeagle/ai-video-reverse) | [/ai-video-reverse/](https://troyeagle.github.io/ai-video-reverse/) | [ai-video-reverse/remark.md](ai-video-reverse/remark.md) | [规约](https://github.com/troyeagle/ai-video-reverse/blob/main/.github/STATIC_PUBLISH.md) |
| [expedition-alfonso-showcase](https://github.com/troyeagle/expedition-alfonso-showcase) | [/expedition-alfonso-showcase/](https://troyeagle.github.io/expedition-alfonso-showcase/) | [expedition-alfonso-showcase/remark.md](expedition-alfonso-showcase/remark.md) | [规约](https://github.com/troyeagle/expedition-alfonso-showcase/blob/main/.github/STATIC_PUBLISH.md) |

默认推送源码 `main` 即独立检查、构建并部署，使用 GITHUB_TOKEN 与 OIDC。每个源码仓库的 Pages Source 选择 GitHub Actions。`SITE_PUBLISH_MODE` 未设置或为 `pages` 时，仅公开仓库的项目站工作流执行；设为 `blog` 时，项目站工作流跳过，保留的 `publish-to-blog.yml` 才会执行。

`clue/` 与 `countdown/` 的旧博客地址不再托管应用，新的项目地址使用完整仓库名。视频与空间对齐工具的项目路径与原地址一致。博客旧目录只保留 `remark.md`，写明原用途、源码仓库和新入口。`tragedy/` 尚未映射到公开源码仓库，保持既有内容。

### 当前由博客托管的私有源码

| 源码仓库 | 发布分支 | 安装 / 输出 | 博客入口 | 工作流 |
| --- | --- | --- | --- | --- |
| [clue-viewer](https://github.com/troyeagle/clue-viewer) | `master` | pnpm / `dist/` | [/clue-viewer/](https://troyeagle.github.io/clue-viewer/) | [构建](https://github.com/troyeagle/clue-viewer/actions/workflows/publish-static.yml) |
| [image-merger-fe](https://github.com/troyeagle/image-merger-fe) | `main` | npm / `dist/` | [/merger/](https://troyeagle.github.io/merger/) | [构建](https://github.com/troyeagle/image-merger-fe/actions/workflows/publish-static.yml) |

博客同步默认只读取启用的槽位，目前是上述两个私有源码。来源、成功构建、分支历史、文件哈希、路径和所有 HTML 引用均经校验后，才更新对应目录和 `.github/apps-state.json`；普通产物更新直接提交 `master` 再触发 Pages，不创建逐次审核 PR。每小时 17、47 分定时检查，GitHub 调度可能延迟。

### 保留的私有化回退配置

`.github/apps.json` 保留六个可信目的目录：两个私有项目 `enabled: true`；四个公开项目回退槽位 `enabled: false`，其来源工作流为 `publish-to-blog.yml`。`source_repositories` 默认只为启用项申请读取权限；明确的接入预览才包括停用项。

从公开项目迁回博客时按以下顺序：

1. 审核允许公开的构建输出。源码私有不等于输出私有，博客 Pages 仍公开；不得发布密钥、内部原文、原始媒体、可编辑模板或 source map。视频只导出 `.github/static-pages.json` 登记的批准案例 HTML。
2. 在源码仓库将 `SITE_PUBLISH_MODE` 设为 `blog`，停用/下线该项目站；给博客 `SOURCE_ARTIFACTS_TOKEN` 增加该源码仓库的 Contents: read、Actions: read，再按要求转换源码可见性。
3. 手动运行源码 `publish-to-blog.yml`，选择其发布分支，等待成功。所有回退档案关闭 source map；打包器仍附带 `_site-sync.json` 供验证，但元数据不复制到网站。
4. 博客先保持该槽位 `enabled: false`，在 [同步工作流](https://github.com/troyeagle/troyeagle.github.io/actions/workflows/sync-apps.yml) 勾选 `dry_run` 与 `include_disabled` 预览。通过审核后启用此槽位，取消 `dry_run` 正式同步，审核后的产物将替换该目录的迁移说明。
5. 验证当时的博客路径与发布状态。线索和倒计时回退时分别使用 `/clue/`、`/countdown/`，与默认项目站路径不同；源码共享构建器会显式使用旧博客 PUBLIC_URL。

返回公开项目站时，先停用博客槽位，再恢复源码公开可见性、把模式设为 `pages` 或删除变量、启用本仓库 Pages 的 GitHub Actions 来源并部署；核对成功后恢复博客 `remark.md`。保留源码回退 workflow 与规约，不删除历史配置。

### 配置入口与最小权限

| 入口 | 用途 |
| --- | --- |
| [博客 Actions Secrets](https://github.com/troyeagle/troyeagle.github.io/settings/secrets/actions) | 保存读取及写入 Token |
| [博客 Actions Variables](https://github.com/troyeagle/troyeagle.github.io/settings/variables/actions) | `SITE_SYNC_ENABLED`、`SITE_SYNC_PUBLISH_ENABLED` 均为 `true` 才真实同步 |
| [博客同步工作流](https://github.com/troyeagle/troyeagle.github.io/actions/workflows/sync-apps.yml) | 预览、手动发布、查看记录 |
| [源码白名单](.github/apps.json) | 每项目启停与回退槽位 |
| [已发布状态](.github/apps-state.json) | 活跃博客产物的来源版本与运行身份 |
| [PAT 管理](https://github.com/settings/personal-access-tokens) | 更新、续期或收缩授权 |
| [博客 Pages 设置](https://github.com/troyeagle/troyeagle.github.io/settings/pages) | 博客自己的构建来源与状态 |

- `SOURCE_ARTIFACTS_TOKEN` 只保存在博客；正常同步推荐授权 `clue-viewer` 与 `image-merger-fe`，Contents: read、Actions: read。使用某个公开项目回退时再扩展对应源码权限。
- `BLOG_PUBLISH_TOKEN` 只保存在博客，仅授权博客 Contents: read/write；不分发到源码项目。
- 回退模式需要即时通知时，可在对应源码保存单独的 `BLOG_DISPATCH_TOKEN`，仅授权博客 Actions: write。它是可选项，不配置也能定时同步。个人仓库 Secret 需要各自保存，即使复用同一 Token。

暂停单个博客项目使用 `enabled: false`；暂停全局发布使用 `SITE_SYNC_PUBLISH_ENABLED=false`，暂停收集使用 `SITE_SYNC_ENABLED=false`。回退旧内容前先暂停相应发布渠道，优先以新源码提交恢复，避免定时任务覆盖回退。

更完整的校验、并发保护与恢复设计见 [STATIC_APP_SYNC.md](.github/STATIC_APP_SYNC.md)。GitHub 设置可能需要本人完成 sudo 身份确认。规则和维护文档保持在 Git 仓库中，不加入 Hux 导航。

## 提交身份与历史维护

人类作者和提交者使用 `troyeagle <troyeagle@qq.com>`，AI 协作者使用 `Bot <bot@anonymous.com>`。仅设置七个项目各自的本地 Git 身份，不改全局配置。

历史身份或公开路径改写前，备份旧分支并暂停两个同步开关；强制更新使用明确旧 SHA 的 `--force-with-lease`。固定共享工作流 SHA 和 `publisher_ref` 随历史映射更新。历史 Actions 运行不可改写，故清空当前 apps-state 后由新源码构建重建来源证明；现有网站文件保持至验证后同步。验证新构建与发布成功后恢复暂停前的开关值。
