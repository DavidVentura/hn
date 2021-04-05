#!/usr/bin/env python3.7
import time
import queue
from pathlib import Path

import gi

from threading import Thread

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, GLib, Gdk, WebKit2, GdkPixbuf, Gio

from api import top_stories, get_comment, get_story, Comment, Story
q = queue.Queue()

SRC_DIR = Path(__file__).parent
STYLE_FILE = Path(__file__).parent / 'css' / 'style.css'
ICONS_DIR = Path(__file__).parent / 'icons'
RESOURCES_FILE = Path(__file__).parent / 'resources'

def load_icon_to_pixbuf(name, width):
    path = str(ICONS_DIR / name)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, -1, True)
    return pixbuf

resource = Gio.Resource.load(str(RESOURCES_FILE))
resource._register()

class AppWindow(Gtk.ApplicationWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_child = None
        self.setup_styles()
        self.set_default_size(360, 640)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        self.stack.set_transition_duration(300)
        self.stack.set_transition_type(Gtk.StackTransitionType.OVER_DOWN_UP)

        self.ct = CommentThread()
        self.news_list = NewsList()
        self.www = WebsiteView() 

        self.stack.add(self.news_list)
        self.stack.add(self.ct)
        self.stack.add(self.www)

        self.add(self.stack)
        self.show_all()
        self.stack.set_visible_child(self.news_list)
    
    def setup_styles(self):
        css_provider = Gtk.CssProvider()
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()

        css_provider.load_from_path(str(STYLE_FILE))
        context.add_provider_for_screen(screen, css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_thread(self, story):
        self.stack.set_visible_child(self.ct)
        self.ct.load_thread(story)
    
    def set_news(self):
        self.stack.set_visible_child(self.news_list)

    def set_website(self, url):
        self.www.load_uri(url)
        self.old_child = self.stack.get_visible_child()
        self.stack.set_visible_child(self.www)

    def pop_website(self):
        assert self.old_child
        self.stack.set_visible_child(self.old_child)


class WebsiteView(Gtk.Grid):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scrolled = Gtk.ScrolledWindow()

        self.www = WebKit2.WebView()
        self.www.set_hexpand(True)
        self.www.set_vexpand(True)

        scrolled.add(self.www)

        back = Gtk.Label(label='Go back')
        back.set_hexpand(True)

        back_event = Gtk.EventBox()
        back_event.add(back)
        back_event.connect('button-release-event', self.back_click)

        self.attach(back_event, 0, 0, 1, 1)
        self.attach(scrolled, 0, 1, 1, 1)

    def load_uri(self, uri):
        self.www.load_uri(uri)

    def back_click(self, box, event):
        self.www.stop_loading()
        window = self.get_toplevel()
        window.pop_website()


@Gtk.Template(resource_path='/hn/ui/NewsList.ui')
class NewsList(Gtk.Grid):
    __gtype_name__ = 'NewsList'
    scrolled_window = Gtk.Template.Child()
    vbox = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrolled_window.connect('edge-overshot', self.edge_overshot)

    def edge_overshot(self, pos, user_data):
        if user_data != Gtk.PositionType.TOP:
            return
        q.put((self.refresh, None))

    def refresh(self, _):
        stories = top_stories()
        GLib.idle_add(self.set_items, stories[:50])  # FIXME

    def set_items(self, news_item):
        for child in self.vbox.get_children():
            GLib.idle_add(child.destroy)

        for i in news_item:
            widget = NewsItem(i)
            self.vbox.pack_start(widget, 0, 0, 0)

@Gtk.Template(resource_path='/hn/ui/ThreadHeader.ui')
class ThreadHeader(Gtk.Grid):
    __gtype_name__ = 'ThreadHeader'

    title = Gtk.Template.Child()
    article_icon = Gtk.Template.Child()
    article_event = Gtk.Template.Child()
    back_event = Gtk.Template.Child()

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.article_event.connect('button-release-event', self.article_click)
        self.back_event.connect('button-release-event', self.back_click)
        self.article_icon.set_from_pixbuf(load_icon_to_pixbuf('open-article.svg', 24))

    def article_click(self, box, event):
        window = self.get_toplevel()
        window.set_website(self.article_url)

    def back_click(self, box, event):
        window = self.get_toplevel()
        window.set_news()

    def set_story_details(self, story):
        self.article_url = story.url
        self.title.set_label(story.title)

@Gtk.Template(resource_path='/hn/ui/CommentThread.ui')
class CommentThread(Gtk.ScrolledWindow):
    __gtype_name__ = 'CommentThread'
    header = Gtk.Template.Child()
    comments_container = Gtk.Template.Child()
    header_comments_vbox = Gtk.Template.Child()

    def load_thread(self, story):
        self.header.set_story_details(story)
        q.put((self._load_thread, story.story_id))

    def _load_thread(self, thread_id):
        for child in self.comments_container.get_children():
            GLib.idle_add(child.destroy)
        story = get_story(thread_id)
        GLib.idle_add(self._set_comments, story.kids)

    def _set_comments(self, comments):
        for i in comments:
            widget1 = CommentItem(i, 0)
            widget1.set_visible(True)
            self.comments_container.pack_start(widget1, 0, 0, 0)  ## fill and expand

@Gtk.Template(resource_path='/hn/ui/NewsItem.ui')
class NewsItem(Gtk.Grid):
    __gtype_name__ = 'NewsItem'
    title = Gtk.Template.Child()
    url = Gtk.Template.Child()
    comments = Gtk.Template.Child()
    comments_event = Gtk.Template.Child()
    title_event = Gtk.Template.Child()

    def __init__(self, _item_id, *args, **kwds):
        super().__init__(*args, **kwds)
        self.article_url = None
        self.thread_id = _item_id
        self.title_event.connect('button-release-event', self.title_click)
        self.comments_event.connect('button-release-event', self.comments_click)
        self.on_show()

    def on_show(self):
        q.put((self._set_content, self.thread_id))

    def comments_click(self, eventbox, event):
        window = self.get_toplevel()
        window.set_thread(self.story)

    def title_click(self, eventbox, event):
        window = self.get_toplevel()
        window.set_website(self.article_url)

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
        self.comment.connect('activate-link', self.activate_link)
        self.revealer_event.connect('button-release-event', self.reveal_replies_click)

        self.on_show()


    def on_show(self):
        if not self.rendered:
            q.put((self._set_content, self.comment_id))

    def _set_content(self, _item_id):
        self.rendered = True
        comment = get_comment(_item_id)
        GLib.idle_add(self.set_content, comment)

    def set_content(self, comment: Comment):
        if comment.deleted and not comment.kids:
            GLib.idle_add(self.destroy)
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
            self.replies.pack_start(wid, 0, 0, 0)

    def reveal_replies_click(self, box, event):
        self.replies_visible = not self.replies_visible
        self.replies_container.set_reveal_child(self.replies_visible)
        if self.replies_visible:
            self.revealer_img.get_style_context().remove_class('rotate')
        else:
            self.revealer_img.get_style_context().add_class('rotate')

    def activate_link(self, label, link):
        window = self.get_toplevel()
        window.set_website(link)
        return True


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="hn.app", **kwargs)

    def do_activate(self):
        self.window = AppWindow(application=self, title="Main Window")
        self.window.present()
        q.put((self.window.news_list.refresh, None))


def background_fn():
    while True:
        fn, arg = q.get()
        fn(arg)
        time.sleep(0.01)


def main():
    t = Thread(target=background_fn)
    t.daemon = True
    t.start()

    app = Application()
    app.run()

if __name__ == '__main__':
    main()
