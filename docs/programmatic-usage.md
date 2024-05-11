# 如何程序化地与 `ruyi` 交互

在一些场景下，如编辑器或 IDE 的 RuyiSDK 插件，这些外部程序需要与 `ruyi` 进行 non-trivial
的交互：不仅仅是以一定的命令行参数调用 `ruyi` 并判断其退出状态码，而需要处理一定的输出信息，甚至可能还涉及向
`ruyi` 输入大量信息。我们不希望这些外部程序解析 `ruyi` 面向人类的命令行输出格式，而希望暴露一个对机器友好的、尽量保证兼容的界面。

借鉴了 Git 一些命令所支持的 `--porcelain` 选项，我们为 `ruyi` 也定义了全局选项
`--porcelain`，用来启用这样的输出格式。并非所有的 `ruyi` 子命令都适配了 `--porcelain`
选项：对于那些暂未适配或没有适配意义的子命令，行为将保持不变。

注意：由于 `ruyi` 的 `--porcelain` 选项是全局的，它需要位于所有子命令之前，否则将会报错。

```sh
# Correct
ruyi --porcelain news list

# Wrong
# ruyi: error: unrecognized arguments: --porcelain
ruyi news list --porcelain
```

## `ruyi` 的 porcelain 输出模式

当处于 porcelain 输出模式时，如无特别说明，`ruyi` 的 stdout 与 stderr 输出格式将变为一行一个
JSON 对象。不保证此 JSON 序列化结果仅包含 ASCII 字符：目前序列化这些对象时，在 Python 一侧采用了
`ensure_ascii=False` 的配置。

所有的 porcelain 输出对象都有 `ty` 字段，用来指示此对象的类型。目前已定义的类型有以下几种：

```python
# ty: "log-v1"
class PorcelainLog(PorcelainEntity):
    t: int
    """Timestamp of the message line in microseconds"""

    lvl: str
    """Log level of the message line (one of D, F, I, W)"""

    msg: str
    """Message content"""


# ty: "newsitem-v1"
class PorcelainNewsItem(PorcelainEntity):
    id: str  # 文章的标识符，字符串
    ord: int  # 文章的序号
    is_read: bool  # 是否已读
    lang: str  # 语言代码，如 en / zh_CN
    display_title: str  # 文章标题
    content: str  # 完整的正文内容，目前保证为 Markdown 格式的字符串
```

当工作在 porcelain 输出模式时，`ruyi` 平时的 stderr 日志信息格式将变为类型为 `log-v1` 的输出对象。
每条消息都带时间戳、日志级别，消息正文末尾不会被自动附加 1 个换行（但如果某条日志的末尾碰巧有一个或一些换行，那么这些换行将不会被删除）。

## 已适配 porcelain 输出模式的命令

### `ruyi news list`

调用方式：

```sh
ruyi --porcelain news list
# 如同常规命令行用法，仅请求未读条目也是允许的
ruyi --porcelain news list --new
```

输出格式：

* stdout：一行一个 `newsitem-v1` 类型的对象
* stderr：无意义

请注意：单纯调用 `ruyi news list` 不会更新文章的已读状态。请另行进行
`ruyi news read -q item...` 的调用以标记用户实际阅读了的文章。
