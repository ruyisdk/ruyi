# ELF ABI 兼容性信息采集与匹配

一个预编译 ELF 二进制包能否在某台目标设备上跑起来，很大程度上取决于一批 ELF ABI
层面的事实：它需要哪些动态库（`DT_NEEDED`）、向这些库索取了哪些符号版本（verneed，
即 `.gnu.version_r`），以及一些架构相关的能力要求（x86-64 的 ISA feature level、
AArch64 的 BTI/PAC、RISC-V 的 ISA 串等等）。这些信息此前散落在各个 ELF 文件的文件头里，
软件源里没有任何地方记录它们。

为此我们让 `ruyi` 具备扫描包内 ELF 文件以采集这些信息的能力，以及基于这些信息判断一个软件包与宿主系统兼容性的能力。
组件实现位于 `ruyi/ruyipkg/abi/`。

## ABI 信息采集

### 采集内容

对每个 ELF 文件，采集：

**架构无关的 ABI 信息**，用 `pyelftools` 读取：

* `e_machine`：原始枚举值；为向前兼容性，不映射到可读名称。
* 位宽（32 / 64）、字节序（little / big）、ELF 类型（exec / dyn / rel / core / other）。
* `PT_INTERP`（动态链接器路径，若有）。
* `DT_SONAME`、`DT_NEEDED`（按链接顺序）。
* verneed：按 soname 归组的所需符号版本集合，并单独记录 `VER_FLG_WEAK`
  的弱版本引用。
* 是否存在未版本化的未定义符号（`needs_unversioned`）。

**架构相关的 ABI 属性容器**，对任何架构都完整采集：

* GNU property notes（`.note.gnu.property`）：解析出通用的 note 与 property array
  框架，得到若干 `(pr_type, 原始载荷)`。
* ELF 属性节（`SHT_*_ATTRIBUTES`，如 `.riscv.attributes`、`.ARM.attributes`）：只解析外层
  vendor subsection 框架，把每个厂商子节的原始载荷整段保存。

这些原始载荷被编码成十六进制字符串存储。单条 blob 长度超过阈值时会被截断并被标记 `truncated = true`。

**解读结果**：对于有支持的 `e_machine`，将原始载荷分发到对应的解码器，以便把它们解码成一组扁平的键值对
`parsed_attrs`。例如：x86-64 的 `isa_level`、AArch64 的 `bti`/`pac`、RISC-V 的 `isa`。

任何架构的原始 ABI 属性容器都会被完整归档。把这些原始 tag 解码成结构化信息是严格的增量步骤，这是为了向前兼容：日后如要支持更多架构，只需新增一个解码器，直接在**已保存的原始字节**上解读即可，无需重新扫描——尤其无需再次从（往往是解压得到的）归档流里把 ELF 掏出来重跑一遍。

解码器只读取通用的 `GnuProperty` / `AttributeVendorBlob` 结构，不涉及 `pyelftools` 数据类型，因而易于单独测试，且与 `pyelftools` 项目实现了版本上的隔离。字节序会被显式传入解码器，因此 big-endian 的信息也能被正确解码。

采集到的原始内容会被去重：

* **按内容去重**：以 ELF 载荷的 sha256 为准，字节完全相同的 ELF（副本、硬链接、同一二进制出现在多处）
  合并为一条记录，`paths` 列出它出现的所有位置。内容不同的二进制永远是不同记录。
* **排除规则**：`scan_source` 接受一组 `.gitignore` 风格的 `exclude` 模式（基于 `pathspec`），
  匹配到的成员在识别 ELF 之前就被跳过，只计入 `excluded_count`，供打包者按需忽略那些测试用 fixtures、仅在特定条件下启用的程序库等实质上不影响 ABI 兼容性的 ELF 文件。

扫描来源可以是一棵普通目录树，也可以是一个归档文件（tar / zip / deb；tar 的任意受支持压缩均适用）；裸压缩的单文件流不受支持。为了性能，对于归档文件，直接流式解压、遍历其成员，不落盘。非 ELF 成员会被计入 `file_count` 但不产生记录。

