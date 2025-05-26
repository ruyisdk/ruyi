# Ruyi 软件源结构定义

Ruyi 软件源承担两种职能，从而也由两部分构成：

* 软件包的元数据描述，
* 相关文件的分发。

以下分别描述。

## 元数据

参考了 Rust 生态系统的经验，目前的 Ruyi 软件源元数据部分是一个 Git 储存库。其结构类似如下：

```
packages-index
├── config.toml
├── manifests
│   └── toolchain
│       └── plct
│           └── 0.20231026.0.toml
├── messages.toml
├── news
│   ├── YYYY-MM-DD-news-title.en_US.md
│   └── YYYY-MM-DD-news-title.zh_CN.md
├── plugins
│   ├── ruyi-cmd-foo-bar
│   │   └── mod.star
│   ├── ruyi-device-provision-strategy-baz
│   │   └── mod.star
│   ├── ruyi-device-provision-strategy-std
│   │   └── mod.star
│   └── ruyi-profile-riscv64
│       └── mod.star
└── README.md
```

以下分别说明。

### README

不是必须的，目前也没有被用于界面展示等 `ruyi` 命令之内的用途，而仅仅用于网页端浏览。

### 全局配置

每个具体的 Ruyi 软件源都必须包含一个全局配置文件，文件名为
`config.toml`。文件内容的格式必须与其扩展名所表示的格式一致。

当此数据的顶层不包含 `ruyi-repo` 字段时，应将其视作“旧版配置”解读。
旧版配置支持两种配置字段，如示例：

```toml
dist = "https://path-to-distfiles-host"
doc_uri = "https://ruyisdk.github.io/docs/"
```

* `dist` 字段表示 Ruyi 软件源分发路径，以 `/` 结尾与否均可。以下将此配置值称作 `${config.dist}`。
* `doc_uri` 是可选的指向该仓库的配套文档首页的 URI 字符串。

当此数据的顶层包含 `ruyi-repo` 字段时，支持以下的配置字段，如示例：

```toml
ruyi-repo = "v1"

[repo]
doc_uri = "https://ruyisdk.github.io/docs/"

[[mirror]]
id = "ruyi-dist"
urls = [
  "https://path-to-distfiles-host",
]

[[mirror]]
id = "foo"
urls = [
  "https://mirrors.foo.com/foo",
  "https://mirrors.bar.org/dist/foo",
  "https://mirrors.baz.edu.cn/quux",
]

[[telemetry]]
id = "ruyisdk-pm"
scope = "pm"
url = "https://test.example.ruyisdk.org/v1/analytics/pm"

[[telemetry]]
id = "ruyisdk-repo"
scope = "repo"
url = "https://test.example.ruyisdk.org/v1/analytics/repo/ruyisdk"
```

其中：

* `repo.doc_uri` 字段含义同旧版配置的 `doc_uri` 字段。
* `mirror` 是镜像源定义，其中 ID 为 `ruyi-dist` 的镜像具备特殊含义：其
  `urls` 字段含义是旧版配置的 `dist` 字段含义的超集。
* `telemetry` 是遥测服务端配置，其中 `scope` 的含义为：
    * `pm` 表示此遥测服务端将被用于 RuyiSDK 包管理器相关的用户使用数据收集；
    * `repo` 表示此遥测服务端将被用于当前软件源的用户使用数据收集。

#### 镜像源定义

可以使用“镜像源”的概念，方便地表达某一实体所提供的多种文件分发渠道。
例如，某软件包定义中的 `urls` 字段的某一条记录形如
`mirror://foo/bar/baz.tar.zst`，那么如果搭配上述配置示例中的 `foo` 镜像源定义，
这条记录就与以下几条具体 URLs 等价：

* `https://mirrors.foo.com/foo/bar/baz.tar.zst`
* `https://mirrors.bar.org/dist/foo/bar/baz.tar.zst`
* `https://mirrors.baz.edu.cn/quux/bar/baz.tar.zst`

