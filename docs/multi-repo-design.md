# 多软件源支持（Overlay 架构）

## 背景与动机

目前 Ruyi 仅支持单一元数据软件源（`packages-index`），通过
`GlobalConfig.repo` 以单例形式进行配置。这在以下场景中存在局限：

1. **厂商/OEM 软件源** — 硬件厂商应能够提供额外的或经过定制的工具链、板卡映像和设备安装策略，而无需 fork 或修改官方软件源。
2. **实验用途** — 开发者在实验新软件包、profile 或插件时，需要一种可在本地快速迭代的方式，无需将内容发布到官方软件源。
3. **企业/内部软件包** — 组织可能需要永远不会发布到上游的私有二进制软件包。
4. **带有附加内容的区域镜像** — 某些地区的镜像站可能希望捆绑补充内容。

Gentoo 的 overlay 系统解决了 ebuild 软件源中类似的问题，提供了一套久经验证的设计思路。我们借鉴的核心原则如下：

* 有序的软件源集合，每个可独立拉取。
* 当同一软件包（以 `category/name` 标识）出现在多个软件源中时，通过明确的**优先级**解析顺序确定生效版本。
* 每个软件源具备自描述能力（`config.toml`、软件源 ID、名称）。
* Overlay 软件源可以**新增**软件包，也可以**遮蔽**（覆盖）低优先级软件源中的特定版本。

## 设计概览

```
┌──────────────────────────────────────────────┐
│                 ruyi CLI                     │
├──────────────────────────────────────────────┤
│              CompositeRepo                   │
│  ┌────────┐ ┌────────┐ ┌────────┐           │
│  │ Repo 0 │ │ Repo 1 │ │ Repo 2 │  ...      │
│  │pri = 0 │ │pri = 50│ │pri =100│           │
│  │ 官方   │ │ 厂商   │ │ 本地   │           │
│  └────────┘ └────────┘ └────────┘           │
├──────────────────────────────────────────────┤
│  ProvidesPackageManifests（协议不变）          │
└──────────────────────────────────────────────┘
```

本设计引入两个新概念：

1. **`RepoEntry`** — 指向单个元数据软件源的配置条目，附带其元信息（ID、名称、优先级、是否启用）。
2. **`CompositeRepo`** — 聚合体，通过按优先级合并所有活跃 `MetadataRepo` 实例的结果来实现 `ProvidesPackageManifests` 协议。

## 详细设计

### 1. 软件源配置

#### 1.1 配置文件 schema

用户级配置文件（`~/.config/ruyi/config.toml`）新增 `[[repos]]` 表数组（table-array）段落。现有的 `[repo]` 段落保留以确保向后兼容，其隐式定义"默认"软件源条目。

```toml
# 现有段落 — 保留以确保向后兼容。
# 如存在，这些字段仅适用于"默认"软件源（软件源 ID 为
# "ruyisdk"）。
[repo]
remote = "https://github.com/ruyisdk/packages-index.git"
branch = "main"
# local = "/path/to/override"   # 可选的绝对路径覆盖

# 新增：额外的软件源，按声明的优先级排序。
[[repos]]
id = "my-vendor"
name = "My Vendor Overlay"
remote = "https://git.example.com/my-vendor/ruyi-overlay.git"
branch = "main"
priority = 50
# active = true  # 默认值

[[repos]]
id = "local-testing"
name = "本地测试 overlay"
local = "/home/user/ruyi-local-overlay"
priority = 100
```

每个 `[[repos]]` 条目的字段说明：

| 字段       | 类型   | 必填   | 默认值      | 说明 |
|------------|--------|--------|-------------|------|
| `id`       | string | 是     | —           | 该软件源的唯一标识符，须匹配 `^[a-z0-9][a-z0-9_-]*$`。 |
| `name`     | string | 否     | 与 `id` 相同 | 人类可读的显示名称。 |
| `remote`   | string | 条件必填 | —         | Git 远程 URL。在未设置 `local` 时必填。 |
| `branch`   | string | 否     | `"main"`    | 要追踪的 Git 分支。 |
| `local`    | string | 否     | —           | 指向本地 checkout 的绝对路径。若设置，`remote`/`branch` 仅在 `ruyi update` 时使用。 |
| `priority` | int    | 否     | `50`        | 优先级**更高**的软件源将遮蔽优先级更低的同名包。默认的官方软件源优先级为 0。 |
| `active`   | bool   | 否     | `true`      | 该软件源是否参与解析。 |

由旧版 `[repo]` 段落（或内置默认值）派生的隐式"默认"软件源条目，始终为 `id = "ruyisdk"`、`priority = 0`。

