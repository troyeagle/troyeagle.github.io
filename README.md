# Troyeagle's Blog

##### 基于 [Hux Blog](https://github.com/Huxpro/huxpro.github.io) 模板搭建的个人博客

#### [访问博客 &rarr;](http://troyeagle.github.io)

## 关于本站
- 标题: Troyeagle's
- 描述: 这个人很勤快，他还是什么都没留下
- SEO 标题: 神速的博客 | Troyeagle's Blog
- 侧边栏描述: 剧本杀 DM、音乐人

## 技术栈
- 基于 Jekyll 构建
- 使用 GitHub Pages 部署
- 主题: Hux Blog

## 独立应用自动同步

当前已接入 [larp-clues-presentation](https://github.com/troyeagle/larp-clues-presentation) → [线上 `/clue/`](https://troyeagle.github.io/clue/)，使用 fine-grained PAT 认证。

源码 `main` 构建成功后，博客端同步工作流校验并复制新产物，直接提交到本仓库 `master`，再由 GitHub Pages 发布；产物更新不会逐次创建 PR。定时检查约每 30 分钟执行一次，GitHub 调度可能延迟，同一构建不会重复提交。普通博客发布会部署仓库里已有的 `clue/` 文件，不会重新构建源码项目。

### 配置与运行入口

| 入口 | 用途 |
| --- | --- |
| [创建 fine-grained PAT](https://github.com/settings/personal-access-tokens/new) | 创建限定仓库、权限和有效期的令牌 |
| [管理已有 PAT](https://github.com/settings/personal-access-tokens) | 查看有效期、更新或撤销令牌 |
| [博客仓库 Actions Secrets](https://github.com/troyeagle/troyeagle.github.io/settings/secrets/actions) | 配置读取产物和提交博客的 PAT |
| [博客仓库 Actions Variables](https://github.com/troyeagle/troyeagle.github.io/settings/variables/actions) | 查看和修改同步、发布开关 |
| [编辑收集开关 `SITE_SYNC_ENABLED`](https://github.com/troyeagle/troyeagle.github.io/settings/variables/actions/SITE_SYNC_ENABLED) | `true` 允许收集、校验；`false` 暂停整个同步流程 |
| [编辑发布开关 `SITE_SYNC_PUBLISH_ENABLED`](https://github.com/troyeagle/troyeagle.github.io/settings/variables/actions/SITE_SYNC_PUBLISH_ENABLED) | `true` 允许自动提交；`false` 只保留收集、校验和预览 |
| [源码构建工作流](https://github.com/troyeagle/larp-clues-presentation/actions/workflows/publish-static.yml) | 查看构建、下载 `site-clue` 产物，或在 `main` 手动生成新构建 |
| [博客同步工作流](https://github.com/troyeagle/troyeagle.github.io/actions/workflows/sync-apps.yml) | 手动预览或发布，查看同步记录和 `prepared-static-updates` 产物 |
| [源码仓库 Actions Secrets](https://github.com/troyeagle/larp-clues-presentation/settings/secrets/actions) | 可选：配置即时通知所需的 `BLOG_DISPATCH_TOKEN` |
| [源码仓库分支保护](https://github.com/troyeagle/larp-clues-presentation/settings/branches) | 如需人工审核，在源码合入 `main` 前设置 PR 和检查要求 |
| [GitHub Pages 设置](https://github.com/troyeagle/troyeagle.github.io/settings/pages) | 查看网站发布来源和部署状态 |
| [博客 Actions 运行记录](https://github.com/troyeagle/troyeagle.github.io/actions) | 排查同步、检查和 Pages 构建部署结果 |

### 凭据配置

以下两个 Secret **都保存在博客仓库**，表中的仓库范围是 PAT 的授权范围：

| Secret 名称 | PAT 授权仓库 | 最小权限 |
| --- | --- | --- |
| `SOURCE_ARTIFACTS_TOKEN` | `troyeagle/larp-clues-presentation` | Contents: read；Actions: read |
| `BLOG_PUBLISH_TOKEN` | `troyeagle/troyeagle.github.io` | Contents: read/write |

即时通知是可选配置：将仅授权 **博客仓库 Actions: write** 的 PAT 保存为源码仓库的 `BLOG_DISPATCH_TOKEN`。未配置时，博客端仍可通过定时检查和手动运行同步。令牌值只保存在 Actions Secrets 中，不写入 README 或其他仓库文件。

### 常用操作

- **只做预览**：在博客同步工作流中选择 `master`，保持 `dry_run` 勾选（默认值为 `true`）。
- **执行真实同步**：两个仓库变量均设为 `true`，在工作流表单中取消勾选 `dry_run`。
- **暂停发布但保留预览**：将 `SITE_SYNC_PUBLISH_ENABLED` 设为 `false`。
- **暂停单个应用**：在 [应用白名单](.github/apps.json) 中将该应用的 `enabled` 设为 `false`。
- **查询已发布源码版本**：查看 [发布状态记录](.github/apps-state.json)。
- **回退应用版本**：先暂停该应用同步，再回退相应发布提交，避免定时任务再次覆盖回退结果。

修改 GitHub 设置时可能需要本人完成 sudo 身份确认。更完整的凭据、校验范围和恢复说明见 [自动同步操作文档](.github/STATIC_APP_SYNC.md)。

## 作者
- GitHub: [troyeagle](https://github.com/troyeagle)

---

## HuxBlog Boilerplate 说明
这是基于 [Hux Blog](https://github.com/Huxpro/huxpro.github.io) 模板搭建的博客。

如果您喜欢 Hux Blog 主题，请为 [huxpro.github.io 仓库](https://github.com/Huxpro/huxpro.github.io) 点赞，而不是这个仓库！谢谢！

#### [查看原始模板 &rarr;](http://huangxuan.me/huxblog-boilerplate/)

#### [查看 Hux 的个人博客 &rarr;](http://huangxuan.me)
