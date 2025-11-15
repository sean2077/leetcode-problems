# LeetCode Problems Crawler

一个用于批量抓取 LeetCode 题目数据的 Python 爬虫工具。

## 功能特点

- 支持 LeetCode.com 和 LeetCode.cn 两个站点
- 自动重试机制，处理网络异常
- Rich 库美化输出，实时进度条显示
- 支持指定题目 ID 范围抓取
- 自动跳过已存在的题目文件
- 详细的统计信息展示

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
# 抓取 LeetCode.com 所有题目
python crawler.py

# 抓取 LeetCode.cn 所有题目
python crawler.py -c

# 指定输出目录
python crawler.py -o my-problems

# 更新已存在的题目
python crawler.py -u
```

### 指定范围抓取

```bash
# 只抓取题目 ID 1-100
python crawler.py --start 1 --end 100

# 从题目 500 开始抓取
python crawler.py --start 500
```

### 使用本地元数据文件

```bash
# 使用已保存的元数据文件，避免重复请求
python crawler.py -m metadata.json
```

## 命令行参数

| 参数              | 简写 | 说明                               | 默认值     |
| ----------------- | ---- | ---------------------------------- | ---------- |
| `--cn`            | `-c` | 使用 LeetCode.cn 而非 LeetCode.com | False      |
| `--output-dir`    | `-o` | 输出目录路径                       | `problems` |
| `--metadata-file` | `-m` | 元数据文件路径（可选）             | None       |
| `--update`        | `-u` | 更新已存在的题目文件               | False      |
| `--start`         |      | 起始题目 ID                        | None       |
| `--end`           |      | 结束题目 ID                        | None       |

## ⚠️ 重要说明

**本爬虫采用串行请求方式，不支持并发抓取。**

原因如下：
- LeetCode 有严格的请求频率限制
- 并发请求容易触发反爬虫机制，导致 IP 被封禁
- 串行请求配合自适应延迟策略，可以稳定长期运行
- 每次请求后会自动延迟 1-60 秒，确保请求频率合理

请勿修改代码实现并发，以免账号或 IP 被封禁。

## 输出格式

题目数据以 JSON 格式保存，文件命名规则：
```
{question_id}.{title_slug}.json
```

例如：`1.two-sum.json`

## 许可证

MIT License
