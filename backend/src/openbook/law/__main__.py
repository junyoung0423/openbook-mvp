"""법령 색인 만들기.

    python -m openbook.law build              # data/law/targets.yaml의 법령을 받아 색인 저장
    python -m openbook.law build --no-embed   # 임베딩 없이 (글자 겹침 검색만)
    python -m openbook.law search "질문"       # 색인에서 찾아보기

필요한 값: LAW_OC (법제처 Open API), UPSTAGE_API_KEY (임베딩). 값은 출력하지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from openbook.law.embed import UpstageEmbedder
from openbook.law.index import DEFAULT_INDEX, LawIndex
from openbook.law.lawgo import LawApiClient

DEFAULT_TARGETS = DEFAULT_INDEX.parent / "targets.yaml"


def build(targets: Path, out: Path, embed: bool) -> int:
    names = [t["name"] for t in yaml.safe_load(targets.read_text(encoding="utf-8"))["laws"]]
    client = LawApiClient.from_env()
    articles = []
    for name in names:
        got = client.articles(name)
        print(f"{name}: 조문 {len(got)}개")
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
    args = p.parse_args(argv)
    if args.cmd == "build":
        return build(args.targets, args.out, embed=not args.no_embed)
    return search(args.question, args.index)


if __name__ == "__main__":
    sys.exit(main())
