# Ruyi 软件源结构定义

Ruyi 软件源承担两种职能，从而也由两部分构成：

* 软件包的元数据描述，
* 相关文件的分发。

以下分别描述。

## 元数据

参考了 Rust 生态系统的经验，目前的 Ruyi 软件源元数据部分是一个 Git 储存库。其结构类似如下：

```
packages-index
├── config.json
├── manifests
│   └── toolchain
│       └── plct
│           └── 0.20231026.0.json
├── profiles
│   └── riscv64.json
└── README.md
```

以下分别说明。

### README

不是必须的，目前也没有被用于界面展示等 `ruyi` 命令之内的用途，而仅仅用于网页端浏览。

### `config.json`

这是某个具体 Ruyi 软件源的全局配置，JSON 格式。

```json
{
    "dist": "https://path-to-distfiles-host"
}
```

* `dist` 字段表示 Ruyi 软件源分发路径，以 `/` 结尾与否均可。以下将此配置值称作 `${config.dist}`。
* `doc_uri` 是可选的指向该仓库的配套文档首页的 URI 字符串。

### `manifests`

此目录内含 0 或多个子目录，子目录对应软件包类别（category），目录名为类别名。

每个类别目录内含 0 或多个子目录，子目录 1:1 对应软件包；目录名为软件包名。

合法的软件包名是仅由字母、数字、`-`（中划线）组成的非空字符串，且不以 `_`（下划线）开头。
以 `_` 开头的软件包名为保留名，留作表示特殊语义用，或用于其他的必要使用场景。

每个软件包的对应目录下，存在 0 或多个对应该包特定版本的具体定义文件；文件名即为版本号，格式为 JSON，后缀为 `.json`。

举例说明：

```json
// 工具链包示例
{
  "slug": "plct-20231026",
  "kind": ["binary", "toolchain"],
  "desc": "RuyiSDK RISC-V Linux Toolchain 20231026 (maintained by PLCT)",
  "vendor": {
    "name": "PLCT",
    "eula": null
  },
  "distfiles": [
    {
      "name": "RuyiSDK-20231026-HOST-riscv64-linux-gnu-riscv64-plct-linux-gnu.tar.xz",
      "size": 162283388,
      "checksums": {
        "sha256": "6e7f269e52afd07b5fb03d1d96666fa12561586e5558fc841cb81bb35f2e3b9b",
        "sha512": "ad5da6ea6a68d5d572619591e767173433db005b78d0e7fbcfe53dc5a17468eb83c72879107e51aa70a42c9bca03f1b0e483eb00ddaf074bf00488d5a4f54914"
      }
    },
    {
      "name": "RuyiSDK-20231026-riscv64-plct-linux-gnu.tar.xz",
      "size": 171803916,
      "checksums": {
        "sha256": "2ae0ad6b513a8cb9541cb6a3373d7d1517a8848137b27cc64823582d3e9c01de",
        "sha512": "6fabe9642a0b2c60f67cdb6162fe6f4bcf399809ca4e0e216df7bebba480f2965e9cd49e4502efbdcc0174ea7dc1c8784bf9f9c920c33466189cd8990fa7c98e"
      }
    }
  ],
  "binary": [
    {
      "host": "riscv64",
      "distfiles": ["RuyiSDK-20231026-HOST-riscv64-linux-gnu-riscv64-plct-linux-gnu.tar.xz"]
    },
    {
      "host": "x86_64",
      "distfiles": ["RuyiSDK-20231026-riscv64-plct-linux-gnu.tar.xz"]
    }
  ],
  "toolchain": {
    "target": "riscv64-plct-linux-gnu",
    "flavors": [],
    "components": [
      {"name": "binutils", "version": "2.40"},
      {"name": "gcc", "version": "13.1.0"},
      {"name": "gdb", "version": "13.1"},
      {"name": "glibc", "version": "2.38"},
      {"name": "linux-headers", "version": "6.4"}
    ],
    "included_sysroot": "riscv64-plct-linux-gnu/sysroot"
  }
}

// 模拟器包示例
{
  "kind": ["binary", "emulator"],
  "desc": "RuyiSDK QEMU linux-user Build (Upstream 8.1.2, built by PLCT)",
  "vendor": {
    "name": "PLCT",
    "eula": null
  },
  "distfiles": [
    {
      "name": "qemu-user-riscv-8.1.2.ruyi-20231121.amd64.tar.zst",
      "size": 15154068,
      "checksums": {
        "sha512": "73ac9c82b4386b5d8cb3d5e6654f600e38a7af6043bd546c7a0ec2940add29382a08f6a769bf1d5db150966dd18224789362add691c89c4e89ea31ae24436bd2",
        "sha256": "24b477630c5f9a01f8a2188e6b1a33bc24723d5217d34285a3bb3509f5a0948a"
      },
      "strip_components": 2
    }
  ],
  "binary": [
    {
      "host": "x86_64",
      "distfiles": ["qemu-user-riscv-8.1.2.ruyi-20231121.amd64.tar.zst"]
    }
  ],
  "emulator": {
    "programs": [
      {
        "path": "bin/qemu-riscv32",
        "flavor": "qemu-linux-user",
        "supported_arches": ["riscv32"],
        "binfmt_misc": ":ruyi-qemu-riscv32:M::\\x7fELF\\x01\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\xf3\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:$BIN:OCF"
      },
      {
        "path": "bin/qemu-riscv64",
        "flavor": "qemu-linux-user",
        "supported_arches": ["riscv64"],
        "binfmt_misc": ":ruyi-qemu-riscv64:M::\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\xf3\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:$BIN:OCF"
      }
    ]
  }
}
```

