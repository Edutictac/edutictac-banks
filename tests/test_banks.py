import httpx
import pytest

from edutictac_banks import Banks, BankError, sanitize_svg, testing
from edutictac_banks.banks import english_terms

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40
JPEG = b"\xff\xd8\xff" + b"0" * 40
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 3h18v18H3z" stroke="#1f2937"/></svg>'


def j(data):
    return httpx.Response(200, json=data)


@pytest.fixture
def net(monkeypatch):
    routes, calls = {}, []

    def handler(request: httpx.Request):
        calls.append(str(request.url))
        for prefix, reply in routes.items():
            if str(request.url).startswith(prefix):
                return reply(request) if callable(reply) else reply
        return httpx.Response(404)

    testing.install(monkeypatch, handler)
    return routes, calls


def test_prefixes_and_native_ids(net):
    routes, _ = net
    routes["https://api.arasaac.org/api/pictograms/ca/search/sol"] = j([{"_id": 7, "keywords": [{"keyword": "sol"}]}])
    items = Banks(image_prefix="/api/image-banks").search("arasaac", "sol", "va")["items"]
    assert items[0]["id"] == 7 and items[0]["thumbnail_url"] == "/api/image-banks/arasaac/7/thumbnail"
    items = Banks().search("arasaac", "sol", "va")["items"]
    assert items[0]["content_url"] == "/api/assets/v1/banks/arasaac/7/content"


def test_image_signature_and_size(net):
    routes, _ = net
    banks = Banks()
    routes["https://static.arasaac.org/pictograms/5/5_300.png"] = httpx.Response(200, content=PNG)
    assert banks.image("arasaac", "5", 300) == (PNG, "image/png")
    routes["https://static.arasaac.org/pictograms/6/6_300.png"] = httpx.Response(200, content=b"<html>x</html>")
    with pytest.raises(BankError) as error:
        banks.image("arasaac", "6", 300)
    assert (error.value.status, error.value.code) == (502, "bank_invalid_image")
    routes["https://static.arasaac.org/pictograms/7/7_300.png"] = httpx.Response(200, content=b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024))
    with pytest.raises(BankError) as error:
        banks.image("arasaac", "7", 300)
    assert error.value.status == 413


def test_openverse_licences_and_unknown_images(net):
    routes, _ = net
    good, bad = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    routes["https://api.openverse.org/v1/images/?"] = j({"results": [
        {"id": good, "license": "by", "license_version": "4.0", "title": "<b>Gat</b>", "thumbnail": "https://cdn.example/t.jpg"},
        {"id": bad, "license": "by-nc"}, {"id": "x", "license": "by"}]})
    routes["https://cdn.example/t.jpg"] = httpx.Response(200, content=JPEG)
    banks = Banks()
    items = banks.search("openverse", "gat")["items"]
    assert [i["id"] for i in items] == [good] and items[0]["title"] == "Gat" and items[0]["license"] == "CC BY 4.0"
    assert banks.image("openverse", good, 300)[1] == "image/jpeg"
    with pytest.raises(BankError):
        banks.image("openverse", "not-a-uuid", 300)


def test_ssrf_private_hosts_http_and_redirects(net, monkeypatch):
    routes, calls = net
    row = {"id": "33333333-3333-3333-3333-333333333333", "license": "cc0"}
    banks = Banks()
    for thumb in ("https://internal.example/x", "http://cdn.example/x.jpg"):
        routes["https://api.openverse.org/v1/images/?"] = j({"results": [{**row, "thumbnail": thumb}]})
        banks.cache.clear()
        item = banks.search("openverse", "a")["items"][0]
        monkeypatch.setattr("edutictac_banks.net.resolve", lambda host: [(0, 0, 0, "", ("10.0.0.5" if host.startswith("internal") else testing.PUBLIC_IP, 443))])
        with pytest.raises(BankError):
            banks.image("openverse", item["id"], 300)
    routes["https://cdn.example/redir.jpg"] = httpx.Response(302, headers={"location": "https://internal.example/x"})
    routes["https://api.openverse.org/v1/images/?"] = j({"results": [{**row, "id": "44444444-4444-4444-4444-444444444444", "thumbnail": "https://cdn.example/redir.jpg"}]})
    item = banks.search("openverse", "b")["items"][0]
    with pytest.raises(BankError):
        banks.image("openverse", item["id"], 300)
    assert not any("internal.example" in call for call in calls)


def test_dns_rebinding_one_resolution_pinned_ip(net, monkeypatch):
    routes, _ = net
    resolved, dialed = [], []
    answers = iter([[(0, 0, 0, "", ("93.184.216.34", 443))], [(0, 0, 0, "", ("127.0.0.1", 443))]])
    monkeypatch.setattr("edutictac_banks.net.resolve", lambda host: resolved.append(host) or next(answers))
    import edutictac_banks.net as network
    real = network.http_client()

    def transport(request: httpx.Request):
        dialed.append(request.url.host)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(network, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False))
    Banks().search("arasaac", "sol")
    assert resolved == ["api.arasaac.org"] and dialed == ["93.184.216.34"]
    answers = iter([[(0, 0, 0, "", ("93.184.216.34", 443)), (0, 0, 0, "", ("10.0.0.8", 443))]])
    with pytest.raises(BankError):
        Banks().search("arasaac", "sol")
    real.close()