### 数据格式

产出是一份确定性的 TOML 报告（对相同的输入，应产生 byte-verbatim 的输出）。顶层是一个 `[summary]` 汇总表、若干
`[[record]]`（按 `sha256` 排序），以及可选的 `[[error]]`。示例：

```toml
[summary]
e_machines = [243]
needed = ["libc.so.6", "libm.so.6"]
elf_count = 3
file_count = 42
excluded_count = 7

[summary.well_known_maxima]
GLIBC = "2.34"

# 按 e_machine 分组的解读汇总；EM_RISCV = 243
[summary.parsed_attrs_rollup.243]
isa_strings = ["rv64gc"]

[[record]]
paths = ["usr/bin/foo", "usr/bin/foo-copy"]
sha256 = "1f0e..."
e_machine = 243
elf_class = 64
endianness = "little"
elf_type = "dyn"
is_dynamic = true
interpreter = "/lib/ld-linux-riscv64-lp64d.so.1"
soname = ""
needed = ["libc.so.6", "libm.so.6"]
needs_unversioned = false
parsed_attrs = { isa = "rv64gc", stack_align = 16 }

[[record.version_needs]]
soname = "libc.so.6"
versions = ["GLIBC_2.17", "GLIBC_2.34"]

# 每个架构都有原始采集；属性节以不透明的十六进制 blob 保存
[[record.elf_attributes]]
vendor = "riscv"
data_hex = "410000001872697363760001000000000572763634..."
```

要点：

* `[summary]` 汇总各记录：`e_machines` 是出现过的机器类型集合；`needed` 是所有 `DT_NEEDED` 的并集；
  `well_known_maxima` 对 `GLIBC`、`GLIBCXX`、`CXXABI`、`ZLIB`、`GCC` 等前缀，按版本号数值序取出各自需要的最高版本；
  `parsed_attrs_rollup` 是按 `e_machine` 归组的解读汇总（x86-64 取最低保证 level，AArch64 对 BTI/PAC
  求与，RISC-V 记录 ISA 串集合）。
* `[[record]]` 里，`parsed_attrs` 是扁平内联表；无对应解码器时为空表 `{}`，`gnu_properties`
  / `elf_attributes` 原始数据照常存在。`gnu_properties`、`elf_attributes` 以数组表形式给出，排序稳定。
* `version_needs` 的 `versions` 只包含强版本引用；若同一个 soname 还有 `VER_FLG_WEAK`
  引用，会额外给出可选键 `weak_versions`。弱版本缺失不影响动态加载，因此不参与兼容性判定。

入口是 `scan_source()`（产出 `ABIReport`），序列化用 `dump_abi_report_toml()`。

### CLI 集成

采集能力通过 `ruyi admin` 下的两个子命令暴露给打包者。

#### `ruyi admin rescan-package-abi <path>`

对一份已构建的产物做离线重扫。`<path>` 既可以是归档文件（tar / zip / deb；tar 的
任意受支持压缩均适用），也可以是一棵已解压的目录树，二者都走前文的
`scan_source()`。注意：`scan_source()` 本身支持的来源只有目录树、tar、zip 与 deb，
裸压缩的单文件流并不在其支持范围内，本命令自然也不受理。

默认把 TOML 报告写到输入旁边的 `<path>.abi.toml`：后缀恰好是 `.abi.toml`，
追加在目标全名之后（例如 `foo-0.1.0.tar.zst` 会得到
`foo-0.1.0.tar.zst.abi.toml`）。`-o FILE` 指定其他输出路径；`-o -` 则把
TOML 写到标准输出，便于与管道、diff 工具配合。

排除模式与 `scan_source()` 的 `exclude` 语义一致，均为 `.gitignore` 风格，匹配路径相对于包镜像根：

