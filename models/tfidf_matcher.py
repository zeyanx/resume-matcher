"""基于 TF-IDF 与余弦相似度的传统文本匹配基线。"""

from math import isfinite

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils.text_preprocessor import normalize_text, tokenize_chinese


def calculate_tfidf_similarity(resume_text: str, jd_text: str) -> float:
    """计算简历和岗位描述之间的 TF-IDF 余弦相似度。

    返回值固定限制在 0 到 1 之间。空输入会抛出带中文说明的异常，
    由网页层负责展示，而不是返回一个容易造成误解的 0 分。
    """
    resume_clean = normalize_text(resume_text)
    jd_clean = normalize_text(jd_text)

    if not resume_clean:
        raise ValueError("简历内容为空，请上传或输入有效的简历文本。")
    if not jd_clean:
        raise ValueError("岗位 JD 为空，请输入岗位职责和任职要求。")

    vectorizer = TfidfVectorizer(
        tokenizer=tokenize_chinese,
        token_pattern=None,
        lowercase=False,
        max_features=10_000,
        sublinear_tf=True,
    )

    try:
        matrix = vectorizer.fit_transform([resume_clean, jd_clean])
    except ValueError as exc:
        raise ValueError("文本中没有可用于匹配的有效词语，请补充具体内容。") from exc

    score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0])
    if not isfinite(score):
        return 0.0
    return max(0.0, min(1.0, score))