#### 1.2 软件源内部的身份标识

每个软件源的 `config.toml`（位于 git 工作树内）已经支持带有可选 `id` 和 `name` 字段的 `[repo]` 段落：

```toml
ruyi-repo = "v1"

[repo]
id = "my-vendor"
name = "My Vendor Overlay"
```

当此软件源内部身份标识存在时，Ruyi 在同步时将其与用户配置中的条目进行比较，如不匹配则发出警告，但**用户配置中的值始终优先**，以防止劫持。

#### 1.3 全局/系统级配置

发行版打包者和系统管理员可以在系统级配置文件中放置软件源条目（`/usr/share/ruyi/config.toml`、`/usr/local/share/ruyi/config.toml` 或 XDG 配置目录）。这些条目的行为与用户配置中的条目完全相同，但以更低的优先级加载，可被用户覆盖（或停用）。

### 2. 磁盘布局

每个软件源的本地 checkout 位于缓存目录下以软件源为单位的子目录中：

```
~/.cache/ruyi/
├── packages-index/          # 旧版 — 首次运行时迁移
└── repos/
    ├── ruyisdk/             # 官方软件源（从 packages-index/ 迁移而来）
    ├── my-vendor/           # overlay 软件源
    └── local-testing/       # 若设置了 `local`，则为符号链接或直接路径
```

**迁移**：升级后首次运行时，若旧版 `packages-index/` 目录存在而 `repos/ruyisdk/` 不存在，Ruyi 会将旧目录移动（或创建符号链接）到新位置，并输出提示信息。

`GlobalConfig.get_repo_dir()` 方法将被替换为 `GlobalConfig.get_repo_dir(repo_id: str)`，返回 `<cache_root>/repos/<repo_id>`。

### 3. 核心抽象

#### 3.1 `RepoEntry` 数据类

```python
@dataclass
class RepoEntry:
    """已配置的软件源指针。"""
    id: str
    name: str
    remote: str | None
    branch: str
    local_path: str | None   # 绝对路径覆盖
    priority: int             # 值越高 = 冲突时优先
    active: bool

    @cached_property
    def metadata_repo(self) -> MetadataRepo:
        """惰性构建此条目对应的 MetadataRepo。"""
        ...
```

`RepoEntry` 是一个轻量级、可序列化的值对象。较重的 `MetadataRepo` 仅在该条目处于活跃状态时惰性构建。

#### 3.2 `CompositeRepo`

```python
class CompositeRepo(ProvidesPackageManifests):
    """按优先级顺序聚合多个 MetadataRepo 实例。"""

    def __init__(self, entries: list[RepoEntry]) -> None:
        # 按优先级升序排列；高优先级的软件源遮蔽低优先级的
        self._entries = sorted(entries, key=lambda e: e.priority)

    # --- ProvidesPackageManifests 实现 ---

    def iter_pkg_manifests(self) -> Iterable[BoundPackageManifest]:
        ...

    def iter_pkgs(self) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        ...

    def get_pkg(self, name, category, ver) -> BoundPackageManifest | None:
        ...

    def get_pkg_latest_ver(self, name, category=None, ...) -> BoundPackageManifest:
        ...

    def get_pkg_by_slug(self, slug) -> BoundPackageManifest | None:
        ...

    # --- 聚合特有方法 ---

    def sync_all(self) -> None:
        """同步所有活跃的软件源。"""
        ...

    def iter_repos(self) -> Iterable[MetadataRepo]:
        """按优先级顺序遍历所有活跃的软件源。"""
        ...
```

#### 3.3 `GlobalConfig` 变更

```python
class GlobalConfig:
    ...
    @cached_property
    def repo_entries(self) -> list[RepoEntry]:
        """所有已配置的软件源条目，包括默认条目。"""
        ...

    @cached_property
    def repo(self) -> CompositeRepo:
        """聚合软件源（替代原来的单一 MetadataRepo）。"""
        return CompositeRepo(self.repo_entries)

    # 为兼容性保留 — 仅返回默认/官方软件源。
    @cached_property
    def default_repo(self) -> MetadataRepo:
        ...
```

`repo` 属性的返回类型从 `MetadataRepo` 变更为 `CompositeRepo`。由于 `CompositeRepo` 实现了 `ProvidesPackageManifests` — 即代码库中已广泛使用的同一协议 — 大多数调用点无需修改。需要访问特定软件源功能（插件、profile、配置、新闻、实体存储）的调用点，须通过 `CompositeRepo.iter_repos()` 改为对单个 `MetadataRepo` 实例进行操作。

### 4. 软件包解析

