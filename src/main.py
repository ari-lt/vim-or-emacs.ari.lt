#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vim-or-emacs.ari.lt"""

import re
import secrets
import time
from datetime import datetime
from enum import Enum, auto
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple
from warnings import filterwarnings as filter_warnings

import flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime
from sqlalchemy import Enum as DBEnum
from sqlalchemy import func
from werkzeug.exceptions import HTTPException
from werkzeug.routing import Rule
from werkzeug.wrappers import Response

db: SQLAlchemy = SQLAlchemy()


class Editor(Enum):
    """editor : vim or emacs"""

    vim = auto()
    emacs = auto()

    @classmethod
    def all(cls) -> Tuple["Editor", ...]:
        """all items"""
        return tuple(cls)


class Vote(db.Model):
    """vim or emacs vote"""

    id: int = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
    )
    editor: Editor = db.Column(
        DBEnum(Editor),
        nullable=False,
    )
    voted: DateTime = db.Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __init__(self, editor: Editor) -> None:
        """initialize a vote"""
        self.editor = editor


app: flask.Flask = flask.Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///voe.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SECRET_KEY"] = secrets.token_bytes(8**5)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["DOMAIN"] = "vim-or-emacs.ari.lt"

db.init_app(app)

with app.app_context():
    db.create_all()

limiter: Limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["30 per minute", "6 per second"],
    storage_uri="memory://",
    strategy="moving-window",
)


@app.context_processor  # type: ignore
def context() -> Dict[str, Any]:
    """expose objects"""
    return {"Editor": Editor}


@app.errorhandler(HTTPException)
def error_handler(e: HTTPException) -> Tuple[Any, int]:
    """handle http errors"""

    if e.code == 429:
        time.sleep(secrets.SystemRandom().random() * 15)

        return (
            flask.Response(
                f"too many requests : {e.description or '<limit>'}",
                mimetype="text/plain",
            ),
            429,
        )

    return (
        flask.render_template(
            "http.j2",
            code=e.code,
            summary=e.name.lower(),
            description=(e.description or f"http error code {e.code}").lower(),
        ),
        e.code or 200,
    )


@app.get("/")
def index() -> str:
    """index page"""

    editor_counts: List[Tuple[Editor, int]] = (  # type: ignore
        db.session.query(Vote.editor, func.count(Vote.editor))  # type: ignore
        .group_by(Vote.editor)
        .all()
    )

    if len(editor_counts) == 0:  # type: ignore
        final_result: Tuple[Optional[Editor], int] = None, 0
    elif len(editor_counts) == 1:  # type: ignore
        final_result = editor_counts[0]  # type: ignore
    else:
        sorted_counts: List[Tuple[Editor, int]] = sorted(editor_counts, key=itemgetter(1), reverse=True)[:2]  # type: ignore

        if sorted_counts[0][1] > sorted_counts[1][1]:
            final_result = sorted_counts[0]  # we have a winner
        else:
            final_result = None, sorted_counts[0][1]  # its a tie

    return flask.render_template(
        "index.j2",
        winner=final_result,
    )


@app.post("/")
@limiter.limit("1 per day")
def vote() -> Response:
    """vote"""

    voe: Optional[str] = flask.request.form.get("voe")

    if not voe:
        flask.abort(400)

    try:
        editor: Editor = Editor(int(voe))
    except Exception:
        flask.abort(400)

    try:
        vote: Vote = Vote(editor)

        db.session.add(vote)
        db.session.commit()

        flask.flash(
            f"Your vote for `{editor.name}` with ID `{vote.id}` has been recorded."
        )
    except Exception:
        db.session.rollback()
        flask.abort(500)

    return flask.redirect("/")


@app.get("/votes")
def votes() -> str:
    """votes"""
    return flask.render_template("votes.j2")


@app.get("/editors.json")
def editors_json() -> Response:
    """editors"""
    return flask.jsonify({editor.value: editor.name for editor in Editor.all()})


