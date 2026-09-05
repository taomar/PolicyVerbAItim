"""A large JSON response is compressed on the wire, and carries nothing extra.

WHY THIS FILE EXISTS

A policy retrieval or a decision receipt is JSON carrying published policy
records, and JSON of that kind compresses by roughly an order of magnitude. Doing
that is one line of middleware; proving it did not change anything else is the
work, and there are three things worth proving:

  * it actually compresses something (a middleware that never fires is not a
    feature, and a size floor set wrongly is exactly how one silently never
    fires);
  * it leaves small responses alone, byte-identical, so an error body or a health
    check is not made larger and no header appears on a response that was not
    encoded; and
  * it **composes nothing**. The middleware reads the bytes a route already
    produced. A request's own credentials — a subscription key, an
    `Authorization` header — cannot enter a response through it, and this holds
    that as a checked property rather than an assumption, over a body the caller
    themselves controls.

The last one is the reason this file names credentials at all. The scenario a
caller sends is echoed back to them by design; the headers they send are not, and
a response layer that started echoing request headers would be a real disclosure
bug that no functional test would notice.
"""
from __future__ import annotations

import gzip
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware

from policy_platform.api.app import RESPONSE_COMPRESSION_MIN_BYTES


#: A stand-in for a credential a caller sends and must never be handed back.
#: Invented, and never read from configuration — a test that read the real one
#: would put it in a log the moment it failed.
_SUBSCRIPTION_KEY = "a-subscription-key-value-that-is-not-real"
_BEARER = "Bearer a-token-value-that-is-not-real"


def _app() -> FastAPI:
    """The two response shapes, under the middleware the API adds.

    Built here rather than through `create_app` on purpose: this is a test of
    the response layer, and standing up the whole application would make it
    depend on settings, routers and a database that have nothing to do with what
    is being checked. The middleware and its floor come from the application
    module, so the two cannot drift.
    """

    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=RESPONSE_COMPRESSION_MIN_BYTES)

    @app.post("/large")
    async def large(body: dict) -> dict:
        # The caller's own text is echoed, exactly as a retrieval echoes the
        # scenario it was given. Their credentials are not.
        return {
            "scenario": body.get("scenario", ""),
            "policies": [
                {
                    "provision_key": f"P-{index}",
                    "heading": "A heading that is long enough to be worth compressing",
                    "source": "A sentence repeated across records, which is what makes "
                    "this shape compressible in the first place.",
                }
                for index in range(200)
            ],
        }

    @app.get("/small")
    async def small() -> dict:
        return {"code": "project_not_found", "message": "No project with that key."}

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_app())


class TestALargeResponseIsCompressed:
    def test_it_is_gzip_encoded_and_materially_smaller(self, client: TestClient) -> None:
        response = client.post(
            "/large",
            json={"scenario": "a question"},
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.headers["content-encoding"] == "gzip"

        # `TestClient` decodes for us, so the encoded length is read from the
        # header the server set rather than from the body we can see.
        encoded = int(response.headers["content-length"])
        decoded = len(response.content)
        assert encoded < decoded, "the middleware claimed gzip and did not shrink anything"
        assert encoded * 2 < decoded, "a compressible JSON body barely compressed"

    def test_the_json_that_arrives_is_the_json_that_was_produced(
        self, client: TestClient
    ) -> None:
        """Compression is a transport concern and must not be a content one."""

        plain = client.post(
            "/large",
            json={"scenario": "a question"},
            headers={"Accept-Encoding": "identity"},
        )
        compressed = client.post(
            "/large",
            json={"scenario": "a question"},
            headers={"Accept-Encoding": "gzip"},
        )

        assert "content-encoding" not in plain.headers
        assert compressed.headers["content-encoding"] == "gzip"
        assert compressed.json() == plain.json()
        assert len(compressed.json()["policies"]) == 200

    def test_the_response_varies_on_what_the_caller_accepts(
        self, client: TestClient
    ) -> None:
        """Without it a shared cache could serve gzip to a client that cannot read it."""

        response = client.post(
            "/large",
            json={"scenario": "a question"},
            headers={"Accept-Encoding": "gzip"},
        )

        assert "accept-encoding" in response.headers["vary"].lower()


class TestASmallResponseIsLeftAlone:
    def test_it_is_served_uncompressed_and_says_so_by_saying_nothing(
        self, client: TestClient
    ) -> None:
        """Below the floor the gzip framing costs more than the encoding saves."""

        response = client.get("/small", headers={"Accept-Encoding": "gzip"})

        assert response.status_code == 200
        assert "content-encoding" not in response.headers
        assert len(response.content) < RESPONSE_COMPRESSION_MIN_BYTES
        assert response.json()["code"] == "project_not_found"


class TestNoCredentialReachesTheResponse:
    def test_neither_a_subscription_key_nor_an_authorization_header_is_echoed(
        self, client: TestClient
    ) -> None:
        """Over a body whose text the caller chose, which is the hard case.

        The scenario is echoed — that is the contract. So the check is not "the
        response contains nothing the caller sent", which would be false and
        useless; it is that the response contains the caller's *content* and
        none of the caller's *credentials*, in the body or in any header.
        """

        scenario = "a question whose text the caller controls"
        response = client.post(
            "/large",
            json={"scenario": scenario},
            headers={
                "Accept-Encoding": "gzip",
                "Ocp-Apim-Subscription-Key": _SUBSCRIPTION_KEY,
                "Api-Key": _SUBSCRIPTION_KEY,
                "Authorization": _BEARER,
            },
        )

        assert response.headers["content-encoding"] == "gzip"

        body = response.text
        assert scenario in body, "the echo this test needs in order to mean anything"
        for secret in (_SUBSCRIPTION_KEY, _BEARER, _BEARER.split(" ", 1)[1]):
            assert secret not in body
            for name, value in response.headers.items():
                assert secret not in value, f"a credential came back in `{name}`"

    def test_a_non_ascii_source_sentence_survives_the_encoding_intact(self) -> None:
        """The bytes a document's own words are carried in must not change.

        Verbatim source text is the one thing this platform may never alter, and
        it is not written in one script. gzip is byte-exact by construction, but
        the encoding *around* it is where a body gets re-serialised — so this
        sends non-ASCII through the compressed path and reads it back, rather
        than assuming a transport layer left it alone.
        """

        sentence = "يجب إخطار اللجنة خلال ثلاثين يوماً." + " padding. " * 200

        with TestClient(_app()) as client:
            response = client.post(
                "/large",
                json={"scenario": sentence},
                headers={
                    "Accept-Encoding": "gzip",
                    "Ocp-Apim-Subscription-Key": _SUBSCRIPTION_KEY,
                    "Authorization": _BEARER,
                },
            )

        assert response.headers["content-encoding"] == "gzip"
        document = json.loads(response.content)
        assert document["scenario"] == sentence
        assert _SUBSCRIPTION_KEY not in json.dumps(document, ensure_ascii=False)
        assert _BEARER not in json.dumps(document, ensure_ascii=False)

        # And a plain gzip round trip of the same document is still readable,
        # which is what a caller's own client does with it.
        raw = json.dumps(document, ensure_ascii=False).encode("utf-8")
        assert json.loads(gzip.decompress(gzip.compress(raw))) == document
