#!python

import json
import random
import time
from pathlib import Path
from typing import Annotated, Optional

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn
from rich.table import Table

app = typer.Typer(add_completion=False)

EN_URL = "https://leetcode.com"
CN_URL = "https://leetcode.cn"

# 常量定义
DEFAULT_RETRY_DELAY = 60
RATE_LIMIT_DELAY = 60
SLOW_RESPONSE_DELAY = 5
NORMAL_DELAY = 1
MAX_RETRIES = 3

console = Console()


# 获取所有题目的元信息
def get_metadata(url: str, session: requests.Session) -> Optional[dict]:
    """获取所有题目的元信息"""
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        console.print(f"[red]Failed to get metadata: {e}[/red]")
        return None
    except json.JSONDecodeError as e:
        console.print(f"[red]Failed to parse metadata JSON: {e}[/red]")
        return None


# 延迟
def adaptive_delay(response: requests.Response) -> None:
    """根据响应状态自适应延迟"""
    if response.status_code == 429:  # Too Many Requests
        console.print("[yellow]Too Many Requests, waiting for 60 seconds...[/yellow]")
        time.sleep(RATE_LIMIT_DELAY + random.random())
    elif response.elapsed.total_seconds() > 2:
        time.sleep(SLOW_RESPONSE_DELAY + random.random())
    else:
        time.sleep(NORMAL_DELAY + random.random())


# 获取题目的详细信息
def get_problem_detail(
    titleSlug: str, url: str, session: requests.Session
) -> Optional[requests.Response]:
    query = """
    query questionData($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            questionId
            questionFrontendId
            boundTopicId
            title
            titleSlug
            content
            translatedTitle
            translatedContent
            isPaidOnly
            difficulty
            likes
            dislikes
            isLiked
            similarQuestions
            contributors {
                username
                profileUrl
                avatarUrl
            }
            langToValidPlayground
            topicTags {
                name
                slug
                translatedName
            }
            companyTagStats
            codeSnippets {
                lang
                langSlug
                code
            }
            stats
            hints
            status
            sampleTestCase
            metaData
            judgerAvailable
            judgeType
            mysqlSchemas
            enableRunCode
            enableTestMode
            envInfo
            libraryUrl
            note
        }
    }
    """
    variables = {"titleSlug": titleSlug}
    try:
        response = session.post(
            url, json={"query": query, "variables": variables}, timeout=30
        )
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {e}[/red]")
        return None


