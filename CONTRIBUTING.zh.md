# 为 RuyiSDK 做贡献

感谢您有兴趣为 RuyiSDK 做贡献！本文档提供了贡献指南，并解释了为本项目做贡献的要求。

阅读本文的其它语言版本：

* [English](./CONTRIBUTING.md)

## 行为准则

在为 RuyiSDK 做贡献时，请尊重并考虑他人。我们旨在为所有贡献者营造一个开放和友好的环境。

请您遵守[《RuyiSDK 社区行为准则》](https://ruyisdk.org/en/code_of_conduct)。

## 开发者原创声明（DCO）

我们要求 RuyiSDK 的所有贡献都包含[开发者原创声明（DCO）](https://developercertificate.org/)。DCO 是一种轻量级方式，使贡献者可以证明他们编写或有权提交所贡献的代码。

### 什么是 DCO？

DCO 是您通过签署（sign-off）提交的方式而作出的声明。其全文非常简短，转载如下：

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### 如何签署提交

您需要在每个提交的说明中添加一行 `Signed-off-by`，证明您同意 DCO：

```
Signed-off-by: 您的姓名 <your.email@example.com>
```

您可以通过在提交时使用 `-s` 或 `--signoff` 参数自动添加此行：

```
git commit -s -m "您的提交说明"
```

确保签名中的姓名和电子邮件与您的 Git 配置匹配。您可以使用以下命令设置您的 Git 姓名和电子邮件：

```
git config --global user.name "您的姓名"
git config --global user.email "your.email@example.com"
```

### CI 中的 DCO 验证

所有拉取请求（PR）都会在我们的持续集成 (CI) 流程中接受自动化 DCO 检查。此检查会验证您的拉取请求中的所有提交是否都有适当的 DCO 签名。如果任何提交缺少签名，CI 检查将失败，在解决问题之前，您的拉取请求将无法被合并。

## 拉取请求流程

1. 从 `main` 分支派生（fork）相应的仓库并创建您的分支。
2. 进行更改，确保它们遵循项目的编码风格和约定。
3. 必要时添加测试。
4. 确保您的提交已包含 DCO 签名。
5. 必要时更新文档。
6. 向主仓库提交拉取请求。

## 开发环境设置

有关设置开发环境的信息，请参阅[构建文档](./docs/building.md)。

## 报告问题

如果您发现错误或有功能请求，请在[工单系统](https://github.com/ruyisdk/ruyi/issues)中创建问题。

## 许可证

您同意您对 RuyiSDK 的贡献将遵循 [Apache 2.0 许可证](./LICENSE-Apache.txt)。
