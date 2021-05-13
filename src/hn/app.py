#!/usr/bin/env python3.7
import time
import pkg_resources

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
#gi.require_version("WebKit2", "4.0")
#from gi.repository import Gtk, GLib, Gdk, WebKit2, GdkPixbuf, Gio, Adwaita
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio, Adw

from hn.api import top_stories, get_comment, get_story, Comment, Story
from hn.bus import Bus

BG_TASKS = ThreadPoolExecutor(max_workers=4)
WEBEXT_DIR = '/home/david/git/webkit-webextension'
Adw.init()  # Must call this otherwise the Template() calls don't know how to resolve any Hdy* widgets

def load_icon_to_pixbuf(name, width):
    path = f'/hn/icons/{name}'
    pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(path, width, -1, True)
    return pixbuf

data = pkg_resources.resource_stream('hn', 'resources')
glib_data = GLib.Bytes.new(data.read())
resource = Gio.Resource.new_from_data(glib_data)
resource._register()
_rs = Gio.resources_lookup_data('/hn/css/reader_mode.css', Gio.ResourceLookupFlags.NONE)
READER_CSS = _rs.get_data().decode().replace('\n', '')


@Gtk.Template(resource_path='/hn/ui/MainWindow.ui')
class AppWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AppWindow'

    ct = Gtk.Template.Child()
    news_list = Gtk.Template.Child()
    www = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_child = None
        self.setup_styles()
        self.set_default_size(360, 720)

        Bus.on("open_thread", self.set_thread)
        Bus.on("open_website", self.set_website)

    def setup_styles(self):
        css_provider = Gtk.CssProvider()
        context = Gtk.StyleContext()
        #screen = Gdk.Screen.get_default()

        css_provider.load_from_resource('/hn/css/style.css')
        #context.add_provider_for_screen(screen, css_provider,
        #                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_thread(self, story):
        self.stack.set_visible_child(self.ct)
    
    def set_news(self):
        self.stack.set_visible_child(self.news_list)

    def set_website(self, url, title):
        self.www.load_uri(url, title)
        self.old_child = self.stack.get_visible_child()
        self.stack.set_visible_child(self.www)

    def pop_website(self):
        assert self.old_child
        self.stack.set_visible_child(self.old_child)


@Gtk.Template(resource_path='/hn/ui/WebsiteHeader.ui')
class WebsiteHeader(Adw.HeaderBar):
    __gtype_name__ = 'WebsiteHeader'
    readable_toggle = Gtk.Template.Child()
    page_title = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Bus.on("open_website", lambda url, title: self.page_title.set_label(title))
        Bus.on("trigger_website_loading", self.readable_toggle.hide)
        Bus.on("website_can_be_readable", self.readable_toggle.show)

    @Gtk.Template.Callback()
    def open_in_browser_click(self, event):
        print('in browser')

    @Gtk.Template.Callback()
    def readability_click(self, event):
        self.readable_toggle.hide()
        Bus.emit("trigger_readability")

    @Gtk.Template.Callback()
    def back_click(self, event):
        Bus.emit("trigger_stop_website")
        # FIXME
        window = self.get_root()
        window.pop_website()

