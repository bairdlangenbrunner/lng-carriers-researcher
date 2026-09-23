"""Tests for scripts/csb_fetch.py — the orderbook parser and --all-pages sweep.

The load-bearing guarantees: a yard's whole orderbook is walked rather than its
first page (the blind spot a date-windowed sweep can never see), and the walk
stops on the failure modes CSB actually shows — an empty page, and a page whose
hulls repeat page 1 because the pagination token didn't advance. Offline: the
fetch is a canned page factory, the sweeper's pacing is stubbed out.
"""
import json

import csb_fetch
import pytest
from csb_fetch import (
    MAX_PAGE,
    PAGE_TOKENS,
    filter_rows,
    is_lng_relevant,
    page_url,
    parse_orderbook_html,
    sweep_all_pages,
)


def _row_html(n, token, hull, typecap="LNG Tanker 174000cbm", owner="MOL",
              delivery="2028 - 05", contract="2026 - 02"):
    return (f"<tr><td>{n}</td>"
            f'<td><a href="ship.aspx?{token}">{hull}</a></td>'
            f"<td>{typecap}</td><td>{owner}</td>"
            f"<td>{delivery}</td><td>{contract}</td></tr>")


def _page_html(rows):
    return "<html><body><table>" + "".join(rows) + "</table></body></html>"


class _Page:
    def __init__(self, text, status="200"):
        self.status, self.text = status, text
        self.notes, self.final_url, self.is_pdf = [], "", False