#### 4.1 合并语义

软件源按**优先级升序**排列。在遍历所有软件包时，`CompositeRepo` 产出所有软件源中软件包的并集。当同一 `(category, name, version)` 三元组存在于多个软件源中时，来自**最高优先级**软件源的实例胜出（遮蔽其他实例）。

这与 Gentoo 的 overlay 行为一致：高优先级的 overlay 可以替换低优先级软件源中的任意 ebuild 版本。

```
get_pkg("gcc-cross", "toolchain", "14.1.0") 的解析过程：

  软件源 "ruyisdk"     (pri  0): toolchain/gcc-cross/14.1.0.toml  ← 被遮蔽
  软件源 "my-vendor"   (pri 50): toolchain/gcc-cross/14.1.0.toml  ← 胜出
  软件源 "local-test"  (pri100): （不存在）
```

#### 4.2 版本列举

`iter_pkg_vers(name, category)` 返回跨所有软件源的合并版本集。若同一版本字符串存在于多个软件源中，则仅出现最高优先级的实例。这确保 `get_pkg_latest_ver` 始终返回经过完整优先级栈解析后的单一最新版本。

#### 4.3 Slug 唯一性

Slug 在聚合集合中是全局唯一的。若两个软件源定义了具有相同 slug 的软件包，高优先级的软件源胜出，并为被遮蔽的 slug 记录警告日志。

#### 4.4 Atom 解析

`Atom.match_in_repo` 和 `Atom.iter_in_repo` 已接受 `ProvidesPackageManifests`，因此无需修改即可与 `CompositeRepo` 配合使用。

### 5. Profile、插件与实体

这些是软件源特有的资源。`CompositeRepo` 对它们进行聚合：

* **Profile**：按架构合并。若两个软件源定义了相同的 `(arch, profile_id)`，高优先级软件源的定义胜出。`CompositeRepo.get_profile(name)` 按优先级降序遍历软件源，返回首个匹配项。

* **插件**：插件 ID 是全局作用域的。当同一插件 ID 存在于多个软件源中时，加载高优先级软件源的插件。每个软件源创建独立的 `PluginHostContext`；各软件源的插件默认仅能访问自身软件源的文件系统。

* **实体**：`EntityStore` 已支持接受多个 `BaseEntityProvider` 实例。`CompositeRepo` 提供的 `entity_store` 将来自所有软件源的 provider 串联起来，高优先级的 provider 优先注册。

* **新闻**：来自所有软件源的新闻条目被聚合在一起。每条新闻附带其来源软件源 ID 以供展示。已读状态追踪保持全局统一。

* **消息**：`RepoMessageStore` 实例仍然按软件源独立维护。在渲染某个软件包的消息时，使用该软件包所属软件源的消息存储（通过 `BoundPackageManifest.repo` 访问）。

### 6. 同步 / 更新

`ruyi update` 同步所有活跃的软件源：

```
$ ruyi update
正在更新软件源 "ruyisdk"（RuyiSDK 官方软件源）...
  正在从 https://github.com/ruyisdk/packages-index.git 拉取...
  完成。
正在更新软件源 "my-vendor"（My Vendor Overlay）...
  正在从 https://git.example.com/my-vendor/ruyi-overlay.git 拉取...
  完成。
软件源已更新。
```

可通过 `ruyi update --repo <id>` 单独同步某个软件源。

对于设置了 `local` 但未设置 `remote` 的软件源，将跳过 git pull 步骤（视为由外部管理），除非同时提供了 `remote` 以支持"按需同步"语义。

### 7. CLI 命令

新增 `ruyi repo` 命令组用于管理软件源配置：

```
ruyi repo list                     # 列出已配置的软件源及其状态
ruyi repo add <id> <url> [opts]    # 添加新的 overlay 软件源
ruyi repo remove <id>              # 移除软件源条目
ruyi repo enable <id>              # 设置 active = true
ruyi repo disable <id>             # 设置 active = false
ruyi repo set-priority <id> <n>    # 变更优先级
```

`ruyi repo list` 示例输出：

```
已配置的软件源（按优先级从高到低）：

  ● local-testing   pri=100  (local: /home/user/ruyi-local-overlay)
  ● my-vendor       pri=50   https://git.example.com/my-vendor/ruyi-overlay.git
  ● ruyisdk         pri=0    https://github.com/ruyisdk/packages-index.git  [默认]
```

`ruyi repo add` 命令写入用户的本地配置文件（`~/.config/ruyi/config.toml`）。系统级配置提供的条目不能从用户配置中删除，只能停用。

### 8. 遥测