@Gtk.Template(resource_path='/hn/ui/WebsiteView.ui')
class WebsiteView(Gtk.Box):
    __gtype_name__ = 'WebsiteView'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # https://stackoverflow.com/questions/60126579/gtk-builder-error-quark-invalid-object-type-webkitwebview
        # Can't have the WevView in ui file without hacks, doing it programatically is clearer
        # FIXME need to update WebKit
        return
        ctx = WebKit2.WebContext.get_default()
        ctx.set_web_extensions_directory(WEBEXT_DIR)
        self.www = WebKit2.WebView.new_with_context(ctx)
        self.www.connect('load-changed', self.load_changed)
        self.www.set_hexpand(True)
        self.www.set_vexpand(True)
        self.add(self.www)

        Bus.on("trigger_readability", self.convert_to_readable)
        Bus.on("open_website", self.load_uri)
        Bus.on("trigger_stop_website", self.www.stop_loading)

    def load_changed(self, webview, state):
        if state == WebKit2.LoadEvent.STARTED:
            Bus.emit("trigger_website_loading")
        finished = state == WebKit2.LoadEvent.FINISHED
        if not finished:
            return
        self.www.run_javascript_from_gresource('/hn/js/Readability.js', None, self._loaded_readability, None)

    def load_uri(self, url, title):
        self.www.load_uri(url)

    def _loaded_readability(self, resource, result, user_data):
        result = resource.run_javascript_from_gresource_finish(result)
        js = 'isProbablyReaderable(document);'
        self.www.run_javascript(js, None, self.on_readerable_result, None)

    def on_readerable_result(self, webview, result, user_data):
        result = self.www.run_javascript_finish(result)
        if result.get_js_value().to_boolean():
            Bus.emit("website_can_be_readable")
            print('making visible', flush=True)

    def convert_to_readable(self):
        self.www.stop_loading()
        js = f'''
          let h = document.head;
          for (let c of h.childNodes) h.removeChild(c);

          let article = new Readability(document).parse();
          document.querySelector('body').innerHTML = article.content;

          // add our style
          var style = document.createElement("style");
          style.innerHTML = '{READER_CSS}';
          document.head.appendChild(style);
        '''
        self.www.run_javascript(js, None, None, None)


@Gtk.Template(resource_path='/hn/ui/NewsList.ui')
class NewsList(Gtk.Box):
    __gtype_name__ = 'NewsList'
    vbox = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Bus.on('refresh_news_list', self.async_refresh)

    def _refresh(self):
        stories = top_stories()
        GLib.idle_add(self.set_items, stories[:50])  # FIXME

    def async_refresh(self):
        BG_TASKS.submit(self._refresh)

    def set_items(self, news_item):
        fc = self.vbox.get_first_child()
        while fc:
            _fc = fc.get_next_sibling()
            self.vbox.remove(fc)
            fc = _fc 

        for i in news_item:
            widget = NewsItem(i)
            self.vbox.prepend(widget)

@Gtk.Template(resource_path='/hn/ui/NewsHeader.ui')
class NewsHeader(Adw.HeaderBar):
    __gtype_name__ = 'NewsHeader'

    @Gtk.Template.Callback()
    def menu_click(self, event):
        Bus.emit("menu_click")

    @Gtk.Template.Callback()
    def on_refresh(self, event):
        Bus.emit("refresh_news_list")

@Gtk.Template(resource_path='/hn/ui/ThreadHeader.ui')
class ThreadHeader(Adw.HeaderBar):
    __gtype_name__ = 'ThreadHeader'

    title = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Bus.on("open_thread", self.set_story_details)

    @Gtk.Template.Callback()
    def article_click(self, event):
        Bus.emit("open_website", url=self.article_url, title=self.article_title)

    @Gtk.Template.Callback()
    def back_click(self, event):
        # FIXME
        window = self.get_root()
        window.set_news()

    def set_story_details(self, story):
        self.article_url = story.url
        self.article_title = story.title
        self.title.set_label(story.title)

@Gtk.Template(resource_path='/hn/ui/CommentThread.ui')
class CommentThread(Gtk.ScrolledWindow):
    __gtype_name__ = 'CommentThread'
    comments_container = Gtk.Template.Child()
    header_comments_vbox = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Bus.on("open_thread", self.async_load_thread)

    def async_load_thread(self, story):
        BG_TASKS.submit(self._load_thread, story)

    def _load_thread(self, story):
        for child in self.comments_container.get_children():
            self.comments_container.remove(child)
        GLib.idle_add(self._set_comments, story.kids)

    def _set_comments(self, comments):
        for i in comments:
            widget1 = CommentItem(i, 0)
            widget1.set_visible(True)
            self.comments_container.prepend(widget1)  ## fill and expand