其中：

* `slug` 是可选的便于称呼该包的全局唯一标识。目前未有任何特定的命名规范，待后续出现第三方软件源再行定义。
* `kind` 说明软件包的性质。目前定义了以下几种：
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
* `binary` 仅在 `kind` 含有 `binary` 时有意义，表示适用于二进制包的额外信息。其类型为列表，每条记录：
    - `host` 代表该条记录所指的二进制包适用的宿主架构。宿主架构的语义与 Python 的 `platform.machine()` 返回值相同。
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。要为此宿主架构安装该包，下载并解压所有这些分发文件到相同目标目录即可。
* `blob` 仅在 `kind` 含有 `blob` 时有意义，表示适用于二进制数据包的额外信息。其中：
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。此包不应被安装；对分发文件的引用应直接指向相应文件的下载目的地。
* `source` 仅在 `kind` 含有 `source` 时有意义，表示适用于源码包的额外信息。其中：
    - `distfiles` 是分发文件名的列表，每条分发文件的具体定义参照 `distfiles` 字段。要向某目标目录解压该源码包，下载并解压所有这些分发文件到该目标目录即可。
* `toolchain` 仅在 `kind` 含有 `toolchain` 时有意义，表示适用于工具链包的额外信息。
    - `target` 是工具链在运行时所预期的 target tuple 取值。
    - `flavors` 是自由形态字符串的列表，用于表示工具链的特殊特征（如支持某厂商未上游的特性，或 `-mcpu` 逻辑与社区版本不同等等）。目前定义了：
        - `xthead`：工具链是由 T-Head 源码构建而成，尤其其 `-mcpu` 取值方式与上游不同。
    - `components` 是该包所含的标准组件及相应（等价）版本的列表。目前暂时没有用上，后续可能会基于此提供展示、过滤、匹配等功能。
    - `included_sysroot` 是可选的字符串。如果该字段存在，则代表在解压该包后，此相对路径是指向目标目录下的一个可供直接复制而为虚拟环境所用的 sysroot 目录。