每个镜像源的定义格式如下：

* `id` 是镜像源的 ID。
* `urls` 是此镜像源下属的所有可用镜像的基础 URL 列表。

虽然目前 Ruyi 在下载文件时的实际行为是按列表顺序逐个尝试下载，但不对此做兼容性保证。

### 全局字符串定义 `messages.toml`

如题，示例：

```toml
ruyi-repo-messages = "v1"

[foo]
en_US = "A message template in Jinja"
zh_CN = "一条 Jinja 格式的文案模板"

[bar]
en_US = "Another message"
```

### `manifests`

此目录内含 0 或多个子目录，子目录对应软件包类别（category），目录名为类别名。

每个类别目录内含 0 或多个子目录，子目录 1:1 对应软件包；目录名为软件包名。

合法的软件包名是仅由字母、数字、`-`（中划线）组成的非空字符串，且不以 `_`（下划线）开头。
以 `_` 开头的软件包名为保留名，留作表示特殊语义用，或用于其他的必要使用场景。

每个软件包的对应目录下，存在 0 或多个对应该包特定版本的具体定义文件；文件名即为版本号，格式为
TOML，后缀为 `.toml`。

举例说明：

```toml
# 工具链包示例
format = "v1"

[metadata]
desc = "RuyiSDK RISC-V Linux Toolchain 20231026 (maintained by PLCT)"
vendor = {
  name = "PLCT",
  eula = null
}

[[metadata.service_level]]
level = "known-issue"
msgid = "known-issue-foo"
params = {}

[[distfiles]]
name = "RuyiSDK-20231026-HOST-riscv64-linux-gnu-riscv64-plct-linux-gnu.tar.xz"
size = 162283388
checksums = {
  sha256 = "6e7f269e52afd07b5fb03d1d96666fa12561586e5558fc841cb81bb35f2e3b9b",
  sha512 = "ad5da6ea6a68d5d572619591e767173433db005b78d0e7fbcfe53dc5a17468eb83c72879107e51aa70a42c9bca03f1b0e483eb00ddaf074bf00488d5a4f54914"
}

[[distfiles]]
name = "RuyiSDK-20231026-riscv64-plct-linux-gnu.tar.xz"
size = 171803916
checksums = {
  sha256 = "2ae0ad6b513a8cb9541cb6a3373d7d1517a8848137b27cc64823582d3e9c01de",
  sha512 = "6fabe9642a0b2c60f67cdb6162fe6f4bcf399809ca4e0e216df7bebba480f2965e9cd49e4502efbdcc0174ea7dc1c8784bf9f9c920c33466189cd8990fa7c98e"
}

[[binary]]
host = "riscv64"
distfiles = ["RuyiSDK-20231026-HOST-riscv64-linux-gnu-riscv64-plct-linux-gnu.tar.xz"]

[[binary]]
host = "x86_64"
distfiles = ["RuyiSDK-20231026-riscv64-plct-linux-gnu.tar.xz"]

[toolchain]
target = "riscv64-plct-linux-gnu"
quirks = []
components = [
  {name = "binutils", version = "2.40"},
  {name = "gcc", version = "13.1.0"},
  {name = "gdb", version = "13.1"},
  {name = "glibc", version = "2.38"},
  {name = "linux-headers", version = "6.4"},
],
included_sysroot = "riscv64-plct-linux-gnu/sysroot"
```

其中：

* `format` 是软件包定义文件的格式版本，目前支持 `v1` 一种。
* `slug` 是可选的便于称呼该包的全局唯一标识。目前未有任何特定的命名规范，待后续出现第三方软件源再行定义。
* `kind` 说明软件包的性质。如果不提供此字段，则 Ruyi 将根据本数据中提及的额外信息种类自动为其赋值。目前定义了以下几种：
    - `binary`：该包为二进制包，安装方式为直接解压。
    - `blob`：该包为不需安装动作、非结构化的纯二进制数据。
    - `source`：该包为源码包，安装方式为直接解压。
    - `toolchain`：该包提供了一套工具链。
    - `emulator`：该包提供了一个或多个模拟器二进制。
    - `provisionable`：该包含有可用于 Ruyi 设备安装器的描述信息。
