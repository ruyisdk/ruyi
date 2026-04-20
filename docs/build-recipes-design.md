# 构建配方（Build Recipe）设计文档

## 背景与动机

当前 RuyiSDK 软件包的构建流程事实上分散在若干独立的仓库与脚本中：

* `packages-index` 保存面向终端用户的软件包清单（manifest），是一份"已构建产物的目录"。
* `ruyici` 仓库保存实际的构建脚本：每个目标软件包对应一组 `ruyi-build-*` 外层脚本（Docker 封装层）与 `ruyi-build-*-inner` 内层脚本（容器内实际构建逻辑），以及一批特定驱动所需的配置文件（`toolchain-configs/`、`qemu-configs/`、`llvm-configs/` 等）与补丁（`toolchain-patches/`）。
* 构建操作者（packager）需要凭记忆或参考 README 才知道"构建 `toolchain/gnu-plct` 0.20231118.0 这个版本对应的命令是 `./ruyi-build-ctng ./toolchain-configs/gnu-plct/host-amd64.defconfig`"。这一"部落知识"从未被系统化。

本设计的目的是：

1. 将"如何构建某个软件包"这一知识本身变成**可版本化的数据**，与构建脚本一同由官方或第三方维护。
2. 让 `ruyi` 作为编排入口自动执行该数据所描述的构建流程，并完成产物登记（校验和、大小、清单片段）以便后续合并进 `packages-index`。
3. 不改变 `packages-index` 的既有 schema，不影响终端用户。

## 核心概念

### 构建配方仓库（build-recipe repository）

一个**构建配方仓库**是一个独立的目录树（通常也是一个独立的 git 仓库），其根目录存在一个 `ruyi-build-recipes.toml` 标记文件。仓库内的 `*.star` 文件即**构建配方**，每一个配方描述了一个或多个可调度的构建任务。

借鉴 `packages-index` 的 overlay 架构（详见[多软件源支持设计文档](./multi-repo-design.md)），用户可以同时配置多个构建配方仓库：

* **官方配方仓库**：目前的 `ruyici` 仓库加上一份 `ruyi-build-recipes.toml` 即成为官方配方仓库；仓库内现有的 `ruyi-build-*` 外层脚本不再被 `ruyi` 直接调用，但可以继续用于手动调试。
* **厂商/OEM 配方仓库**：硬件厂商可在自己的仓库中维护为特定开发板或 BSP 定制的构建流程。
* **个人/实验配方仓库**：开发者可在本地仓库中临时编写配方，无需改动任何上游仓库。

需要强调的是：配方仓库对**仓库内部布局**不做硬性约束。配方可以是 `recipes/foo.star`、`my-builds/bar.star` 乃至根目录下的 `baz.star`，均由配方作者自行决定。`ruyi` 只依赖标记文件定位项目根；配方之间的相互引用使用下文定义的 URI Scheme。

### 构建配方（build recipe）

一个构建配方是一份 Starlark 源文件，在顶层以与现有插件完全一致的方式声明 API 版本：

```python
RUYI = ruyi_plugin_rev(1)
```

配方在模块加载时通过 `RUYI.build.schedule_build(fn, name=...)` **显式注册**一个或多个可调度的构建函数。每个构建函数接收一个 `ctx` 参数，返回一个子进程调用计划（`Invocation`）。

仅当宿主以"构建配方上下文"加载该 Starlark 模块时，`RUYI.build` 命名空间才可访问；普通插件尝试访问会得到明确的错误。该门控由新增的 `build-recipe-v1` feature flag 控制，复用现有 `RuyiHostAPI.has_feature()` 机制。

### 配方项目根与安全边界

`ruyi-build-recipes.toml` 不仅是一个分类标记，同时定义了一个安全边界：

* `ruyi admin build-package ./xxx.star` 的行为是：对 `xxx.star` 取 `realpath`，自底向上查找第一个含有 `ruyi-build-recipes.toml` 的祖先目录，即视为**项目根**。若追溯到 `/` 仍未找到标记文件，则命令拒绝执行并给出清晰的错误信息。
* 配方在使用 `ruyi-build://` URI 引用项目内其他文件时，最终解析路径必须仍落在项目根以内（反 `..` 逃逸检查）。
* 构建产物默认落在项目根下的 `output_dir`（由标记文件声明，默认 `out/`）；若配方希望使用项目根之外的目录作为产物根，则该目录必须出现在标记文件的 `extra_artifact_roots` 白名单中。

该约束与 Bazel 的 `WORKSPACE` / `MODULE.bazel` 根文件机制类似：将**项目边界**从"用户记得切换到哪里"这种易出错的隐式行为，转化为一条可被机器校验的显式事实。

## 标记文件格式

```toml
format = "v1"

[project]
name = "ruyici"                     # 人类可读名称；用于日志与构建报告
output_dir = "out"                  # 默认产物目录（相对项目根）
extra_artifact_roots = ["/tmp"]     # 可选：允许产物落在项目根之外的绝对路径前缀白名单
```

