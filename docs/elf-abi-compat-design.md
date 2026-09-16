# ELF ABI 兼容性信息采集

一个预编译 ELF 二进制包能否在某台目标设备上跑起来，很大程度上取决于一批 ELF ABI
层面的事实：它需要哪些动态库（`DT_NEEDED`）、向这些库索取了哪些符号版本（verneed，
即 `.gnu.version_r`），以及一些架构相关的能力要求（x86-64 的 ISA feature level、
AArch64 的 BTI/PAC、RISC-V 的 ISA 串等等）。这些信息此前散落在各个 ELF 文件的文件头里，
软件源里没有任何地方记录它们。

为此我们让 `ruyi` 具备扫描包内 ELF 文件以采集这些信息的能力，为兼容性判断打基础。
本文描述这个采集组件与它产出的元数据格式。组件实现位于 `ruyi/ruyipkg/abi/`。

## 采集内容

对每个 ELF 文件，采集：

**架构无关的 ABI 信息**，用 `pyelftools` 读取：

* `e_machine`：原始枚举值；为向前兼容性，不映射到可读名称。
* 位宽（32 / 64）、字节序（little / big）、ELF 类型（exec / dyn / rel / core / other）。
* `PT_INTERP`（动态链接器路径，若有）。
* `DT_SONAME`、`DT_NEEDED`（按链接顺序）。
* verneed：按 soname 归组的所需符号版本集合。
* 是否存在未版本化的未定义符号（`needs_unversioned`）。

**架构相关的 ABI 属性容器**，对任何架构都完整采集：

* GNU property notes（`.note.gnu.property`）：解析出通用的 note 与 property array
  框架，得到若干 `(pr_type, 原始载荷)`。
* ELF 属性节（`SHT_*_ATTRIBUTES`，如 `.riscv.attributes`、`.ARM.attributes`）：只解析外层
  vendor subsection 框架，把每个厂商子节的原始载荷整段保存。

这些原始载荷被编码成十六进制字符串存储。单条 blob 长度超过阈值时会被截断并被标记 `truncated = true`。

**解读结果**：对于有支持的 `e_machine`，将原始载荷分发到对应的解码器，以便把它们解码成一组扁平的键值对
`parsed_attrs`。例如：x86-64 的 `isa_level`、AArch64 的 `bti`/`pac`、RISC-V 的 `isa`。

## 原始采集与解读分离

任何架构的原始 ABI 属性容器都会被完整归档。把这些原始 tag 解码成结构化信息是严格的增量步骤，这是为了向前兼容：日后如要支持更多架构，只需新增一个解码器，直接在**已保存的原始字节**上解读即可，无需重新扫描——尤其无需再次从（往往是解压得到的）归档流里把 ELF 掏出来重跑一遍。

解码器只读取通用的 `GnuProperty` / `AttributeVendorBlob` 结构，不涉及 `pyelftools` 数据类型，因而易于单独测试，且与 `pyelftools` 项目实现了版本上的隔离。字节序会被显式传入解码器，因此 big-endian 的信息也能被正确解码。

## 去重与排除

* **按内容去重**：以 ELF 载荷的 sha256 为准，字节完全相同的 ELF（副本、硬链接、同一二进制出现在多处）
  合并为一条记录，`paths` 列出它出现的所有位置。内容不同的二进制永远是不同记录。
* **排除规则**：`scan_source` 接受一组 `.gitignore` 风格的 `exclude` 模式（基于 `pathspec`），
  匹配到的成员在识别 ELF 之前就被跳过，只计入 `excluded_count`，供打包者按需忽略那些测试用 fixtures、仅在特定条件下启用的程序库等实质上不影响 ABI 兼容性的 ELF 文件。

扫描来源可以是一棵普通目录树，也可以是一个归档文件（tar / zip / deb / 裸压缩流）。为了性能，对于归档文件，直接流式解压、遍历其成员，不落盘。非 ELF 成员会被计入 `file_count` 但不产生记录。

## 数据格式

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

入口是 `scan_source()`（产出 `ABIReport`），序列化用 `dump_abi_report_toml()`。
