import io
import json

import pytest

from utils.faircv import FairCVError, fetch_faircv_rows, parse_faircv_payload, remove_protected_content


def sample_payload():
    return {
        "rows": [
            {
                "row_idx": 7,
                "row": {
                    "metadata": {
                        "age": "22",
                        "gender": "女",
                        "hukou": "北京市",
                        "marriage": "未婚",
                        "political": "群众",
                        "disability": "无",
                        "position": "后端开发工程师",
                        "skill_level": "中等",
                        "recruitment_type": "校招",
                        "company_size": None,
                        "industry": None,
                    },
                    "content": (
                        "### 个人信息\n- **姓名**：张三\n- **年龄**：22\n"
                        "- **性别**：女\n- **邮箱**：demo@example.com\n\n---\n"
                        "### 专业技能\n- Python\n- SQL"
                    ),
                },
            }
        ],
        "num_rows_total": 1_440_180,
        "partial": True,
    }


def test_protected_fields_are_removed_from_matching_text():
    batch = parse_faircv_payload(sample_payload())
    record = batch.records[0]
    assert "Python" in record.matching_text
    assert "张三" not in record.matching_text
    assert "demo@example.com" not in record.matching_text
    assert record.protected_attributes["gender"] == "女"
    assert record.context_attributes["position"] == "后端开发工程师"


def test_remove_protected_content_handles_unsectioned_lines():
    cleaned = remove_protected_content("- **电话**：13800138000\n项目经验：接口开发")
    assert "13800138000" not in cleaned
    assert "接口开发" in cleaned


def test_fetch_uses_bounded_rows_api_request():
    payload_bytes = json.dumps(sample_payload(), ensure_ascii=False).encode("utf-8")

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_opener(request, timeout):
        assert "dataset=OhMyKing%2FFairCV" in request.full_url
        assert "length=1" in request.full_url
        assert timeout == 5
        return FakeResponse(payload_bytes)

    batch = fetch_faircv_rows(offset=7, length=1, timeout_seconds=5, opener=fake_opener)
    assert batch.records[0].row_index == 7


@pytest.mark.parametrize("length", [0, 101])
def test_fetch_rejects_unbounded_page_sizes(length):
    with pytest.raises(FairCVError, match="length"):
        fetch_faircv_rows(length=length)