@pytest.fixture(autouse=True)
def _work_dir(tmp_path, monkeypatch):
    """Point paths.work_dir()/csb_dir() at a throwaway directory."""
    monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path))
    import paths
    (tmp_path / "csb").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "csb_dir", lambda: tmp_path / "csb")
    monkeypatch.setattr(csb_fetch, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(csb_fetch, "csb_dir", lambda: tmp_path / "csb")
    return tmp_path


def _sweep(pages_by_url, tmp_path, yards=("samsung",), **kw):
    """Run sweep_all_pages against a canned {url: _Page} map, unpaced."""
    calls = []

    def fake_fetch(url, **_):
        calls.append(url)
        return pages_by_url.get(url, _Page("", status="404"))

    result = sweep_all_pages(yards, fetch=fake_fetch, echo=lambda *a: None,
                             out_path=tmp_path / "sweep.jsonl",
                             sleep=lambda s: None, clock=lambda: 0.0,
                             rng=lambda a, b: 0.0, **kw)
    return result, calls


class TestParse:
    def test_parses_a_row(self):
        rows = parse_orderbook_html(_page_html([_row_html(1, "TOK1", "2301")]), "samsung")
        assert rows == [{
            "yard": "samsung", "row_num": 1,
            "ship_url": "http://www.chinashipbuild.com/ship.aspx?TOK1",
            "ship_token": "TOK1", "hull": "2301", "hull_assigned": True,
            "typecap": "LNG Tanker 174000cbm", "owner": "MOL",
            "delivery": "2028-05", "contract": "2026-02"}]

    def test_yard_name_placeholder_is_not_an_assigned_hull(self):
        rows = parse_orderbook_html(_page_html([_row_html(1, "T", "Samsung HI")]), "samsung")
        assert rows[0]["hull_assigned"] is False

    def test_lng_scope(self):
        assert is_lng_relevant("LNG Tanker 174000cbm")
        assert is_lng_relevant("FSRU 170000cbm")
        assert not is_lng_relevant("LNG Bunkering Vessel 18000cbm")
        assert not is_lng_relevant("Container 8000TEU")

    def test_since_filter(self):
        rows = [{"contract": "2025-12"}, {"contract": "2026-02"}]
        assert filter_rows(rows, since="2026-01") == [{"contract": "2026-02"}]


class TestPageUrl:
    def test_page_one_is_the_bare_url(self):
        assert page_url("samsung") == csb_fetch.ALL_YARDS["samsung"]

    def test_later_pages_append_the_token(self):
        assert page_url("samsung", 3).endswith("aORDERBOOK" + PAGE_TOKENS[3])

    def test_unknown_yard_and_page(self):
        with pytest.raises(ValueError):
            page_url("nope")
        with pytest.raises(ValueError):
            page_url("samsung", MAX_PAGE + 1)


class TestSweepAllPages:
    def test_walks_past_page_one_and_accumulates(self, tmp_path):
        pages = {
            page_url("samsung", 1): _Page(_page_html([_row_html(1, "A", "2301")])),
            page_url("samsung", 2): _Page(_page_html([_row_html(2, "B", "2302")])),
            page_url("samsung", 3): _Page(_page_html([])),
        }
        result, calls = _sweep(pages, tmp_path)
        st = result["samsung"]
        assert [r["hull"] for r in st["rows"]] == ["2301", "2302"]
        assert [r["page"] for r in st["rows"]] == [1, 2]
        assert st["pages"] == 2
        assert st["stopped"] == "page 3 empty"
        assert len(calls) == 3        # stopped as soon as a page came back empty

    def test_stops_when_a_page_repeats_page_one(self, tmp_path):
        """An invalid pagination token silently re-serves page 1."""
        p1 = _page_html([_row_html(1, "A", "2301")])
        pages = {page_url("samsung", 1): _Page(p1), page_url("samsung", 2): _Page(p1)}
        result, calls = _sweep(pages, tmp_path)
        st = result["samsung"]
        assert [r["hull"] for r in st["rows"]] == ["2301"]   # no duplicate
        assert st["stopped"] == "page 2 repeats page 1"
        assert len(calls) == 2

    def test_a_yard_that_never_answers_is_reported_not_crashed(self, tmp_path):
        result, _ = _sweep({}, tmp_path)
        assert result["samsung"]["rows"] == []
        assert result["samsung"]["pages"] == 0
        assert result["samsung"]["stopped"]

    def test_one_yard_stopping_does_not_stop_the_others(self, tmp_path):
        pages = {
            page_url("samsung", 1): _Page(_page_html([_row_html(1, "A", "2301")])),
            page_url("samsung", 2): _Page(_page_html([])),
            page_url("jiangnan", 1): _Page(_page_html([_row_html(1, "C", "H2706")])),
            page_url("jiangnan", 2): _Page(_page_html([_row_html(2, "D", "H2707")])),
            page_url("jiangnan", 3): _Page(_page_html([])),
        }
        result, _ = _sweep(pages, tmp_path, yards=("samsung", "jiangnan"))
        assert result["samsung"]["pages"] == 1
        assert [r["hull"] for r in result["jiangnan"]["rows"]] == ["H2706", "H2707"]

    def test_max_page_caps_the_walk(self, tmp_path):
        pages = {page_url("samsung", n): _Page(_page_html([_row_html(n, f"T{n}", f"230{n}")]))
                 for n in range(1, MAX_PAGE + 1)}
        result, calls = _sweep(pages, tmp_path, max_page=2)
        assert result["samsung"]["pages"] == 2
        assert "max_page 2" in result["samsung"]["stopped"]
        assert len(calls) == 2

    def test_html_is_kept_for_the_parser(self, tmp_path):
        pages = {page_url("samsung", 1): _Page(_page_html([_row_html(1, "A", "2301")])),
                 page_url("samsung", 2): _Page(_page_html([]))}
        _sweep(pages, tmp_path)
        assert (tmp_path / "csb" / "samsung_p1.html").exists()

    def test_the_sweep_is_resumable(self, tmp_path):
        """A second run re-reads the JSONL and re-fetches nothing already answered."""
        pages = {page_url("samsung", 1): _Page(_page_html([_row_html(1, "A", "2301")])),
                 page_url("samsung", 2): _Page(_page_html([]))}
        _sweep(pages, tmp_path)
        _, calls = _sweep(pages, tmp_path)
        assert calls == []
        recs = [json.loads(ln) for ln in (tmp_path / "sweep.jsonl").read_text().splitlines()]
        assert {r["yard"] for r in recs} == {"samsung"}
        assert {r["page"] for r in recs} == {1, 2}