* `desc` 是包内容的一句话描述，仅用于向用户展示。
* `doc_uri` 是可选的指向该包的配套文档首页的 URI 字符串。
* `vendor` 提供了包的提供者相关信息。其中：
    - `name`：提供者名称，目前仅用于向用户展示。
    - `eula`：目前仅支持取值为 `null`，表示安装该包前不需要征得用户明确同意任何协议。
* `service_level` 是可选的该包的服务等级描述。如果不提供该字段，则等效于存在一条 `untested` 的记录。
    - `level`：服务等级。目前支持以下取值：
        - `known_issue`：存在已知问题。
        - `untested`：测试状态未知：可能稳定可用，也可能存在问题。
    - `msgid`：当 `level` 为 `known_issue` 时，用来描述问题的文案字符串在 `messages.toml` 中的消息 ID。
    - `params`：键、值类型均为字符串的键值对，是渲染上述消息时要传入的参数。
* `upstream_version` 是可选的字符串，用来记录该包在上游所用的版本号。这可以让 RuyiSDK 软件源的管理工具在一定程度上感知、处理那些不遵循 SemVer 规范的上游版本号。
* `distfiles` 内含包的相关分发文件（distfile）声明。其中每条记录：
    - `name` 是文件名。当 `urls` 字段不存在时，表示此文件可从 `${config.dist}/dist/${name}` 这样的路径获取到。
    - `urls` 是可选的 URL 字符串列表，表示此文件可额外从这些 URL 中的任意一个获取到。下载到本地的文件仍应被保存为 `name` 所指的文件名。
    - `restrict` 是可选的对于该文件应施加的额外限制列表。每个元素可选以下之一：
        - `mirror`：该文件只能从 `urls` 所给定的 URLs 获取，不要试图从镜像源获取（默认会带上对应从镜像源获取的 URL，且优先从镜像源获取）。
        - `fetch`：该文件不应被自动获取。应提示用户自行下载并放置于规定位置，尔后再重试其先前操作。
    - `size` 是以字节计的文件大小，用于完整性校验。
    - `checksums` 是文件内容校验和的 K-V 映射，每条记录的 key 为所用的算法，value 为按照该算法得到的该文件预期的校验和。目前接受以下几种算法：
        - `sha256`：值为文件 SHA256 校验和的十六进制表示。
        - `sha512`：值为文件 SHA512 校验和的十六进制表示。
    - `strip_components` 是可选的整数，表示解压此文件内容时，对每个成员文件名需要忽略的路径前缀段数，遵循 GNU tar 的 `--strip-components` 参数的语义。如不存在，则视作 1。
    - `prefixes_to_unpack` 是可选的字符串列表，表示仅解压归档中以指定路径前缀开头的文件。目前该字段仅对 tar 格式的归档文件有效，会作为路径参数传递给 `tar` 命令。如果不指定或指定了空列表，则解压归档中的所有文件。出于信息安全考虑，列表中的路径前缀不能以 `-` 字符开头。
    - `unpack` 是可选的字符串枚举，表示应如何解包此文件。如不存在此字段，视为 `auto`。如存在此字段，则应无视 `name` 字段所示的文件扩展名，而一定按此字段指定的语义处理。
        - `auto`：按 `name` 字段所示的文件扩展名，自动处理。如遇到不知道如何处理的扩展名则应当报错。
        - `tar.auto`：视作 tarball，但交由 `tar` 命令检查、处理具体的压缩格式。
        - `raw`：不解包。解包动作等价于复制。
        - `tar` `tar.gz` `tar.bz2` `tar.lz4` `tar.xz` `tar.zst`：视作相应压缩算法（或未压缩）的 tarball 处理。
        - `gz` `bz2` `lz4` `xz` `zst`：视作相应压缩算法的字节流处理，解包后的文件名为 `name` 所示文件名去除最后一层后缀后的结果。
        - `zip` ：视作 Zip 归档文件处理。
        - `deb`：视作 Debian 软件包文件处理。
    - `fetch_restriction` 是可选的该文件所受的下载限制信息，具体来说是一条面向用户的、描述如何手工下载该文件的字符串。其中：
        - `msgid`：该文件的下载步骤说明文案，在 `messages.toml` 中的消息 ID。
        - `params`：键、值类型均为字符串的键值对，是渲染该消息时要传入的参数。
