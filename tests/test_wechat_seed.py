from v2g.wechat_seed import _account_allowed, _extract_image_urls, _parse_image_size


def test_extract_image_urls_dedup_and_filter_gif():
    html = """
    <img data-src="https://mmbiz.qpic.cn/mmbiz_jpg/abc/640?wx_fmt=jpeg" />
    <img src="https://mmbiz.qpic.cn/mmbiz_jpg/abc/640?wx_fmt=jpeg" />
    <img data-src="https://mmbiz.qpic.cn/mmbiz_gif/abc/640?wx_fmt=gif" />
    <script>var x={cdn_url:"https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png"};</script>
    """
    urls = _extract_image_urls(html, "https://mp.weixin.qq.com/s/test")
    assert urls == [
        "https://mmbiz.qpic.cn/mmbiz_jpg/abc/640?wx_fmt=jpeg",
        "https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png",
    ]


def test_parse_image_size_png_and_jpeg():
    # PNG: 1920x1080
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x07\x80"  # 1920
        b"\x00\x00\x04\x38"  # 1080
        b"\x08\x02\x00\x00\x00"
    )
    assert _parse_image_size(png) == (1920, 1080)

    # Minimal JPEG with SOF0: 1280x720
    jpeg = (
        b"\xff\xd8"
        b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
        b"\xff\xc0\x00\x11\x08\x02\xd0\x05\x00\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        b"\xff\xd9"
    )
    assert _parse_image_size(jpeg) == (1280, 720)


def test_account_allowed_by_substring():
    allow = ["智东西", "36氪", "新智元"]
    assert _account_allowed("智东西", allow) is True
    assert _account_allowed("36氪Pro", allow) is True
    assert _account_allowed("新智元", allow) is True
    assert _account_allowed("腾讯研究院", allow) is False