未来新增字段（例如默认的 builder image 摘要、默认 subprocess 环境变量）时，沿用 `format = "vN"` 语义化递增；`ruyi` 核心对未知版本拒绝加载并建议升级 `ruyi`。

## Starlark 宿主 API

### 模块加载时（`RUYI`）

* `RUYI = ruyi_plugin_rev(1)` — 与既有插件完全相同，仅在启用 `build-recipe-v1` feature 的宿主上下文中，`RUYI.build` 子命名空间才可访问。
* `RUYI.build.schedule_build(fn, name=None)` — 注册一个构建函数。`name` 缺省时取 `fn.__name__`；同一配方内重名为错误；完整加载后未注册任何构建为错误。
* `RUYI.log`、`RUYI.i18n`（若宿主上下文启用 i18n）— 沿用现有 `RuyiHostAPI` 中的对应字段，供配方输出进度或本地化提示。
* 注意：`RUYI.call_subprocess_argv` 在构建配方上下文中被显式关闭。所有子进程调用必须经由下文的 `ctx.subprocess(...)` 以计划形式声明。

### 构建执行时（`ctx`）

`ctx` 是每次调度时由宿主新建的上下文对象，绑定到具体的某次被调度构建，仅在该 `fn(ctx)` 调用期间有效：

* `ctx.subprocess(argv, cwd=None, env=None, produces=[]) -> Invocation` — 构造一个子进程调用计划。该方法**不立即执行**，仅返回一个不可变记录，由宿主在计划返回后统一调度。
* `ctx.artifact(glob, root=None) -> Artifact` — 声明一个产物 glob。`root` 为 `None` 时取项目标记文件的 `output_dir`；为绝对路径时必须落在 `extra_artifact_roots` 允许的前缀下。
* `ctx.var(name, default=None) -> str` — 读取命令行传入的 `-v NAME=VALUE` 变量。未提供且无默认值为错误。
* `ctx.repo_root: str` — 项目根绝对路径。
* `ctx.repo_path(rel: str) -> str` — 相对项目根的安全路径拼接（内含反 `..` 逃逸检查）。
* `ctx.name: str` — 当前调度构建的名称；`ctx.recipe_file: str` — 触发本次调度的 `.star` 文件路径。两者主要用于错误信息与构建报告。

故意保持极简：**核心 API 中不存在 `docker_run`、`driver`、`input_config` 这些概念**。Docker 封装与 image tag 管理属于"配方上用户空间"的工具，由配方作者在项目内以 Starlark 库的形式（例如 `lib/docker.star`）提供，通过 `ruyi-build://` URI 被其他配方 `load` 复用。`ruyi` 核心只认 `subprocess`。

## 加载路径 URI Scheme

现有的 `ruyi/pluginhost/paths.py` 已经支持以下 URI scheme：

* `ruyi-plugin://<id>` — 按插件 ID 定位 `packages-index/plugins/<id>/mod.star`；
* `ruyi-plugin-data://<id>/...` — 对应的数据文件访问。

本设计在此基础上新增两个 scheme，语义一致但解析根不同：

* `ruyi-build://<project-relative-path>` — 将路径解析为**当前配方项目根**下的子路径，用于加载项目内的 Starlark 代码；
* `ruyi-build-data://<project-relative-path>` — 同上，但走数据加载通道（`is_for_data=True`），供 `load_toml` 等场景使用。

两种 scheme 在解析后均强制执行反 `..` 逃逸检查，最终路径必须仍在项目根以内。裸 `//foo` 形式（不含 scheme）继续保持拒绝，与现有策略一致。

在配方文件中的使用示例：

```python
RUYI = ruyi_plugin_rev(1)
load("ruyi-build://lib/docker.star", "docker_run")
load("ruyi-build://lib/images.star", "pkgbuilder_image_tag")
```

## 完整示例

下例展示将现有 `ruyici/ruyi-build-qemu` 的一次 `both` 变体调用改写为配方：

```python
# recipes/qemu-riscv-upstream.star
RUYI = ruyi_plugin_rev(1)

load("ruyi-build://lib/docker.star", "docker_run")
load("ruyi-build://lib/images.star", "pkgbuilder_image_tag")


def build_qemu_riscv_upstream(ctx):
    arch = ctx.var("arch", default = "amd64")
    flavor = ctx.var("flavor", default = "both")

    produces = []
    if flavor in ("both", "system"):
        produces.append(ctx.artifact(
            glob = "qemu-system-riscv-upstream-*.%s.tar.zst" % arch))
    if flavor in ("both", "user"):
        produces.append(ctx.artifact(
            glob = "qemu-user-riscv-upstream-*.%s.tar.zst" % arch))

    return ctx.subprocess(
        argv = docker_run(
            image = pkgbuilder_image_tag("unified", "amd64"),
            mounts_rw = [
                (ctx.repo_path("out"), "/out"),
                (ctx.repo_path("work"), "/work"),
            ],
            mounts_ro = [
                (ctx.repo_path("ruyi-build-qemu-inner"),
                 "/usr/local/bin/ruyi-build-qemu-inner"),
                (ctx.repo_path("qemu-configs/upstream-20250908.sh"),
                 "/tmp/config.sh"),
                (ctx.repo_path("qemu-10.0.4.tar.xz"), "/tmp/src.tar.xz"),
            ],
            tmpfs = ["/tmp/mem"],
            argv = ["ruyi-build-qemu-inner", "/tmp/config.sh", arch, flavor],
        ),
        cwd = ctx.repo_root,
        produces = produces,
    )


RUYI.build.schedule_build(build_qemu_riscv_upstream)
```

