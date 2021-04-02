from bs4 import BeautifulSoup, NavigableString

def to_pango(node):
    def escape(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if isinstance(node, NavigableString):
        return escape(node)

    escaped_text = escape(node.text)
    if node.name == 'pre':
        return f'<tt>{escaped_text}</tt>'

    if node.name == 'a':
        href = node["href"].replace('&', '&amp;')
        return f'<a href="{href}">{escaped_text}</a>'

    if node.name == 'p':
        ret = '\n'
        for child in node.children:
            ret += to_pango(child)
        ret += '\n'
        return ret

    if node.name in ['i', 'b']:
        return str(node)

    print('wtf!!', node)
    return escaped_text

def html_to_pango(html):
    soup = BeautifulSoup(html, features="lxml")
    ret = ''
    for node in soup.body.children:
        pango = to_pango(node)
        if pango:
            ret += pango
    return ret.strip()