@pytest.mark.parametrize("payload", [
    b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><path d="M0 0"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0" fill="url(https://evil.test/x)"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.test/x.png"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div/></foreignObject></svg>',
    b'<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>',
    b'<html><body>no es svg</body></html>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><style>*{}</style></svg>',
])
def test_svg_sanitizer_rejects_active_content(payload):
    with pytest.raises(BankError):
        sanitize_svg(payload)


def test_svg_sanitizer_keeps_shapes():
    out = sanitize_svg(SVG)
    assert b"<path" in out and b"script" not in out


def test_icons_terms_and_media_type(net):
    routes, calls = net
    routes["https://api.iconify.design/search"] = lambda req: j({"icons": ["tabler:scissors", "lucide:scissors", "mdi:evil", "bad"]})
    assert english_terms("Tijeras") == english_terms("tisores") == ["scissors"]
    assert Banks().search("icons", "tijeras")["items"][0]["media_type"] == "image/svg+xml"
    assert Banks(icon_media_type="image/png").search("icons", "tijeras")["items"][0]["media_type"] == "image/png"
    items = Banks().search("icons", "tijeras")["items"]
    assert [i["id"] for i in items] == ["tabler:scissors", "lucide:scissors"] and any("query=scissors" in c for c in calls)


def test_sound_bank_limits_prefix_and_download(net):
    routes, calls = net
    good = "55555555-5555-5555-5555-555555555555"

    def row(i, **extra):
        return {"id": i, "license": "by", "license_version": "4.0", "source": "freesound", "filetype": "ogg", "duration": 3000,
                "url": "https://cdn.freesound.org/s.ogg", "title": "Plof", "creator": "Eva", **extra}

    routes["https://api.openverse.org/v1/audio/?"] = j({"results": [
        row(good), row("66666666-6666-6666-6666-666666666666", filesize=9_000_000),
        row("77777777-7777-7777-7777-777777777777", license="by-nc"),
        row("88888888-8888-8888-8888-888888888888", url="https://evil.test/a.ogg"),
        row("99999999-9999-9999-9999-999999999999", duration=50_000)]})
    routes["https://cdn.freesound.org/s.ogg"] = httpx.Response(200, content=b"OggS" + b"0" * 100)
    banks = Banks(sound_prefix="/api/audio-banks", sound_suffix="preview", max_sound_bytes=10 * 1024 * 1024)
    items = banks.search("openverse-audio", "plof", "es", max_seconds=30)["items"]
    # El de 9 MB cabe en el tope de 10 MiB; el de 50 s supera los 30 s pedidos; los NC y de otros anfitriones se descartan.
    assert [i["id"] for i in items] == [good, "66666666-6666-6666-6666-666666666666"]
    assert [i["id"] for i in Banks().search("openverse-audio", "plof", "es", max_seconds=30)["items"]] == [good]  # tope por defecto: 2 MiB
    assert items[0]["preview_url"] == f"/api/audio-banks/openverse-audio/{good}/preview" and items[0]["kind"] == "sound"
    assert banks.image("openverse-audio", good, 500) == (b"OggS" + b"0" * 100, "audio/ogg")
    with pytest.raises(BankError) as error:
        banks.image("openverse-audio", good, 300)
    assert error.value.status == 404
    routes["https://cdn.freesound.org/s.ogg"] = httpx.Response(302, headers={"location": "https://evil.test/a.ogg"})
    with pytest.raises(BankError):
        banks.image("openverse-audio", good, 500)
    assert not any("evil.test" in c for c in calls)


def test_import_asset_returns_credit_and_title(net):
    routes, _ = net
    banks = Banks()
    routes["https://static.arasaac.org/pictograms/9/9_500.png"] = httpx.Response(200, content=PNG)
    data, media, credit, title = banks.import_asset("arasaac", 9)
    assert (data, media) == (PNG, "image/png") and "ARASAAC" in credit and "arasaac.org/pictograms/9" in credit
    good = "11111111-1111-1111-1111-111111111111"
    routes[f"https://api.openverse.org/v1/images/{good}/"] = j({"id": good, "license": "by", "license_version": "4.0", "title": "Gat", "creator": "Ana",
                                                               "url": "https://cdn.example/big.jpg", "thumbnail": "https://cdn.example/t.jpg"})
    routes["https://cdn.example/big.jpg"] = httpx.Response(200, content=JPEG)
    data, media, credit, title = banks.import_asset("openverse", good)
    assert media == "image/jpeg" and "Ana" in credit and title == "Gat"
    with pytest.raises(BankError):
        banks.credit_of("openverse", "no-es-uuid")
    assert "Iconify" in banks.credit_of("icons", "lucide:home")
