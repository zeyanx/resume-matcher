"""运行融合权重网格搜索并保存可追溯结果。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.weight_search import (  # noqa: E402
    load_labeled_cases,
    run_weight_grid_search,
    save_weight_search_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="在验证集上搜索融合权重，并隔离评估测试集。")
    parser.add_argument("--input", type=Path, required=True, help="带预计算子分数和标签的 CSV。")
    parser.add_argument("--output-dir", type=Path, required=True, help="实验结果保存目录。")
    parser.add_argument("--step", type=float, default=0.1, help="权重网格步长，默认 0.1。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_labeled_cases(args.input)
    result = run_weight_grid_search(cases, step=args.step)
    summary_path, comparison_path = save_weight_search_result(result, args.output_dir)
    best = result.best_validation
    print(
        "最佳验证集权重："
        f"semantic={best.weights.semantic:.2f}, "
        f"skill={best.weights.skill:.2f}, "
        f"experience={best.weights.experience:.2f}"
    )
    print(
        "验证集 Spearman："
        + (f"{best.spearman:.4f}" if best.spearman is not None else "不可计算")
    )
    print(f"数据状态：{', '.join(result.data_statuses)}")
    print(f"最佳权重文件：{summary_path}")
    print(f"权重对比文件：{comparison_path}")


if __name__ == "__main__":
    main()
