# `ruyi` 的构建方式

为了[让构建产物可复现](https://reproducible-builds.org/)，`ruyi` 默认使用基于
Docker 的构建方式。但考虑到调试、复杂的发行版打包场景、为非官方支持架构打包等等因素，`ruyi`
的构建系统也支持以环境变量的形式被调用。

## 官方支持架构列表

目前 RuyiSDK 官方支持的架构有：

|`dist.sh` 架构名|`uname -m` 输出|
|----------------|---------------|
|`amd64`|`x86_64`|
|`arm64`|`aarch64`|
|`riscv64`|`riscv64`|

在这些架构上，目前 RuyiSDK 官方支持的操作系统是 Linux。

如果一个架构与操作系统的组合没有出现在这里，其实也有很大可能 `ruyi` 能够在其上正常工作。事实上，只要
`ruyi` 涉及的少数原生扩展库能够在该系统上被构建、工作，那么 `ruyi` 就可以工作。目前这些库有：

* [`pygit2`](https://pypi.org/project/pygit2/)：涉及 `openssl`、`libssh2`、`libgit2`、`cffi`
* [`xingque`](https://pypi.org/project/xingque/)：主要涉及 `pyo3`、`maturin`、`nix`

请注意：因为 RuyiSDK 官方软件源中的软件包目前主要以二进制方式分发，且
RuyiSDK 团队只会为官方支持的架构、操作系统提供二进制包，所以尽管您可以为非官方支持的架构或操作系统构建出
`ruyi`，但这样构建出的 `ruyi` 用途可能十分有限。如果您仍然准备这样做，您需要有**自行维护一套“平行宇宙”软件源**的预期。

## Linux 环境下基于 Docker 的构建

如果不需要什么特殊定制，`ruyi` 的构建方法十分简单。因为会使用预制的构建容器镜像的缘故，在宿主方面需要做的准备工作很少。您只需要确保：

* bash 版本大于等于 4.0，
* `docker` 可用，
* GitHub 容器镜像源 `ghcr.io` 可访问，

便可在 `ruyi` 仓库根目录下执行：

```sh
# 为当前（宿主）架构构建 ruyi
# 仅保证在官方支持架构上正常工作
./scripts/dist.sh

# 也可以明确指定目标架构
# 受限于 Nuitka 工作原理，必须使用目标架构的 Python 执行构建。
# 因此如果您需要交叉构建，则需要首先自行配置 QEMU linux-user binfmt_misc
./scripts/dist.sh riscv64
```

许多发行版的 QEMU linux-user 模拟器包都会自带 binfmt\_misc 配置，例如在
systemd 系统上，往 `/etc/binfmt.d` 安装相应的配置文件。由于模拟器的执行环境在
Docker 容器内，因此需要使用静态链接的 QEMU linux-user 模拟器，并且您需要确保
binfmt\_misc 配置中使用了 `F` (freeze) flag 以保证从未经修改的目标架构 sysroot 中也能访问到模拟器程序。

## Linux 环境下非基于 Docker 的构建

对于没有条件运行 Docker，或者官方未提供适用的构建容器镜像等等场合，您只能选择非基于
Docker 的构建方式。您需要自行准备环境：

* Python 版本：详见 `pyproject.toml`。目前官方使用的 Python 版本为 3.12.x。
* 需要在 `PATH` 中有以下软件可用：
    * 所有情况下
        * `poetry`
    * 需要现场编译原生扩展的情况下
        * `auditwheel`
        * `cibuildwheel`
        * `maturin`

如果您的架构、操作系统不在官方支持的列表，那么 `scripts/dist.sh` 将发出警告并自动切换为非
Docker 的构建。不过，如果您的环境实际上支持 `docker` 并且您仿照 `scripts/dist-image`
中的官方构建容器镜像描述自行打包了您环境的构建容器镜像，您也可以强制使用 Docker 构建：

```sh
export RUYI_DIST_FORCE_IMAGE_TAG=your-account/your-builder-image:tag

# 如果您的架构的 Docker 架构名（几乎总是等价于 GOARCH）与 dist.sh 或曰 Debian
# 架构名不同，则设置 RUYI_DIST_GOARCH
# 此处假设您的架构在 `uname -m` 叫 foo64el，在 Debian 叫 foo64，在 Go 叫 foo64le
export RUYI_DIST_GOARCH=foo64le

./scripts/dist.sh foo64
```

可以设置以下的环境变量来覆盖它们各自的默认取值。以下约定：

* 以 `$REPO_ROOT` 表示 `ruyi` 仓库的 checkout 路径，
* 以 `$ARCH` 表示 `scripts/dist.sh` 接受的参数，即 Debian 式的目标架构名。

|变量名|含义|默认取值|
|------|----|--------|
|`CCACHE_DIR`|ccache 缓存|`$REPO_ROOT/tmp/ccache.$ARCH`|
|`MAKEFLAGS`|`make` 默认参数|`-j$(nproc)`|
|`POETRY_CACHE_DIR`|Poetry 缓存|`$REPO_ROOT/tmp/poetry-cache.$ARCH`|
|`RUYI_DIST_BUILD_DIR`|`ruyi` 构建临时目录|`$REPO_ROOT/tmp/build.$ARCH`|
|`RUYI_DIST_CACHE_DIR`|`ruyi` 构建系统缓存|`$REPO_ROOT/tmp/ruyi-dist-cache.$ARCH`|

请自行翻阅源码以了解更详细的行为。如果此文档没有收到及时更新，也应以源码行为为准。

## Windows 环境下的构建

除了使用 PowerShell 以及 Windows 各种惯例之外，Windows 下构建 `ruyi` 的方式与
Linux 环境下的非基于 Docker 的构建很相似。请参考 GitHub Actions 中的相应定义。
