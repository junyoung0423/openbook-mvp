"""M7 조항 Q&A (정준영). 사용자 계약서·표준계약서에서 근거 조항을 찾아 원문을 인용해 답한다.

법령 조문은 호출한 쪽이 openbook.law 색인에서 찾아 넘긴다 (색인이 없으면 법령 없이 답한다).
"""

from openbook.qa.answer import answer_question
from openbook.qa.models import NOT_FOUND_ANSWER, QA_NOTICE, Citation, QAResult

__all__ = ["NOT_FOUND_ANSWER", "QA_NOTICE", "Citation", "QAResult", "answer_question"]
