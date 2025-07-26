#!python

import json
import random
import time
from pathlib import Path

import requests
import typer

EN_URL = "https://leetcode.com"
CN_URL = "https://leetcode.cn"


# 获取所有题目的元信息
def get_metadata(url=f"{EN_URL}/api/problems/all/") -> dict:
    response = requests.get(url)
    return response.json()


# 延迟
def adaptive_delay(response: requests.Response):
    if response.status_code == 429:  # Too Many Requests
        typer.echo("Too Many Requests, waiting for 60 seconds...")
        time.sleep(60 + random.random())  # 遇到限制时等待更长时间
    elif response.elapsed.total_seconds() > 2:
        typer.echo("Waiting for 5 seconds...")
        time.sleep(5 + random.random())  # 如果响应时间较长，增加等待时间
    else:
        typer.echo("Waiting for 1 second...")
        time.sleep(1 + random.random())  # 正常情况下的基本延迟


# 获取题目的详细信息
def get_problem_detail(titleSlug, url=f"{EN_URL}/graphql_url") -> requests.Response:
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
    response = requests.post(url, json={"query": query, "variables": variables})
    return response


app = typer.Typer(add_completion=False)


@app.command()
def main(
    cn: bool = typer.Option(False, "-c", help="Use leetcode.cn instead of leetcode.com"),
    output_dir: Path = typer.Option("problems", "-o", help="Output directory"),
    metadata_file: Path = typer.Option(None, "-m", help="Metadata file"),
    update: bool = typer.Option(False, "-u", help="Update existing problems"),
):
    """Crawl all problems from leetcode.com or leetcode.cn"""
    if cn:
        metadata_url = f"{CN_URL}/api/problems/all/"  # https://leetcode.cn/api/problems/all/
        graphql_url = f"{CN_URL}/graphql"
    else:
        metadata_url = f"{EN_URL}/api/problems/all/"
        graphql_url = f"{EN_URL}/graphql"

    if metadata_file:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        metadata = get_metadata(metadata_url)
    stat_status_pairs = metadata.get("stat_status_pairs", [])
    if not stat_status_pairs:
        typer.echo("Failed to get problems.")
        raise typer.Exit()
    # 按 stat.question_id 排序
    stat_status_pairs.sort(key=lambda x: x["stat"]["question_id"])

    for stat in stat_status_pairs:
        question = stat["stat"]
        question_id = question["question_id"]
        title_slug = question["question__title_slug"]

        # 如果文件已存在，则跳过
        outfile = output_dir / f"{question_id}.{title_slug}.json"
        if outfile.exists() and not update:
            typer.echo(f"Skipping {outfile}...")
            continue

        title = question["question__title"]
        typer.echo(f"Fetching {question_id}. {title}...")
        while True:
            try:
                resp = get_problem_detail(title_slug, graphql_url)
                break
            except Exception as e:
                typer.echo(f"Failed to fetch {title}: {e}")
                typer.echo("Waiting for 60 seconds...")
                time.sleep(60)
                continue
        detail = resp.json()
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=4)
        adaptive_delay(resp)


if __name__ == "__main__":
    app()