* `binary` 仅在 `kind` 含有 `binary` 时有意义，表示适用于二进制包的额外信息。其类型为列表，每条记录：
    - `host` 代表该条记录所指的二进制包适用的宿主架构与操作系统，格式为 `os/arch` 或 `arch`；当 `os` 部分省略时，视作 `linux`。`arch` 部分的语义与 Python 的 `platform.machine()` 返回值相同。`os` 部分的语义与 Python 的 `sys.platform` 相同，但将 `win32` 变为 `windows`。
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。要为此宿主安装该包，下载并解压所有这些分发文件到相同目标目录即可。
    - `commands` 是可选的键值对，用来将该包所提供的一些命令暴露供用户或虚拟环境调用。其中每个键是需要暴露的命令名称，值为相应命令基于该包安装路径根的相对路径。
* `blob` 仅在 `kind` 含有 `blob` 时有意义，表示适用于二进制数据包的额外信息。其中：
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。此包不应被安装；对分发文件的引用应直接指向相应文件的下载目的地。
* `source` 仅在 `kind` 含有 `source` 时有意义，表示适用于源码包的额外信息。其中：
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。要向某目标目录解压该源码包，下载并解压所有这些分发文件到该目标目录即可。
* `toolchain` 仅在 `kind` 含有 `toolchain` 时有意义，表示适用于工具链包的额外信息。
    - `target` 是工具链在运行时所预期的 target tuple 取值。
    - `quirks` 是自由形态字符串的列表，用于表示工具链的特殊特征（如支持某厂商未上游的特性，或 `-mcpu` 逻辑与社区版本不同等等）。目前定义了：
        - `xthead`：工具链是由 T-Head 源码构建而成，尤其其 `-mcpu` 取值方式与上游不同。
    - `flavors` 是 `quirks` 的别名，为了兼容性而保留。
    - `components` 是该包所含的标准组件及相应（等价）版本的列表。目前暂时没有用上，后续可能会基于此提供展示、过滤、匹配等功能。
    - `included_sysroot` 是可选的字符串。如果该字段存在，则代表在解压该包后，此相对路径是指向目标目录下的一个可供直接复制而为虚拟环境所用的 sysroot 目录。
* `emulator` 仅在 `kind` 含有 `emulator` 时有意义，表示适用于模拟器包的额外信息。其中：
    - `quirks` 是自由形态字符串的列表，用于表示模拟器的特殊特征（如支持某厂商未上游的特性，或 `-cpu` 逻辑与社区版本不同等等）。目前定义了：
        - `xthead`：模拟器是由 T-Head 源码构建而成，尤其其 `-cpu`/`QEMU_CPU` 取值方式与上游不同。
    - `flavors` 是 `quirks` 的别名，为了兼容性而保留。
    - `programs` 是该包内可用的模拟器二进制的定义列表，每条记录：
        - `path` 是相对包安装根目录的，指向相应二进制的相对路径。
        - `flavor` 是该模拟器二进制的性质。可选的值有：
            - `qemu-linux-user`：该二进制的用法如同静态链接的 QEMU linux-user 模拟器。
        - `supported_arches` 是该二进制支持模拟的架构列表。架构值的语义与 `binary` 的 `host` 字段相同。
        - `binfmt_misc` 是适合该二进制的 Linux `binfmt_misc` 配置串。注意转义。其中支持的特殊写法：
            - `$BIN`：将在渲染时被替换为指向该二进制的绝对路径。
