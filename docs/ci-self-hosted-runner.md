# Repo CI: Self-hosted runner 管理

目前 GitHub Actions 官方提供的 runners 仅支持 amd64 架构，且官方的 self-hosted runner 支持仅覆盖
amd64 与 arm64 架构。鉴于 `ruyi` 需要支持 amd64、arm64 与 riscv64 三种架构，并且
Nuitka [架构上无法支持交叉编译](https://github.com/Nuitka/Nuitka/issues/43)而
QEMU 模拟下的 Nuitka 又很慢（半小时左右），因此总之我们都需要自行维护一些
runners 以使 CI 运行速度不至于过分缓慢。

## riscv64 runner

GitHub Actions Runner 官方暂未提供 riscv64 架构支持，所幸社区已有勇士将流程走通。
我们使用的是 [dkurt/github_actions_riscv](https://github.com/dkurt/github_actions_riscv)
项目提供的成品包。

有一些地方需要注意：

* v2.312.0 中的 `externals/node16` 未替换为 riscv64 二进制，这会导致 `actions/cache@v4`
  等 action 运行失败。需要手动编译替换。
* 如果宿主系统是 Debian 系的发行版：Runner 依赖 `docker` 但发行版未打包。
  需要安装 `podman` 并做些特殊处理。

### 替换 Node.js 16.x

v2.312.0 中的 `node16` 是 16.20.2 这个当下最新的 LTS 版本。应该不用非得是这个版本。

去 https://nodejs.org/download/release/latest-v16.x/ 下载源码，解压，然后构建 tarball：

```sh
# 以 v16.20.2 为例

tar xf node-v16.20.2.tar.xz
cd node-16.20.2

# 如果准备启用 LTO，可能需要调整 LTO 并发数，否则默认的 4 喂不饱一些核数多的硬件
# vim common.gypi
# 寻找 flto=4 的字样并调整之

# 自行调整并发
# 该版本 node 自带的 openssl 无法以默认参数通过编译（系统会被探测为 x86_64），
# 因此需要在系统级别安装 libssl-dev 并动态链接之
# 为了提高构建速度，使用 Ninja (apt-get install ninja-build)
make binary -j64 CONFIG_FLAGS='--enable-lto --ninja --shared-openssl'
```

然后替换 GHA runner 的 `externals/node16`：

```sh
cd /path/to/gha/externals
rm -rf node16
tar xf /path/to/your/node-v16.20.2-linux-riscv64.tar.xz
mv node-v16.20.2-linux-riscv64 node16
```

### 配置 podman

本库使用基于容器的 CI 配置，因此需要在 runner 宿主上准备好容器运行时。由于目前
Debian riscv64 port 没有打包 `docker`，我们换用 `podman`。但 GitHub Actions runner
官方[暂未支持 `podman`](https://github.com/actions/runner/issues/505)，因此也需要一些特殊处理。

为了避免不必要的麻烦，最好在 GHA 以自己的用户身份第一次发起 `podman` 调用之前执行。

```sh
cd /usr/local/bin
sudo ln -s /usr/bin/podman docker

cd /var/run
sudo ln -s podman/podman.sock docker.sock

# 本例中 GHA runner 以 gha 用户身份执行，系统上已分配了 100000-231071 的 subuid/subgid 范围
# 请自行调整
sudo usermod --add-subuids 231072-296607 --add-subgids 231072-296607 gha
```

阅读材料：

* 关于 `cannot re-exec process` 相关错误
    - https://github.com/containers/podman/issues/9137
    - https://github.com/containers/podman/issues/14635
* [Podman rootless mode tutorial](https://github.com/containers/podman/blob/v4.9/docs/tutorials/rootless_tutorial.md)
