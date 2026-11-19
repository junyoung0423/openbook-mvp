"""M7 조항 Q&A (정준영). 사용자 계약서·표준계약서에서 근거 조항을 찾아 원문을 인용해 답한다.

법령 조문 검색은 데이터가 준비되면 붙인다 (MVP 1차에는 없음).
"""

from openbook.qa.answer import answer_question
from openbook.qa.models import NOT_FOUND_ANSWER, QA_NOTICE, Citation, QAResult

__all__ = ["NOT_FOUND_ANSWER", "QA_NOTICE", "Citation", "QAResult", "answer_question"]