* `--exclude GLOB` 可重复给出，逐条累加；
* `--exclude @FILE` 从文件中读取模式，每行一条；空行与以 `#` 开头的注释行会被跳过；
* `--strip-components N` 仅对归档输入有效：在匹配排除规则与记录路径之前，丢弃每个成员路径的前 N 段；默认 0。目录输入本身已以给定目录为根，不接受该选项。

需要注意的是，文件扫描排除的只是 `pathspec` 层面的成员匹配，与 Ruyi 运行时
对 `_` 前缀条目的忽略是两回事（后者由仓库结构约定，见下）。

#### `ruyi admin build-package`

构建软件包时默认顺带产出 ABI 元数据：对每个成功构建出的归档产物，在其旁边
生成一份同名的 `<archive>.abi.toml` sidecar，后缀规则与 `rescan-package-abi`
相同。

* `--no-abi-scan` 关闭这一默认行为，只构建产物、不生成 sidecar。
* recipe 可以按产物粒度定制排除规则：`ctx.artifact(glob, root, exclude=[...], strip_components=N)`，
  其中 `exclude` 的含义同 `scan_source()`，`strip_components` 用于去掉归档产物内部的顶层目录。

### 产物在软件源中的摆放

生成的 sidecar 需要随软件源一起提交，具体放在保留的、以 `_` 开头的位置下
（约定见 `docs/repo-structure.md`：软件包目录内任何 `_` 开头的条目都是保留的
辅助内容，`ruyi` 运行时忽略、`ruyi admin check` 接受）。在哪个版本、以什么
文件名被 Ruyi 摄入（ingest），属于后续工作，本文暂不约定。

## ABI 兼容性匹配

### 目的与入口

匹配分两步：

* **探测主机**：`HostABIProber.probe(manifest) -> HostABIReport`。以包的 `ABIReport`
  （来自 `scan_source()` 或 `.abi.toml` sidecar）为导向，只采集判定所需的事实，
  产出冻结的 `HostABIReport`。
* **逐条判定**：`check_host_compatibility(package, host) -> HostABICompatReport`。这是一个
  纯函数，不产生任何 I/O，把包的 `ABIReport` 与主机的 `HostABIReport` 逐规则比对，产出
  `HostABICompatReport`。

`HostABICompatReport` 给出一组 `HostABICompatItem`（每项对应一条规则的一次判定），以及几个
汇总视图：

* `compatible`：三态属性，`True` 表示兼容、`False` 表示确定不兼容、`None` 表示无法判定。
* `bool(report)`：宽松谓词，只要没有任何一项是确定不兼容（`False`）就为 `True`。
* `strictly_compatible`：严格谓词，只有当 `compatible is True`（所有规则都判为兼容）时才为 `True`。
* `problems()`：返回所有 `compatible is not True`（即 `False` 或 `None`）的条目，供上层渲染解释信息。

`bool(report)` 与 `strictly_compatible` 的差别是刻意的：前者回答"有没有硬伤"，后者回答
"能否拍板说一定行"。例如一个带有未版本化符号的包（见下文 `unversioned` 规则）会让
`strictly_compatible` 保持 `False`，但只要没有确定不兼容的条目，`bool(report)` 仍为 `True`。

### 探测内容

`HostABIProber.probe()` 刻意避免全量扫描主机：包的 `ABIReport` 就是查询计划，主机 I/O 只发生在
清单点名要查的地方。具体来说：

* **主机架构事实**：由 `get_native_host().arch` 经查询各个 interpreter 得到；未知架构时 `e_machines` 为空，表示“无法判定”，但仍然会假定它为一个
  64 位小端序架构。
* **`PT_INTERP`**：只检查清单中出现过的动态链接器路径在文件系统上是否存在
  （`interpreter_paths_present`）。
* **`DT_NEEDED`**：对 `manifest.summary.needed` 里的每个 soname，只问"能否解析到库文件"
  （`resolvable_sonames`），不进一步扫描这些库。
