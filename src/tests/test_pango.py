from hn.hn import html_to_pango


def test_pango_1():
    text = 'HN traffic isn&#x27;t all that & demanding[1]. <p>[1]: &lt;<a href=\"somehref\" rel=\"nofollow\">some anchor text ...</a>&gt;'
    expected = 'HN traffic isn\'t all that &amp; demanding[1]. \n\n[1]: &lt;<a href="somehref">some anchor text ...</a>&gt;'
    parsed = html_to_pango(text)
    for i in range(0, len(parsed)):
        print(parsed[i], expected[i])
        assert parsed[i] == expected[i], f'{i}: {parsed[i]} vs {expected[i]}'