* `emulator` 仅在 `kind` 含有 `emulator` 时有意义，表示适用于模拟器包的额外信息。其中：
    - `flavors` 是自由形态字符串的列表，用于表示模拟器的特殊特征（如支持某厂商未上游的特性，或 `-cpu` 逻辑与社区版本不同等等）。目前定义了：
        - `xthead`：模拟器是由 T-Head 源码构建而成，尤其其 `-cpu`/`QEMU_CPU` 取值方式与上游不同。
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
        - `boot`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `boot` 分区。
        - `root`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `root` 分区。
        - `uboot`：对于使用 fastboot 烧写的设备，代表 fastboot 视角的 `uboot` 分区。

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

### `profiles`

此目录内含 0 或多个 JSON 格式的配置文件定义。目前没有特殊规定文件名的语义，也没有对其特别限制。

每个配置文件定义形如下：

```json
{
  "arch": "riscv64",
  "generic_opts": {
      "march": "rv64gc",
      "mabi": "lp64d",
      "mcpu": ""
  },
  "profiles": [
    {
      "name": "sipeed-lpi4a",
      "need_flavor": ["xthead"],
      "mcpu": "thead-c910"
    },
    {
      "name": "milkv-duo",
      "mcpu": "thead-c906"
    }
  ],
  "flavor_specific_mcpus": {
    "xthead": {
      "thead-c906": "c906",
      "thead-c910": "c910"
    }
  },
  "emulator_presets": {
    "generic": {
      "qemu-linux-user": {
        "env": {
          "QEMU_CPU": "rv64"
        }
      }
    },
    "thead-c906": {
      "qemu-linux-user": {
        "env": {
          "QEMU_CPU": "thead-c906"
        }
      }
    }
  }
}
```

其中 `arch` 是此配置文件定义对应的架构名，目前定义了 `riscv32`、`riscv64` 两种。
其他字段的存在与否、取值、结构与含义均由 `arch` 取值决定。

对 `riscv32`、`riscv64` 架构而言：

* `generic_opts` 包含 `march`、`mabi`、`mcpu` 取值，是本文件所定义的每种配置相应字段不取值时，默认使用的值。
* `profiles` 是具体配置定义列表，每条记录：
    - `name` 是配置名，会被广泛用于展示、命令行参数等。
    - `doc_uri` 是可选的指向该配置的配套文档首页的 URI 字符串。
    - `need_flavor` 是该配置要求对应的工具链包需要提供的 flavors 列表，如不为空，所有条目必须全部匹配。
    - `mabi` `march` `mcpu` 如果存在，代表此配置的相应编译器参数使用该值，而非通用值。对于 `-mcpu` 参数，如果 `need_flavor` 不为空，实际使用的值会额外经过一层映射，映射关系由 `flavor_specific_mcpus` 定义。
* `flavor_specific_mcpus` 是当某配置文件需求了某工具链 flavor 时，对 `mcpu` 取值的映射关系。
* `emulator_presets` 是对应各配置的模拟器预置设定。此键值对的每个键是 `mcpu` 取值，其值是从每种受支持的模拟器包 flavor 到相应预置设定数据的键值对。预置设定数据的结构如下：
    - `need_flavor` 是该配置要求对应的模拟器包需要提供的 flavors 列表，如不为空，所有条目必须全部匹配。
    - `env` 是键值对，每条记录的键为用户需设置的环境变量名，值为该环境变量需取的值。

对于模拟器预置设定，如果一个 `mcpu` 取值没有相应的 `emulator_presets` 配置，则应为其适用 `generic` 配置的设定。

对于 `qemu-linux-user` flavor 的模拟器，除了 `env` 所配置的环境变量之外，额外地还会有以下特殊处理：

* 如当前虚拟环境有搭配了 sysroot 配置，那么将新增一个 `QEMU_LD_PREFIX` 环境变量，指向此 sysroot。

## 分发

目前仅要求以 HTTP/HTTPS 协议提供服务。

在 `${config.dist}` 路径下，目前仅要求实现一个 `dist` 目录，内含分发文件。

要求 distfiles 的下载服务必须支持断点续传。