* **`version_needs`**：只有清单里按 soname 归组的所需符号版本，才会把对应的 provider 库
  解析出来、单独扫一遍，记录其 `.gnu.version_d` 里定义的版本（`providers`）。
* **架构相关属性**：对清单中出现的每个 `e_machine`，调用对应解释器的 `host_attrs()` 读取
  主机 CPU 能力（x86-64 的 ISA level、AArch64 的 BTI/PAC、RISC-V 的 ISA 串等）。

探测状态不会被持久化到磁盘，这样在用户的系统被更新之后，不会有任何缓存结果因此过时。

各探测步骤都会吞掉 I/O 失败而不是把异常抛进匹配器，但降级方式因类别而异：

* provider 库扫描失败与属性探测失败会降级为 `None`（无法判定）；
* 动态库解析与动态链接器存在性检查是二元的，一次读取失败会让索引不完整、存在性检查返回负结果，从而在 `soname` / `interp` 条目上表现为确定的 `False`。

### 主机库解析策略

主机库解析只回答"某个 soname 对应哪个文件"，且只模拟**安装后的包**的搜索路径，而不是
`ruyi` 进程自身的加载路径。按顺序查询：

* glibc 的 `ld.so.cache`（`/etc/ld.so.cache`）：仅当魔数与版本匹配时才解析；条目按 ELF 类型
  标志（libc6）与按架构的 required 标志（x86-64 的 `FLAG_X8664_LIB64`、AArch64 的
  `FLAG_AARCH64_LIB64`、RISC-V 的 float-ABI soft/double）过滤。
* musl 的路径文件（`/etc/ld-musl-<arch>.path`）。
* 标准目录 `/lib`、`/usr/lib`、`/usr/local/lib`，以及 triplet 目录 `/lib/<triplet>`、
  `/usr/lib/<triplet>`。

解析刻意**不做**三件事，这是 Nuitka 打包安全的关键：绝不读 `LD_LIBRARY_PATH` 环境变量；
绝不 `dlopen` 候选库去试探；绝不从 `__file__` 或 `ruyi.__compiled__` 推导路径——`ruyi`
自身随 Nuitka onefile 携带的库对安装后的包不可消费，必须在这里保持不可见。

### 兼容性判定结果

每条规则的判定结果都是三态的：

* `True`: 兼容；
* `False`: 确定不兼容；
* `None`: 无法判定。

按如下方式将判定结果列表聚合为整体兼容性判定结果：

* 只要有任何一项为 `False`，`compatible` 就是 `False`；
* 否则只要有任何一项为 `None`，`compatible` 就是 `None`；
* 否则（全部 `True`，或没有任何条目）`compatible` 为 `True`。

如前所述，`bool(report)` 等价于 `compatible is not False`，`strictly_compatible` 等价于
`compatible is True`。

### 判定规则描述

`check_host_compatibility()` 依次执行七条规则，每条规则为每个受检对象产出一条
`HostABICompatItem`（`check` 字段标识规则，`msgid` 与 `params` 供上层用 i18n 机制渲染解释）：

| 规则 | `check` | 判定依据 | 可能结果 |
| --- | --- | --- | --- |
| 扫描错误 | `scan-error` | `package.errors` 中的每条记录 | 恒为 `None` |
| 架构 | `e-machine` / `elf-class` | 包的 `summary.e_machines` 必须是主机 `e_machines` 的子集；另按记录数统计 `elf_class` / 字节序与主机不符的条数 | 子集成立 `True`、不成立 `False`、主机架构未知 `None`；`elf-class` 条目只在主机 `elf_class` 已知时产出，结果只有 `True`/`False` |
| 动态链接器 | `interp` | 包内每个 `PT_INTERP` 路径都必须在 `interpreter_paths_present` 中 | `True`/`False` |
| 动态库 | `soname` | 每个 `summary.needed` 都必须在 `resolvable_sonames` 中 | `True`/`False` |
| 符号版本 | `verneed` | 每个 `summary.version_needs` 所要求的强版本都必须出现在对应 provider 记录的 `version_defs` 中；弱版本引用（`weak_versions`）不参与判定 | 全有 `True`、缺版本 `False`、provider 扫描失败或未扫到 `None` |
| 未版本化符号 | `unversioned` | 任一记录 `needs_unversioned` 为真 | 恒为 `None` |
| 架构属性 | `attrs` | 对每个去重后的 `(e_machine, parsed_attrs)` 组合，用解释器 `check(host_attrs, required)` 比对 | `True`/`False`/`None` |

