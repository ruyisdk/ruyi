# CI: 自动化版本发布

为方便、规范 RuyiSDK 的发版工作，有必要将这些工作自动化。目前，RuyiSDK
包管理器（`ruyi`，也即本仓库）已经接入了自动化发版机制。

## `ruyi` 的发版自动化

详见本仓库的 GitHub Actions workflow 定义。

### RuyiSDK 镜像源的同步

在 GHA 自动创建 Release 之后，为将此 release 同步进 RuyiSDK 镜像源，从而方便境内用户下载使用，需要额外做一些工作。

理想情况下，这可用一个监听 release 类型消息的 GitHub Webhook 实现，但这要求部署一个
HTTP 服务，从而造成很大的额外运维成本。因此，目前使用一种开销相对较高但仍可接受的方式：轮询，来实现与
GitHub Release 的同步。

首先准备一台既能访问 GitHub API、GitHub Release assets，又有权限访问 RuyiSDK
rsync 镜像源的 Linux 主机，用来部署 helper 服务。

在此主机上准备一个 `ruyi-backend` 的开发环境：

```sh
git clone https://github.com/ruyisdk/ruyi-backend.git
cd ruyi-backend
# 略过了初始化 Python virtualenv 的步骤
poetry install
```

准备一个目录，用于存储 rsync 同步状态与相关的 release assets：

```sh
# 假设以 /opt/ruyi-tmp-rsync 为状态目录
mkdir /opt/ruyi-tmp-rsync
```

配置系统，使此任务被周期性执行。您可参考 [ruyi-backend 项目随附的 systemd 单元定义][systemd-example-units]：

[systemd-example-units]: https://github.com/ruyisdk/ruyi-backend/tree/main/examples/systemd

```sh
# 把示例单元文件复制到 /etc/systemd/system/ 然后调整其内容以适应您的环境
systemctl daemon-reload
systemctl enable ruyi-ci-sync-release.timer
```

后续，应不时更新此 `ruyi-backend` checkout，并跟进依赖版本变更、此处的流程变更等等。
