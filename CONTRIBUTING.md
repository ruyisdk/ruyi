# Contributing to RuyiSDK

Thank you for your interest in contributing to RuyiSDK! This document provides guidelines and explains the requirements for contributions to this project.

Read in other languages:

* [中文](./CONTRIBUTING.zh.md)

## Code of Conduct

Please be respectful and considerate of others when contributing to RuyiSDK. We aim to foster an open and welcoming environment for all contributors.

Please follow [the RuyiSDK Code of Conduct](https://ruyisdk.org/en/code_of_conduct).

## Developer's Certificate of Origin (DCO)

We require that all contributions to RuyiSDK are covered under the [Developer's Certificate of Origin (DCO)](https://developercertificate.org/). The DCO is a lightweight way for contributors to certify that they wrote or otherwise have the right to submit the code they are contributing.

### What is the DCO?

The DCO is a declaration that you make when you sign-off a commit, simple
enough that the original text is fully reproduced below.

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

### How to Sign-Off Commits

You need to add a `Signed-off-by` line to each commit message, which certifies that you agree with the DCO:

```
Signed-off-by: Your Name <your.email@example.com>
```

You can add this automatically by using the `-s` or `--signoff` flag when committing:

```
git commit -s -m "Your commit message"
```

Make sure that the name and email in the signature matches your Git configuration. You can set your Git name and email with:

```
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### DCO enforcement in CI

All pull requests go through an automated DCO check in our continuous integration (CI) pipeline. This check verifies that all commits in your pull request have a proper DCO sign-off. If any commits are missing the sign-off, the CI check will fail, and your pull request cannot be merged until the issue is fixed.

## Pull Request Process

1. Fork the repository and create your branch from `main`.
2. Make your changes, ensuring they follow the project's coding style and conventions.
3. Add tests if applicable.
4. Ensure your commits are signed-off with the DCO.
5. Update documentation if necessary.
6. Submit a pull request to the main repository.

## Development Setup

Please refer to the [building documentation](./docs/building.md) for information on setting up your development environment.

## Reporting Issues

If you find a bug or have a feature request, please create an issue in [the issue tracker](https://github.com/ruyisdk/ruyi/issues).

## License

By contributing to RuyiSDK, you agree that your contributions will be licensed under the [Apache 2.0 License](./LICENSE-Apache.txt).
