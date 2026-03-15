# 多软件源（Overlay）支持

Ruyi 支持同时配置多个软件包软件源（repo）。多个软件源按照优先级叠加：
优先级更高的软件源，会遮蔽低优先级软件源中类别、名称、版本均相同的软件包。
默认的 `ruyisdk` 软件源始终存在，优先级固定为 0。

## 配置方式

额外的软件源通过用户配置文件（`$XDG_CONFIG_HOME/ruyi/config.toml`）中的
TOML array-of-tables 语法声明，例如：

```toml
[[repos]]
id = "my-overlay"
name = "My Overlay Repo"
remote = "https://git.example.com/overlay.git"
branch = "main"
priority = 100
active = true

[[repos]]
id = "local-dev"
local = "/home/user/repos/local-dev"
priority = 50
active = true
```

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | 是 | 无 | 软件源唯一标识（`[a-z0-9][a-z0-9_-]*`） |
| `name` | string | 否 | 与 `id` 相同 | 供人阅读的软件源名称 |
| `remote` | string | 否* | 无 | Git 远端 URL |
| `branch` | string | 否 | `"main"` | 要跟踪的 Git 分支 |
| `local` | string | 否* | 无 | 本地绝对路径，会覆盖默认缓存位置 |
| `priority` | int | 否 | `0` | 数值越大，优先级越高 |
| `active` | bool | 否 | `true` | 此软件源是否启用 |

\* `remote` 和 `local` 至少要提供一个。

保留 ID `ruyisdk` 不能用于额外软件源；默认软件源应通过 `[repo]` 段进行配置。

### 系统提供的软件源

在系统级配置文件（如 `/etc/xdg/ruyi/config.toml`、`/usr/share/ruyi/config.toml`
等）中声明的软件源，会被标记为“系统提供”。这些条目在 `ruyi repo list`
输出中会带有 `(system)` 标记，并且不能被移除，只能通过
`ruyi repo disable` 禁用。

## CLI 命令

### `ruyi repo list`

列出所有已配置的软件源，并按优先级从高到低排序。

```
$ ruyi repo list
  * ruyisdk (default)  priority=0  https://github.com/ruyisdk/packages-index.git
  * my-overlay  priority=100  https://git.example.com/overlay.git
    local-dev  priority=50  /home/user/repos/local-dev
```

* `*` 表示该软件源已启用。
* `(default)` 表示内建默认软件源。
* `(system)` 表示系统提供的软件源（如果有）。

### `ruyi repo add <id> [url] [options]`

向用户配置中新增一个软件源条目。

```
ruyi repo add my-overlay https://git.example.com/overlay.git --priority 100
ruyi repo add local-dev --local /path/to/repo --priority 50
ruyi repo add mixed https://example.com/repo.git --local /path/to/cache --branch dev
```

可用选项：
* `--branch <branch>`：要跟踪的 Git 分支。
* `--priority <n>`：优先级，默认为 0。
* `--local <path>`：本地绝对路径。
* `--name <name>`：供人阅读的软件源名称。

### `ruyi repo remove <id> [--purge]`

从用户配置中移除某个软件源。传入 `--purge` 时，还会一并删除磁盘上的缓存数据。

默认软件源（`ruyisdk`）和系统提供的软件源不能移除；如需停用，请改用
`ruyi repo disable`。

### `ruyi repo enable <id>` / `ruyi repo disable <id>`

在保留配置条目的前提下启用或禁用某个软件源。被禁用的软件源不会进行同步，
其软件包也不会出现在列表和安装候选中。

### `ruyi repo set-priority <id> <priority>`

修改某个软件源的优先级。

### `ruyi update [--repo <id>]`

同步软件源元数据。不带 `--repo` 时会同步所有已启用的软件源；带
`--repo <id>` 时只同步指定软件源。

## 优先级与遮蔽规则

当多个软件源提供同一个软件包（即类别、名称、版本都相同）时，将采用优先级更高的软件源版本。
各软件源中独有的软件包则始终可见，不受优先级影响。

例如：如果 `base`（优先级 0）提供 `toolchain/gcc 13.2.0`，而 `overlay`
（优先级 100）也提供 `toolchain/gcc 13.2.0`，那么列表展示和安装时采用的都会是
`overlay` 中的那个版本。

## 软件包列表展示

当配置了多个软件源时，`ruyi list` 的输出会包含 `[repo-id]` 标记，用于说明每个软件包来自哪个软件源。

## 软件源目录布局

额外软件源默认存放在 `$XDG_CACHE_HOME/ruyi/repos/<id>/` 下。可以通过每个软件源的
`local` 字段覆盖这一默认位置。

为保持向后兼容，默认软件源仍使用旧路径
`$XDG_CACHE_HOME/ruyi/packages-index/`。

## 创建一个 Overlay 软件源

Overlay 软件源本质上是一个标准的 Ruyi 元数据软件源，也就是一个 Git 仓库。
其最少需要包含以下内容：

1. 仓库根目录下的 `config.toml`：

```toml
ruyi-repo = "v1"

[repo]
id = "my-overlay"

[[mirrors]]
id = "ruyi-dist"
urls = ["https://example.com/dist/"]
```

其中 `[repo].id` 应与用户配置中 `[[repos]]` 条目的 `id` 一致。如果两者不一致，
`ruyi update` 会发出警告。

2. 一个 `manifests/` 目录，内部包含符合标准[软件源结构定义](repo-structure.md)的软件包定义。

## 迁移说明

现有的单软件源配置无需修改。默认的 `ruyisdk` 软件源仍会像以前一样继续工作。
`[repo]` 配置段也仍然保留，用于配置默认软件源的 URL 和分支。

新增 Overlay 软件源时，可按以下步骤操作：

1. 在 `~/.config/ruyi/config.toml` 中添加 `[[repos]]` 条目，或使用 `ruyi repo add`。
2. 运行 `ruyi update` 同步新软件源。
3. 使用 `ruyi list --all` 查看所有软件源中的软件包。
