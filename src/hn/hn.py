#!/usr/bin/env python3.7
import time
import queue
from pathlib import Path

import gi

from threading import Thread

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, GLib, Gdk, WebKit2

from api import top_stories, get_comment, get_story, Comment, Story
q = queue.Queue()

STYLE_FILE = Path(__file__).parent / 'css' / 'style.css'

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
    
    def setup_styles(self):
        css_provider = Gtk.CssProvider()
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()

        css_provider.load_from_path(str(STYLE_FILE))
        context.add_provider_for_screen(screen, css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_thread(self, thread_id, thread_title):
        self.stack.set_visible_child(self.ct)
        self.ct.load_thread(thread_id, thread_title)
    
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


class NewsList(Gtk.Grid):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.connect('edge-overshot', self.edge_overshot)

        self.add(scrolled_window)
        self.vbox = Gtk.VBox()
        scrolled_window.add(self.vbox)
        self.show_all()

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

class ThreadHeader(Gtk.Grid):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.set_vexpand(False)
        self.get_style_context().add_class('thread-header')

        self.title = Gtk.Label(label='...')
        self.title.set_line_wrap(True)
        self.title.set_xalign(0)
        self.title.get_style_context().add_class('thread-title')

        back_icon = Gtk.Image.new_from_icon_name(icon_name='go-previous', size=Gtk.IconSize.BUTTON)
        back_icon.set_halign(Gtk.Align.START)
        back_icon.get_style_context().add_class('thread-back')

        back_event = Gtk.EventBox()
        back_event.add(back_icon)
        back_event.connect('button-release-event', self.back_click)

        self.attach(back_event, 0, 0, 1, 1)
        self.attach(self.title, 0, 1, 6, 1)

        self.show_all()

    def back_click(self, box, event):
        window = self.get_toplevel()
        window.set_news()

    def set_title(self, title):
        self.title.set_label(title)

class CommentThread(Gtk.Grid):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.add(scrolled_window)

        self.header = ThreadHeader()
        self.header.set_hexpand(True)
        self.comments_container = Gtk.VBox()
        self.comments_container.set_vexpand(True)
        self.comments_container.get_style_context().add_class('thread-comments')
        header_comments_vbox = Gtk.VBox()
        header_comments_vbox.pack_start(self.header, 0, 0, 0)
        header_comments_vbox.pack_start(self.comments_container, 1, 1, 0)
        # Allow comments_container to grow and take all space

        scrolled_window.add(header_comments_vbox)
        self.show_all()

    def load_thread(self, thread_id, thread_title):
        self.header.set_title(thread_title)
        q.put((self._load_thread, thread_id))

    def _load_thread(self, thread_id):
        for child in self.comments_container.get_children():
            GLib.idle_add(child.destroy)
        story = get_story(thread_id)
        self._set_comments(story.kids)

    def _set_comments(self, comments):

        for i in comments:
            widget1 = CommentItem(i, 0)
            self.comments_container.pack_start(widget1, 0, 0, 0)  ## fill and expand

class NewsItem(Gtk.Grid):
    def __init__(self, _item_id, *args, **kwds):
        super().__init__(*args, **kwds)
        self.get_style_context().add_class('news-item')

        self.set_column_homogeneous(True)
        self.article_url = None
        self.thread_id = _item_id

        self.title = Gtk.Label()
        self.title.set_line_wrap(True)
        self.title.set_xalign(0)
        self.title.set_hexpand(True)

        self.title_event = Gtk.EventBox()
        self.title_event.connect('button-release-event', self.title_click)
        self.title_event.add(self.title)
        self.attach(self.title_event, 0, 0, 8, 2)

        self.url = Gtk.Label()
        self.url.set_xalign(0)
        self.url.set_hexpand(True)
        self.attach(self.url, 0, 3, 7, 1)

        self.comments = Gtk.Label()
        self.comments.set_vexpand(True)
        self.comments.set_hexpand(True)
        self.comments.set_xalign(0.5)
        self.comments.get_style_context().add_class('news-item-commentcount')

        self.comments_event = Gtk.EventBox()
        self.comments_event.add(self.comments)
        self.comments_event.connect('button-release-event', self.comments_click)
        self.attach(self.comments_event, 9, 0, 1, 4)

        self.show_all()
        q.put((self._set_content, _item_id))

    def comments_click(self, eventbox, event):
        window = self.get_toplevel()
        window.set_thread(self.thread_id, self.thread_title)

    def title_click(self, eventbox, event):
        window = self.get_toplevel()
        window.set_website(self.article_url)

    def _set_content(self, _item_id):
        story = get_story(_item_id)
        GLib.idle_add(self.set_content, story)

    def set_content(self, story: Story):
        self.article_url = story.url
        self.thread_title = story.title
        self.title.set_label(story.title)
        self.title.get_style_context().add_class('news-item-title')
        self.url.set_label(story.url_domain)
        self.comments.set_label(str(story.comment_count))


class CommentItem(Gtk.VBox):
    def __init__(self, _item_id, nesting, *args, **kwds):
        super().__init__(*args, **kwds)

        self.nesting = nesting
        self.get_style_context().add_class(f'comment-item-nested-{nesting}')

        self.set_vexpand(False)
        self.comment_body = Gtk.Grid()

        self.comment_body.get_style_context().add_class('comment-item')
        self._time = Gtk.Label()
        self._time.set_margin_bottom(10)
        self._time.set_xalign(0)
        self.comment_body.attach(self._time, 1, 1, 1, 1)

        self.comment = Gtk.Label(label='...')
        self.comment.set_vexpand(True)
        self.comment.set_line_wrap(True)
        self.comment.set_selectable(True)
        self.comment.set_xalign(0)
        self.comment.connect('activate-link', self.activate_link)
        self.comment_body.attach(self.comment, 1, 2, 20, 1)

        self.replies_visible = True
        self.replies_container = Gtk.Revealer()
        self.replies = Gtk.VBox()
        self.replies.set_vexpand(True)
        self.replies.get_style_context().add_class('comment-replies')
        self.replies_container.add(self.replies)
        self.replies_container.set_reveal_child(False)

        self.add(self.comment_body)
        self.add(self.replies_container)
        self.show_all()

        q.put((self._set_content, _item_id))

    def _set_content(self, _item_id):
        comment = get_comment(_item_id)
        GLib.idle_add(self.set_content, comment)

    def set_content(self, comment: Comment):
        if comment.deleted and not comment.kids:
            GLib.idle_add(self.destroy)
            return

        if comment.dead:
            self.get_style_context().add_class('comment-item-dead')

        self._time.set_markup(f"<small><span foreground='#999'>2m ago</span> - <b>{comment.user}</b></small>")
        self.comment.set_markup(comment.markup)

        if comment.kids:
            self.replies_container.set_reveal_child(True)
            self.revealer_event = Gtk.EventBox()
            self.revealer_label = Gtk.Image.new_from_icon_name(icon_name='go-up', size=Gtk.IconSize.SMALL_TOOLBAR)
            self.revealer_label.get_style_context().add_class('comment-item-toggle')
            self.revealer_event.connect('button-release-event', self.reveal_replies_click)
            self.revealer_event.add(self.revealer_label)
            self.comment_body.attach(self.revealer_event, 1, 3, 20, 1)
            self.show_all()

        for i in comment.kids:
            wid = CommentItem(i, self.nesting + 1)
            wid.set_visible(True)
            self.replies.pack_start(wid, 0, 0, 0)

    def reveal_replies_click(self, box, event):
        self.replies_visible = not self.replies_visible
        self.replies_container.set_reveal_child(self.replies_visible)
        if self.replies_visible:
            self.revealer_label.get_style_context().remove_class('rotate')
        else:
            self.revealer_label.get_style_context().add_class('rotate')

    def activate_link(self, label, link):
        window = self.get_toplevel()
        window.set_website(link)
        return True


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="org.example.myapp", **kwargs)

    def do_activate(self):
        self.window = AppWindow(application=self, title="Main Window")
        self.window.present()
        q.put((self.window.news_list.refresh, None))


def background_fn():
    while True:
        fn, arg = q.get()
        fn(arg)
        #time.sleep(0.1)


def main():
    t = Thread(target=background_fn)
    t.daemon = True
    t.start()
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
