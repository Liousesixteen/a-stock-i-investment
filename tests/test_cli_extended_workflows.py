from typer.testing import CliRunner

from stock_assistant.cli import app


def test_cli_industry_outputs_chain_sections():
    runner = CliRunner()

    result = runner.invoke(app, ["industry", "AI算力"])

    assert result.exit_code == 0
    assert "产业链研究" in result.output
    assert "上游" in result.output
    assert "中游" in result.output
    assert "下游" in result.output
    assert "风险提示" in result.output


def test_cli_portfolio_review_outputs_risk_sections():
    runner = CliRunner()

    result = runner.invoke(app, ["portfolio", "review"])

    assert result.exit_code == 0
    assert "组合风险诊断" in result.output
    assert "行业集中度" in result.output
    assert "总仓位建议" in result.output


def test_cli_trade_add_list_and_review(tmp_path, monkeypatch):
    db_path = tmp_path / "trades.db"
    monkeypatch.setenv("STOCK_ASSISTANT_DB", str(db_path))
    runner = CliRunner()

    add = runner.invoke(
        app,
        [
            "trade",
            "add",
            "--symbol",
            "002415",
            "--action",
            "buy",
            "--price",
            "31.8",
            "--quantity",
            "100",
            "--reason",
            "计划内试错",
        ],
    )
    listed = runner.invoke(app, ["trade", "list"])
    review = runner.invoke(app, ["trade", "review"])

    assert add.exit_code == 0
    assert "trade recorded" in add.output
    assert listed.exit_code == 0
    assert "002415" in listed.output
    assert review.exit_code == 0
    assert "交易复盘" in review.output
    assert "交易纪律" in review.output
