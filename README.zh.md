<div align="center">
<img alt="RuyiSDK Logo" src="resources/ruyi-logo-256.png" height="128" />
<h3>Ruyi</h3>
<p><a href="https://github.com/ruyisdk">RuyiSDK</a> 的包管理器。</p>
</div>

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ruyisdk/ruyi/ci.yml)
![GitHub License](https://img.shields.io/github/license/ruyisdk/ruyi)
![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![GitHub Tag](https://img.shields.io/github/v/tag/ruyisdk/ruyi?label=latest%20tag)
![PyPI - Version](https://img.shields.io/pypi/v/ruyi)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/ruyisdk/ruyi/total?label=all%20github%20dl)
![PyPI - Downloads](https://img.shields.io/pypi/dm/ruyi?label=pypi%20dl)

[English](./README.md) | 简体中文

## 安装

`ruyi` 以两种形式分发：PyPI 软件包、单二进制文件。通过 PyPI 安装时，`ruyi` 的各项操作通常性能更好；而单文件形式更容易上手，因为无需事先配置 Python 环境。无论您使用哪种方式安装，`ruyi` 支持的功能都应当一致。

### 推荐：通过 PyPI 安装

我们推荐在您的机器上如此安装 `ruyi`。在任意 Python 虚拟环境中，执行：

```sh
pip install ruyi
```

如果您使用其他 Python 包管理器，您也可以执行等效的相应命令。安装完成后，`ruyi` 命令会出现在该虚拟环境的 `bin` 目录中；如果已经激活了该环境，您现在就可以开始使用 `ruyi` 了。

### 备选：使用单二进制文件发行版

您可以从 [GitHub Releases][ghr] 或 [RuyiSDK 镜像站][mirror-iscas] 获取 `ruyi` 的预构建二进制，以便您试用。将下载的文件重命名为 `ruyi`，赋予其可执行权限，最后放到你的 `$PATH` 中，即可使用了。

[ghr]: https://github.com/ruyisdk/ruyi/releases
[mirror-iscas]: https://mirror.iscas.ac.cn/ruyisdk/ruyi/tags/

### 平台兼容性说明

由于 `ruyi` 是以平台无关的 Python 编写，您通常可以在任何拥有 Python 包管理器的系统上安装它。然而，若您的系统不在 [RuyiSDK 平台支持文档][ruyisdk-plat-support-zh]（[English][ruyisdk-plat-support-en]）之列，则您可能无法从官方 RuyiSDK 软件源安装二进制软件包：因为这些软件包仅为官方支持的系统构建。这种情况下，您也许能够从 [RuyiSDK 开发者社区][ruyisdk-community]获取由社区提供的支持。

[ruyisdk-plat-support-en]: https://ruyisdk.org/en/docs/Other/platform-support/
[ruyisdk-plat-support-zh]: https://ruyisdk.org/docs/Other/platform-support/
[ruyisdk-community]: https://ruyisdk.cn/

## 使用

您可以在 [RuyiSDK 文档站][docs]查阅文档（目前仅提供中文版）。如需帮助，欢迎在[我们的社区论坛][ruyisdk-community]搜索或发贴。

[docs]: https://ruyisdk.org/docs/intro

## 配置

`ruyi` 的各项行为可以通过配置文件或环境变量进行配置。

### 配置搜索路径

`ruyi` 会尊重 `$XDG_CONFIG_HOME` 与 `$XDG_CONFIG_DIRS`，并据此搜索配置文件。如果您未显式设置这些环境变量（这是通常情况），默认的配置目录通常为 `~/.config/ruyi`。

### 配置文件

目前 `ruyi` 会在其 XDG 配置目录中搜索一个可选的 `config.toml`。若该文件存在，其内容应该类似如下所示，如果一个值没有被指定那么此处展示的是它将取到的默认值：

```toml
[packages]
# 在匹配仓库中的软件包版本时，是否考虑预发行版本。
prereleases = false

[repo]
# 本地 RuyiSDK 元数据仓库路径。必须为绝对路径，否则该设置会被忽略。
# 若未设置或为空，则使用 $XDG_CACHE_HOME/ruyi/packages-index。
local = ""
# RuyiSDK 元数据仓库的远端地址。
# 若未设置或为空，则使用下述默认值。
remote = "https://github.com/ruyisdk/packages-index.git"
# 要使用的分支名。
# 若未设置或为空，则使用下述默认值。
branch = "main"

[telemetry]
# 是否收集遥测信息以改进 RuyiSDK 的开发者体验，以及是否周期性地将数据发送给 RuyiSDK 团队。
# 可选值为 `local`、`off` 与 `on`——详见文档。
#
# 若未设置或为空，则使用下述默认值：收集数据并每周上传，上传日根据安装的匿名 ID 随机确定。
mode = "on"
# 用户同意上传遥测数据的时刻。如果系统时刻晚于这里给出的时刻，则每次执行 `ruyi` 时将不再展示同意横幅。
# 若未来 RuyiSDK 更新了遥测政策，此处记录的确切时刻也有助于处理相关事项。
#
# 如需隐藏同意横幅，请将其设为当前本地时刻，例如：
#
#     upload_consent = 2024-12-02T15:61:00+08:00
#
# 此处提供的时间戳格式无效，这是有意而为：如您需要手工修改，请注意。
upload_consent = ""
# 覆盖 RuyiSDK 包管理器作用域的遥测服务器 URL。
# 若未设置，则使用仓库配置的默认值；若设为空，则禁用遥测上传。
#pm_telemetry_url = ""
```

### 环境变量

目前 `ruyi` 支持以下环境变量：

* `RUYI_TELEMETRY_OPTOUT` —— 布尔值，是否选择退出遥测。
* `RUYI_VENV` —— 字符串，显式指定要使用的 Ruyi 虚拟环境。

对于布尔值，`1`、`true`、`x`、`y` 或 `yes`（不区分大小写）均视为“真”。

### 遥测

Ruyi 包管理器会收集使用数据，以帮助我们改进您的使用体验。数据由 RuyiSDK 团队收集，并与社区共享。您可以通过在常用的 Shell 中将环境变量 `RUYI_TELEMETRY_OPTOUT` 设为 `1`、`true`、`x`、`y` 或 `yes` 中的任意一个，来选择退出遥测。退出遥测等效于下述的 `off` 模式。

共有 3 种遥测模式：

* `local`：收集数据，但不会在用户未主动操作的情况下上传。
* `off`：既不收集也不上传数据。
* `on`：收集数据并周期性上传。

默认启用的模式是 `on`，这意味着每次执行 `ruyi` 都会在本地记录一些非敏感信息以及 `ruyi` 的若干状态，并且收集的数据会在每周的某一日上传至服务器，该服务器位于中华人民共和国境内，由 RuyiSDK 团队管理。上传日是星期几仅由当前实例的匿名 ID 决定。

你可以通过编辑 `ruyi` 的配置文件来更改遥测模式，或简单地将 `RUYI_TELEMETRY_OPTOUT` 环境变量设置为任一视同为真的取值来禁用遥测。

我们通过 `ruyi` 收集以下信息：

* 运行设备的基础信息：
    * 架构与操作系统
    * 若架构为 RISC-V：
        * ISA 能力
        * 开发板型号名称
        * 逻辑 CPU 数量
    * 操作系统发行版 ID（大致等同于发行版类型）
    * libc 的类型与版本
    * Shell 类型（bash、fish、zsh 等）
* 数据上传时的 `ruyi` 版本
* 各类 `ruyi` 子命令的调用模式：
    * 不暴露任何参数
    * 调用时间以 1 分钟为粒度记录

你可以在 RuyiSDK 网站上查看我们的隐私政策。

## 贡献

欢迎您为 Ruyi 做贡献！请参阅我们的[贡献指南](./CONTRIBUTING.zh.md)（[English](./CONTRIBUTING.md)）以了解如何开始。

## 许可

版权所有 © 中国科学院软件研究所（ISCAS）。保留所有权利。

`ruyi` 采用 [Apache 2.0 许可证](./LICENSE-Apache.txt) 授权。

`ruyi` 的单文件二进制发行版含有依据 [Mozilla Public License 2.0](https://mozilla.org/MPL/2.0/) 授权的代码。您可以从相应项目的官方网站获取其源代码：

* [`certifi`](https://github.com/certifi/python-certifi)：未作修改

本项目所涉商标均归其各自所有者所有。