* `provisionable` 仅在 `kind` 含有 `provisionable` 时有意义，表示可被 Ruyi 设备安装器读取的额外信息。其中：
    - `partition_map` 是该包提供的分区映像信息，是键值对；每条记录的 key 为目标分区性质，value 为相对于该包安装目录的，对应目标分区的未压缩原始映像文件的路径。目前支持的分区性质有：
        - `disk`：特殊，表示全盘映像。
        - `live`：特殊，表示 Live 介质、安装介质等。
        - `boot`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `boot` 分区。
        - `root`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `root` 分区。
        - `uboot`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `uboot` 分区。
    - `strategy` 是 Ruyi 设备安装器在安装该包时所应采取的策略，可选的值有：
        - `dd-v1`：对 `partition_map` 中声明的每个分区，询问用户相应的设备文件路径，然后分别以 `sudo dd` 方式刷写目标设备。
        - `fastboot-v1`：按照 `partition_map` 的定义，以 `sudo fastboot` 方式刷写目标设备。
        - `fastboot-v1(lpi4a-uboot)`：以 LicheePi 4A 文档推荐的方式，按照 `partition_map` 中 `uboot` 分区的定义刷写目标设备。

同时请注意，目前 `ruyi` 的参考实现存在如下的特殊情况：

* 目前未实现分发文件的 `restrict: fetch` 功能。其具体实现细节仍待进一步细化。
* 目前 Zip 压缩包的解压工作由系统的 `unzip` 命令提供。由于该命令不支持类似 `tar` 的 `--strip-components` 选项，因此 Zip 格式的分发文件的 `strip_components` 配置目前不会被尊重。

### `news`

此目录内含 0 或多份 Markdown 格式的通知消息。

每个通知消息文件的文件名应遵循 `YYYY-MM-DD-title[.LANG].md` 格式，
如 `2024-01-02-foo.md` 或 `2024-01-02-foo.zh-CN.md`。
其中 `LANG` 的部分，意在对应 Linux 系统上 `$LANG` 环境变量的语言部分；
如果该部分存在于文件名之中，那么在运行时，带有 `$LANG` 所对应的语言的那些通知消息文件，
将被视为覆盖了名为 `YYYY-MM-DD-title.md` 的通知消息文件。

通知消息的内容为带有 frontmatter 的 Markdown，形如下：

```markdown
---
title: '文章的完整标题'
if-installed: 'toolchain/plct(<1.0.0)'
---

# 文章的完整标题

文章正文……
```

在 frontmatter 中，接受如下的字段：

* `title`: 必须提供，文章的完整标题。
* `if-installed`: 可选提供，格式为 atom。
  如果提供了此字段，那么只有当本地已经安装了此字段取值所能匹配到的包版本时，相应的通知消息才会被重点展示。

### `plugins`

此目录内含 0 或多个 RuyiSDK 插件的代码实现。目前实现了如下几种插件类型：

* 形如 `ruyi-cmd-foo-bar` 的插件，可以 `ruyi admin run-plugin-cmd foo-bar` 的方式被调用。
* 形如 `ruyi-device-provision-strategy-foo` 的插件，可供设备安装器调用。
    * 特别地，`ruyi-device-provision-strategy-std` 是设备安装器的“标准库”。
* 形如 `ruyi-profile-quux` 的插件，为 `ruyi venv` 等工具提供 `quux` 架构的 profile 功能支持。

关于各类插件的具体写作方法，请参考官方软件源中的现有插件源码。

目前我们不对插件 API 的稳定性、兼容性做任何保证，但在需要破坏兼容性的情况下，对位于官方软件源的插件，我们一般会尽力维持它们兼容最近的
1~3 个 `ruyi` 版本。

## 分发

目前仅要求以 HTTP/HTTPS 协议提供服务。

在 `${config.dist}` 路径下，目前仅要求实现一个 `dist` 目录，内含分发文件。

要求 distfiles 的下载服务必须支持断点续传。