对于需要"多主机矩阵"的场景（例如 `toolchain/gnu-upstream` 分别为 amd64/arm64/riscv64 三个主机产出 sysroot 归档），在配方顶层以 Python/Starlark 循环显式注册多次即可：

```python
for host in ("amd64", "arm64", "riscv64"):
    RUYI.build.schedule_build(_make_plan(host), name = host)
```

Starlark 本身提供的 `if/for/字符串格式化`等能力足以覆盖所有分支/矩阵场景，无需在配方格式之外再引入 TOML schema 或占位符插值语言。

## 命令行接口

```
ruyi admin build-package <RECIPE.star>
    [-v, --var KEY=VALUE]...
    [-n, --name BUILD_NAME]...
    [--dry-run]
    [--output-dir DIR]
```

* `<RECIPE.star>` — 指向要执行的配方文件的文件系统路径（绝对或相对）。
* `-v / --var` — 以 `KEY=VALUE` 形式注入到 `ctx.var(...)` 可读取的变量空间；可重复。
* `-n / --name` — 仅执行指定名称的调度构建；可重复；缺省时执行配方内全部注册构建。
* `--dry-run` — 执行加载与计划构建阶段，但跳过 `subprocess` 实际执行；打印渲染后的 argv、env、cwd 以供审核。
* `--output-dir` — 覆盖项目标记文件中声明的默认 `output_dir`。

退出码：成功为 `0`；子进程失败原样透传其退出码；校验错误（标记文件不存在、配方未注册任何构建、`ctx.var` 无默认值且未传入等）为 `2`。

## 构建报告

对每一个成功执行的调度构建，宿主在产物目录下写入一个机器可读的构建报告：

```
<output_dir>/_ruyi-build-report.<recipe_slug>.<build_name>.<timestamp>.toml
```

内容包括：配方文件路径、构建名称、解析后的 argv/env/cwd、所有匹配到的产物绝对路径、每个产物的大小与 sha256/sha512，以及执行时间戳。该报告同时是未来可能实现的 `ruyi admin publish-package` 命令的消费对象。

为便于操作者将构建结果补入 `packages-index`，命令在成功结束时向标准输出打印一段可直接粘贴的 `[[distfiles]]` TOML 片段。当前版本不自动修改任何 `packages-index` 清单。

## 安全模型

* **信任模型与现有插件一致**：配置或直接调用一个配方仓库，等同于以当前用户身份运行该仓库内任意代码。`ruyi` 不对配方内 `ctx.subprocess(...)` 的 argv 做允许列表校验；信任来源是"用户主动指向了该 `.star` 文件所属项目"。
* **项目边界**由标记文件**客观决定**，不依赖环境变量、工作目录或 git 状态，从而避免"误把某个随意目录当作项目根"的隐性风险。
* **路径逃逸**：`ruyi-build://`、`ruyi-build-data://`、`ctx.repo_path(...)` 均在 realpath 解析后强制路径仍位于项目根下；`ctx.artifact(root=...)` 的绝对路径必须落在 `extra_artifact_roots` 白名单中。
* **模块加载上下文隔离**：`build-recipe-v1` feature 仅在以构建配方身份加载时启用；普通 `packages-index` 插件无法访问 `RUYI.build`；构建配方无法调用 `RUYI.call_subprocess_argv` 绕过 `ctx.subprocess` 的计划化管控。

## 与现状的关系、演进路径

* **`packages-index` 零改动**：不新增软件包 kind，不新增 category，不影响 `ruyi list` / `ruyi install` 等终端用户命令。
* **`ruyici` 成为官方配方仓库**：仅需增加一份 `ruyi-build-recipes.toml`、`lib/docker.star`、`lib/images.star`，以及若干初始配方文件。现有 `ruyi-build-*` 外层脚本可保留用于手动调试，但不再作为 `ruyi admin build-package` 的入口。官方仓库可分阶段逐步将各 driver 从外层 bash 脚本迁移至 Starlark helper 库。
* **`ruyi` 核心只新增装配代码与一个 admin 子命令**：不新增 package manager 概念，不修改既有 schema。

后续工作（不在本设计范围内）：

1. `ruyi admin publish-package`：串联构建、校验、上传、更新 `packages-index` 清单、提交 PR，将当前"构建报告→人工粘贴"的最后一步也自动化。
2. 构建镜像摘要固定与重现性校验：将 builder image 的 `@sha256:...` 摘要写入标记文件或配方，执行时校验漂移。此能力可在"配方空间"或"核心"任一侧实现。
3. 并行调度与缓存策略：在单次 `build-package` 调用内并行执行多个调度构建，或基于内容寻址跳过已完成的构建。
