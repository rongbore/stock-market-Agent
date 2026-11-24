# 离线校验研究 ZIP

对批量离线研究、显式行情采集或快捷研究产生的 ZIP，运行：

```bash
python -m scripts.verify_research_package --input research.zip
```

命令只读输入，不联网、不解压、不写文件、不执行 HTML。标准输出为单个 JSON 对象，含中文 `message`、固定机器原因码 `reason`、`integrity_verified`、已检查文件数和字节数。完整性通过返回退出码 0；损坏、无效或超过限额返回 2。参数用法错误由 argparse 返回 2。

Python 调用方式：

```python
from scripts.verify_research_package import verify_research_package
result = verify_research_package("research.zip")
```

校验要求 `manifest.json` 为当前版本三种导出器之一的严格结构，拒绝重复 JSON 键和重复清单路径；包内除清单外的文件集合、逐文件长度和 SHA-256 必须完全匹配。拒绝重复 ZIP 成员、目录、绝对路径、`..` 路径、反斜杠、特殊文件、符号链接、加密和非 stored/deflate 压缩。

| 限额 | 默认值 |
| --- | --- |
| ZIP 文件字节数 | 100 MiB |
| 成员数量（含清单） | 128 |
| 中央目录元数据 | 256 KiB |
| 单个解压后成员 | 16 MiB |
| 全部解压后成员合计（含清单） | 64 MiB |
| 清单字节数 | 256 KiB |

在 `ZipFile` 创建成员元数据对象之前预检标准 EOCD 和中央目录体积；不支持 ZIP64、多磁盘 ZIP 或附加尾部数据。实际成员数据分块读取并再次限制体积，不为校验解压到磁盘。

成功状态 `INTEGRITY_VERIFIED_UNVERIFIED_SOURCE` 只说明文件与包内清单字节一致。清单本身没有外部签名，修改文件并同步重写清单仍可通过。程序不会认证来源、金融内容、交易所日历、历史可用性或来源独立性，返回的所有来源核验标记始终为 `false`；包内自行声称的 `verified` 标签不会提升校验结论。未生成研究页面的诊断包也可通过完整性校验，通过不表示研究成功。