@app.get("/votes.json")
def votes_json() -> Response:
    """votes filtering api"""

    from_id: Optional[int] = flask.request.args.get("from", default=None, type=int)
    to_id: Optional[int] = flask.request.args.get("to", default=None, type=int)
    editor: Optional[int] = flask.request.args.get("editor", default=None, type=int)

    filters: List[Any] = []

    if from_id is not None:
        filters.append(Vote.id >= from_id)

    if to_id is not None:
        filters.append(Vote.id <= to_id)

    if editor is not None:
        try:
            filters.append(Vote.editor == Editor(editor))
        except Exception:
            pass

    votes: Dict[int, Dict[str, Any]] = {}

    for vote in Vote.query.filter(*filters).all():  # type: ignore
        votes[vote.id] = {  # type: ignore
            "editor": vote.editor.value,  # type: ignore
            "voted": vote.voted.timestamp(),  # type: ignore
        }

    return flask.jsonify(votes)


@app.get("/stats.json")
def stats_json() -> Response:
    """stats"""

    votes: List[Vote] = Vote.query.all()  # type: ignore

    total_votes: int = len(votes)  # type: ignore
    vote_counts: Dict[int, int] = {editor.value: 0 for editor in Editor.all()}  # type: ignore
    latest_vote: Optional[datetime] = max(votes, key=lambda vote: vote.voted).voted if votes else None  # type: ignore
    first_vote: Optional[datetime] = min(votes, key=lambda vote: vote.voted).voted if votes else None  # type: ignore

    for vote in votes:
        vote_counts[vote.editor.value] += 1

    return flask.jsonify(
        {
            "total": total_votes,
            "votes": vote_counts,
            "latest": latest_vote.timestamp() if latest_vote else None,  # type: ignore
            "first": first_vote.timestamp() if first_vote else None,  # type: ignore
        }
    )


@app.route("/robots.txt", methods=["GET", "POST"])
def robots_txt() -> flask.Response:
    """robots.txt file"""
    return flask.Response(
        """User-agent: *
Allow: *
Sitemap: https://vim-or-emacs.ari.lt/sitemap.xml""",
        mimetype="text/plain",
    )


rule: Rule

pat: re.Pattern[str] = re.compile(r"<.+?:(.+?)>")

sitemap: str = '<?xml version="1.0" encoding="UTF-8"?>\
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'


def surl(loc: str) -> str:
    """sitemap url"""

    u: str = "<url>"
    u += (
        f'<loc>{app.config["PREFERRED_URL_SCHEME"]}://{app.config["DOMAIN"]}{loc}</loc>'
    )
    u += "<priority>1.0</priority>"
    return u + "</url>"


for rule in app.url_map.iter_rules():
    url: str = pat.sub(r"\1", rule.rule)
    sitemap += surl(url)


@app.route("/sitemap.xml", methods=["GET", "POST"])
def sitemap_xml() -> flask.Response:
    """sitemap"""

    esitemap: str = sitemap
    return flask.Response(esitemap + "</urlset>", mimetype="application/xml")


@app.route("/manifest.json", methods=["GET", "POST"])
def manifest_json() -> flask.Response:
    """manifest"""
    return flask.jsonify(
        {
            "$schema": "https://json.schemastore.org/web-manifest-combined.json",
            "short_name": "Vim or Emacs",
            "name": "Ari::web -> VimOrEmacs",
            "description": "Vim or GNU Emacs?",
            "icons": [{"src": "/favicon.ico", "sizes": "128x128", "type": "image/png"}],
            "start_url": ".",
            "display": "standalone",
            "theme_color": "#fbfbfb",
            "background_color": "#181818",
        }
    )


@app.route("/favicon.ico", methods=["GET", "POST"])
def favicon_ico() -> Response:
    """favicon"""
    return flask.redirect("https://ari.lt/favicon.ico")


def main() -> int:
    """entry/main function"""

    app.run("127.0.0.1", 8080, True)

    return 0


if __name__ == "__main__":
    assert main.__annotations__.get("return") is int, "main() should return an integer"

    filter_warnings("error", category=Warning)
    raise SystemExit(main())
