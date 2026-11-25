"""법령 색인 만들기.

    python -m openbook.law build              # data/law/targets.yaml의 법령을 받아 색인 저장
    python -m openbook.law build --no-embed   # 임베딩 없이 (글자 겹침 검색만)
    python -m openbook.law search "질문"       # 색인에서 찾아보기
    python -m openbook.law eval               # data/law/eval.yaml로 검색 정확도 재기

필요한 값: LAW_OC (법제처 Open API), UPSTAGE_API_KEY (임베딩). 값은 출력하지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from openbook.law.embed import UpstageEmbedder
from openbook.law.evaluate import evaluate, unknown_labels
from openbook.law.index import DEFAULT_INDEX, LawIndex
from openbook.law.lawgo import LawApiClient
from openbook.law.models import LawArticle

DEFAULT_TARGETS = DEFAULT_INDEX.parent / "targets.yaml"
DEFAULT_EVAL = DEFAULT_INDEX.parent / "eval.yaml"


def select_articles(articles: list[LawArticle], keep: list[str] | None) -> list[LawArticle]:
    """targets.yaml에 articles가 있으면 그 조문만 (예: 소득세법은 원천징수 조문만). 없으면 전부."""
    if not keep:
        return articles
    got = [a for a in articles if a.article_no in keep]
    missing = set(keep) - {a.article_no for a in got}
    if missing:
        raise SystemExit(f"targets.yaml의 조문을 찾지 못함: {sorted(missing)}")
    return got


def build(targets: Path, out: Path, embed: bool) -> int:
    laws = yaml.safe_load(targets.read_text(encoding="utf-8"))["laws"]
    client = LawApiClient.from_env()
    articles = []
    for law in laws:
        got = select_articles(client.articles(law["name"]), law.get("articles"))
        print(f"{law['name']}: 조문 {len(got)}개")
        articles.extend(got)
    vectors = None
    if embed:
        texts = [f"{a.law_name} {a.article_no} {a.title or ''}\n{a.text}" for a in articles]
        vectors = UpstageEmbedder.from_env().embed_passages(texts)
    LawIndex(articles, vectors).save(out)
    print(f"저장: {out} (조문 {len(articles)}개, 임베딩 {'있음' if vectors else '없음'})")
    return 0


def search(question: str, path: Path) -> int:
    index = LawIndex.load(path)
    embedder = UpstageEmbedder.from_env() if index.vectors else None
    for a in index.search(question, embedder):
        print(f"- {a.law_name} {a.article_no} {a.title or ''} (시행 {a.effective_date})")
    return 0


def run_eval(cases_path: Path, path: Path, embed: bool) -> int:
    index = LawIndex.load(path)
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))["questions"]
    missing = unknown_labels(index, cases)
    if missing:
        print("색인에 없는 정답 조문 (평가 파일 확인):", ", ".join(missing))
        return 1
    embedder = UpstageEmbedder.from_env() if embed and index.vectors else None
    report = evaluate(index, cases, embedder)
    for r in report.rows:
        mark = "O" if r.ok else "X"
        print(f"{mark} {r.question}")
        print(f"    정답 {list(r.expect) or '(붙이지 않음)'}")
        print(f"    결과 {list(r.got)}")
    answerable = sum(1 for r in report.rows if r.expect)
    print()
    print(
        f"정답 있는 질문 {answerable}개 중 상위 3개 안에 정답: {report.hit_rate:.0%}"
        f" · 법령 밖 질문 {len(report.rows) - answerable}개 중 붙이지 않음: {report.abstain_rate:.0%}"
        f" ({'임베딩+BM25' if embedder else 'BM25만'})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openbook.law")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    b.add_argument("--out", type=Path, default=DEFAULT_INDEX)
    b.add_argument("--no-embed", action="store_true")
    s = sub.add_parser("search")
    s.add_argument("question")
    s.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    e = sub.add_parser("eval")
    e.add_argument("--cases", type=Path, default=DEFAULT_EVAL)
    e.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    e.add_argument("--no-embed", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "build":
        return build(args.targets, args.out, embed=not args.no_embed)
    if args.cmd == "eval":
        return run_eval(args.cases, args.index, embed=not args.no_embed)
    return search(args.question, args.index)


if __name__ == "__main__":
    sys.exit(main())
