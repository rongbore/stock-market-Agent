"""Classify known TradingAgents failure logs without calling external services.

Reads a local text file and emits a short diagnostic; never uploads log content.
"""
import argparse
from pathlib import Path


def classify_log(log: str) -> tuple[str, str]:
    if "Unexpected response type from OpenAI-compatible endpoint" in log:
        return ("model_response_invalid",
                "模型兼容接口响应格式异常；核对模型 ID 和服务端兼容性，不要自动重复付费运行。")
    if "分析日期必须使用 YYYY-MM-DD" in log or "分析日期无效" in log:
        return ("invalid_analysis_date", "分析日期格式错误；使用 YYYY-MM-DD 或留空。")
    if "请先在仓库 Actions secrets 中配置 DEEPSEEK_API_KEY" in log:
        return ("missing_api_key", "缺少模型密钥；仅在 GitHub Actions secrets 中配置。")
    if "FRED_API_KEY environment variable is not set" in log:
        return ("optional_macro_unavailable",
                "可选宏观数据不可用；不能单凭此警告认定分析失败根因。")
    if "Yahoo Finance has no news articles tagged" in log:
        return ("news_unavailable",
                "Yahoo 新闻覆盖缺失；不能据此推断没有重大新闻。")
    return ("unknown", "未识别失败类型；请检查日志最后的异常，勿上传密钥。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    args = parser.parse_args()
    category, advice = classify_log(args.log_file.read_text(encoding="utf-8"))
    print(f"category: {category}")
    print(f"advice: {advice}")


if __name__ == "__main__":
    main()