@app.command()
def main(
    cn: Annotated[
        bool, typer.Option("-c", help="Use leetcode.cn instead of leetcode.com")
    ] = False,
    output_dir: Annotated[Path, typer.Option("-o", help="Output directory")] = Path(
        "problems"
    ),
    metadata_file: Annotated[
        Optional[Path], typer.Option("-m", help="Metadata file")
    ] = None,
    update: Annotated[
        bool, typer.Option("-u", help="Update existing problems")
    ] = False,
    start: Annotated[
        Optional[int], typer.Option("--start", help="Start from question ID")
    ] = None,
    end: Annotated[
        Optional[int], typer.Option("--end", help="End at question ID")
    ] = None,
):
    """Crawl all problems from leetcode.com or leetcode.cn"""
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 配置URL
    if cn:
        metadata_url = f"{CN_URL}/api/problems/all/"
        graphql_url = f"{CN_URL}/graphql"
        site_name = "LeetCode CN"
    else:
        metadata_url = f"{EN_URL}/api/problems/all/"
        graphql_url = f"{EN_URL}/graphql"
        site_name = "LeetCode"

    console.print(
        Panel(f"[bold cyan]LeetCode Problem Crawler - {site_name}[/bold cyan]")
    )

    # 创建Session以复用连接
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    # 获取元数据
    if metadata_file:
        console.print(f"[cyan]Loading metadata from {metadata_file}...[/cyan]")
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            console.print(f"[red]Failed to load metadata file: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print("[cyan]Fetching metadata from API...[/cyan]")
        metadata = get_metadata(metadata_url, session)
        if metadata is None:
            raise typer.Exit(1)

    stat_status_pairs = metadata.get("stat_status_pairs", [])
    if not stat_status_pairs:
        console.print("[red]Failed to get problems.[/red]")
        raise typer.Exit(1)

    # 按 stat.question_id 排序
    stat_status_pairs.sort(key=lambda x: x["stat"]["question_id"])

    # 过滤范围
    if start is not None or end is not None:
        stat_status_pairs = [
            s
            for s in stat_status_pairs
            if (start is None or s["stat"]["question_id"] >= start)
            and (end is None or s["stat"]["question_id"] <= end)
        ]

    # 统计信息
    stats = {"total": len(stat_status_pairs), "success": 0, "skipped": 0, "failed": 0}

    # 进度条
    with Progress(
        SpinnerColumn(), *Progress.get_default_columns(), console=console
    ) as progress:
        task = progress.add_task("[cyan]Crawling problems...", total=stats["total"])

        for stat in stat_status_pairs:
            question = stat["stat"]
            question_id = question["question_id"]
            title_slug = question["question__title_slug"]
            title = question["question__title"]

            # 如果文件已存在，则跳过
            outfile = output_dir / f"{question_id}.{title_slug}.json"
            if outfile.exists() and not update:
                progress.update(
                    task,
                    description=f"[yellow]Skipping {question_id}. {title}[/yellow]",
                )
                stats["skipped"] += 1
                progress.advance(task)
                continue

            progress.update(
                task, description=f"[cyan]Fetching {question_id}. {title}[/cyan]"
            )

            # 重试机制
            retry_count = 0
            success = False

            while retry_count < MAX_RETRIES:
                resp = get_problem_detail(title_slug, graphql_url, session)

                if resp is None:
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        console.print(
                            f"[yellow]Retry {retry_count}/{MAX_RETRIES} for {title}...[/yellow]"
                        )
                        time.sleep(DEFAULT_RETRY_DELAY)
                    continue

                # 检查响应状态
                if resp.status_code != 200:
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        console.print(
                            f"[yellow]Status {resp.status_code}, retry {retry_count}/{MAX_RETRIES}...[/yellow]"
                        )
                        adaptive_delay(resp)
                    continue

                # 解析JSON
                try:
                    detail = resp.json()
                    # 验证响应数据
                    if (
                        "data" not in detail
                        or detail.get("data", {}).get("question") is None
                    ):
                        console.print(
                            f"[yellow]Invalid response data for {title}[/yellow]"
                        )
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            time.sleep(DEFAULT_RETRY_DELAY)
                        continue
                except json.JSONDecodeError as e:
                    console.print(f"[red]JSON decode error for {title}: {e}[/red]")
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        time.sleep(DEFAULT_RETRY_DELAY)
                    continue

                # 保存文件
                try:
                    with open(outfile, "w", encoding="utf-8") as f:
                        json.dump(detail, f, ensure_ascii=False, indent=4)
                    stats["success"] += 1
                    success = True
                    adaptive_delay(resp)
                    break
                except IOError as e:
                    console.print(f"[red]Failed to write file {outfile}: {e}[/red]")
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        time.sleep(DEFAULT_RETRY_DELAY)

            if not success:
                console.print(
                    f"[red]Failed to fetch {question_id}. {title} after {MAX_RETRIES} retries[/red]"
                )
                stats["failed"] += 1

            progress.advance(task)

    # 显示统计表格
    table = Table(title="\n[bold]Crawling Statistics[/bold]")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta", justify="right")

    table.add_row("Total", str(stats["total"]))
    table.add_row("Success", f"[green]{stats['success']}[/green]")
    table.add_row("Skipped", f"[yellow]{stats['skipped']}[/yellow]")
    table.add_row("Failed", f"[red]{stats['failed']}[/red]")

    console.print(table)

    if stats["failed"] > 0:
        console.print(
            "\n[yellow]Some problems failed to download. You can re-run with -u flag to retry.[/yellow]"
        )

    session.close()


if __name__ == "__main__":
    app()