@Gtk.Template(resource_path='/hn/ui/NewsItem.ui')
class NewsItem(Gtk.Grid):
    __gtype_name__ = 'NewsItem'
    title = Gtk.Template.Child()
    url = Gtk.Template.Child()
    comments = Gtk.Template.Child()
    comments_btn = Gtk.Template.Child()
    title_event = Gtk.Template.Child()

    def __init__(self, _item_id, *args, **kwds):
        super().__init__(*args, **kwds)
        self.article_url = None
        self.thread_id = _item_id
        self.on_show()

    def on_show(self):
        BG_TASKS.submit(self._set_content, self.thread_id)

    @Gtk.Template.Callback()
    def comments_click(self, event):
        Bus.emit("open_thread", story=self.story)

    @Gtk.Template.Callback()
    def title_click(self, event):
        Bus.emit("open_website", url=self.article_url, title=self.thread_title)

    def _set_content(self, _item_id):
        story = get_story(_item_id)
        GLib.idle_add(self.set_content, story)

    def set_content(self, story: Story):
        self.story = story
        self.article_url = story.url
        self.thread_title = story.title
        self.title.set_label(story.title)
        self.title.get_style_context().add_class('news-item-title')
        self.url.set_label(story.url_domain)
        self.comments.set_label(str(story.comment_count))


@Gtk.Template(resource_path='/hn/ui/CommentItem.ui')
class CommentItem(Gtk.Box):
    __gtype_name__ = 'CommentItem'
    time_lbl = Gtk.Template.Child()
    comment = Gtk.Template.Child()
    comment_body = Gtk.Template.Child()
    replies_container = Gtk.Template.Child()
    replies = Gtk.Template.Child()
    revealer_img = Gtk.Template.Child()
    revealer_event = Gtk.Template.Child()

    def __init__(self, _item_id, nesting, *args, **kwds):
        super().__init__(*args, **kwds)
        self.rendered = False
        self.comment_id = _item_id
        self.replies_visible = True

        self.nesting = nesting
        self.get_style_context().add_class(f'comment-item-nested-{nesting}')

        self.on_show()


    def on_show(self):
        if not self.rendered:
            BG_TASKS.submit(self._set_content, self.comment_id)

    def _set_content(self, _item_id):
        self.rendered = True
        comment = get_comment(_item_id)
        GLib.idle_add(self.set_content, comment)

    def set_content(self, comment: Comment):
        if comment.deleted and not comment.kids:
            root = self.get_root()
            root.remove(self)
            return

        if comment.dead:
            self.get_style_context().add_class('comment-item-dead')

        self.time_lbl.set_markup(f"<small><span foreground='#999'>{comment.age}</span> - <b>{comment.user}</b></small>")
        self.comment.set_markup(comment.markup)

        if comment.kids:
            self.revealer_event.set_visible(True)
            self.replies_container.set_visible(True)
            self.replies_container.set_reveal_child(True)

        for i in comment.kids:
            wid = CommentItem(i, self.nesting + 1)
            wid.set_visible(True)
            self.replies.prepend(wid)

    @Gtk.Template.Callback()
    def reveal_replies_click(self, event):
        self.replies_visible = not self.replies_visible
        self.replies_container.set_reveal_child(self.replies_visible)
        if self.replies_visible:
            self.revealer_img.get_style_context().remove_class('rotate')
        else:
            self.revealer_img.get_style_context().add_class('rotate')

    @Gtk.Template.Callback()
    def activate_link(self, label, link):
        Bus.emit("open_website", url=link, title="FIX TITLE")
        return True


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="hn.app", **kwargs)

    def do_activate(self):
        self.window = AppWindow(application=self, title="Hacker News")
        self.window.present()
        Bus.emit("refresh_news_list")


def main():
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
