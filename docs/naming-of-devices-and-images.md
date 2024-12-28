# 设备、系统镜像的命名约定

为便于自动化集成、管理 RuyiSDK 所支持的设备型号与系统镜像，也便于用户、开发者理解、接受，有必要为设备与系统镜像在
RuyiSDK 体系内的命名作出一些约定。

以下是目前在用的约定，随着事情发展，可能会有调整。

## 设备型号 ID

设备型号 ID (device ID) 应当符合 `$vendor-$model` 的形式，其中 `$vendor` 是供应商 ID，`$model` 是型号 ID。

例：

* `sipeed-lcon4a`: Sipeed Lichee Console 4A
* `sipeed-tangmega138kpro`: Sipeed Tang Mega 138K Pro
* `starfive-visionfive`: StarFive VisionFive
* `wch-ch32v203-evb`: WCH CH32V203 EVB

### 供应商 ID

供应商 ID 一般取相应供应商的英文商标名的全小写形式；如果供应商全名显得太长，也可取其知名缩写的全小写形式。

已知（已在使用）的供应商 ID 如下：

| 供应商 ID | 供应商名称 |
|-----------|------------|
| `awol` | Allwinner |
| `canaan` | Canaan |
| `milkv` | Milk-V
| `pine64` | Pine64 |
| `sifive` | SiFive |
| `sipeed` | Sipeed |
| `starfive` | StarFive |
| `wch` | WinChipHead |

如后续有增加适配其他未在列表中的供应商，请同步更新此文档。

### 型号 ID

型号 ID 的具体形式目前没有特别的约定，但一般遵循以下规则：

* 如在厂商文档、示例代码、SDK 等公开资料存在较为一致的 codename 称呼，则使用 codename 的全小写形式。例如：
    * Duo S = `duos`
    * Kendryte K230 = `k230`
    * LicheePi 4A = `lpi4a`
    * Meles = `meles`
    * Pioneer Box = `pioneer`
* 如相应厂商没有对某型板卡使用完善、一致的 codename，但在自然语言中，该板卡一般被称作“芯片型号 (chip model) + 产品形态 (form factor)”的形式，则使用 `$chip_model-$form_factor` 的全小写形式。例如：
    * CH32V203 EVB = `ch32v203-evb`
* 如果上述两条都不能很好满足，则使用产品市场名称的全小写形式。例如：
    * Tang Mega 138K Pro = `tangmega138kpro`

## 型号变体 ID

有些不同的板卡 SKU 型号之间存在相当的相似度，一般是源自某些产品属性维度的排列组合。在
RuyiSDK 设备安装器中，我们不在“设备”一级区分这些 SKU，而是将相关联的 SKU 全部视作某个型号的“变体” (variant)，以便降低用户的信息处理负担。

有些时候，虽然某个型号有多种变体，但从软件视角看来它们完全兼容，此时出于维护成本考虑，也可以不单独定义变体。但对于软件上不能做到完全兼容的多种变体，为了成功支持它们，就必须定义清楚。

由于 SKU 的制定方式众多，我们对于变体 ID 的具体写法除了应为全小写形式之外，不作明确的风格要求，但一般以简短为好。自动化处理相关数据的组件可能需要支持一定程度的模板字符串渲染等功能。

例如：

* `sipeed-lpi4a` 有 8G RAM 与 16G RAM 两种配置，部分软件不能通用，必须区分。设置两种变体：
    * `8g`: `Sipeed LicheePi 4A (8G RAM)`
    * `16g`: `Sipeed LicheePi 4A (16G RAM)`
* `wch-ch32v203-evb` 有 11 种配置，对应 CH32V203 的 11 种各项指标各异的 SKU。设置 11 种变体：
    * `c6t6`: `WCH CH32V203 EVB (CH32V203C6T6)`
    * `c8t6`: `WCH CH32V203 EVB (CH32V203C8T6)`
    * `c8u6`: `WCH CH32V203 EVB (CH32V203C8U6)`
    * `f6p6`: `WCH CH32V203 EVB (CH32V203F6P6)`
    * etc.
* 多数型号没有明确的变体，对此均设置单一 `generic` 变体，称呼为 `generic variant`。以 `sipeed-maix1` 为例：
    * `generic`: `Sipeed Maix-I (generic variant)`

## 系统镜像包名

应为 `board-image/$os-$device_id` 或 `board-image/$os-$device_id-$variant` (当 variant 不为 `generic` 且区分 variant 很重要时) 的形式。

例如：

* `board-image/revyos-milkv-meles`: 虽然 `milkv-meles` 有 `4g` 与 `8g` 两种变体，但 RevyOS 对此无感，故不在命名上体现变体。
* `board-image/uboot-revyos-milkv-meles-4g`: 由于 U-Boot 对板载 RAM 容量敏感，故需要在名称上区分不同变体。