现有的遥测基础设施已在 `TelemetryScope` 中包含 `repo_name` 字段：

```python
class TelemetryScope:
    def __init__(self, repo_name: str | None) -> None:
        self.repo_name = repo_name
```

支持多软件源后，`TelemetryProvider.init_store` 将为每个声明了 `[[telemetry]]` 段落的软件源调用，创建各自的遥测存储。`telemetry/provider.py:161` 处现有的 TODO 将通过遍历 `CompositeRepo.iter_repos()` 而非硬编码 `"ruyisdk"` 来解决。

未声明 `[[telemetry]]` 段落的 overlay 软件源不会有遥测存储 — 其软件包仍被追踪在 PM 级别的遥测范围下。

### 9. 状态与安装追踪

`PackageInstallationRecord` 已携带 `repo_id` 字段，因此即使跨多个软件源，安装记录也能正确归属。无需变更 schema。

在检查可升级软件包时（`BoundInstallationStateStore.iter_upgradable_pkgs`），将使用已安装软件包的 `repo_id` 优先在其对应软件源中查找最新版本，然后在所有软件源中查找可能已迁移到其他软件源的包。

### 10. 迁移计划

分阶段过渡以尽量减少对现有用户的影响：

#### 阶段一 — 内部重构（非破坏性）

* 引入 `RepoEntry` 和 `CompositeRepo`，放置于 `GlobalConfig.repo` 之后。
* 聚合体仅包含一个条目（当前的默认软件源），因此行为不变。
* 将磁盘布局迁移至 `repos/<id>/`，从旧的 `packages-index/` 路径创建兼容性符号链接。
* 更新所有访问 `MetadataRepo` 特有方法（插件、profile、新闻、实体存储）的调用点，改为通过 `CompositeRepo` 的聚合辅助方法进行访问。

#### 阶段二 — 多软件源配置支持

* 从配置文件中解析 `[[repos]]`。
* 实现 `ruyi repo {list,add,remove,enable,disable,set-priority}`。
* 在 `CompositeRepo` 中实现聚合解析。
* 更新 `ruyi update` 以同步所有软件源。

#### 阶段三 — 细化与文档

* 面向用户的文档和迁移指南。
* 包含多软件源 fixture 的集成测试。
* 稳定 overlay 软件源格式（明确对纯 overlay 软件源的约束，如是否必须声明 `config.toml`）。
* 在有足够采用率之后移除旧的 `[repo]` 单软件源代码路径（保留配置解析以确保向后兼容）。

### 11. 安全考量

* **信任模型**：Overlay 软件源扩展了信任边界。用户必须通过 `ruyi repo add` 显式添加软件源。系统级配置可以预装发行版信任的软件源。
* **插件沙箱**：现有的插件宿主不提供沙箱（这已在文档中明确说明）。每个 overlay 软件源的插件以相同权限运行。多软件源支持不改变这一点，但按软件源维护插件加载边界，使得某个 overlay 的插件无法通过插件宿主 API 直接访问其他软件源的文件。
* **配置劫持**：overlay 的 `config.toml` 无法更改用户配置级别的软件源 ID 或优先级。软件源内部的身份标识仅供参考，不匹配时会发出警告。
* **名称抢注**：overlay 可能会用恶意内容遮蔽官方软件包。通过要求显式的优先级分配，以及在日志中记录每个已安装软件包来自哪个软件源来缓解此风险。

### 12. 待讨论问题

1. **overlay 中的 `config.toml` 是否应为必需？** Gentoo 要求 `profiles/repo_name`。我们可以至少要求包含 `ruyi-repo = "v1"` 和 `[repo] id = "..."`。

2. **跨软件源依赖**：overlay A 中的软件包是否应能声明对软件源 B 中软件包的依赖？目前软件包是独立的，解析是全局性的 — 不需要显式的跨软件源依赖声明。

3. **overlay 中的分发文件镜像**：overlay 是否应能定义自己的 `[[mirror]]` 条目？这些条目应当是 overlay 作用域的还是全局合并的？建议：默认为 overlay 作用域，可通过镜像声明中的 `global = true` 标志开启全局合并。

4. **软件源数量上限**：是否应有硬限制？Gentoo 不设上限。建议：不设硬限制，但当配置的软件源数量超过 20 个时发出警告（出于性能考虑）。

5. **虚拟环境的软件源固定**：虚拟环境当前在 `ruyi-venv.toml` 中按 `repo_id` 记录软件包。支持多软件源后，虚拟环境应继续记录 `repo_id`，以便重新创建时指向同一软件源。若某软件源后续被移除，虚拟环境可回退到在剩余软件源中进行解析，并发出警告。