几点说明：

* `attrs` 规则对 `(e_machine, parsed_attrs)` 组合去重，因此一个由 50 个同类 ELF
  组成的包只会产生一条属性条目。
* `scan-error` 规则把 `package.errors` 里未能成功扫描的成员也变为 `None` 条目，避免
  缺失 ABI 数据的包因为其余规则都通过而被当作（严格）兼容。
* `unversioned` 规则恒产出 `None`：一个需要未版本化符号的包，其兼容性无法在本组件的能力
  范围内判定，于是 `strictly_compatible` 永远不为 `True`，但只要其他规则都通过，
  `bool(report)` 仍为 `True`。
* 属性比对的具体语义由各架构解释器的 `check()` 决定。x86-64 比较 ISA level 数值（要求的
  level 不超过主机 level）；RISC-V 把 ISA 串展开成扩展集合做子集判断，例如
  跨越到不同 XLEN 的需求是确定的不匹配）。

#### AArch64 的 PAC/BTI

AArch64 的 BTI 与 PAC 都位于 hint space：不支持的主机执行这些指令时会把它们当 no-op，而
不是崩溃。因此当包要求 BTI/PAC 而主机缺少对应能力时，`check()` 返回 `None`（特性将惰性
失效）而非 `False`；只有当主机确实支持（或包不要求）时才返回 `True`。这也意味着一个在 BTI
支持的主机上构建、但目标主机不支持 BTI 的包，其 `attrs` 条目会降级为 `None`。

### 已知限制

* **multilib / 兼容架构**：主机被归约成单一的 `(e_machine, elf_class, endianness)` 三元组，
  仅由本机 canonical 架构映射得到。带 32 位兼容（如 x86-64 主机上的 i686、AArch64 主机上的
  armv7）的多 ABI 主机不会被建模，因此需要 32 位库的包即便在有多架构支持的主机上也会被判为
  架构不匹配。
* **异构多 hart 的 RISC-V**：`host_attrs()` 只取 `/proc/cpuinfo` 里第一条 `isa` 行，即第一个
  hart 的 ISA。在大小核式异构 ISA 的系统上，其余 hart 的能力不参与判定。
* **x86 的异构 CPU**：x86-64 的 ISA level 同样只取 `/proc/cpuinfo` 里第一条 `flags` 行
  （第一个 CPU）判定。混合了不同 AVX-512 支持程度的 CPU 时，以第一个 CPU 为准。
* **binfmt_misc**：动态链接器路径只按文件系统存在性检查；经由 binfmt_misc 等内核机制提供的
  解释器（如 qemu 模拟）没有对应真实文件，会被判为缺失。
* **不做传递性 NEEDED 检查**：只核对包自身的 `DT_NEEDED` 可解析性与 `version_needs` 版本
  要求；provider 库自身的依赖（其 `DT_NEEDED`）不做递归检查。
* **探测失败的降级不对称**：provider 扫描与属性探测失败会降级为 `None`，而动态库解析与
  动态链接器存在性检查失败会留下（可能是错误的）负结果，表现为确定的 `False`。一次瞬时的
  读库失败可能把本可运行的包误判为不兼容。
* **无磁盘缓存**：探测结果只在进程内记忆化，不落盘。这是刻意为之（避免陈旧缓存掩盖系统
  更新），代价是每个进程都要重读主机状态。
